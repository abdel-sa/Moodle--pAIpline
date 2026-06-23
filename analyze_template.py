#!/usr/bin/env python3
"""
Template Analyzer - Hilft, Activity-IDs und XML-Struktur zu verstehen
Lädt moodle_backup.xml und zeigt dir, welche Activities existieren
"""

import os
from lxml import etree

TEMPLATE_DIR = "template_backup"
BACKUP_XML = os.path.join(TEMPLATE_DIR, "moodle_backup.xml")

def parse_xml(filepath):
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(filepath, parser)
    return tree

def analyze_backup():
    """Analysiert moodle_backup.xml und zeigt Activities"""
    
    if not os.path.exists(BACKUP_XML):
        print(f"❌ {BACKUP_XML} nicht gefunden!")
        print(f"   Hast du den Backup-Ordner korrekt in 'template_backup/' entpackt?")
        return
    
    print("=" * 70)
    print("Template Analyzer – Activity Detection")
    print("=" * 70 + "\n")
    
    tree = parse_xml(BACKUP_XML)
    root = tree.getroot()
    
    # Finde alle <activity>
    activities = root.findall(".//activity")
    
    if not activities:
        print("⚠️  Keine Activities gefunden!")
        return
    
    print(f"📊 Gefundene Activities: {len(activities)}\n")
    
    activity_map = {}
    
    for activity in activities:
        module_id = activity.find("moduleid")
        module_name = activity.find("modulename")
        
        if module_id is not None and module_name is not None:
            mid = module_id.text
            mname = module_name.text
            
            key = f"{mname}_{mid}"
            activity_map[key] = {
                "moduleid": mid,
                "modulename": mname
            }
            
            # Finde Directory-Info
            directory = activity.find("directory")
            if directory is not None:
                activity_map[key]["directory"] = directory.text
            
            print(f"  [{key}]")
            print(f"    moduleid: {mid}")
            print(f"    modulename: {mname}")
            if "directory" in activity_map[key]:
                print(f"    directory: {activity_map[key]['directory']}")
            print()
    
    print("=" * 70)
    print("📝 Nutze folgende Keys in input.json:")
    print("=" * 70)
    for key in sorted(activity_map.keys()):
        print(f'  "{key}": {{ ... }}')
    print()
    
    # Prüfe jede Activity in der Festplatte
    print("=" * 70)
    print("✓ Validierung: Existieren die Activity-Ordner?")
    print("=" * 70)
    
    activities_dir = os.path.join(TEMPLATE_DIR, "activities")
    if os.path.isdir(activities_dir):
        for key in sorted(activity_map.keys()):
            activity_path = os.path.join(activities_dir, key)
            if os.path.isdir(activity_path):
                print(f"  ✓ {activity_path}")
                
                # Zeige XML-Dateien darin
                for fname in os.listdir(activity_path):
                    if fname.endswith(".xml"):
                        print(f"      └─ {fname}")
            else:
                print(f"  ❌ {activity_path} (FEHLT!)")
    else:
        print(f"  ❌ {activities_dir} nicht gefunden!")
    
    print("\n" + "=" * 70)
    print("🔍 XML-Struktur in questions.xml prüfen")
    print("=" * 70 + "\n")
    
    # Suche Quiz und analysiere questions.xml
    quiz_key = None
    for key in activity_map.keys():
        if "quiz" in key:
            quiz_key = key
            break
    
    if quiz_key:
        questions_xml = os.path.join(TEMPLATE_DIR, "activities", quiz_key, "questions.xml")
        if os.path.exists(questions_xml):
            print(f"📄 {questions_xml}\n")
            tree_q = parse_xml(questions_xml)
            root_q = tree_q.getroot()
            
            qbe_list = root_q.findall(".//question_bank_entry")
            print(f"  Gefundene Question Bank Entries: {len(qbe_list)}\n")
            
            for qbe in qbe_list:
                qbe_id = qbe.get("id", "???")
                question = qbe.find(".//question")
                
                q_id = "???"
                q_name = "???"
                if question is not None:
                    q_id = question.get("id", "???")
                    name_elem = question.find("name")
                    if name_elem is not None:
                        q_name = name_elem.text
                
                print(f"  [QBE ID {qbe_id}]")
                print(f"    Question ID: {q_id}")
                print(f"    Name: {q_name}")
                
                if question is not None:
                    answers = question.findall(".//answer")
                    print(f"    Answers: {len(answers)}")
                print()
        else:
            print(f"  ❌ {questions_xml} nicht gefunden!")
    else:
        print("  ℹ️  Kein Quiz in diesem Template gefunden")
    
    print("=" * 70)
    print("💡 Nächster Schritt:")
    print("=" * 70)
    print(f"""
1. Nutze die Activity-Keys oben für dein input.json:
   - "page_X" für Page-Activities
   - "assign_Y" für Assign-Activities
   - "quiz_Z" für Quiz-Activities

2. Nutze die Question Bank Entry IDs für "qbe_id" in Fragen

3. Beispiel input.json:
   {{
     "activities": {{
       "{list(activity_map.keys())[0] if activity_map else 'page_3'}": {{
         "type": "page",
         "name": "Mein Titel",
         "content_html": "<p>...</p>"
       }}
     }}
   }}

4. Starte dann: python build_v1.py
""")

if __name__ == "__main__":
    analyze_backup()
