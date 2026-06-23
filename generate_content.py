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
  python generate_content.py "Java" --provider gemini --model gemini-3.5-flash
"""

import json
import sys
import re
import os
import argparse
import time
import urllib.request
import urllib.error

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ============================================================================
# KONFIGURATION
# ============================================================================

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_DEFAULT_MODEL = "llama3.2"

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"
GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_DEFAULT_MODEL = "gemini-2.5-flash"
GEMINI_MODEL_ALIASES = {
    "gemini-3.5-flash": GEMINI_DEFAULT_MODEL,
    "gemini-3.5-flash-latest": GEMINI_DEFAULT_MODEL,
}
CEREBRAS_URL = "https://api.cerebras.ai/v1/chat/completions"
CEREBRAS_DEFAULT_MODEL = "gpt-oss-120b"


def _load_dotenv(path: str = ".env") -> None:
    """Load simple KEY=VALUE pairs from .env without overriding real env vars."""
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


_load_dotenv()

# ============================================================================
# PROMPTS
# ============================================================================

SYSTEM_PROMPT = (
    "Du bist ein erfahrener Lehrer und Didaktik-Experte. "
    "Du erstellst umfangreiche, strukturierte Moodle-Kursmaterialien auf Deutsch. "
    "Du antwortest ausschließlich mit gültigem JSON, ohne Markdown, ohne Erklärungen."
)

# ── Vollständiger Prompt für leistungsstarke Cloud-Modelle (Groq) ─────────────
# Erzeugt 12 Fragen, detaillierten Theorieinhalt und ausführliche Aufgaben.
def build_prompt_full(topic: str) -> str:
    return f"""Erstelle einen vollständigen, umfangreichen Moodle-Kurs für das Thema: "{topic}"

Der Kurs soll wie ein Schulbuchkapitel aufgebaut sein – mit detailliertem Theorieinhalt,
praxisnahen Aufgaben und einem Quiz mit 12 Fragen aus verschiedenen Teilbereichen.

Antworte NUR mit diesem JSON-Objekt (kein Markdown, keine Erklärungen):

{{
  "course_metadata": {{
    "fullname": "Vollständiger Kursname",
    "shortname": "kurs_kurzname",
    "summary": "<p>Beschreibung des Kurses (2-3 Sätze, Zielgruppe, Lernziele).</p>",
    "lang": "de",
    "visible": true
  }},
  "sections": {{
    "section_6": {{"name": "Kursübersicht", "summary": "<p>Einstieg und Überblick.</p>"}},
    "section_7": {{"name": "Theorie und Grundlagen", "summary": "<p>Theoretische Inhalte.</p>"}},
    "section_8": {{"name": "Aufgaben und Quiz", "summary": "<p>Übungen und Wissenstest.</p>"}}
  }},
  "activities": {{
    "page_3": {{
      "type": "page",
      "name": "Theorie: {topic}",
      "content_html": "<h1>{topic}</h1><p>Einleitungstext (3-4 Sätze): Was ist das Thema und warum ist es wichtig?</p><h2>1. Grundlagen und Begriffe</h2><p>Erkläre die 4 wichtigsten Grundbegriffe ausführlich mit je einem konkreten Beispiel.</p><ul><li><strong>Begriff 1:</strong> Erklärung und Beispiel.</li><li><strong>Begriff 2:</strong> Erklärung und Beispiel.</li><li><strong>Begriff 3:</strong> Erklärung und Beispiel.</li><li><strong>Begriff 4:</strong> Erklärung und Beispiel.</li></ul><h2>2. Kernkonzepte im Detail</h2><p>Tiefergehende Erklärung (mind. 150 Wörter) der wichtigsten Konzepte mit Zusammenhängen und Alltagsbeispielen.</p><h2>3. Wichtige Regeln und Merksätze</h2><ol><li>Regel/Merksatz 1 mit Anwendungsbeispiel.</li><li>Regel/Merksatz 2 mit Anwendungsbeispiel.</li><li>Regel/Merksatz 3 mit Anwendungsbeispiel.</li><li>Regel/Merksatz 4 mit Anwendungsbeispiel.</li></ol><h2>4. Drei Anwendungsbeispiele</h2><p>Drei konkrete, durchgearbeitete Beispiele mit Lösungsweg.</p><h2>5. Häufige Fehler</h2><ul><li>Fehler 1 und Tipp zur Vermeidung.</li><li>Fehler 2 und Tipp zur Vermeidung.</li><li>Fehler 3 und Tipp zur Vermeidung.</li></ul><h2>6. Zusammenfassung</h2><p>Kompakte Zusammenfassung aller wichtigen Punkte als Liste.</p>"
    }},
    "assign_4": {{
      "type": "assign",
      "name": "Aufgabe: {topic}",
      "intro_html": "<p>Wende dein Wissen zu <strong>{topic}</strong> an.</p><ol><li><strong>Teilaufgabe A (Grundlagen):</strong> Konkrete Aufgabe mit Zahlen/Fakten die Grundwissen prüft.</li><li><strong>Teilaufgabe B (Anwendung):</strong> Alltagsnahe Aufgabe mit realem Kontext.</li><li><strong>Teilaufgabe C (Transfer):</strong> Komplexere Aufgabe die mehrere Konzepte verbindet.</li><li><strong>Teilaufgabe D (Reflexion):</strong> Erkläre ein Kernkonzept in eigenen Worten mit eigenem Beispiel.</li></ol><p><em>Zeige alle Schritte/Begründungen. Bewertung: 25 Punkte je Teilaufgabe.</em></p>"
    }},
    "quiz_5": {{
      "type": "quiz",
      "name": "Quiz: {topic}",
      "questions": [
        {{"qbe_id":1,"question_id":1,"name":"Frage 1 – Definition","questiontext_html":"<p>Was beschreibt [zentraler Begriff aus {topic}] am besten?</p>","answers":[{{"text_html":"<p>Korrekte Definition</p>","fraction":1.0}},{{"text_html":"<p>Falsche Definition A</p>","fraction":0.0}},{{"text_html":"<p>Falsche Definition B</p>","fraction":0.0}},{{"text_html":"<p>Falsche Definition C</p>","fraction":0.0}}]}},
        {{"qbe_id":2,"question_id":2,"name":"Frage 2 – Konzept","questiontext_html":"<p>Welches Prinzip / Konzept ist für {topic} grundlegend?</p>","answers":[{{"text_html":"<p>Richtige Antwort</p>","fraction":1.0}},{{"text_html":"<p>Falsch A</p>","fraction":0.0}},{{"text_html":"<p>Falsch B</p>","fraction":0.0}},{{"text_html":"<p>Falsch C</p>","fraction":0.0}}]}},
        {{"qbe_id":3,"question_id":3,"name":"Frage 3 – Anwendung","questiontext_html":"<p>Konkrete Anwendungsaufgabe zu {topic} mit Zahlen oder realem Beispiel?</p>","answers":[{{"text_html":"<p>Richtiges Ergebnis</p>","fraction":1.0}},{{"text_html":"<p>Falsches Ergebnis A</p>","fraction":0.0}},{{"text_html":"<p>Falsches Ergebnis B</p>","fraction":0.0}},{{"text_html":"<p>Falsches Ergebnis C</p>","fraction":0.0}}]}},
        {{"qbe_id":4,"question_id":4,"name":"Frage 4 – Regel/Gesetz","questiontext_html":"<p>Welche Regel / welches Gesetz gilt für [Aspekt von {topic}]?</p>","answers":[{{"text_html":"<p>Korrekte Regel</p>","fraction":1.0}},{{"text_html":"<p>Falsche Regel A</p>","fraction":0.0}},{{"text_html":"<p>Falsche Regel B</p>","fraction":0.0}},{{"text_html":"<p>Falsche Regel C</p>","fraction":0.0}}]}},
        {{"qbe_id":5,"question_id":5,"name":"Frage 5 – Vergleich","questiontext_html":"<p>Was unterscheidet [Begriff A] von [Begriff B] bei {topic}?</p>","answers":[{{"text_html":"<p>Korrekte Unterscheidung</p>","fraction":1.0}},{{"text_html":"<p>Falsch A</p>","fraction":0.0}},{{"text_html":"<p>Falsch B</p>","fraction":0.0}},{{"text_html":"<p>Falsch C</p>","fraction":0.0}}]}},
        {{"qbe_id":6,"question_id":6,"name":"Frage 6 – Alltagsbezug","questiontext_html":"<p>In welchem Alltags- oder Berufsbereich ist {topic} besonders wichtig?</p>","answers":[{{"text_html":"<p>Korrekte Antwort mit Begründung</p>","fraction":1.0}},{{"text_html":"<p>Falsch A</p>","fraction":0.0}},{{"text_html":"<p>Falsch B</p>","fraction":0.0}},{{"text_html":"<p>Falsch C</p>","fraction":0.0}}]}},
        {{"qbe_id":7,"question_id":7,"name":"Frage 7 – Chronologie/Prozess","questiontext_html":"<p>In welcher Reihenfolge läuft [typischer Prozess zu {topic}] ab?</p>","answers":[{{"text_html":"<p>Korrekte Reihenfolge</p>","fraction":1.0}},{{"text_html":"<p>Falsche Reihenfolge A</p>","fraction":0.0}},{{"text_html":"<p>Falsche Reihenfolge B</p>","fraction":0.0}},{{"text_html":"<p>Falsche Reihenfolge C</p>","fraction":0.0}}]}},
        {{"qbe_id":8,"question_id":8,"name":"Frage 8 – Ursache/Wirkung","questiontext_html":"<p>Was ist die Ursache / Folge von [Phänomen in {topic}]?</p>","answers":[{{"text_html":"<p>Korrekte Ursache-Wirkung</p>","fraction":1.0}},{{"text_html":"<p>Falsch A</p>","fraction":0.0}},{{"text_html":"<p>Falsch B</p>","fraction":0.0}},{{"text_html":"<p>Falsch C</p>","fraction":0.0}}]}},
        {{"qbe_id":9,"question_id":9,"name":"Frage 9 – Ausnahme","questiontext_html":"<p>Welche Ausnahme / welcher Sonderfall gilt bei [Aspekt von {topic}]?</p>","answers":[{{"text_html":"<p>Korrekte Ausnahme</p>","fraction":1.0}},{{"text_html":"<p>Falsch A</p>","fraction":0.0}},{{"text_html":"<p>Falsch B</p>","fraction":0.0}},{{"text_html":"<p>Falsch C</p>","fraction":0.0}}]}},
        {{"qbe_id":10,"question_id":10,"name":"Frage 10 – Rechenaufgabe","questiontext_html":"<p>Berechne / Bestimme: [konkrete Aufgabe zu {topic} mit konkreten Werten]?</p>","answers":[{{"text_html":"<p>Richtiges Ergebnis</p>","fraction":1.0}},{{"text_html":"<p>Falsches Ergebnis A</p>","fraction":0.0}},{{"text_html":"<p>Falsches Ergebnis B</p>","fraction":0.0}},{{"text_html":"<p>Falsches Ergebnis C</p>","fraction":0.0}}]}},
        {{"qbe_id":11,"question_id":11,"name":"Frage 11 – Vertiefung","questiontext_html":"<p>Vertiefung: [Frage die mehrere Konzepte aus {topic} verbindet]?</p>","answers":[{{"text_html":"<p>Vollständige korrekte Antwort</p>","fraction":1.0}},{{"text_html":"<p>Teilweise richtig A</p>","fraction":0.0}},{{"text_html":"<p>Teilweise richtig B</p>","fraction":0.0}},{{"text_html":"<p>Komplett falsch C</p>","fraction":0.0}}]}},
        {{"qbe_id":12,"question_id":12,"name":"Frage 12 – Abschluss","questiontext_html":"<p>Welche Aussage zu {topic} ist KORREKT?</p>","answers":[{{"text_html":"<p>Korrekte Aussage</p>","fraction":1.0}},{{"text_html":"<p>Falsches Missverständnis A</p>","fraction":0.0}},{{"text_html":"<p>Falsches Missverständnis B</p>","fraction":0.0}},{{"text_html":"<p>Falsch C</p>","fraction":0.0}}]}}
      ]
    }}
  }}
}}

WICHTIG: Ersetze ALLE Platzhalter (in eckigen Klammern) durch echte, korrekte Inhalte zu "{topic}".
Kein Platzhalter darf im finalen JSON stehen. Beginne mit {{ und ende mit }}. Kein Markdown.
"""

# ── Kompakter Prompt für kleine lokale Modelle (Ollama / llama3.2 etc.) ────────
# Erzeugt 6 Fragen mit je 3 Antworten + kürzeren Theorieinhalt.
# Bewusst klein gehalten damit llama3.2 (3B) es in <3 Min abarbeiten kann.
def build_prompt_lite(topic: str) -> str:
    return f"""Erstelle Moodle-Kursmaterialien für das Thema: "{topic}"

Antworte NUR mit diesem JSON (kein Markdown, kein Text davor/danach):

{{
  "course_metadata": {{
    "fullname": "Kurs: {topic}",
    "shortname": "kurs_{topic[:15].replace(' ','_').lower()}",
    "summary": "<p>Dieser Kurs behandelt {topic}. Lernende erwerben Grundkenntnisse und können das Wissen anwenden.</p>",
    "lang": "de",
    "visible": true
  }},
  "sections": {{
    "section_6": {{"name": "Einführung", "summary": "<p>Überblick über den Kurs.</p>"}},
    "section_7": {{"name": "Theorie: {topic}", "summary": "<p>Grundlagen und wichtige Konzepte.</p>"}},
    "section_8": {{"name": "Übungen und Quiz", "summary": "<p>Aufgaben und Wissenstest.</p>"}}
  }},
  "activities": {{
    "page_3": {{
      "type": "page",
      "name": "Einführung: {topic}",
      "content_html": "<h1>{topic}</h1><p>EINLEITUNG: Was ist {topic} und warum ist es wichtig? (2-3 Sätze)</p><h2>Wichtige Grundbegriffe</h2><ul><li><strong>Begriff 1:</strong> Definition und Beispiel</li><li><strong>Begriff 2:</strong> Definition und Beispiel</li><li><strong>Begriff 3:</strong> Definition und Beispiel</li></ul><h2>Kernkonzept</h2><p>Erkläre das wichtigste Konzept von {topic} mit einem konkreten Beispiel (3-5 Sätze).</p><h2>Zusammenfassung</h2><p>Die 3 wichtigsten Punkte zu {topic}: (1) ... (2) ... (3) ...</p>"
    }},
    "assign_4": {{
      "type": "assign",
      "name": "Aufgabe: {topic}",
      "intro_html": "<p>Bearbeite folgende Aufgaben zu <strong>{topic}</strong>:</p><ol><li>Erkläre einen Grundbegriff aus {topic} in eigenen Worten und nenne ein Beispiel.</li><li>Löse eine konkrete Anwendungsaufgabe zu {topic} (mit Zahlen oder Fakten).</li><li>Beschreibe eine reale Situation, in der {topic} eine Rolle spielt.</li></ol>"
    }},
    "quiz_5": {{
      "type": "quiz",
      "name": "Quiz: {topic}",
      "questions": [
        {{"qbe_id":1,"question_id":1,"name":"Frage 1","questiontext_html":"<p>Was ist die wichtigste Eigenschaft / Definition von {topic}?</p>","answers":[{{"text_html":"<p>Korrekte Antwort zu {topic}</p>","fraction":1.0}},{{"text_html":"<p>Falsche Antwort A</p>","fraction":0.0}},{{"text_html":"<p>Falsche Antwort B</p>","fraction":0.0}}]}},
        {{"qbe_id":2,"question_id":2,"name":"Frage 2","questiontext_html":"<p>Welches Konzept / Prinzip ist zentral für {topic}?</p>","answers":[{{"text_html":"<p>Richtiges Konzept</p>","fraction":1.0}},{{"text_html":"<p>Falsches Konzept A</p>","fraction":0.0}},{{"text_html":"<p>Falsches Konzept B</p>","fraction":0.0}}]}},
        {{"qbe_id":3,"question_id":3,"name":"Frage 3","questiontext_html":"<p>Wo / wofür wird {topic} im Alltag oder Beruf angewendet?</p>","answers":[{{"text_html":"<p>Richtige Anwendung</p>","fraction":1.0}},{{"text_html":"<p>Falsch A</p>","fraction":0.0}},{{"text_html":"<p>Falsch B</p>","fraction":0.0}}]}},
        {{"qbe_id":4,"question_id":4,"name":"Frage 4","questiontext_html":"<p>Welche Aussage zu {topic} ist FALSCH?</p>","answers":[{{"text_html":"<p>Falsche Aussage (richtige Antwort auf diese Frage)</p>","fraction":1.0}},{{"text_html":"<p>Wahre Aussage A</p>","fraction":0.0}},{{"text_html":"<p>Wahre Aussage B</p>","fraction":0.0}}]}},
        {{"qbe_id":5,"question_id":5,"name":"Frage 5","questiontext_html":"<p>Was ist der Unterschied zwischen [Begriff A] und [Begriff B] bei {topic}?</p>","answers":[{{"text_html":"<p>Korrekte Unterscheidung</p>","fraction":1.0}},{{"text_html":"<p>Verwechslung A-B</p>","fraction":0.0}},{{"text_html":"<p>Beides falsch</p>","fraction":0.0}}]}},
        {{"qbe_id":6,"question_id":6,"name":"Frage 6","questiontext_html":"<p>Welche der folgenden Aussagen zu {topic} ist KORREKT?</p>","answers":[{{"text_html":"<p>Korrekte Aussage</p>","fraction":1.0}},{{"text_html":"<p>Falsches Missverständnis A</p>","fraction":0.0}},{{"text_html":"<p>Falsches Missverständnis B</p>","fraction":0.0}}]}}
      ]
    }}
  }}
}}

Ersetze ALLE Platzhalter durch echte Inhalte zu "{topic}". Beginne mit {{, ende mit }}. Kein Markdown.
"""

# ============================================================================
# LLM-PROVIDER
# ============================================================================

class GroqRateLimitError(RuntimeError):
    def __init__(self, wait_seconds: float, message: str):
        super().__init__(message)
        self.wait_seconds = wait_seconds


class GeminiRateLimitError(RuntimeError):
    def __init__(self, wait_seconds: float, message: str):
        super().__init__(message)
        self.wait_seconds = wait_seconds


class CerebrasRateLimitError(RuntimeError):
    def __init__(self, wait_seconds: float, message: str):
        super().__init__(message)
        self.wait_seconds = wait_seconds


def _extract_retry_seconds(body: str, default: float = 60.0) -> float:
    match = re.search(r"try again in ([0-9]+(?:\.[0-9]+)?)s", body, re.IGNORECASE)
    if match:
        return float(match.group(1)) + 2.0
    retry_after = re.search(r'"retryDelay"\s*:\s*"([0-9]+(?:\.[0-9]+)?)s"', body)
    if retry_after:
        return float(retry_after.group(1)) + 2.0
    return default

def _http_post(url: str, payload: dict, headers: dict, timeout: int = 90) -> dict:
    """Führt einen HTTP POST aus und gibt geparsten JSON-Response zurück."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if e.code == 429 and "api.groq.com" in url:
            raise GroqRateLimitError(
                _extract_retry_seconds(body),
                f"HTTP 429 von {url}:\n{body}",
            ) from e
        if e.code == 429 and "generativelanguage.googleapis.com" in url:
            raise GeminiRateLimitError(
                _extract_retry_seconds(body),
                f"HTTP 429 von {url}:\n{body}",
            ) from e
        if e.code == 429 and "cerebras.ai" in url:
            raise CerebrasRateLimitError(
                _extract_retry_seconds(body, default=10.0),
                f"HTTP 429 von {url}:\n{body}",
            ) from e
        raise RuntimeError(f"HTTP {e.code} von {url}:\n{body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Verbindung zu {url} fehlgeschlagen: {e.reason}") from e


def call_ollama(prompt: str, model: str) -> str:
    """
    Ruft Ollama lokal auf und gibt den Rohtext zurück.
    Verwendet stream=True damit der Socket bei langen Generierungen nicht
    durch einen Read-Timeout abgebrochen wird.
    """
    print(f"  → Ollama ({model}) wird aufgerufen...")
    payload = {"model": model, "prompt": prompt, "stream": True}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL, data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            chunks = []
            token_count = 0
            print("  → Generiere (das kann 1-3 Minuten dauern)", end="", flush=True)
            for raw_line in resp:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                chunk = json.loads(line)
                token = chunk.get("response", "")
                chunks.append(token)
                token_count += 1
                if token_count % 50 == 0:
                    print(".", end="", flush=True)
                if chunk.get("done"):
                    break
            print(f" ({token_count} Tokens)")
            return "".join(chunks)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} von {OLLAMA_URL}:\n{body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Verbindung zu Ollama fehlgeschlagen: {e.reason}") from e


def call_groq(prompt: str, model: str, api_key: str, max_tokens: int = 8192) -> str:
    """Ruft die Groq-API auf (kostenloser Tier) und gibt den Rohtext zurück."""
    print(f"  → Groq ({model}) wird aufgerufen...")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "max_tokens": max_tokens,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "moodle-paipline/1.0",
    }
    for api_attempt in range(1, 4):
        try:
            resp = _http_post(GROQ_URL, payload, headers)
            return resp["choices"][0]["message"]["content"]
        except GroqRateLimitError as e:
            if api_attempt == 3:
                raise
            wait = max(1, round(e.wait_seconds))
            print(f"  Groq Rate Limit erreicht. Warte {wait}s und versuche es erneut...")
            time.sleep(wait)

    raise RuntimeError("Groq-Aufruf fehlgeschlagen.")


def call_gemini(prompt: str, model: str, api_key: str, max_tokens: int = 16000) -> str:
    """Call the official Google Gemini generateContent REST API."""
    model = GEMINI_MODEL_ALIASES.get(model, model)
    print(f"  → Gemini ({model}) wird aufgerufen...")
    url = GEMINI_URL_TEMPLATE.format(model=model)
    payload = {
        "systemInstruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.35,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
        "User-Agent": "moodle-paipline/1.0",
    }

    for api_attempt in range(1, 4):
        try:
            resp = _http_post(url, payload, headers)
            candidates = resp.get("candidates") or []
            if not candidates:
                feedback = resp.get("promptFeedback")
                raise RuntimeError(f"Gemini lieferte keine Antwort. Feedback: {feedback}")

            candidate = candidates[0]
            finish_reason = candidate.get("finishReason")
            parts = candidate.get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
            if not text.strip():
                raise RuntimeError(f"Gemini-Antwort enthält keinen Text. finishReason={finish_reason}")
            if finish_reason == "MAX_TOKENS":
                raise RuntimeError(
                    "Gemini-Antwort wurde wegen maxOutputTokens abgeschnitten. "
                    "Reduziere Einheiten/Umfang oder erhöhe das Tokenbudget."
                )
            return text
        except GeminiRateLimitError as e:
            if api_attempt == 3:
                raise
            wait = max(1, round(e.wait_seconds))
            print(f"  Gemini Rate Limit erreicht. Warte {wait}s und versuche es erneut...")
            time.sleep(wait)

    raise RuntimeError("Gemini-Aufruf fehlgeschlagen.")


def call_cerebras(prompt: str, model: str, api_key: str, max_tokens: int = 8192) -> str:
    """Ruft die Cerebras-API auf (OpenAI-kompatibel) und gibt den Rohtext zurück."""
    # Cerebras ist sehr schnell — wenn es nicht in 25s antwortet, ist es nicht erreichbar
    CEREBRAS_TIMEOUT = 25
    print(f"  → Cerebras ({model}) wird aufgerufen... (Timeout: {CEREBRAS_TIMEOUT}s)")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "max_tokens": min(max_tokens, 8192),
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "moodle-paipline/1.0",
    }
    for api_attempt in range(1, 4):
        try:
            resp = _http_post(CEREBRAS_URL, payload, headers, timeout=CEREBRAS_TIMEOUT)
            print(f"  ✓ Cerebras geantwortet.")
            return resp["choices"][0]["message"]["content"]
        except CerebrasRateLimitError as e:
            if api_attempt == 3:
                raise
            wait = max(1, round(e.wait_seconds))
            print(f"  Cerebras Rate Limit. Warte {wait}s...")
            time.sleep(wait)

    raise RuntimeError("Cerebras-Aufruf fehlgeschlagen.")

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
    """Prüft ob das LLM-Output die Mindeststruktur hat (Moodle-Format)."""
    if "activities" not in data:
        raise ValueError("LLM-Output hat kein 'activities'-Feld.")
    activities = data["activities"]
    for key, act in activities.items():
        if "type" not in act:
            raise ValueError(f"Activity '{key}' hat kein 'type'-Feld im LLM-Output.")


def validate_course_output(data: dict, expected_units: int) -> None:
    """Prüft ob das LLM-Output das Course-Editor-Format hat."""
    if "units" not in data:
        raise ValueError("LLM-Output hat kein 'units'-Feld.")
    if not isinstance(data["units"], list) or len(data["units"]) == 0:
        raise ValueError("'units' ist leer oder kein Array.")
    actual = len(data["units"])
    if actual != expected_units:
        print(f"  ⚠ Erwartet {expected_units} Einheiten, erhalten: {actual}. Weiter mit {actual}.")
    _normalize_units(data["units"])


def _normalize_units(units: list) -> None:
    """Post-processes units: derives theoryContent and questions from contentBlocks."""
    for unit_index, unit in enumerate(units, 1):
        unit.setdefault("learningObjectives", [])
        unit.setdefault("estimatedDuration", 60)
        unit.setdefault("materials", [])
        if unit.get("contentBlocks"):
            for block in unit["contentBlocks"]:
                title = str(block.get("title", "")).strip()
                block_type = block.get("type", "activity")
                if not title:
                    if block_type == "theory":
                        block["title"] = "Theory"
                    elif block_type == "example":
                        block["title"] = "Lernpfad"
                    elif block_type == "activity":
                        block["title"] = "Agenda"
                    elif block_type == "homework":
                        block["title"] = "Assignment"
                    elif block_type == "reflection":
                        block["title"] = "Feedback"
                    elif block_type == "quiz":
                        block["title"] = "Self-Check"
                if block.get("type") == "quiz":
                    block.setdefault("questions", [])
                    continue
                if block.get("content"):
                    continue
                unit_title = unit.get("title", "dieser Lerneinheit")
                if block_type == "activity":
                    block["content"] = (
                        f"Bearbeiten Sie in Kleingruppen eine konkrete Fragestellung zu {unit_title}. "
                        "Halten Sie zentrale Begriffe, Beobachtungen und offene Fragen fest und stellen Sie "
                        "das Ergebnis kurz im Plenum vor."
                    )
                elif block_type == "homework":
                    block["content"] = (
                        f"Vertiefen Sie {unit_title} im Selbststudium. Erstellen Sie eine strukturierte "
                        "Zusammenfassung mit den wichtigsten Fachbegriffen, einem Beispiel und zwei offenen "
                        "Fragen fuer die naechste Einheit."
                    )
                elif block_type == "reflection":
                    block["content"] = (
                        f"Reflektieren Sie, welche Aspekte von {unit_title} bereits sicher verstanden sind "
                        "und wo noch Klaerungsbedarf besteht."
                    )
                else:
                    block["content"] = f"Ausgearbeiteter Lerninhalt zu {unit_title}."
            # Derive theoryContent from theory + example blocks if missing
            if not unit.get("theoryContent"):
                parts = [
                    b.get("content", "")
                    for b in unit["contentBlocks"]
                    if b.get("type") in ("theory", "example")
                ]
                unit["theoryContent"] = "\n\n".join(filter(None, parts))
            # Derive flat questions from quiz blocks if missing
            if not unit.get("questions"):
                all_q: list = []
                for block in unit["contentBlocks"]:
                    if block.get("type") == "quiz" and block.get("questions"):
                        all_q.extend(block["questions"])
                unit["questions"] = all_q
        unit.setdefault("theoryContent", "")
        unit.setdefault("questions", [])


def _sanitize_question_types(course: dict) -> None:
    """Remove didactically invalid question types for the detected subject area."""
    area_id = course.get("subjectArea") or _detect_subject_area(
        f"{course.get('subject', '')} {course.get('title', '')}"
    )
    allow_coderunner = _SUBJECT_AREAS.get(area_id, _GENERAL_AREA).get("use_coderunner", False)
    if allow_coderunner:
        return

    for unit in course.get("units", []):
        question_sources = [unit.get("questions", [])]
        for block in unit.get("contentBlocks") or []:
            if block.get("type") == "quiz":
                question_sources.append(block.get("questions", []))
        for questions in question_sources:
            for q in questions or []:
                if q.get("questionType") == "coderunner":
                    q["questionType"] = "open_text"
                    q["sampleAnswer"] = q.get("solution") or q.get("expectedOutput") or "Fachlich begruendete Antwort."
                    q.pop("programmingLanguage", None)
                    q.pop("starterCode", None)
                    q.pop("testCases", None)
                    q.pop("solution", None)


def _contains_generation_placeholder(text: object) -> bool:
    value = str(text or "").lower()
    placeholder_bits = [
        "ausfuehrlicher, fachlich dichter lehrtext",
        "ausführlicher, fachlich dichter lehrtext",
        "voll ausgearbeitete praesenzaktivitaet",
        "voll ausgearbeitete präsenzaktivität",
        "voll ausgearbeitete selbstlernaufgabe",
        "konkretes fachlich passendes beispiel",
        "kurzer einstieg mit relevanz",
        "reflexionsimpuls mit transferfrage",
        "fachlich passendes beispiel mit ausgangslage",
        "fragen_im_passenden_typ",
        "gleiche_fragen_wie_im_quiz_block",
    ]
    return any(bit in value for bit in placeholder_bits)


def _reject_placeholder_content(unit: dict) -> None:
    for obj in unit.get("learningObjectives") or []:
        if str(obj).strip().lower() in {"lernziel 1", "lernziel 2", "learning objective 1", "learning objective 2"}:
            raise ValueError("Lernziele enthalten Platzhalter statt kompetenzorientierter Ziele.")
    for block in unit.get("contentBlocks") or []:
        if block.get("type") != "quiz" and _contains_generation_placeholder(block.get("content")):
            raise ValueError(
                f"Block '{block.get('title', block.get('id', 'unbekannt'))}' enthaelt nur Prompt-Platzhalter statt Fachinhalt."
            )
        for q in block.get("questions") or []:
            if _contains_generation_placeholder(q.get("question")):
                raise ValueError("Quizfrage enthaelt Prompt-Platzhalter statt Fachinhalt.")
    if _contains_generation_placeholder(unit.get("theoryContent")):
        raise ValueError("theoryContent enthaelt Prompt-Platzhalter statt Fachinhalt.")


def _apply_workload_defaults(course: dict, d: dict) -> None:
    """Ensure compact per-unit workload metadata exists if the LLM omitted it."""
    course["estimatedTotalWorkload"] = d["total_minutes"]
    course["estimatedTotalWorkloadHours"] = d["total_hours"]

    for unit in course.get("units", []):
        unit["estimatedDuration"] = int(unit.get("estimatedDuration") or d["dur"])
        unit.setdefault("classActivityMinutes", d["class_minutes"])
        unit.setdefault("selfStudyMinutes", d["self_minutes"])


# ============================================================================
# SUBJECT AREA DETECTION
# ============================================================================

_SUBJECT_AREAS: dict = {
    "healthcare": {
        "keywords": [
            "pflege", "krankenpflege", "gesundheits- und krankenpflege", "gesundheitspflege",
            "pflegewissenschaft", "patient", "patientin", "patienten", "krankheit",
            "erkrankung", "diagnostik", "therapie", "anatomie", "physiologie", "medizin",
            "klinisch", "klinik", "symptom", "symptome", "behandlung", "wundversorgung",
            "medikation", "pflegeplanung", "pflegeprozess", "assessment", "vitalzeichen",
            "hygiene", "infektion", "immunsystem", "nervensystem", "herz", "kreislauf",
            "demenz", "diabetes", "schmerz", "geriatrie", "palliativ", "rehabilitation",
        ],
        "label": "Gesundheit / Pflege / Medizin",
        "use_coderunner": False,
        "preferred_q_types": [
            "single_choice", "true_false", "matching", "ordering", "open_text", "reflection",
        ],
        "unit_variation": (
            "Gestalte die Einheit wie eine Lernveranstaltung in Pflege/Gesundheit:\n"
            "- Fachliche Grundlagen: Anatomie/Physiologie/Pathophysiologie verstaendlich und korrekt erklaeren.\n"
            "- Klinischer Bezug: Symptome, Beobachtungskriterien, Diagnostik, Therapie und Pflegeimplikationen verbinden.\n"
            "- Class Activities: Fallvignette, Gruppenanalyse, Pflegeassessment, Priorisierung, Kommunikation oder Dokumentation.\n"
            "- Self Study: Leitfragen, Fachbegriffe, kurzer Rechercheauftrag, Pflegeplan-/Reflexionsaufgabe.\n"
            "- Quiz: Fachbegriffe, Reihenfolgen, Zuordnungen, sichere/unsichere Aussagen, Transferfragen.\n"
            "Kein CodeRunner. Keine Programmier-, Debugging- oder Rechenprogrammieraufgaben."
        ),
    },
    "programming": {
        "keywords": [
            "python", "java", "javascript", "typescript", "c++", "c#", "php", "ruby", "swift",
            "programmier", "coding", "code", "algorithmus", "algorithmen", "datenstruktur",
            "sql", "datenbank", "database", "webentwicklung", "html", "css", "react", "angular",
            "software", "informatik", "api", "oop", "objektorientiert", "klassen", "funktion",
            "debug", "rekursion", "schleife", "array", "liste", "stack", "compiler",
        ],
        "label": "Informatik / Programmierung",
        "use_coderunner": True,
        "preferred_q_types": [
            "single_choice", "true_false", "fill_in_the_blank", "coderunner", "matching", "open_text",
        ],
        "unit_variation": (
            "Variiere die Einheiten so (nicht jede gleich aufbauen!):\n"
            "- Einführungseinheiten: Theorie + Begriffe → single_choice, true_false\n"
            "- Codeeinheiten: Lückentext + kleines Coding-Problem → fill_in_the_blank, coderunner\n"
            "- Debugeinheiten: Fehler finden / analysieren → coderunner, open_text\n"
            "- Implementierungseinheiten: Algorithmus schreiben → coderunner, single_choice\n"
            "- Abschlusseinheiten: Wiederholung + Reflexion → matching, open_text\n"
            "CodeRunner MUSS in mindestens jeder zweiten Einheit vorkommen."
        ),
    },
    "math": {
        "keywords": [
            "mathematik", "mathe", "algebra", "geometrie", "trigonometrie", "analysis",
            "calculus", "integral", "differentialrechnung", "statistik", "wahrscheinlichkeit",
            "gleichung", "matrix", "vektor", "lineare algebra", "bruchrechnung", "prozentrechnung",
            "pythagoras", "binomial", "quadratisch", "logarithmus", "exponential", "funktion",
            "kurvendiskussion", "wurzel", "potenz", "primzahl", "kombinatorik",
        ],
        "label": "Mathematik",
        "use_coderunner": False,
        "preferred_q_types": [
            "single_choice", "true_false", "calculation", "numerical", "ordering", "fill_in_the_blank", "open_text",
        ],
        "unit_variation": (
            "Variiere die Einheiten so (nicht jede gleich aufbauen!):\n"
            "- Einführungseinheiten: Definitionen + Begriffe → single_choice, true_false\n"
            "- Recheneinheiten: Schrittweise Beispiel → calculation, numerical\n"
            "- Anwendungseinheiten: Realweltaufgaben → calculation, open_text\n"
            "- Testeinheiten: Selbstcheck → single_choice, numerical, true_false\n"
            "- Abschluss: Transfer + offene Aufgabe → open_text\n"
            "Rechenschritte IMMER in solutionSteps angeben. Kein CodeRunner."
        ),
    },
    "history": {
        "keywords": [
            "geschichte", "historisch", "krieg", "revolution", "antike", "mittelalter",
            "belagerung", "weltkrieg", "empire", "reich", "kultur", "zivilisation",
            "türkenbelagerung", "napoleon", "renaissance", "industrialisierung", "reformation",
            "habsburger", "habsburger", "österreich", "wien", "kreuzzug", "kolonisation",
        ],
        "label": "Geschichte",
        "use_coderunner": False,
        "preferred_q_types": [
            "single_choice", "true_false", "ordering", "matching", "open_text", "reflection",
        ],
        "unit_variation": (
            "Variiere die Einheiten so (nicht jede gleich aufbauen!):\n"
            "- Einführungseinheiten: Kontext + Überblick → single_choice, true_false\n"
            "- Chronologieeinheiten: Zeitstrahl + Ereignisse → ordering, matching\n"
            "- Quelleneinheiten: Analyse + offene Fragen → open_text, reflection\n"
            "- Zuordnungseinheiten: Personen/Ereignisse/Orte → matching, single_choice\n"
            "- Abschlusseinheiten: Reflexion + Diskussion → reflection, open_text\n"
            "Kein CodeRunner. Reflexionsfragen unbedingt einbauen."
        ),
    },
    "language": {
        "keywords": [
            "sprache", "grammatik", "vokabel", "deutsch", "englisch", "französisch", "spanisch",
            "literatur", "text", "lesen", "schreiben", "kommunikation", "linguistik",
            "wortschatz", "konjugation", "deklination", "syntax", "phonetik", "rechtschreibung",
        ],
        "label": "Sprache / Literatur",
        "use_coderunner": False,
        "preferred_q_types": [
            "single_choice", "matching", "fill_in_the_blank", "open_text", "ordering", "true_false",
        ],
        "unit_variation": (
            "Variiere die Einheiten so (nicht jede gleich aufbauen!):\n"
            "- Vokabeleinheiten: Zuordnung + Lückentext → matching, fill_in_the_blank\n"
            "- Grammatikeinheiten: Regelübungen → fill_in_the_blank, single_choice\n"
            "- Leseverständniseinheiten: Textanalyse + Fragen → open_text, single_choice\n"
            "- Schreibeinheiten: Freier Text + Reflexion → open_text, reflection\n"
            "- Wiederholungseinheiten: Gemischte Übungen → matching, fill_in_the_blank\n"
            "Kein CodeRunner."
        ),
    },
    "business": {
        "keywords": [
            "wirtschaft", "betriebswirtschaft", "bwl", "marketing", "finanz", "finanzen",
            "buchhaltung", "management", "strategie", "handel", "unternehmen", "kosten",
            "investition", "controlling", "logistik", "rechnungswesen", "bilanz", "steuer",
        ],
        "label": "Wirtschaft / BWL",
        "use_coderunner": False,
        "preferred_q_types": [
            "single_choice", "true_false", "calculation", "matching", "open_text", "ordering",
        ],
        "unit_variation": (
            "Variiere die Einheiten so (nicht jede gleich aufbauen!):\n"
            "- Grundlageneinheiten: Begriffe + Konzepte → single_choice, matching\n"
            "- Fallbeispieleinheiten: Analyse + Entscheidung → open_text, calculation\n"
            "- Recheneinheiten: Kennzahlen + Berechnungen → calculation, numerical\n"
            "- Strategieeinheiten: Szenario + Entscheidung → open_text, single_choice\n"
            "- Abschlusseinheiten: Transfer + Reflexion → reflection, matching\n"
            "Kein CodeRunner. Praxisbezug durch Fallbeispiele."
        ),
    },
    "science": {
        "keywords": [
            "physik", "chemie", "biologie", "naturwissenschaft", "atom", "molekül",
            "energie", "kraft", "evolution", "ökologie", "astronomie", "genetik",
            "reaktion", "thermodynamik", "mechanik", "optik", "elektromagnetismus",
            "spektrum", "gravitation", "zelle", "dns", "protein", "enzym",
        ],
        "label": "Naturwissenschaft",
        "use_coderunner": False,
        "preferred_q_types": [
            "single_choice", "true_false", "calculation", "numerical", "ordering", "open_text", "matching",
        ],
        "unit_variation": (
            "Variiere die Einheiten so (nicht jede gleich aufbauen!):\n"
            "- Grundlageneinheiten: Begriffe + Gesetze → single_choice, true_false\n"
            "- Formeleinheiten: Beispielrechnung → calculation, numerical\n"
            "- Experimentiereinheiten: Aufbau + Analyse → ordering, open_text\n"
            "- Anwendungseinheiten: Transfer + Problemlösung → calculation, single_choice\n"
            "Kein CodeRunner. Rechenaufgaben mit Einheiten (m, kg, J, …)."
        ),
    },
}
_GENERAL_AREA: dict = {
    "label": "Allgemein",
    "use_coderunner": False,
    "preferred_q_types": ["single_choice", "true_false", "matching", "open_text", "ordering", "fill_in_the_blank"],
    "unit_variation": (
        "Variiere die Einheiten abwechslungsreich (nicht jede gleich!):\n"
        "- Einführungseinheiten: Begriffe + Definitionen → single_choice, true_false\n"
        "- Vertiefungseinheiten: Anwendung + Beispiele → matching, open_text\n"
        "- Übungseinheiten: Praktische Aufgaben → ordering, fill_in_the_blank\n"
        "- Abschlusseinheiten: Reflexion + Wiederholung → open_text, single_choice"
    ),
}


def _detect_subject_area(topic: str) -> str:
    """Detects the subject area from topic keywords."""
    t = topic.lower()
    for area_id, area in _SUBJECT_AREAS.items():
        if any(kw in t for kw in area["keywords"]):
            return area_id
    return "general"


# ── Compact JSON snippets as type reference for the LLM ───────────────────────
_Q_TYPE_REFS = {
    "single_choice":  '{"questionType":"single_choice","question":"Was ist …?","answers":[{"id":"a1","text":"Richtige Antwort","isCorrect":true},{"id":"a2","text":"Falsch A","isCorrect":false},{"id":"a3","text":"Falsch B","isCorrect":false}],"explanation":"Erklärung…"}',
    "true_false":     '{"questionType":"true_false","question":"Ist … wahr?","isTrue":true,"explanation":"Erklärung…"}',
    "fill_in_the_blank": '{"questionType":"fill_in_the_blank","question":"Ergänze:","textWithBlanks":"Das _____ Prinzip basiert auf _____.","blanks":["erste","OOP"]}',
    "calculation":    '{"questionType":"calculation","question":"Berechne …","correctNumber":42.5,"tolerance":0.5,"numberUnit":"m","solutionSteps":"Schritt 1: … Schritt 2: …"}',
    "coderunner":     '{"questionType":"coderunner","question":"Schreibe eine Funktion …","programmingLanguage":"python","starterCode":"def solve(x):\\n    pass","solution":"def solve(x):\\n    return x**2","testCases":[{"id":"t1","input":"solve(5)","expectedOutput":"25"},{"id":"t2","input":"solve(0)","expectedOutput":"0"}]}',
    "ordering":       '{"questionType":"ordering","question":"Bringe in die richtige Reihenfolge:","items":[{"id":"i1","text":"Erstes","position":1},{"id":"i2","text":"Zweites","position":2},{"id":"i3","text":"Drittes","position":3}]}',
    "matching":       '{"questionType":"matching","question":"Ordne zu:","matchingPairs":[{"id":"p1","left":"Begriff A","right":"Definition A"},{"id":"p2","left":"Begriff B","right":"Definition B"}]}',
    "open_text":      '{"questionType":"open_text","question":"Erkläre in eigenen Worten …","sampleAnswer":"Eine mögliche Antwort …"}',
    "reflection":     '{"questionType":"reflection","question":"Reflektiere: Was hast du gelernt?","sampleAnswer":"Meine Erkenntnisse …"}',
    "numerical":      '{"questionType":"numerical","question":"Wie groß ist …?","correctNumber":9.81,"tolerance":0.1,"numberUnit":"m/s²"}',
}


# ============================================================================
# MULTI-UNIT COURSE GENERATION
# ============================================================================

def _parse_ects(ects: str) -> float | None:
    """Parse ECTS values such as '3', '3.5' or '3,5'."""
    if not ects:
        return None
    match = re.search(r"\d+(?:[,.]\d+)?", str(ects))
    if not match:
        return None
    value = float(match.group(0).replace(",", "."))
    return value if value > 0 else None


def _default_unit_duration(num_units: int, provider: str) -> int:
    if provider == "ollama":
        return 45
    if num_units <= 2:
        return 90
    if num_units <= 5:
        return 75
    return 60


def _workload_plan(num_units: int, ects: str, provider: str, detail: str = "compact") -> dict:
    """Compact workload model.

    ECTS is intentionally not used to scale generation size. The selected ECTS
    value is kept as metadata only so cloud token budgets are not consumed by
    oversized course/unit prompts.
    """
    detail = detail if detail in ("compact", "normal", "detailed") else "compact"
    unit_minutes = 45 if provider == "ollama" else 60
    class_minutes = 30 if unit_minutes >= 60 else 20
    self_minutes = unit_minutes - class_minutes
    total_minutes = num_units * unit_minutes
    if detail == "detailed":
        q_count = 6
        theory = (
            "ausfuehrlicher, fachlich dichter Lehrtext (450-650 Woerter) "
            "mit Definitionen, Zusammenhaengen, typischen Fehlannahmen, Beispiel und kurzer Einordnung"
        )
        activity = (
            "voll ausgearbeitete Praesenzaktivitaet mit Fall/Szenario, Arbeitsauftrag, "
            "Arbeitsschritten, Sozialform, Ergebnisprodukt, Auswertung und Zeitrahmen"
        )
        homework = (
            "voll ausgearbeitete Selbstlernaufgabe mit Leitfragen, Recherche-/Uebungsauftrag, "
            "Abgabeartefakt, Umfang und Bewertungskriterien"
        )
    elif detail == "normal":
        q_count = 4
        theory = "solider Lehrtext (220-320 Woerter) mit Kernidee, Beispiel und wichtiger Abgrenzung"
        activity = "konkrete Praesenzaktivitaet mit Arbeitsschritten, Ergebnis und kurzer Auswertung"
        homework = "konkrete Selbstlernaufgabe mit klarer Abgabe, Leitfragen oder Reflexionsauftrag"
    else:
        q_count = 3
        theory = "kompakter Lehrtext (120-180 Woerter) mit Kernidee und Beispiel"
        activity = "kurze konkrete Praesenzaktivitaet mit Arbeitsauftrag"
        homework = "kurze konkrete Selbstlernaufgabe"
    answers = 3

    return {
        "q": q_count,
        "a": answers,
        "obj": 2,
        "theory": theory,
        "activity": activity,
        "homework": homework,
        "detail": detail,
        "dur": unit_minutes,
        "class_minutes": class_minutes,
        "self_minutes": self_minutes,
        "total_minutes": total_minutes,
        "total_hours": round(total_minutes / 60, 1),
        "hours_per_unit": round(unit_minutes / 60, 1),
        "ects_value": _parse_ects(ects),
    }


def _unit_depth(num_units: int, provider: str, ects: str = "", detail: str = "compact") -> dict:
    """Return compact per-unit generation limits. ECTS is metadata only."""
    return _workload_plan(num_units, ects, provider, detail)


def build_prompt_course_units(topic: str, num_units: int, ects: str,
                              audience: str, extra: str, provider: str) -> str:
    """
    Dynamic multi-unit course prompt.
    - Detects subject area and chooses appropriate content structure + question types
    - Generates contentBlocks (theory, example, quiz) per unit for Groq
    - Falls back to simple flat format for Ollama
    - CodeRunner only appears for technical/programming topics
    """
    area_id    = _detect_subject_area(topic)
    area       = _SUBJECT_AREAS.get(area_id, _GENERAL_AREA)
    d          = _unit_depth(num_units, provider, ects)
    audience   = audience or "Allgemein"
    ects_info  = f" | {ects} ECTS" if ects else ""
    extra_info = f"\nZusatzwünsche des Lektors: {extra}" if extra else ""
    total_dur  = d["total_minutes"]
    id_end     = f"u{num_units:02d}"
    workload_rule = (
        f"KOMPAKTER WORKLOAD: ECTS ist nur Metadatum und skaliert NICHT den Umfang. "
        f"Plane je Einheit kurz: {d['class_minutes']} Minuten Class Activities "
        f"und {d['self_minutes']} Minuten Self Study. "
        "Halte Inhalte, Uebungen und Quiz kompakt, damit Cloud-Tokenbudgets geschont werden."
    )

    # Ollama: use simplified flat format (no contentBlocks)
    if provider == "ollama":
        return _build_prompt_ollama_units(topic, num_units, ects, audience, extra, d, area_id)

    # Groq: rich contentBlocks format with varied question types
    use_coderunner = area.get("use_coderunner", False)
    q_types        = area.get("preferred_q_types", ["single_choice", "open_text"])

    # Build compact type-reference (show only relevant types + coderunner if applicable)
    ref_types = q_types[:5]
    if use_coderunner and "coderunner" not in ref_types:
        ref_types.append("coderunner")
    type_ref_lines = [f"  {qt}: {_Q_TYPE_REFS[qt]}" for qt in ref_types if qt in _Q_TYPE_REFS]
    type_ref = "\n".join(type_ref_lines)

    coderunner_note = (
        f"\n  coderunner: {_Q_TYPE_REFS['coderunner']}"
        if use_coderunner else
        "\nKEINE coderunner-Fragen (passt nicht zum Thema)."
    )

    return f"""Erstelle GENAU {num_units} Unterrichtseinheiten für den Kurs "{topic}"{ects_info}.
Themenbereich: {area["label"]} | Zielgruppe: {audience}.{extra_info}

{workload_rule}

DIDAKTISCHE STRUKTUR ({area["label"]}):
{area["unit_variation"]}

ERLAUBTE FRAGETYPEN – wähle passend, mindestens 3 verschiedene Typen im gesamten Kurs:
{type_ref}{coderunner_note}

Jede Einheit enthält "contentBlocks" – abwechslungsreiche Lernblöcke:
  "theory":     Ausführlicher Theorietext (content-Feld)
  "example":    Konkretes Beispiel oder Demonstration (content-Feld)
  "activity":   Praktische Aufgabe / Übung (content-Feld)
  "quiz":       Fragen ({d["q"]}-{d["q"]+1} Stück, questions-Array, VERSCHIEDENE Typen)
  "reflection": Reflexionsimpuls (content-Feld)
  "homework":   Hausübung (content-Feld)

Jede Einheit soll nach Moeglichkeit beide Bereiche klar enthalten:
- Class Activities: mindestens ein activity-, example- oder quiz-Block mit Titel beginnend mit "Class Activities:".
- Self Study: mindestens ein homework-, reflection- oder quiz-Block mit Titel beginnend mit "Self Study:".
- Waehle Aktivitaeten fachlich passend: Programmieraufgaben und CodeRunner fuer Programmierung, Fallstudien fuer Wirtschaft, Labor-/Experimentieraufgaben fuer technische und naturwissenschaftliche Themen, Quellenanalyse fuer Geschichte, Sprachproduktion fuer Sprachen.
- Umfang nicht anhand von ECTS vergroessern. Jede Einheit kompakt halten: kurze Inhalte, klare Aktivitaet, kurze Selbstlernaufgabe, kurzer Lerncheck.

Antworte NUR mit diesem JSON-Objekt (kein Markdown, kein Text davor/danach):

{{
  "title": "Vollständiger Kurstitel",
  "description": "Kursbeschreibung (2–3 Sätze).",
  "subject": "{topic}",
  "subjectArea": "{area_id}",
  "targetAudience": "{audience}",
  "ects": "{ects}",
  "estimatedTotalWorkload": {total_dur},
  "units": [
    {{
      "id": "u01",
      "title": "Erster Teilaspekt von {topic}",
      "description": "Kurze Beschreibung.",
      "learningObjectives": ["Lernziel 1", "Lernziel 2"],
      "estimatedDuration": {d["dur"]},
      "classActivityMinutes": {d["class_minutes"]},
      "selfStudyMinutes": {d["self_minutes"]},
      "materials": [],
      "theoryContent": "Fließtext für Moodle-Export (mind. 50 Wörter).",
      "contentBlocks": [
        {{
          "id": "cb-01-01",
          "type": "theory",
          "title": "Grundlagen",
          "content": "{d['theory']}"
        }},
        {{
          "id": "cb-01-02",
          "type": "example",
          "title": "Praxisbeispiel",
          "content": "Konkretes illustrierendes Beispiel zu diesem Teilthema."
        }},
        {{
          "id": "cb-01-03",
          "type": "quiz",
          "title": "Lerncheck",
          "questions": [
            FRAGE_IM_PASSENDEN_TYP_GEMAESS_FRAGETYPEN_REFERENZ
          ]
        }}
      ],
      "questions": [GLEICHE_FRAGEN_WIE_IM_QUIZ_BLOCK]
    }},
    {{ "id": "u02", "...": "Einheit 2 im gleichen Format, ANDEREN Block-Aufbau wählen" }},
    {{ "...": "alle weiteren Einheiten bis {id_end}" }}
  ]
}}

PFLICHTREGELN:
1. GENAU {num_units} Einheiten (IDs u01 bis {id_end}).
2. Jede Einheit behandelt einen ANDEREN Teilaspekt von "{topic}".
3. NICHT jede Einheit gleich – Blocktypen und Fragetypen pro Einheit variieren.
4. "questions" am Unit-Level = exakt die gleichen Fragen wie im quiz-ContentBlock.
5. Keine Platzhalter – echte, korrekte Inhalte zu "{topic}".
6. Beginne mit {{, ende mit }}. Kein Markdown.
"""


def _build_prompt_ollama_units(topic: str, num_units: int, ects: str,
                               audience: str, extra: str, d: dict, area_id: str) -> str:
    """Simplified flat prompt for Ollama (no contentBlocks)."""
    ects_info  = f" | {ects} ECTS" if ects else ""
    extra_info = f"\nZusatzwünsche: {extra}" if extra else ""
    total_dur  = d["total_minutes"]
    id_end     = f"u{num_units:02d}"
    workload_rule = (
        f"Kompakter Workload: ECTS ist nur Metadatum. "
        f"Pro Einheit ca. {d['class_minutes']} Minuten Class Activities und "
        f"{d['self_minutes']} Minuten Self Study. Nicht wegen ECTS ausweiten."
    )
    ans_tpl = ",".join(
        [f'{{"id":"a-NN-01-{j+1:02d}","text":"{"Richtige Antwort" if j == 0 else f"Falsche Antwort {chr(64+j)}"}","isCorrect":{str(j == 0).lower()}}}'
         for j in range(d["a"])]
    )
    return f"""Erstelle GENAU {num_units} Unterrichtseinheiten für den Kurs "{topic}"{ects_info}.
Zielgruppe: {audience or "Allgemein"}.{extra_info}

{workload_rule}
Jede Einheit soll Class Activities und Self Study enthalten. Nutze fachlich passende Aufgabenformen und variiere die Aktivitaeten.

Antworte NUR mit diesem JSON (kein Markdown):

{{
  "title": "Kurstitel",
  "description": "Kurzbeschreibung.",
  "subject": "{topic}",
  "subjectArea": "{area_id}",
  "targetAudience": "{audience or "Allgemein"}",
  "ects": "{ects}",
  "estimatedTotalWorkload": {total_dur},
  "units": [
    {{
      "id": "u01",
      "title": "Teilthema 1",
      "description": "Kurze Beschreibung.",
      "learningObjectives": ["Lernziel 1", "Lernziel 2"],
      "theoryContent": "Theorietext zu diesem Teilthema...",
      "estimatedDuration": {d["dur"]},
      "classActivityMinutes": {d["class_minutes"]},
      "selfStudyMinutes": {d["self_minutes"]},
      "questions": [
        {{
          "id": "q-01-01",
          "questionType": "single_choice",
          "question": "Frage zu diesem Thema?",
          "explanation": "Erklärung.",
          "answers": [{ans_tpl}]
        }}
      ]
    }},
    {{ "id": "u02", "...": "weitere Einheit" }},
    {{ "...": "bis {id_end}" }}
  ]
}}

REGELN: GENAU {num_units} Einheiten (u01–{id_end}). Echte Inhalte. Beginne mit {{.
"""


def _provider_default_model(provider: str, model: str | None) -> str:
    if model:
        return model
    if provider == "groq":
        return GROQ_DEFAULT_MODEL
    if provider == "gemini":
        return GEMINI_DEFAULT_MODEL
    if provider == "cerebras":
        return CEREBRAS_DEFAULT_MODEL
    return OLLAMA_DEFAULT_MODEL


def _call_course_provider(provider: str, prompt: str, model: str | None,
                          api_key: str | None, max_tokens: int) -> str:
    model_name = _provider_default_model(provider, model)
    effective_key = api_key or os.environ.get({
        "groq": "GROQ_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "cerebras": "CEREBRAS_API_KEY",
    }.get(provider, ""), "")

    print(f"  → {provider} ({model_name}) wird aufgerufen...")

    if provider == "groq":
        return call_groq(prompt, model_name, effective_key, max_tokens=max_tokens)
    if provider == "gemini":
        return call_gemini(prompt, model_name, effective_key, max_tokens=max_tokens)
    if provider == "cerebras":
        return call_cerebras(prompt, model_name, effective_key, max_tokens=max_tokens)
    return call_ollama(prompt, model_name)


def _question_type_reference(area: dict) -> str:
    q_types = area.get("preferred_q_types", ["single_choice", "open_text"])
    ref_types = q_types[:5]
    if area.get("use_coderunner") and "coderunner" not in ref_types:
        ref_types.append("coderunner")
    lines = [f"  {qt}: {_Q_TYPE_REFS[qt]}" for qt in ref_types if qt in _Q_TYPE_REFS]
    if not area.get("use_coderunner"):
        lines.append("  KEINE coderunner-Fragen, wenn das Thema nicht Programmierung/Informatik ist.")
    return "\n".join(lines)


def _moodle_course_pattern(area: dict, language: str = "de") -> str:
    if language == "en":
        base = (
            "Moodle course pattern learned from real exports:\n"
            "- Course-level orientation section: LV/course organisation, schedule, assessment, communication, learning path.\n"
            "- Repeating Class/Presence sections: slides or theory input, case/exercise material, worked examples, in-class task.\n"
            "- Repeating Self-Study sections: script/reading material, guided task, hand-in assignment or portfolio/reflection task.\n"
            "- Assessment section: question catalogue, exam/quiz preparation, retake or final hand-in where appropriate.\n"
            "- Names are concrete, e.g. 'Class 1 Topic', 'Self-Study A Topic', 'Hand-In Assignment 1', 'Cases Topic Block 3'."
        )
    else:
        base = (
            "Moodle-Kursmuster aus echten Exporten:\n"
            "- Kursstart/LV-Organisation: Ablauf, Kommunikation, Beurteilung, Lernpfad, Termine.\n"
            "- Wiederholte Praesenz-/Class-Abschnitte: Folien/Fachinput, Fall-/Uebungsmaterial, Beispiele, Praesenzaufgabe.\n"
            "- Wiederholte Eigenstudium-/Self-Study-Abschnitte: Skript/Lesematerial, angeleitete Aufgabe, Abgabe oder Portfolio/Reflexion.\n"
            "- Pruefungs-/Abschlussbereich: Fragenkatalog, Pruefungsvorbereitung, Abschlussquiz oder Wiederholung.\n"
            "- Namen sind konkret, z.B. 'Praesenz 1 Thema', 'Eigenstudium A Thema', 'Hand-In Assignment 1', 'Faelle Themenblock 3'."
        )

    if area.get("label") == "Gesundheit / Pflege / Medizin":
        base += (
            "\nPflege/Gesundheit: Jede Einheit braucht fachlich passende Pflege-/Medizinaktivitaeten: "
            "Fallvignette, Beobachtungskriterien, Assessment, Pflegeplanung, Patientenedukation, "
            "Dokumentation, Kommunikation, Sicherheitsaspekte, Reflexion. Kein CodeRunner."
        )
    return base


def _build_prompt_course_structure(topic: str, num_units: int, ects: str,
                                   audience: str, extra: str, provider: str,
                                   detail: str = "compact", language: str = "de") -> str:
    area_id = _detect_subject_area(topic)
    area = _SUBJECT_AREAS.get(area_id, _GENERAL_AREA)
    d = _unit_depth(num_units, provider, ects, detail)
    audience = audience or "Allgemein"
    extra_info = f"\nZusatzwuensche des Lektors: {extra}" if extra else ""
    id_end = f"u{num_units:02d}"
    moodle_pattern = _moodle_course_pattern(area, language)

    return f"""Du bist ein Moodle-Kursgenerator.

WICHTIG: Erstelle NICHT den gesamten Kurs. Erzeuge NUR die Kursstruktur.

Kurs: "{topic}" | Zielgruppe: {audience} | Themenbereich: {area["label"]}{extra_info}
ECTS: {ects or "nicht angegeben"} (nur Metadatum, NICHT zur Umfangssteigerung verwenden).
Sprache: {"Deutsch" if language == "de" else "Englisch"}. Detailgrad: {d["detail"]}.
Kompakter Plan: pro Einheit ca. {d['class_minutes']} Minuten Class Activities und {d['self_minutes']} Minuten Self Study.

{moodle_pattern}

Die Kursstruktur soll wie ein realer Moodle-Kursplan aussehen:
- Einheit 1 darf Orientierung/Fachgrundlagen enthalten, aber NICHT nur organisatorisch sein.
- Jede fachliche Einheit muss direkt als Paar gedacht werden: Praesenz/Class + Eigenstudium/Self-Study.
- Titel muessen nach echten LV-Abschnitten klingen, nicht nach generischen Kapiteln.
- Lernziele muessen kompetenzorientiert sein, keine Platzhalter wie "Lernziel 1".

Antworte NUR mit validem JSON:
{{
  "title": "Vollstaendiger Kurstitel",
  "description": "Kurze Kursbeschreibung mit Zielgruppe und Kompetenzziel.",
  "subject": "{topic}",
  "subjectArea": "{area_id}",
  "targetAudience": "{audience}",
  "ects": "{ects}",
  "estimatedTotalWorkload": {d['total_minutes']},
  "units": [
    {{
      "id": "u01",
      "title": "Titel der ersten Lerneinheit",
      "description": "Kurzbeschreibung, keine Inhalte ausformulieren.",
      "learningObjectives": [
        "Konkretes Kompetenzziel zur fachlichen Einordnung",
        "Konkretes Kompetenzziel zur Anwendung in Praesenz oder Eigenstudium"
      ],
      "estimatedDuration": {d['dur']},
      "classActivityMinutes": {d['class_minutes']},
      "selfStudyMinutes": {d['self_minutes']},
      "materials": []
    }},
    {{ "id": "u02", "...": "weitere Struktur-Einheit" }},
    {{ "...": "bis {id_end}" }}
  ]
}}

REGELN:
1. GENAU {num_units} Einheiten mit IDs u01 bis {id_end}.
2. Nur Struktur: keine Theorieinhalte, keine Quizfragen, keine contentBlocks.
3. Jede Einheit braucht Titel, Kurzbeschreibung, Lernziele und kompakten Workload.
4. Jede Einheit behandelt einen anderen Teilaspekt von "{topic}".
5. Lernziele muessen konkrete Kompetenzen sein, keine Platzhalter.
6. Beginne mit {{ und ende mit }}. Kein Markdown.
"""


def _build_prompt_single_unit(course: dict, unit_stub: dict, unit_index: int,
                              num_units: int, topic: str, ects: str,
                              audience: str, extra: str, provider: str,
                              detail: str = "compact", language: str = "de") -> str:
    area_id = course.get("subjectArea") or _detect_subject_area(topic)
    area = _SUBJECT_AREAS.get(area_id, _GENERAL_AREA)
    d = _unit_depth(num_units, provider, ects, detail)
    audience = audience or course.get("targetAudience") or "Allgemein"
    q_ref = _question_type_reference(area)
    moodle_pattern = _moodle_course_pattern(area, language)
    structure = [
        {
            "id": u.get("id"),
            "title": u.get("title"),
            "description": u.get("description", ""),
        }
        for u in course.get("units", [])
    ]
    extra_info = f"\nZusatzwuensche des Lektors: {extra}" if extra else ""
    if d["detail"] == "detailed":
        detail_rule = (
            "- Detailgrad detailed: Die Einheit soll wie ein vollwertiger Moodle-Abschnitt fuer eine Lehrveranstaltung wirken. "
            "Sie braucht einen Lernueberblick, einen langen fachlichen Theorieblock, ein praxisnahes Beispiel/Fallbeispiel, "
            "eine voll ausformulierte Class Activity, eine voll ausformulierte Self-Study-Aufgabe, Reflexion/Transfer "
            f"und mindestens {d['q']} Quizfragen. Keine leeren content-Felder."
        )
    elif d["detail"] == "normal":
        detail_rule = (
            "- Detailgrad normal: Inhalte sollen solide ausgearbeitet sein. "
            "Activity und Homework muessen konkrete Arbeitsauftraege enthalten."
        )
    else:
        detail_rule = "- Detailgrad compact: Inhalte kurz, aber alle content-Felder trotzdem konkret ausfuellen."

    return f"""Du bist ein Moodle-Kursgenerator.

WICHTIG:
Generiere jetzt NUR EINE einzelne Lerneinheit. Erstelle niemals den gesamten Kurs auf einmal.

Kurs: "{course.get('title', topic)}"
Thema: "{topic}" | Zielgruppe: {audience} | Themenbereich: {area["label"]}{extra_info}
Sprache: {"Deutsch" if language == "de" else "Englisch"}. Detailgrad: {d["detail"]}.
Gesamte Kursstruktur zur Orientierung:
{json.dumps(structure, ensure_ascii=False)}

Jetzt auszuarbeitende Einheit:
{json.dumps(unit_stub, ensure_ascii=False)}

Didaktische Vorgaben:
{area["unit_variation"]}

{moodle_pattern}

Workload dieser Einheit:
- estimatedDuration: {unit_stub.get('estimatedDuration', d['dur'])} Minuten
- Class Activities: {unit_stub.get('classActivityMinutes', d['class_minutes'])} Minuten
- Self Study: {unit_stub.get('selfStudyMinutes', d['self_minutes'])} Minuten
- ECTS nicht zur Umfangssteigerung verwenden.
{detail_rule}
- Jede Einheit muss klar in ZWEI Bereiche geteilt sein:
  1. "Class {unit_index:02d}": Inhalte und Aktivitaeten fuer die Praesenzphase.
  2. "Self Study {unit_index:02d}": Aufgaben und Vertiefung fuer das Selbststudium.
- Diese Namen sind Abschnittsueberschriften. Innerhalb der Abschnitte duerfen Blocktitel die Praefixe NICHT wiederholen.
- Verwende innerhalb der Bereiche kurze Moodle-Elementnamen wie "Lernpfad", "Theory", "Agenda", "Supplemental Material", "Videos", "Assignment", "Self-Check", "Feedback".
- Fachliche Passung ist Pflicht: Verwende nur Aktivitaets- und Fragetypen, die fuer Themenbereich "{area["label"]}" didaktisch sinnvoll sind.
- Wenn der Themenbereich Pflege/Gesundheit/Medizin ist: nutze Fallvignetten, Beobachtung, Assessment, Pflegeplanung, Kommunikation, Patientensicherheit, Dokumentation und Reflexion. Niemals CodeRunner.
- Wenn der Themenbereich nicht Informatik/Programmierung ist: Niemals CodeRunner, keine Programmieraufgaben, keine Debugging-Aufgaben.
- Diese Einheit soll nicht wie ein kurzer Lernzettel wirken, sondern wie ein Moodle-Abschnitt einer echten Lehrveranstaltung: mit Materialien, klarer Aufgabenstellung, didaktischem Ablauf und Ergebnisprodukt.

Erlaubte/passende Fragetypen:
{q_ref}

Antworte NUR mit validem JSON fuer DIESE EINE Einheit:
{{
  "unit": {{
    "id": "{unit_stub.get('id', f'u{unit_index:02d}')}",
    "title": "{unit_stub.get('title', 'Lerneinheit')}",
    "description": "Kurzbeschreibung.",
    "learningObjectives": [
      "Konkretes Kompetenzziel zur fachlichen Einordnung dieser Einheit",
      "Konkretes Kompetenzziel zur Anwendung in Fall, Uebung oder Praxis"
    ],
    "estimatedDuration": {unit_stub.get('estimatedDuration', d['dur'])},
    "classActivityMinutes": {unit_stub.get('classActivityMinutes', d['class_minutes'])},
    "selfStudyMinutes": {unit_stub.get('selfStudyMinutes', d['self_minutes'])},
    "materials": [
      "Foliensatz oder Fachinput zur Praesenzphase",
      "Skript/Lesematerial fuer das Eigenstudium",
      "Fall-/Uebungsmaterial oder Arbeitsblatt"
    ],
    "theoryContent": "Moodle-Export-Fliesstext der Einheit.",
    "contentBlocks": [
      {{
        "id": "cb-{unit_index:02d}-00",
        "type": "example",
        "title": "Lernpfad",
        "content": "Schreibe hier echten fachlichen Inhalt: Relevanz der Einheit, 3-5 konkrete Leitfragen und erwartete Kompetenzen fuer diese konkrete Einheit."
      }},
      {{
        "id": "cb-{unit_index:02d}-01",
        "type": "theory",
        "title": "Theory",
        "content": "Schreibe hier den vollstaendigen fachlichen Lehrtext. Anforderung: {d['theory']}. Der Text muss konkrete Begriffe, Zusammenhaenge und Beispiele zur Einheit enthalten."
      }},
      {{
        "id": "cb-{unit_index:02d}-02",
        "type": "example",
        "title": "Example / Case",
        "content": "Schreibe hier ein echtes Praxisbeispiel oder eine echte Fallvignette zur Einheit mit Ausgangslage, Fragestellung und Auswertungshinweisen."
      }},
      {{
        "id": "cb-{unit_index:02d}-03",
        "type": "activity",
        "title": "Agenda",
        "content": "Schreibe hier eine echte Aktivitaet. Anforderung: {d['activity']}. Sie muss fachlich zur Einheit passen."
      }},
      {{
        "id": "cb-{unit_index:02d}-04",
        "type": "homework",
        "title": "Assignment",
        "content": "Schreibe hier eine echte Selbstlernaufgabe. Anforderung: {d['homework']}. Sie muss ein klares Ergebnisprodukt enthalten."
      }},
      {{
        "id": "cb-{unit_index:02d}-05",
        "type": "reflection",
        "title": "Feedback",
        "content": "Schreibe hier echte Reflexions- und Transferfragen zur Einheit mit Bezug zur beruflichen oder fachlichen Praxis."
      }},
      {{
        "id": "cb-{unit_index:02d}-06",
        "type": "quiz",
        "title": "Self-Check",
        "questions": [
          FRAGEN_IM_PASSENDEN_TYP
        ]
      }}
    ],
    "questions": [GLEICHE_FRAGEN_WIE_IM_QUIZ_BLOCK]
  }}
}}

REGELN:
1. Nur diese eine Einheit ausarbeiten, keine anderen Einheiten generieren.
2. Inhalte, Moodle-Aktivitaeten, Selbstlernaufgaben, Quizfragen und praktische Uebungen muessen fachlich konkret zum Thema passen.
3. CodeRunner ist ausschliesslich bei Informatik/Programmierung erlaubt. Bei Pflege, Medizin, Gesundheit, Geschichte, Sprachen, BWL, Kunst und Naturwissenschaft ohne Programmierbezug ist CodeRunner verboten.
4. Pflege/Gesundheit: Fallarbeit, Pflegeassessment, Beobachtung, Patientensicherheit, Edukation, Dokumentation und Reflexion. Wirtschaft: Fallstudien/Szenarien. Geschichte: Quellenanalyse. Technik/Naturwissenschaft: Experiment/Analyse/Rechenaufgaben ohne CodeRunner.
5. "questions" am Unit-Level entspricht exakt den Quizfragen aus dem quiz-contentBlock.
6. Jede Einheit braucht mindestens vier Class-Bloecke und mindestens drei Self-Study-Elemente inklusive Lerncheck.
7. materials muss 2-4 konkrete Moodle-Materialien nennen, z.B. Foliensatz, Skript, Fallmaterial, Arbeitsblatt, Leitfragen.
8. Lernziele muessen konkrete Kompetenzen beschreiben, niemals "Lernziel 1" oder "Lernziel 2".
9. Blocktitel duerfen NICHT mit "Class", "Praesenz", "Self Study" oder "Eigenstudium" beginnen; das sind nur Abschnittstitel.
10. Kopiere NIEMALS die Beispielsaetze aus dem JSON-Schema. Schreibe echte Kursinhalte.
11. Kein content-Feld darf leer sein. Keine Platzhalter. Beginne mit {{ und ende mit }}. Kein Markdown.
"""


def _normalize_course_structure(course: dict, topic: str, num_units: int,
                                ects: str, audience: str, provider: str,
                                detail: str = "compact", language: str = "de") -> dict:
    d = _unit_depth(num_units, provider, ects, detail)
    area_id = course.get("subjectArea") or _detect_subject_area(topic)
    units = course.get("units", [])
    if not isinstance(units, list) or not units:
        raise ValueError("Kursstruktur enthaelt keine units-Liste.")
    if len(units) != num_units:
        print(f"  ⚠ Struktur: Erwartet {num_units} Einheiten, erhalten: {len(units)}. Weiter mit {len(units)}.")

    normalized_units = []
    for idx, unit in enumerate(units, 1):
        if not isinstance(unit, dict):
            unit = {}
        normalized_units.append({
            "id": unit.get("id") or f"u{idx:02d}",
            "title": unit.get("title") or f"Lerneinheit {idx}",
            "description": unit.get("description", ""),
            "learningObjectives": unit.get("learningObjectives") or [],
            "estimatedDuration": int(unit.get("estimatedDuration") or d["dur"]),
            "classActivityMinutes": int(unit.get("classActivityMinutes") or d["class_minutes"]),
            "selfStudyMinutes": int(unit.get("selfStudyMinutes") or d["self_minutes"]),
            "materials": unit.get("materials") or [],
        })

    result = {
        "title": course.get("title") or f"Kurs: {topic}",
        "description": course.get("description", ""),
        "subject": course.get("subject") or topic,
        "subjectArea": area_id,
        "targetAudience": course.get("targetAudience") or audience or "Allgemein",
        "ects": course.get("ects", ects),
        "detailLevel": detail,
        "language": language,
        "generationStatus": "plan",
        "estimatedTotalWorkload": d["total_minutes"],
        "units": normalized_units,
    }
    _apply_workload_defaults(result, d)
    return result


def _normalize_generated_unit(data: dict, fallback: dict) -> dict:
    unit = data.get("unit", data)
    if not isinstance(unit, dict):
        raise ValueError("Einheiten-Output ist kein JSON-Objekt.")

    merged = {**fallback, **unit}
    merged.setdefault("learningObjectives", fallback.get("learningObjectives", []))
    merged.setdefault("estimatedDuration", fallback.get("estimatedDuration", 60))
    merged.setdefault("classActivityMinutes", fallback.get("classActivityMinutes", 25))
    merged.setdefault("selfStudyMinutes", fallback.get("selfStudyMinutes", 35))
    merged.setdefault("materials", fallback.get("materials", []))
    merged.setdefault("theoryContent", "")
    merged.setdefault("contentBlocks", [])
    merged.setdefault("questions", [])
    _normalize_units([merged])
    _reject_placeholder_content(merged)
    return merged


def generate_course_units(topic: str, num_units: int, ects: str, audience: str,
                          extra: str, provider: str, model: str | None,
                          api_key: str | None, detail: str = "compact",
                          language: str = "de") -> dict:
    """
    Calls the LLM and returns a Course Editor JSON with num_units units.
    Retries up to MAX_RETRIES times on invalid JSON.
    """
    if provider == "groq" and not api_key and not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError(
            "Groq benötigt einen API-Key.\n"
            "Kostenlos unter: https://console.groq.com"
        )
    if provider == "gemini" and not api_key and not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError(
            "Gemini benötigt einen API-Key.\n"
            "Setze GEMINI_API_KEY in deiner .env-Datei oder als Umgebungsvariable.\n"
            "Hinweis: .env.example ist nur eine Vorlage und wird nicht als Konfiguration verwendet."
        )
    if provider == "ollama" and num_units > 10:
        print("  Hinweis: Viele Einheiten koennen mit lokalen Ollama-Modellen laenger dauern.")

    workload = _unit_depth(num_units, provider, ects, detail)

    print("  → Schritt 1/2: Generiere nur die Kursstruktur …")
    structure_error = None
    course_structure = None
    for attempt in range(1, MAX_RETRIES + 1):
        if attempt > 1:
            print(f"  → Struktur-Versuch {attempt}/{MAX_RETRIES} (Fehler: {structure_error})")
        prompt = (
            _build_prompt_course_structure(topic, num_units, ects, audience, extra, provider, detail, language)
            + (f"\n\nFEHLER im letzten Versuch: {structure_error}\n"
               "Antworte NUR mit dem JSON-Objekt fuer die Kursstruktur." if attempt > 1 else "")
        )
        try:
            raw = _call_course_provider(provider, prompt, model, api_key, max_tokens=5000)
            data = extract_json(raw)
            course_structure = _normalize_course_structure(data, topic, num_units, ects, audience, provider, detail, language)
            break
        except (ValueError, RuntimeError) as e:
            structure_error = str(e)[:180]

    if course_structure is None:
        raise RuntimeError(
            f"LLM hat nach {MAX_RETRIES} Versuchen keine valide Kursstruktur geliefert.\n"
            f"Letzter Fehler: {structure_error}"
        )

    print(f"  → Struktur erhalten: {len(course_structure.get('units', []))} Einheiten.")
    print("  → Schritt 2/2: Generiere jede Lerneinheit einzeln …")

    generated_units = []
    for idx, unit_stub in enumerate(course_structure.get("units", []), 1):
        unit_error = None
        generated_unit = None
        print(f"  → Einheit {idx}/{len(course_structure['units'])}: {unit_stub.get('title', unit_stub.get('id'))}")
        for attempt in range(1, MAX_RETRIES + 1):
            if attempt > 1:
                print(f"    → Einheiten-Versuch {attempt}/{MAX_RETRIES} (Fehler: {unit_error})")
            prompt = (
                _build_prompt_single_unit(
                    course_structure, unit_stub, idx, len(course_structure["units"]),
                    topic, ects, audience, extra, provider, detail, language,
                )
                + (f"\n\nFEHLER im letzten Versuch: {unit_error}\n"
                   "Antworte NUR mit dem JSON-Objekt fuer diese eine Einheit." if attempt > 1 else "")
            )
            try:
                raw = _call_course_provider(provider, prompt, model, api_key, max_tokens=9000)
                data = extract_json(raw)
                generated_unit = _normalize_generated_unit(data, unit_stub)
                break
            except (ValueError, RuntimeError) as e:
                unit_error = str(e)[:180]

        if generated_unit is None:
            raise RuntimeError(
                f"Einheit {unit_stub.get('id', idx)} konnte nach {MAX_RETRIES} Versuchen nicht generiert werden.\n"
                f"Letzter Fehler: {unit_error}"
            )
        generated_units.append(generated_unit)

    course_data = {**course_structure, "units": generated_units}
    course_data["generationStatus"] = "complete"
    validate_course_output(course_data, len(generated_units))
    _sanitize_question_types(course_data)
    _apply_workload_defaults(course_data, workload)
    return course_data


def generate_course_plan(topic: str, num_units: int, ects: str, audience: str,
                         extra: str, provider: str, model: str | None,
                         api_key: str | None, detail: str = "compact",
                         language: str = "de") -> dict:
    """Generate only the course plan preview, without unit content."""
    if provider == "groq" and not api_key and not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("Groq benötigt einen API-Key.")
    if provider == "gemini" and not api_key and not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError(
            "Gemini benötigt einen API-Key.\n"
            "Setze GEMINI_API_KEY in deiner .env-Datei oder als Umgebungsvariable."
        )

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        if attempt > 1:
            print(f"  → Plan-Versuch {attempt}/{MAX_RETRIES} (Fehler: {last_error})")
        prompt = (
            _build_prompt_course_structure(topic, num_units, ects, audience, extra, provider, detail, language)
            + (f"\n\nFEHLER im letzten Versuch: {last_error}\n"
               "Antworte NUR mit dem JSON-Objekt fuer die Kursstruktur." if attempt > 1 else "")
        )
        try:
            raw = _call_course_provider(provider, prompt, model, api_key, max_tokens=5000)
            data = extract_json(raw)
            return _normalize_course_structure(data, topic, num_units, ects, audience, provider, detail, language)
        except (ValueError, RuntimeError) as e:
            last_error = str(e)[:180]

    raise RuntimeError(
        f"LLM hat nach {MAX_RETRIES} Versuchen keine valide Kursstruktur geliefert.\n"
        f"Letzter Fehler: {last_error}"
    )


def generate_unit_for_course(course: dict, unit_id: str, provider: str,
                             model: str | None, api_key: str | None,
                             extra: str = "", detail: str | None = None,
                             language: str | None = None) -> dict:
    """Generate or regenerate one unit and return the updated course JSON."""
    if provider == "groq" and not api_key and not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("Groq benötigt einen API-Key.")
    if provider == "gemini" and not api_key and not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError(
            "Gemini benötigt einen API-Key.\n"
            "Setze GEMINI_API_KEY in deiner .env-Datei oder als Umgebungsvariable."
        )

    units = course.get("units", [])
    if not isinstance(units, list) or not units:
        raise RuntimeError("Kurs hat keine Einheiten.")

    unit_index = next((i for i, u in enumerate(units, 1) if u.get("id") == unit_id), None)
    if unit_index is None:
        raise RuntimeError(f"Einheit {unit_id} nicht gefunden.")

    topic = course.get("subject") or course.get("title") or "Kurs"
    ects = str(course.get("ects", ""))
    audience = course.get("targetAudience", "")
    detail = detail or course.get("detailLevel", "compact")
    language = language or course.get("language", "de")
    unit_stub = units[unit_index - 1]

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        if attempt > 1:
            print(f"  → Einheit-Versuch {attempt}/{MAX_RETRIES} (Fehler: {last_error})")
        prompt = (
            _build_prompt_single_unit(
                course, unit_stub, unit_index, len(units), topic, ects, audience,
                extra, provider, detail, language,
            )
            + (f"\n\nFEHLER im letzten Versuch: {last_error}\n"
               "Antworte NUR mit dem JSON-Objekt fuer diese eine Einheit." if attempt > 1 else "")
        )
        try:
            raw = _call_course_provider(provider, prompt, model, api_key, max_tokens=9000)
            data = extract_json(raw)
            generated_unit = _normalize_generated_unit(data, unit_stub)
            updated_units = [generated_unit if u.get("id") == unit_id else u for u in units]
            course["units"] = updated_units
            course["generationStatus"] = (
                "complete"
                if all(u.get("contentBlocks") for u in updated_units)
                else "partial"
            )
            course["detailLevel"] = detail
            course["language"] = language
            _sanitize_question_types(course)
            return course
        except (ValueError, RuntimeError) as e:
            last_error = str(e)[:180]

    raise RuntimeError(
        f"Einheit {unit_id} konnte nach {MAX_RETRIES} Versuchen nicht generiert werden.\n"
        f"Letzter Fehler: {last_error}"
    )


# ============================================================================
# HAUPTFUNKTION
# ============================================================================

MAX_RETRIES = 3

def generate(topic: str, provider: str, model: str | None, api_key: str | None) -> dict:
    """
    Generiert ein vollständiges input.json für das gegebene Topic.

    Prompt-Strategie je Provider:
      - groq   → build_prompt_full()  (12 Fragen, ausführliche Theorie, 8 192 Tokens)
      - ollama → build_prompt_lite()  (6 Fragen, kompakte Theorie, passt für llama3.2)

    Bei ungültigem JSON-Output wird bis zu MAX_RETRIES Mal wiederholt.
    """
    if provider == "groq" and not api_key and not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError(
            "Groq benötigt einen API-Key.\n"
            "Setze: export GROQ_API_KEY=gsk_...\n"
            "Kostenlos unter: https://console.groq.com"
        )
    if provider == "gemini" and not api_key and not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError(
            "Gemini benötigt einen API-Key.\n"
            "Setze GEMINI_API_KEY in deiner .env-Datei oder als Umgebungsvariable.\n"
            "Hinweis: .env.example ist nur eine Vorlage und wird nicht als Konfiguration verwendet.\n"
            "API-Key: https://aistudio.google.com/app/apikey"
        )

    # Wähle Prompt-Variante passend zur Modellgröße
    build_prompt = build_prompt_full if provider in ("groq", "gemini") else build_prompt_lite
    if provider == "ollama":
        print("  ℹ Ollama-Modus: kompakter Prompt (6 Fragen) – läuft auf llama3.2 in ~2-4 Min.")
        print("    Tipp: Verwende --provider groq für den vollen 12-Fragen-Kurs (schneller).")

    prompt = build_prompt(topic)
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        if attempt > 1:
            print(f"  → Versuch {attempt}/{MAX_RETRIES} (Fehler: {last_error})")
            prompt = (
                f"{build_prompt(topic)}\n\n"
                f"WICHTIG: Dein letzter Versuch war ungültig: {last_error}\n"
                f"Antworte ausschließlich mit dem JSON-Objekt. Kein Markdown, kein Text davor oder danach."
            )

        if provider == "groq":
            raw = call_groq(prompt, model or GROQ_DEFAULT_MODEL, api_key)
        elif provider == "gemini":
            raw = call_gemini(prompt, model or GEMINI_DEFAULT_MODEL, api_key, max_tokens=12000)
        else:
            raw = call_ollama(prompt, model or OLLAMA_DEFAULT_MODEL)

        print("  → Antwort empfangen, parse JSON...")
        try:
            data = extract_json(raw)
            validate_output(data)
            if attempt > 1:
                print(f"  → Erfolgreich nach {attempt} Versuchen.")
            return data
        except ValueError as e:
            last_error = str(e)[:120]

    raise RuntimeError(
        f"LLM hat nach {MAX_RETRIES} Versuchen kein valides JSON geliefert.\n"
        f"Letzter Fehler: {last_error}"
    )


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
  python generate_content.py "Geschichte" --num-units 5 --ects 3 --course-out courses/geschichte.json
  python generate_content.py "Pythagoras" --provider groq
  python generate_content.py "Newton" --provider ollama --model mistral
  python generate_content.py "Java" --provider gemini --model gemini-3.5-flash

Provider:
  ollama  Lokal (kostenlos, kein API-Key) – Install: https://ollama.com
  groq    Cloud  (kostenlos, API-Key nötig) – Key: https://console.groq.com
  gemini  Google Gemini API – Key: https://aistudio.google.com/app/apikey,
          dann GEMINI_API_KEY=... in .env setzen
        """,
    )
    parser.add_argument("topic", help="Lehrthema, z.B. 'Photosynthese'")
    parser.add_argument("--provider", choices=["ollama", "groq", "gemini", "cerebras"], default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--out", default="input.json",
                        help="Moodle input.json Ausgabedatei")
    # ── New multi-unit args ──────────────────────────────────────────────────
    parser.add_argument("--num-units", type=int, default=0,
                        help="Anzahl der Unterrichtseinheiten (0 = altes Moodle-Format)")
    parser.add_argument("--ects", default="",
                        help="ECTS-Punkte des Kurses (z.B. '3')")
    parser.add_argument("--audience", default="",
                        help="Zielgruppe/Niveau (z.B. 'Studierende im 1. Semester')")
    parser.add_argument("--extra", default="",
                        help="Zusatzwünsche des Lektors")
    parser.add_argument("--course-out", default="",
                        help="Pfad für das Course-Editor-JSON (units-Format)")
    parser.add_argument("--course-in", default="",
                        help="Bestehendes Course-Editor-JSON fuer Unit-Generierung")
    parser.add_argument("--plan-only", action="store_true",
                        help="Nur Kursstruktur/Preview erzeugen, keine Einheiten ausarbeiten")
    parser.add_argument("--generate-unit", default="",
                        help="Nur eine Einheit anhand ihrer ID generieren/regenerieren")
    parser.add_argument("--detail", choices=["compact", "normal", "detailed"], default="compact",
                        help="Detailgrad fuer generierte Inhalte (Standard: compact)")
    parser.add_argument("--language", choices=["de", "en"], default="de",
                        help="Ausgabesprache fuer Kursinhalte")

    args = parser.parse_args()

    groq_api_key = os.environ.get("GROQ_API_KEY")
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    cerebras_api_key = os.environ.get("CEREBRAS_API_KEY")
    provider = args.provider or ("groq" if groq_api_key else "gemini" if gemini_api_key else "ollama")
    if provider == "gemini":
        api_key = gemini_api_key
    elif provider == "cerebras":
        api_key = cerebras_api_key
    else:
        api_key = groq_api_key
    default_model = (
        GROQ_DEFAULT_MODEL if provider == "groq"
        else GEMINI_DEFAULT_MODEL if provider == "gemini"
        else CEREBRAS_DEFAULT_MODEL if provider == "cerebras"
        else OLLAMA_DEFAULT_MODEL
    )

    print("=" * 60)
    print("Moodle pAIpline – Content Generator")
    print("=" * 60)
    print(f"  Thema     : {args.topic}")
    print(f"  Provider  : {provider}")
    print(f"  Model     : {args.model or default_model}")
    if args.num_units:
        print(f"  Einheiten : {args.num_units}")
    if args.ects:
        print(f"  ECTS      : {args.ects}")
    if args.audience:
        print(f"  Zielgruppe: {args.audience}")
    print(f"  Output    : {args.out}")
    if args.course_out:
        print(f"  Course-Out: {args.course_out}")
    if args.plan_only:
        print("  Modus     : Course Plan Preview")
    if args.generate_unit:
        print(f"  Einheit   : {args.generate_unit}")
    print(f"  Detail    : {args.detail}")
    print(f"  Sprache   : {args.language}")
    print()

    try:
        # ── Mode A: Course Plan Preview only ────────────────────────────────
        if args.plan_only:
            if args.num_units <= 0:
                raise RuntimeError("--plan-only benötigt --num-units.")
            print("  → Generiere Course Plan Preview …")
            course_data = generate_course_plan(
                topic=args.topic,
                num_units=args.num_units,
                ects=args.ects,
                audience=args.audience,
                extra=args.extra,
                provider=provider,
                model=args.model,
                api_key=api_key,
                detail=args.detail,
                language=args.language,
            )
            out_path = args.course_out or args.out
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(course_data, f, ensure_ascii=False, indent=2)
            print(f"\n✓ Course Plan gespeichert: {out_path}")

        # ── Mode B: Generate/regenerate one unit ────────────────────────────
        elif args.generate_unit:
            course_path = args.course_in or args.course_out
            if not course_path:
                raise RuntimeError("--generate-unit benötigt --course-in oder --course-out.")
            print(f"  → Generiere Einheit {args.generate_unit} …")
            with open(course_path, "r", encoding="utf-8") as f:
                course_data = json.load(f)
            course_data = generate_unit_for_course(
                course=course_data,
                unit_id=args.generate_unit,
                provider=provider,
                model=args.model,
                api_key=api_key,
                extra=args.extra,
                detail=args.detail,
                language=args.language,
            )
            out_path = args.course_out or course_path
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(course_data, f, ensure_ascii=False, indent=2)
            print(f"\n✓ Einheit gespeichert: {out_path}")

        # ── Mode C: Multi-unit Course Editor JSON ────────────────────────────
        elif args.num_units > 0:
            print(f"  → Generiere {args.num_units} Unterrichtseinheiten …")
            course_data = generate_course_units(
                topic=args.topic,
                num_units=args.num_units,
                ects=args.ects,
                audience=args.audience,
                extra=args.extra,
                provider=provider,
                model=args.model,
                api_key=api_key,
                detail=args.detail,
                language=args.language,
            )

            # Save full Course Editor JSON
            if args.course_out:
                os.makedirs(os.path.dirname(args.course_out) or ".", exist_ok=True)
                with open(args.course_out, "w", encoding="utf-8") as f:
                    json.dump(course_data, f, ensure_ascii=False, indent=2)
                print(f"\n✓ Course-Editor JSON gespeichert: {args.course_out}")

            # Also save a simplified Moodle input.json (from first unit)
            moodle_data = _course_to_moodle_input(course_data, args.topic)
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(moodle_data, f, ensure_ascii=False, indent=2)
            print(f"✓ Moodle input.json gespeichert: {args.out}")

        # ── Mode B: Classic single-activity Moodle format ────────────────────
        else:
            data = generate(args.topic, provider, args.model, api_key)
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"\n✓ {args.out} erfolgreich erzeugt.")
            print("\nNächster Schritt: python build_v1.py")

    except RuntimeError as e:
        print(f"\n✗ Fehler: {e}", file=sys.stderr)
        sys.exit(1)


def _course_to_moodle_input(course: dict, topic: str) -> dict:
    """Convert a multi-unit Course Editor JSON to the Moodle input.json format
    (used by build_v1.py for MBZ export). Uses the first unit's content."""
    units = course.get("units", [])
    first = units[0] if units else {}

    # Collect all questions from all units for the quiz
    all_questions = []
    for u_idx, unit in enumerate(units):
        for q_idx, q in enumerate(unit.get("questions", []), 1):
            answers = [
                {"text_html": f"<p>{a.get('text', '')}</p>",
                 "fraction": 1.0 if a.get("isCorrect") else 0.0}
                for a in q.get("answers", [])
            ]
            all_questions.append({
                "qbe_id": u_idx * 100 + q_idx,
                "question_id": u_idx * 100 + q_idx,
                "name": q.get("question", "")[:60],
                "questiontext_html": f"<p>{q.get('question', '')}</p>",
                "answers": answers,
            })

    # Build theory HTML from all units
    theory_html = "".join(
        f"<h2>{u.get('title', '')}</h2><p>{u.get('theoryContent', '')}</p>"
        for u in units
    )

    shortname = re.sub(r'[^a-z0-9_]', '', topic.lower().replace(' ', '_'))[:20]

    return {
        "course_metadata": {
            "fullname": course.get("title", topic),
            "shortname": shortname,
            "summary": f"<p>{course.get('description', '')}</p>",
            "lang": "de",
            "visible": True,
        },
        "sections": {
            "section_6": {"name": "Einführung", "summary": "<p>Kursübersicht.</p>"},
            "section_7": {"name": "Theorie", "summary": "<p>Alle Lerneinheiten.</p>"},
            "section_8": {"name": "Übungen & Quiz", "summary": "<p>Abschlusstest.</p>"},
        },
        "activities": {
            "page_3": {
                "type": "page",
                "name": f"Theorie: {topic}",
                "content_html": theory_html or "<p>Kein Inhalt.</p>",
            },
            "assign_4": {
                "type": "assign",
                "name": f"Aufgabe: {topic}",
                "intro_html": f"<p>Bearbeite die Aufgaben zum Kurs <strong>{topic}</strong>.</p>",
            },
            "quiz_5": {
                "type": "quiz",
                "name": f"Quiz: {topic}",
                "questions": all_questions[:12],  # Moodle template supports up to 12
            },
        },
    }


if __name__ == "__main__":
    main()

