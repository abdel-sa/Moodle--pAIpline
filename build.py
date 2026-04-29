#!/usr/bin/env python3
"""
Moodle pAIpline v0: Template-basiertes Kurs-Backup-Generator
Kopiert einen Template-Backup-Ordner, patcht XMLs mit Inhalt aus input.json und erzeugt .mbz
"""

import json
import shutil
import os
import zipfile
import re
from pathlib import Path
from lxml import etree

# ============================================================================
# KONFIGURATION
# ============================================================================

TEMPLATE_DIR = "template_backup"
OUTPUT_DIR = "out_build"
OUTPUT_MBZ = "generated_course.mbz"
INPUT_FILE = "input.json"

# XML-Namespace (Moodle nutzt diese)
MOODLE_NS = {
    'moodle': 'http://purl.org/dc/elements/1.1/'  # Fallback; prüfe dein Template
}

# ============================================================================
# HELPER: HTML ESCAPING
# ============================================================================

def escape_html_for_xml(text):
    """Escapt HTML für XML-Einbettung."""
    if text is None:
        return ""
    # XML-spezifische Zeichen escapen
    text = text.replace("&", "&amp;")  # MUSS zuerst kommen!
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&apos;")
    return text

# ============================================================================
# HELPER: XML PATCHEN
# ============================================================================

def parse_xml_file(filepath):
    """Parst XML-Datei mit Namespaces."""
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(filepath, parser)
    return tree

def write_xml_file(filepath, tree):
    """Schreibt XML zurück (mit Encoding, aber ohne pretty_print um Whitespace zu preserven)."""
    tree.write(filepath, encoding="utf-8", xml_declaration=True, standalone=True)

# ============================================================================
# PATCH-FUNKTIONEN
# ============================================================================

def patch_page_activity(page_xml_path, content_html):
    """
    Patcht activities/page_3/page.xml
    Sucht <page><content> und ersetzt Text mit escaped HTML.
    """
    print(f"  → Patching {page_xml_path}")
    
    if not os.path.exists(page_xml_path):
        raise FileNotFoundError(f"page.xml nicht gefunden: {page_xml_path}")
    
    tree = parse_xml_file(page_xml_path)
    root = tree.getroot()
    
    # Finde <page><content>
    content_elem = root.find(".//content")
    if content_elem is None:
        raise ValueError(f"<content> Element nicht gefunden in {page_xml_path}")
    
    # Escaped HTML in Text umwandeln
    escaped = escape_html_for_xml(content_html)
    content_elem.text = escaped
    
    write_xml_file(page_xml_path, tree)
    print(f"    ✓ <content> updated")

def patch_assign_activity(assign_xml_path, intro_html):
    """
    Patcht activities/assign_4/assign.xml
    Sucht <assign><intro> und ersetzt mit escaped HTML.
    """
    print(f"  → Patching {assign_xml_path}")
    
    if not os.path.exists(assign_xml_path):
        raise FileNotFoundError(f"assign.xml nicht gefunden: {assign_xml_path}")
    
    tree = parse_xml_file(assign_xml_path)
    root = tree.getroot()
    
    # Finde <assign><intro>
    intro_elem = root.find(".//intro")
    if intro_elem is None:
        raise ValueError(f"<intro> Element nicht gefunden in {assign_xml_path}")
    
    escaped = escape_html_for_xml(intro_html)
    intro_elem.text = escaped
    
    write_xml_file(assign_xml_path, tree)
    print(f"    ✓ <intro> updated")

def patch_quiz_questions(questions_xml_path, questions_data):
    """
    Patcht activities/quiz_5/questions.xml
    Für jede Frage in questions_data:
      - Finde <question_bank_entry id=qbe_id>
      - Finde darin <question id=question_id>
      - Ersetze <name>, <questiontext>, <answers>
    """
    print(f"  → Patching {questions_xml_path}")
    
    if not os.path.exists(questions_xml_path):
        raise FileNotFoundError(f"questions.xml nicht gefunden: {questions_xml_path}")
    
    tree = parse_xml_file(questions_xml_path)
    root = tree.getroot()
    
    for q_data in questions_data:
        qbe_id = str(q_data.get("qbe_id", "1"))
        question_id = str(q_data.get("question_id", "1"))
        q_name = q_data.get("name", "Untitled Question")
        q_text = q_data.get("questiontext_html", "")
        answers = q_data.get("answers", [])
        
        # Finde <question_bank_entry id=qbe_id>
        qbe = root.find(f".//question_bank_entry[@id='{qbe_id}']")
        if qbe is None:
            raise ValueError(f"question_bank_entry mit id={qbe_id} nicht gefunden")
        
        # Finde <question id=question_id> darin
        q = qbe.find(f".//question[@id='{question_id}']")
        if q is None:
            raise ValueError(f"question mit id={question_id} in qbe={qbe_id} nicht gefunden")
        
        # Update <name>
        name_elem = q.find("name")
        if name_elem is not None:
            name_elem.text = q_name
        
        # Update <questiontext>
        qt_elem = q.find("questiontext")
        if qt_elem is not None:
            escaped_qt = escape_html_for_xml(q_text)
            qt_elem.text = escaped_qt
        
        # Ersetze <answers>
        answers_elem = q.find("answers")
        if answers_elem is not None:
            # Lösche alle alten <answer>-Elemente
            for old_answer in answers_elem.findall("answer"):
                answers_elem.remove(old_answer)
            
            # Füge neue Answers ein
            for idx, answer_data in enumerate(answers, start=1):
                answer_text = answer_data.get("text_html", "")
                fraction = answer_data.get("fraction", 0.0)
                
                # Erstelle neues <answer id=idx>
                answer_elem = etree.SubElement(answers_elem, "answer")
                answer_elem.set("id", str(idx))
                
                # <text>escaped_html</text>
                text_elem = etree.SubElement(answer_elem, "text")
                text_elem.text = escape_html_for_xml(answer_text)
                
                # <fraction>value</fraction>
                fraction_elem = etree.SubElement(answer_elem, "fraction")
                fraction_elem.text = str(fraction)
    
    write_xml_file(questions_xml_path, tree)
    print(f"    ✓ Questions updated")

# ============================================================================
# HAUPTLOGIK
# ============================================================================

def load_input(input_file):
    """Lädt input.json"""
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"input.json nicht gefunden: {input_file}")
    
    with open(input_file, "r", encoding="utf-8") as f:
        return json.load(f)

def copy_template(template_dir, output_dir):
    """Kopiert Template in Output-Dir."""
    if os.path.exists(output_dir):
        print(f"  → Lösche alten {output_dir}")
        shutil.rmtree(output_dir)
    
    print(f"  → Kopiere {template_dir} → {output_dir}")
    shutil.copytree(template_dir, output_dir)

def patch_activities(output_dir, input_data):
    """Patcht alle Activities basierend auf input.json"""
    activities = input_data.get("activities", {})
    
    # PAGE
    if "page_3" in activities:
        print("Patching PAGE (activities/page_3/page.xml):")
        page_data = activities["page_3"]
        page_xml = os.path.join(output_dir, "activities", "page_3", "page.xml")
        patch_page_activity(page_xml, page_data.get("content_html", ""))
    
    # ASSIGN
    if "assign_4" in activities:
        print("Patching ASSIGN (activities/assign_4/assign.xml):")
        assign_data = activities["assign_4"]
        assign_xml = os.path.join(output_dir, "activities", "assign_4", "assign.xml")
        patch_assign_activity(assign_xml, assign_data.get("intro_html", ""))
    
    # QUIZ
    if "quiz_5" in activities:
        print("Patching QUIZ (activities/quiz_5/questions.xml):")
        quiz_data = activities["quiz_5"]
        questions_xml = os.path.join(output_dir, "activities", "quiz_5", "questions.xml")
        questions = quiz_data.get("questions", [])
        if questions:
            patch_quiz_questions(questions_xml, questions)

def create_mbz(output_dir, mbz_filename):
    """Packt output_dir in eine .mbz (ZIP-Datei)"""
    print(f"Packe {output_dir} → {mbz_filename}")
    
    # Erstelle ZIP mit allen Dateien aus output_dir
    with zipfile.ZipFile(mbz_filename, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                file_path = os.path.join(root, file)
                # Arcname = Pfad relativ zu output_dir
                arcname = os.path.relpath(file_path, output_dir)
                zf.write(file_path, arcname)
    
    print(f"  ✓ {mbz_filename} erstellt ({os.path.getsize(mbz_filename)} bytes)")

def main():
    print("=" * 70)
    print("Moodle pAIpline v0")
    print("=" * 70)
    
    try:
        # 1. Input laden
        print("\n[1] Input laden...")
        input_data = load_input(INPUT_FILE)
        print(f"  ✓ input.json geladen")
        
        # 2. Template kopieren
        print("\n[2] Template-Backup kopieren...")
        copy_template(TEMPLATE_DIR, OUTPUT_DIR)
        print(f"  ✓ Kopiert zu {OUTPUT_DIR}")
        
        # 3. XMLs patchen
        print("\n[3] Activities patchen...")
        patch_activities(OUTPUT_DIR, input_data)
        
        # 4. MBZ packen
        print("\n[4] .mbz-Datei erstellen...")
        create_mbz(OUTPUT_DIR, OUTPUT_MBZ)
        
        print("\n" + "=" * 70)
        print(f"✅ SUCCESS! Kursdatei erzeugt: {OUTPUT_MBZ}")
        print("=" * 70)
        print("\nNächste Schritte:")
        print("  1. In Moodle: Kurs → More → Course reuse → Restore")
        print("  2. generated_course.mbz wählen")
        print("  3. Durchklicken und wiederherstellen")
        
    except Exception as e:
        print(f"\n❌ FEHLER: {e}", flush=True)
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()
