# Changelog – Moodle pAIpline

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

## Geplant (nächste Schritte)

- **LLM-Integration**: Topic-String rein → fertiges `input.json` raus (Claude API)
- **Section-Titel patchen**: `sections/section_X/section.xml` mit Namen aus `input.json`
- **Batch-Mode**: CSV mit Topics → mehrere `.mbz`-Dateien auf einmal
- **CLI mit argparse**: `python build_v1.py --input mein_kurs.json --template ./backup`
- **`validate.py` / `verify.py` zusammenführen**: beide machen Datei-Checks, einer reicht
