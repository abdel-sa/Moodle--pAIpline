#!/usr/bin/env python3
"""
Moodle pAIpline – LLM Content Generator

Topic rein → input.json raus, fertig für build_v1.py.

Unterstützte Provider (beide kostenlos):
  - Ollama  : läuft lokal, kein API-Key, kein Limit
               Install: https://ollama.com  dann: ollama pull llama3.2
  - Groq    : kostenloser Cloud-Tier, schneller als Ollama
               API-Key: https://console.groq.com (kostenlos)
               Dann: export GROQ_API_KEY=gsk_...

Provider-Auswahl:
  1. --provider ollama|groq  (explizit)
  2. GROQ_API_KEY gesetzt    → Groq automatisch
  3. Sonst                   → Ollama (localhost)

Verwendung:
  python generate_content.py "Photosynthese"
  python generate_content.py "Pythagoras" --model llama3.2 --out mein_kurs.json
  python generate_content.py "Newton" --provider groq
"""

import json
import sys
import re
import os
import argparse
import urllib.request
import urllib.error

# ============================================================================
# KONFIGURATION
# ============================================================================

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_DEFAULT_MODEL = "llama3.2"

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"

# ============================================================================
# PROMPT
# ============================================================================

SYSTEM_PROMPT = (
    "Du bist ein erfahrener Lehrer und Didaktik-Experte. "
    "Du erstellst strukturierte Moodle-Kursmaterialien auf Deutsch. "
    "Du antwortest ausschließlich mit gültigem JSON, ohne Markdown, ohne Erklärungen."
)

def build_prompt(topic: str) -> str:
    return f"""Erstelle vollständige Moodle-Kursmaterialien für das Thema: "{topic}"

Antworte NUR mit diesem JSON-Objekt (kein Markdown, keine Erklärungen davor oder danach):

{{
  "course_metadata": {{
    "fullname": "Vollständiger Kursname",
    "shortname": "kurz_name_ohne_leerzeichen",
    "summary": "<p>Kurze HTML-Beschreibung des Kurses (1-2 Sätze).</p>",
    "lang": "de",
    "visible": true
  }},
  "sections": {{
    "section_6": {{
      "name": "Allgemeines",
      "summary": "<p>Einstieg und Überblick über den Kurs.</p>"
    }},
    "section_7": {{
      "name": "Theorie: [Thema]",
      "summary": "<p>Theoretische Grundlagen zum Thema.</p>"
    }},
    "section_8": {{
      "name": "Übungen & Quiz",
      "summary": "<p>Praktische Aufgaben und Wissenstest.</p>"
    }}
  }},
  "activities": {{
    "page_3": {{
      "type": "page",
      "name": "Einführung: [Thema]",
      "content_html": "<h1>[Thema]</h1><p>Einführungstext mit Erklärung des Themas...</p><h2>Wichtige Konzepte</h2><ul><li>Punkt 1</li><li>Punkt 2</li><li>Punkt 3</li></ul><p>Zusammenfassung...</p>"
    }},
    "assign_4": {{
      "type": "assign",
      "name": "Aufgabe: [Aufgabenname]",
      "intro_html": "<p>Aufgabenbeschreibung mit klaren Anweisungen.</p><ol><li>Aufgabenschritt 1</li><li>Aufgabenschritt 2</li><li>Aufgabenschritt 3</li></ol>"
    }},
    "quiz_5": {{
      "type": "quiz",
      "name": "Quiz: [Thema]",
      "questions": [
        {{
          "qbe_id": 1,
          "question_id": 1,
          "name": "Frage 1",
          "questiontext_html": "<p>Erste Frage zum Thema?</p>",
          "answers": [
            {{"text_html": "<p>Richtige Antwort</p>", "fraction": 1.0}},
            {{"text_html": "<p>Falsche Antwort A</p>", "fraction": 0.0}},
            {{"text_html": "<p>Falsche Antwort B</p>", "fraction": 0.0}}
          ]
        }},
        {{
          "qbe_id": 2,
          "question_id": 2,
          "name": "Frage 2",
          "questiontext_html": "<p>Zweite Frage zum Thema?</p>",
          "answers": [
            {{"text_html": "<p>Richtige Antwort</p>", "fraction": 1.0}},
            {{"text_html": "<p>Falsche Antwort A</p>", "fraction": 0.0}},
            {{"text_html": "<p>Falsche Antwort B</p>", "fraction": 0.0}}
          ]
        }},
        {{
          "qbe_id": 3,
          "question_id": 3,
          "name": "Frage 3",
          "questiontext_html": "<p>Dritte Frage zum Thema?</p>",
          "answers": [
            {{"text_html": "<p>Richtige Antwort</p>", "fraction": 1.0}},
            {{"text_html": "<p>Falsche Antwort A</p>", "fraction": 0.0}},
            {{"text_html": "<p>Falsche Antwort B</p>", "fraction": 0.0}}
          ]
        }}
      ]
    }}
  }}
}}

Thema: "{topic}"
Antworte ausschließlich mit dem JSON. Beginne mit {{ und ende mit }}.
"""

# ============================================================================
# LLM-PROVIDER
# ============================================================================

def _http_post(url: str, payload: dict, headers: dict) -> dict:
    """Führt einen HTTP POST aus und gibt geparsten JSON-Response zurück."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} von {url}:\n{body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Verbindung zu {url} fehlgeschlagen: {e.reason}") from e


def call_ollama(prompt: str, model: str) -> str:
    """Ruft Ollama lokal auf und gibt den Rohtext zurück."""
    print(f"  → Ollama ({model}) wird aufgerufen...")
    payload = {"model": model, "prompt": prompt, "stream": False}
    resp = _http_post(OLLAMA_URL, payload, {"Content-Type": "application/json"})
    return resp.get("response", "")


def call_groq(prompt: str, model: str, api_key: str) -> str:
    """Ruft die Groq-API auf (kostenloser Tier) und gibt den Rohtext zurück."""
    print(f"  → Groq ({model}) wird aufgerufen...")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "max_tokens": 2048,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    resp = _http_post(GROQ_URL, payload, headers)
    return resp["choices"][0]["message"]["content"]

# ============================================================================
# JSON-EXTRAKTION & VALIDIERUNG
# ============================================================================

def extract_json(raw: str) -> dict:
    """
    Extrahiert das JSON-Objekt aus dem LLM-Output.
    Robust gegen Markdown-Code-Blöcke und vorangestellten Text.
    """
    # Markdown-Codeblock entfernen falls vorhanden
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip()

    # Erstes { bis letztes } nehmen
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("Kein JSON-Objekt im LLM-Output gefunden.")

    json_str = raw[start:end]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON-Parse-Fehler: {e}\n\nRoh-Output:\n{json_str[:500]}") from e


def validate_output(data: dict) -> None:
    """Prüft ob das LLM-Output die Mindeststruktur hat."""
    if "activities" not in data:
        raise ValueError("LLM-Output hat kein 'activities'-Feld.")
    activities = data["activities"]
    for key, act in activities.items():
        if "type" not in act:
            raise ValueError(f"Activity '{key}' hat kein 'type'-Feld im LLM-Output.")


# ============================================================================
# HAUPTFUNKTION
# ============================================================================

def generate(topic: str, provider: str, model: str | None, api_key: str | None) -> dict:
    """Generiert ein vollständiges input.json für das gegebene Topic."""
    prompt = build_prompt(topic)

    if provider == "groq":
        if not api_key:
            raise RuntimeError(
                "Groq benötigt einen API-Key.\n"
                "Setze: export GROQ_API_KEY=gsk_...\n"
                "Kostenlos unter: https://console.groq.com"
            )
        raw = call_groq(prompt, model or GROQ_DEFAULT_MODEL, api_key)
    else:
        raw = call_ollama(prompt, model or OLLAMA_DEFAULT_MODEL)

    print("  → Antwort empfangen, parse JSON...")
    data = extract_json(raw)
    validate_output(data)
    return data


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generiert input.json aus einem Lehrthema via LLM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python generate_content.py "Photosynthese"
  python generate_content.py "Der Zweite Weltkrieg" --out geschichte.json
  python generate_content.py "Pythagoras" --provider groq --model llama-3.3-70b-versatile
  python generate_content.py "Newton" --provider ollama --model mistral

Provider:
  ollama  Lokal (kostenlos, kein API-Key) – Install: https://ollama.com
  groq    Cloud  (kostenlos, API-Key nötig) – Key: https://console.groq.com
        """,
    )
    parser.add_argument("topic", help="Lehrthema, z.B. 'Photosynthese'")
    parser.add_argument("--provider", choices=["ollama", "groq"], default=None,
                        help="LLM-Provider (Standard: groq wenn GROQ_API_KEY gesetzt, sonst ollama)")
    parser.add_argument("--model", default=None,
                        help="Modell-Name (Standard: llama3.2 für Ollama, llama-3.3-70b-versatile für Groq)")
    parser.add_argument("--out", default="input.json",
                        help="Output-Datei (Standard: input.json)")

    args = parser.parse_args()

    api_key = os.environ.get("GROQ_API_KEY")

    # Provider automatisch wählen wenn nicht explizit angegeben
    if args.provider is None:
        provider = "groq" if api_key else "ollama"
    else:
        provider = args.provider

    print("=" * 60)
    print(f"Moodle pAIpline – Content Generator")
    print("=" * 60)
    print(f"  Thema   : {args.topic}")
    print(f"  Provider: {provider}")
    print(f"  Model   : {args.model or (GROQ_DEFAULT_MODEL if provider == 'groq' else OLLAMA_DEFAULT_MODEL)}")
    print(f"  Output  : {args.out}")
    print()

    try:
        data = generate(args.topic, provider, args.model, api_key)

        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"\n✓ {args.out} erfolgreich erzeugt.")
        print(f"\nNächster Schritt: python build_v1.py")

    except RuntimeError as e:
        print(f"\n✗ Verbindungsfehler: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"\n✗ LLM-Output ungültig: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
