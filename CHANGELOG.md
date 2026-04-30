# Changelog – Moodle pAIpline

---

## [Unreleased] – 2026-04-30

### New Features

**Section-Titel und Summary patchen** (`build_v1.py`, `generate_content.py`)
- Neue Funktion `patch_sections()` schreibt `name` und `summary` in `sections/section_X/section.xml`.
- Ersetzt den Moodle-Platzhalter `$@NULL@$` durch echten Inhalt — ohne Sections-Patch zeigt Moodle immer "Abschnitt 1", "Abschnitt 2" etc.
- `input.json` Schema erweitert um `"sections": { "section_6": { "name": "...", "summary": "..." }, ... }`.
- LLM-Prompt in `generate_content.py` generiert jetzt ebenfalls Section-Namen und Beschreibungen.

---

## [Unreleased] – 2026-04-29

### Bug Fixes

**Double-Escaping in XML-Patching** (`build_v1.py`, `build.py`)
- lxml escapiert XML-Sonderzeichen automatisch wenn man `element.text = value` setzt.
- Die alte Funktion `escape_html_for_xml()` hat `<` → `&lt;` gemacht, dann hat lxml das `&` nochmal zu `&amp;` escaped: `&amp;lt;`.
- Ergebnis: Jede generierte `.mbz` hatte rohe Entitäten statt HTML im Moodle-Kurs.
- Fix: `escape_html_for_xml()` vollständig entfernt. `element.text = raw_html` direkt setzen.

**`course_metadata` wurde ignoriert** (`build_v1.py`)
- `fullname` und `shortname` aus `input.json` wurden zwar geladen, aber nie in `course/course.xml` geschrieben.
- Jeder generierte Kurs behielt den Namen des Templates.
- Fix: Neue Funktion `patch_course_metadata()` schreibt alle Felder in `course/course.xml`.

**Fragile `type`-Erkennung per String-Split** (`build_v1.py`)
- Fehlende `type`-Felder wurden per `activity_key.split("_")[0]` geraten (`"page_3"` → `"page"`).
- Ein Key wie `"new_page_1"` wäre als Typ `"new"` erkannt worden.
- Fix: `type` ist jetzt ein Pflichtfeld. Fehlt es, wirft der Build einen `ValidationError`.

### Refactoring

**`build.py` (v0) gelöscht**
- `build.py` und `build_v1.py` teilten ~80% identischen Code (sechs Funktionen 1:1 dupliziert).
- `build_v1.py` ist in allen Punkten besser: dynamische Activity-Keys, Validierung, Logging.
- Einziger Build-Entrypoint ist jetzt `build_v1.py`.

### New Features

**`course_metadata` vollständig** (`build_v1.py`)

Alle Felder werden jetzt in `course/course.xml` geschrieben:

| Feld | Typ | Beschreibung |
|---|---|---|
| `fullname` | `str` | Voller Kursname |
| `shortname` | `str` | Kurzkürzel (keine Leerzeichen) |
| `summary` | `str` | HTML-Kursbeschreibung (auf der Kursseite sichtbar) |
| `lang` | `str` | Sprachcode z.B. `"de"`, `"en"` |
| `visible` | `bool` | Kurs sichtbar (`true`) oder versteckt (`false`) |
| `startdate` | `str` | ISO-Datum `"YYYY-MM-DD"` → wird zu Unix-Timestamp konvertiert |
| `enddate` | `str` | ISO-Datum `"YYYY-MM-DD"` → Unix-Timestamp (`0` = kein Ende) |

Beispiel `input.json`:
```json
"course_metadata": {
  "fullname": "Brüche – Einführung",
  "shortname": "bruche_intro",
  "summary": "<p>Einführungskurs für die 5. Klasse.</p>",
  "lang": "de",
  "visible": true,
  "startdate": "2026-05-01",
  "enddate": "2026-07-31"
}
```

---

**`generate_content.py` – echte LLM-Integration** (`generate_content.py`)

Ersetzt den toten statischen Stub durch einen funktionierenden LLM-Content-Generator.
Topic rein → fertig strukturiertes `input.json` raus, direkt für `build_v1.py` nutzbar.

Unterstützte Provider (beide kostenlos):

| Provider | Typ | API-Key | Setup |
|---|---|---|---|
| **Ollama** | lokal | keiner | `ollama pull llama3.2` |
| **Groq** | Cloud | `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) |

Auto-Auswahl: Groq wenn `GROQ_API_KEY` gesetzt, sonst Ollama.

```bash
python generate_content.py "Photosynthese"
python generate_content.py "Pythagoras" --provider groq --out kurs.json
```

**`validate.py` + `verify.py` zusammengeführt**

Beide Skripte machten Datei-Checks mit überlappender Logik. Zusammengeführt zu einem
einzigen `validate.py` das alles prüft: Projektdateien, Template-Backup, input.json
Struktur, Python-Syntax, Abhängigkeiten, Ollama-Status, Groq-Key-Präsenz.
`verify.py` wurde gelöscht.

---

## Geplant (nächste Schritte)

- **Section-Titel patchen**: `sections/section_X/section.xml` mit Namen aus `input.json`
- **Batch-Mode**: CSV mit Topics → mehrere `.mbz`-Dateien auf einmal
- **CLI mit argparse für build_v1.py**: `python build_v1.py --input mein_kurs.json --template ./backup`
- **Docs aufräumen**: 10+ Markdown-Dateien auf ein gutes README reduzieren
