# Moodle pAIpline

Generiert importierbare Moodle-Kurs-Backups (`.mbz`) aus einem JSON-Input.  
Entweder manuell befüllt oder automatisch per LLM aus einem Lehrthema generiert.

---

## Schnellstart

```bash
pip install lxml

# Option A – LLM generiert input.json automatisch
python generate_content.py "Photosynthese"   # schreibt input.json
python build_v1.py                           # erzeugt generated_course.mbz

# Option B – input.json manuell befüllen
# input.json editieren, dann:
python build_v1.py
```

Danach in Moodle: **Kurs → Course administration → Restore → generated_course.mbz**

---

## Voraussetzungen

- Python 3.8+
- `pip install lxml`
- Für `generate_content.py` zusätzlich einen der folgenden LLM-Provider:

| Provider | Kosten | Setup |
|---|---|---|
| **Ollama** (lokal) | kostenlos | [ollama.com](https://ollama.com) installieren, dann `ollama pull llama3.2` |
| **Groq** (Cloud) | kostenloser Tier | API-Key unter [console.groq.com](https://console.groq.com), dann `export GROQ_API_KEY=gsk_...` |

Auto-Auswahl: Groq wenn `GROQ_API_KEY` gesetzt, sonst Ollama.

---

## Projektstruktur

```
moodle_pipeline_v0/
├── build_v1.py           # Haupt-Build-Script: Template + input.json → .mbz
├── generate_content.py   # LLM-Generator: Topic → input.json
├── analyze_template.py   # Zeigt Activity-IDs des Templates
├── validate.py           # Pre-Build-Check (Dateien, JSON, Dependencies)
├── input.json            # Kursinhalte (editieren oder per LLM generieren)
├── input_v1_example.json # Vollständiges Beispiel (3 Quiz-Fragen)
├── template_backup/      # Entpacktes Moodle-Backup (als Template)
└── CHANGELOG.md          # Alle Änderungen und neuen Features
```

---

## Template vorbereiten

Das Template ist ein normales Moodle-Backup, das als Vorlage dient.

1. In Moodle einen Kurs mit den gewünschten Activities anlegen (Page, Assign, Quiz)
2. **Kurs → Course administration → Backup** → `.mbz` herunterladen
3. `.mbz` in `template_backup/` entpacken:
   ```bash
   tar -xf backup.mbz -C template_backup/
   ```
4. Activity-IDs prüfen:
   ```bash
   python analyze_template.py
   ```
   Gibt aus: `page_3`, `assign_4`, `quiz_5` etc. — diese Keys in `input.json` verwenden.

---

## input.json – Schema

```json
{
  "course_metadata": {
    "fullname":  "Vollständiger Kursname",
    "shortname": "kurz_name",
    "summary":   "<p>HTML-Kursbeschreibung</p>",
    "lang":      "de",
    "visible":   true,
    "startdate": "2026-05-01",
    "enddate":   "2026-07-31"
  },
  "activities": {
    "page_3": {
      "type": "page",
      "name": "Seitentitel",
      "content_html": "<h1>Überschrift</h1><p>Inhalt...</p>"
    },
    "assign_4": {
      "type": "assign",
      "name": "Aufgabentitel",
      "intro_html": "<p>Aufgabenbeschreibung</p>"
    },
    "quiz_5": {
      "type": "quiz",
      "name": "Quiz-Name",
      "questions": [
        {
          "qbe_id": 1,
          "question_id": 1,
          "name": "Frage 1",
          "questiontext_html": "<p>Fragetext?</p>",
          "answers": [
            { "text_html": "<p>Richtig</p>", "fraction": 1.0 },
            { "text_html": "<p>Falsch</p>",  "fraction": 0.0 }
          ]
        }
      ]
    }
  }
}
```

**Wichtig:**
- `type` ist Pflichtfeld pro Activity (`page`, `assign`, `quiz`)
- `qbe_id` und `question_id` müssen mit den IDs im Template übereinstimmen (→ `analyze_template.py`)
- `fraction`: `1.0` = richtig, `0.5` = halb richtig, `0.0` = falsch
- HTML in Feldern wird von `build_v1.py` automatisch korrekt escapiert

---

## Scripts

### `build_v1.py`
Haupt-Pipeline. Kopiert `template_backup/`, patcht alle XMLs, erzeugt `generated_course.mbz`.
```bash
python build_v1.py
```

### `generate_content.py`
Ruft Ollama oder Groq auf und erzeugt `input.json` aus einem Lehrthema.
```bash
python generate_content.py "Photosynthese"
python generate_content.py "Newton" --provider groq --model llama-3.3-70b-versatile
python generate_content.py "Brüche" --out mathe_bruche.json
```

### `analyze_template.py`
Liest `template_backup/moodle_backup.xml` und zeigt Activity-Keys und Question-Bank-IDs.
```bash
python analyze_template.py
```

### `validate.py`
Prüft alles vor dem Build: Dateien, Template-Struktur, input.json, Dependencies, Ollama/Groq.
```bash
python validate.py
```

---

## Fehlersuche

**`Template-Dir nicht gefunden`**  
→ `template_backup/` existiert nicht oder ist leer. Backup entpacken (siehe oben).

**`question_bank_entry mit id=X nicht gefunden`**  
→ `qbe_id` in `input.json` stimmt nicht mit dem Template überein. `analyze_template.py` zeigen lassen.

**`Activity 'X' hat kein 'type'-Feld`**  
→ Jede Activity in `input.json` braucht `"type": "page"` / `"assign"` / `"quiz"`.

**Ollama nicht erreichbar**  
→ `ollama serve` starten oder Groq mit `GROQ_API_KEY` verwenden.

**Moodle akzeptiert `.mbz` nicht**  
→ War das Original-Template in Moodle importierbar? Template-Backup prüfen.
