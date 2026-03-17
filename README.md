# Moodle pAIpline

## Übersicht
Dieses Projekt ist eine Pipeline zur Verarbeitung und Verwaltung von Fragensammlungen im XML-Format für Moodle. Die Pipeline automatisiert den Prozess des Importierens, Validierens und Verarbeitens von Quiz-Daten, um diese in Moodle-kompatiblem Format bereitzustellen.

## Projektstruktur

### XML Fragedateien
Die Fragedateien sind im standardisierten Moodle-XML-Format organisiert und nach Themen und Jahren strukturiert:

### Python Skripte

- **pipeline.py** - Hauptprozess für die Datenverarbeitung und Pipeline-Ausführung
- **validate.py** - XML-Validierung und Strukturprüfung
- **verify.py** - Verifikation der Datenintegrität und Konsistenzprüfung

### Konfiguration
- **requirements.txt** - Python-Abhängigkeiten und benötigte Pakete
- **plan_XXXX.json** - Konfigurationsdateien für verschiedene Szenarien

## Installation

1. Abhängigkeiten installieren:
```bash
pip install -r requirements.txt
```

## Verwendung

### Workflow-Übersicht
Die Pipeline läuft in zwei Schritten ab: Planung und Generierung.

### Schritt 1: Planung erstellen

Erstellen Sie einen Plan aus einer Textdatei:

```bash
python pipeline.py plan \
  --chapter <EINGABEDATEI.txt> \
  --title "<TITEL>" \
  --base-category "<KATEGORIE>" \
  --out <AUSGABEPLAN.json> \
  --model <MODELL>
```

**Parameter:**
- `<EINGABEDATEI.txt>` - Textdatei mit den Inhalten
- `<TITEL>` - Titel für die Fragensammlung
- `<KATEGORIE>` - Basis-Kategoriepfad (z.B. "Thema/Jahr")
- `<AUSGABEPLAN.json>` - Name der generierten Plan-Datei
- `<MODELL>` - AI-Modell für die Verarbeitung (z.B. mistral)

### Schritt 2: XML-Datei generieren

Generieren Sie die XML-Datei basierend auf dem Plan:

```bash
python pipeline.py generate \
  --plan <PLAN.json> \
  --out <AUSGABEDATEI.xml> \
  --model <MODELL>
```

**Parameter:**
- `<PLAN.json>` - Die im ersten Schritt erstellte Plan-Datei
- `<AUSGABEDATEI.xml>` - Name der generierten XML-Datei
- `<MODELL>` - AI-Modell für die Generierung

### Zusätzliche Validierungen

Zum Validieren von Dateien:
```bash
python validate.py
```

Zur Verifikation der Daten:
```bash
python verify.py
```

## Dateiformat

Die XML-Dateien folgen dem Moodle-Standard für Quiz-Importe und enthalten:
- Fragen mit verschiedenen Fragetypen
- Antwortalternativen mit Bewertungen
- Kategorisierung und Tags
- Feedback für jede Antwort
