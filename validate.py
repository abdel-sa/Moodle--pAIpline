#!/usr/bin/env python3
"""
Moodle pAIpline – Validierung & Status-Check

Prüft alles vor dem Build:
  - Projektdateien vorhanden
  - input.json gültig und vollständig
  - Template-Backup vorhanden und korrekt strukturiert
  - Python-Abhängigkeiten installiert
  - Ollama erreichbar (optional)

Verwendung:
  python validate.py
"""

import os
import sys
import json
import urllib.request
import urllib.error
import py_compile

# Windows-Terminals unterstützen manchmal kein UTF-8 standardmäßig
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ============================================================================
# HILFSFUNKTIONEN
# ============================================================================

_ok = 0
_warn = 0
_fail = 0


def ok(msg):
    global _ok
    _ok += 1
    print(f"  ✓  {msg}")


def warn(msg):
    global _warn
    _warn += 1
    print(f"  ⚠  {msg}")


def fail(msg):
    global _fail
    _fail += 1
    print(f"  ✗  {msg}")


def section(title):
    print(f"\n[{title}]")

# ============================================================================
# CHECKS
# ============================================================================

def check_project_files():
    section("Projektdateien")
    required = ["build_v1.py", "input.json", "generate_content.py",
                "analyze_template.py", "requirements.txt"]
    optional = ["input_v1_example.json", "CHANGELOG.md"]

    for fname in required:
        if os.path.isfile(fname):
            ok(fname)
        else:
            fail(f"{fname}  ← Pflichtdatei fehlt!")

    for fname in optional:
        if os.path.isfile(fname):
            ok(f"{fname}  (optional)")
        else:
            warn(f"{fname}  (optional, fehlt)")


def check_template():
    section("Template-Backup  (template_backup/)")
    if not os.path.isdir("template_backup"):
        fail("template_backup/  nicht gefunden – Moodle-Backup hier entpacken")
        return

    ok("template_backup/  vorhanden")

    required_items = [
        ("moodle_backup.xml", os.path.isfile),
        ("activities",        os.path.isdir),
        ("sections",          os.path.isdir),
        ("course",            os.path.isdir),
    ]
    for name, check_fn in required_items:
        path = os.path.join("template_backup", name)
        if check_fn(path):
            ok(f"  {name}")
        else:
            fail(f"  {name}  fehlt in template_backup/")

    # Aktivitäten-Ordner zeigen
    acts_dir = os.path.join("template_backup", "activities")
    if os.path.isdir(acts_dir):
        activities = sorted(os.listdir(acts_dir))
        for act in activities:
            act_path = os.path.join(acts_dir, act)
            if os.path.isdir(act_path):
                xmls = [f for f in os.listdir(act_path) if f.endswith(".xml")]
                ok(f"  activities/{act}/  ({len(xmls)} XML-Dateien)")


def check_input_json():
    section("input.json  Struktur")
    if not os.path.isfile("input.json"):
        fail("input.json  nicht gefunden")
        return

    try:
        with open("input.json", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        fail(f"JSON-Fehler: {e}")
        return

    ok("input.json  ist gültiges JSON")

    # course_metadata
    meta = data.get("course_metadata", {})
    if meta:
        ok(f"course_metadata  (fullname: \"{meta.get('fullname', '?')}\")")
    else:
        warn("course_metadata  fehlt (Kurs bekommt Template-Namen)")

    # activities
    activities = data.get("activities", {})
    if not activities:
        fail("'activities'  fehlt oder leer")
        return

    ok(f"{len(activities)} Activit{'y' if len(activities) == 1 else 'ies'}  definiert")

    allowed_types = {"page", "assign", "quiz"}
    for key, act in activities.items():
        atype = act.get("type")
        if not atype:
            fail(f"  '{key}'  hat kein 'type'-Feld  (erlaubt: page, assign, quiz)")
        elif atype not in allowed_types:
            fail(f"  '{key}'  unbekannter type='{atype}'")
        else:
            # Inhalt vorhanden?
            has_content = bool(
                act.get("content_html") or act.get("intro_html") or act.get("questions")
            )
            if has_content:
                ok(f"  '{key}'  type={atype}  ✓ hat Inhalt")
            else:
                warn(f"  '{key}'  type={atype}  ⚠ kein Inhalt definiert")

        if atype == "quiz":
            questions = act.get("questions", [])
            if not questions:
                warn(f"  '{key}'  Quiz hat keine Fragen")
            else:
                ok(f"  '{key}'  {len(questions)} Frage(n)")


def check_syntax():
    section("Python-Syntax")
    scripts = ["build_v1.py", "generate_content.py", "analyze_template.py", "validate.py"]
    for script in scripts:
        if not os.path.isfile(script):
            continue
        try:
            py_compile.compile(script, doraise=True)
            ok(script)
        except py_compile.PyCompileError as e:
            fail(f"{script}  Syntax-Fehler: {e}")


def check_dependencies():
    section("Python-Abhängigkeiten")
    deps = {"lxml": "pip install lxml"}
    for dep, install_hint in deps.items():
        try:
            __import__(dep)
            ok(dep)
        except ImportError:
            fail(f"{dep}  fehlt  →  {install_hint}")


def check_ollama():
    section("Ollama  (optional, für generate_content.py)")
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
        models = [m["name"] for m in data.get("models", [])]
        if models:
            ok(f"Ollama läuft  –  verfügbare Modelle: {', '.join(models[:5])}")
        else:
            warn("Ollama läuft, aber keine Modelle geladen  →  ollama pull llama3.2")
    except Exception:
        warn("Ollama nicht erreichbar  (nur nötig für generate_content.py ohne Groq)")


def check_groq():
    section("Groq API Key  (optional, Alternative zu Ollama)")
    api_key = os.environ.get("GROQ_API_KEY")
    if api_key:
        ok(f"GROQ_API_KEY  gesetzt  (endet auf ...{api_key[-6:]})")
    else:
        warn("GROQ_API_KEY  nicht gesetzt  –  Ollama wird als Fallback genutzt")

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "=" * 60)
    print("Moodle pAIpline – Validierung")
    print("=" * 60)

    check_project_files()
    check_template()
    check_input_json()
    check_syntax()
    check_dependencies()
    check_ollama()
    check_groq()

    print("\n" + "=" * 60)
    print(f"  ✓ OK     : {_ok}")
    if _warn:
        print(f"  ⚠ Warnungen : {_warn}")
    if _fail:
        print(f"  ✗ Fehler    : {_fail}")
    print("=" * 60)

    if _fail == 0:
        print("\nAlles bereit! Nächster Schritt:")
        print("  python generate_content.py 'Dein Thema'")
        print("  python build_v1.py")
    else:
        print("\nBitte die Fehler oben beheben, dann erneut prüfen.")

    print()
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
