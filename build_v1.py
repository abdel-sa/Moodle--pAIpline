#!/usr/bin/env python3
"""
Moodle pAIpline v1: Multi-Question, Multi-Activity, mit Validierung & Logging
- Unterstützt mehrere Question Bank Entries (qbe_id)
- Validiert Dateien & XML-Struktur vor dem Patchen
- Strukturiertes Logging der Patch-Operationen
"""

import json
import shutil
import os
import zipfile
import sys
from pathlib import Path
from lxml import etree

# ============================================================================
# KONFIGURATION
# ============================================================================

TEMPLATE_DIR = "template_backup"
OUTPUT_DIR = "out_build"
OUTPUT_MBZ = "generated_course.mbz"
INPUT_FILE = "input.json"

# Logging
DEBUG = True

def log(msg, level="INFO"):
    """Logging mit Timestamps"""
    prefix = {
        "INFO": "ℹ️ ",
        "OK": "✓ ",
        "WARN": "⚠️ ",
        "ERROR": "❌ "
    }
    print(f"{prefix.get(level, '')} {msg}")

# ============================================================================
# VALIDIERUNG
# ============================================================================

class ValidationError(Exception):
    pass

def validate_template_structure():
    """Prüft, ob Template-Dir existiert und die Basis-Struktur stimmt"""
    log(f"Validiere Template in: {TEMPLATE_DIR}")
    
    if not os.path.isdir(TEMPLATE_DIR):
        raise ValidationError(f"Template-Dir nicht gefunden: {TEMPLATE_DIR}")
    
    required_files = [
        "moodle_backup.xml",
        "activities",
        "sections"
    ]
    
    for item in required_files:
        path = os.path.join(TEMPLATE_DIR, item)
        if not os.path.exists(path):
            raise ValidationError(f"Template-Datei fehlt: {item}")
    
    log("Template-Struktur OK", "OK")

def validate_activity_in_template(output_dir, activity_key, activity_type):
    """
    Prüft, ob Activity im Output-Dir vorhanden ist.
    activity_key: "page_3", "quiz_5" etc.
    activity_type: "page", "assign", "quiz"
    """
    activity_path = os.path.join(output_dir, "activities", activity_key)
    
    if not os.path.isdir(activity_path):
        log(f"Activity nicht gefunden: {activity_key} ({activity_type})", "WARN")
        return False
    
    log(f"Activity gefunden: {activity_key}", "OK")
    return True

def validate_xml_element(tree, xpath, element_name):
    """Prüft, ob ein XML-Element existiert"""
    root = tree.getroot()
    elem = root.find(xpath)
    if elem is None:
        raise ValidationError(f"XML-Element nicht gefunden: {element_name} (XPath: {xpath})")
    return elem

# ============================================================================
# XML-HELPER
# ============================================================================

def parse_xml_file(filepath):
    """Parst XML-Datei"""
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(filepath, parser)
    return tree

def write_xml_file(filepath, tree):
    """Schreibt XML zurück"""
    tree.write(filepath, encoding="utf-8", xml_declaration=True, standalone=True)

# ============================================================================
# PATCH-FUNKTIONEN (V1)
# ============================================================================

def patch_page_activity(page_xml_path, page_data):
    """
    Patcht Page Activity.
    page_data: {"name": "...", "content_html": "..."}
    """
    log(f"Patche PAGE: {page_xml_path}")
    
    if not os.path.exists(page_xml_path):
        raise ValidationError(f"page.xml nicht gefunden: {page_xml_path}")
    
    tree = parse_xml_file(page_xml_path)
    root = tree.getroot()
    
    # Update <name>
    if "name" in page_data:
        name_elem = root.find(".//name")
        if name_elem is not None:
            name_elem.text = page_data["name"]
            log(f"  → <name> = {page_data['name']}", "OK")
    
    # Update <content>
    if "content_html" in page_data:
        content_elem = root.find(".//content")
        if content_elem is None:
            raise ValidationError(f"<content> nicht gefunden in {page_xml_path}")
        content_elem.text = page_data["content_html"]
        log(f"  → <content> updated ({len(page_data['content_html'])} chars)", "OK")
    
    write_xml_file(page_xml_path, tree)

def patch_assign_activity(assign_xml_path, assign_data):
    """Patcht Assign Activity"""
    log(f"Patche ASSIGN: {assign_xml_path}")
    
    if not os.path.exists(assign_xml_path):
        raise ValidationError(f"assign.xml nicht gefunden: {assign_xml_path}")
    
    tree = parse_xml_file(assign_xml_path)
    root = tree.getroot()
    
    # Update <name>
    if "name" in assign_data:
        name_elem = root.find(".//name")
        if name_elem is not None:
            name_elem.text = assign_data["name"]
            log(f"  → <name> = {assign_data['name']}", "OK")
    
    # Update <intro>
    if "intro_html" in assign_data:
        intro_elem = root.find(".//intro")
        if intro_elem is None:
            raise ValidationError(f"<intro> nicht gefunden in {assign_xml_path}")
        intro_elem.text = assign_data["intro_html"]
        log(f"  → <intro> updated ({len(assign_data['intro_html'])} chars)", "OK")
    
    write_xml_file(assign_xml_path, tree)

def patch_quiz_questions(questions_xml_path, questions_data):
    """
    Patcht Quiz-Fragen (v1: mehrere qbe_id möglich).
    questions_data: [
        { "qbe_id": 1, "question_id": 1, "name": "...", "questiontext_html": "...", "answers": [...] },
        { "qbe_id": 2, "question_id": 2, "name": "...", ... },
        ...
    ]
    """
    log(f"Patche QUIZ QUESTIONS: {questions_xml_path}")
    log(f"  → {len(questions_data)} Frage(n) zu patchen")
    
    if not os.path.exists(questions_xml_path):
        raise ValidationError(f"questions.xml nicht gefunden: {questions_xml_path}")
    
    tree = parse_xml_file(questions_xml_path)
    root = tree.getroot()
    
    for q_data in questions_data:
        qbe_id = str(q_data.get("qbe_id", "1"))
        question_id = str(q_data.get("question_id", "1"))
        q_name = q_data.get("name", "Untitled Question")
        q_text = q_data.get("questiontext_html", "")
        answers = q_data.get("answers", [])
        
        log(f"  Frage: qbe_id={qbe_id}, question_id={question_id}")
        
        # Finde <question_bank_entry id=qbe_id>
        qbe = root.find(f".//question_bank_entry[@id='{qbe_id}']")
        if qbe is None:
            raise ValidationError(f"question_bank_entry mit id={qbe_id} nicht gefunden")
        
        # Finde <question id=question_id> darin
        q = qbe.find(f".//question[@id='{question_id}']")
        if q is None:
            raise ValidationError(f"question mit id={question_id} in qbe={qbe_id} nicht gefunden")
        
        # Update <name>
        name_elem = q.find("name")
        if name_elem is not None:
            name_elem.text = q_name
        
        # Update <questiontext>
        qt_elem = q.find("questiontext")
        if qt_elem is not None:
            qt_elem.text = q_text
        
        # Ersetze <answers>
        answers_elem = q.find("answers")
        if answers_elem is not None:
            # Lösche alte Answers
            for old_answer in answers_elem.findall("answer"):
                answers_elem.remove(old_answer)
            
            # Füge neue ein
            for idx, answer_data in enumerate(answers, start=1):
                answer_text = answer_data.get("text_html", "")
                fraction = answer_data.get("fraction", 0.0)
                
                answer_elem = etree.SubElement(answers_elem, "answer")
                answer_elem.set("id", str(idx))
                
                text_elem = etree.SubElement(answer_elem, "text")
                text_elem.text = answer_text
                
                fraction_elem = etree.SubElement(answer_elem, "fraction")
                fraction_elem.text = str(fraction)
            
            log(f"    → {len(answers)} Antwort(en) aktualisiert", "OK")
    
    write_xml_file(questions_xml_path, tree)

# ============================================================================
# HAUPTLOGIK (V1)
# ============================================================================

def load_input(input_file):
    """Lädt input.json mit Validierung"""
    if not os.path.exists(input_file):
        raise ValidationError(f"input.json nicht gefunden: {input_file}")
    
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    log(f"input.json geladen", "OK")
    return data

def copy_template(template_dir, output_dir):
    """Kopiert Template in Output-Dir"""
    if os.path.exists(output_dir):
        log(f"Lösche alten {output_dir}")
        shutil.rmtree(output_dir)
    
    log(f"Kopiere {template_dir} → {output_dir}")
    shutil.copytree(template_dir, output_dir)
    log(f"Template kopiert", "OK")

def patch_activities_v1(output_dir, input_data):
    """
    V1: Unterstützt mehrere Activities und flexible Keys.
    Patcht nur die Activities, die in input.json definiert sind.
    """
    activities = input_data.get("activities", {})
    
    if not activities:
        log("Keine Activities in input.json definiert", "WARN")
        return
    
    for activity_key, activity_data in activities.items():
        activity_type = activity_data.get("type", None)
        
        # Versuche zu erraten, ob type fehlt
        if not activity_type:
            if "_" in activity_key:
                activity_type = activity_key.split("_")[0]  # "page_3" → "page"
        
        log(f"\nPatche Activity: {activity_key} (Typ: {activity_type})")
        
        # Prüfe, ob Activity existiert
        if not validate_activity_in_template(output_dir, activity_key, activity_type):
            log(f"SKIPPED: {activity_key}", "WARN")
            continue
        
        try:
            if activity_type == "page":
                page_xml = os.path.join(output_dir, "activities", activity_key, "page.xml")
                patch_page_activity(page_xml, activity_data)
            
            elif activity_type == "assign":
                assign_xml = os.path.join(output_dir, "activities", activity_key, "assign.xml")
                patch_assign_activity(assign_xml, activity_data)
            
            elif activity_type == "quiz":
                # Versuche zuerst: questions.xml in activities/quiz_X/
                questions_xml = os.path.join(output_dir, "activities", activity_key, "questions.xml")
                # Fallback: questions.xml in Output-Root
                if not os.path.exists(questions_xml):
                    questions_xml = os.path.join(output_dir, "questions.xml")
                
                questions = activity_data.get("questions", [])
                if questions:
                    patch_quiz_questions(questions_xml, questions)
                else:
                    log(f"Keine Fragen definiert für {activity_key}", "WARN")
            
            else:
                log(f"Unbekannter Activity-Typ: {activity_type}", "WARN")
        
        except Exception as e:
            log(f"FEHLER beim Patchen von {activity_key}: {e}", "ERROR")
            raise

def create_mbz(output_dir, mbz_filename):
    """Packt output_dir in .mbz"""
    log(f"Erstelle .mbz-Datei: {mbz_filename}")
    
    if os.path.exists(mbz_filename):
        os.remove(mbz_filename)
    
    with zipfile.ZipFile(mbz_filename, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, output_dir)
                zf.write(file_path, arcname)
    
    file_size = os.path.getsize(mbz_filename)
    log(f"{mbz_filename} erstellt ({file_size} bytes)", "OK")

def main():
    print("\n" + "=" * 70)
    print("Moodle pAIpline v1 – Multi-Question Edition")
    print("=" * 70 + "\n")
    
    try:
        # 1. Validierung
        print("[1] Validierung")
        validate_template_structure()
        
        # 2. Input laden
        print("\n[2] Input laden")
        input_data = load_input(INPUT_FILE)
        
        # 3. Template kopieren
        print("\n[3] Template kopieren")
        copy_template(TEMPLATE_DIR, OUTPUT_DIR)
        
        # 4. Activities patchen
        print("\n[4] Activities patchen")
        patch_activities_v1(OUTPUT_DIR, input_data)
        
        # 5. MBZ erstellen
        print("\n[5] .mbz-Datei erstellen")
        create_mbz(OUTPUT_DIR, OUTPUT_MBZ)
        
        # Erfolg
        print("\n" + "=" * 70)
        print("✅ ERFOLG! Kursdatei erzeugt: " + OUTPUT_MBZ)
        print("=" * 70)
        print("\nNächste Schritte:")
        print("  1. In Moodle: Kurs → Course administration → Restore")
        print("  2. " + OUTPUT_MBZ + " auswählen")
        print("  3. Durchklicken und Kursinhalte werden wiederhergestellt")
        print()
        
    except ValidationError as e:
        log(f"Validierungsfehler: {e}", "ERROR")
        sys.exit(1)
    except Exception as e:
        log(f"Fehler: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
