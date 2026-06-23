#!/usr/bin/env python3
"""
Moodle pAIpline v1: Multi-Question, Multi-Activity, mit Validierung & Logging
- Unterstützt mehrere Question Bank Entries (qbe_id)
- Validiert Dateien & XML-Struktur vor dem Patchen
- Strukturiertes Logging der Patch-Operationen
"""

import copy
import gzip
import json
import shutil
import os
import tarfile
import sys
import argparse
from datetime import datetime, timezone
from lxml import etree

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ============================================================================
# KONFIGURATION (Defaults – überschreibbar per CLI)
# ============================================================================

DEFAULT_TEMPLATE_DIR = "template_backup"
DEFAULT_OUTPUT_DIR = "out_build"
DEFAULT_OUTPUT_MBZ = "generated_course.mbz"
DEFAULT_INPUT_FILE = "input.json"

def log(msg, level="INFO"):
    prefixes = {"OK": "✓ ", "WARN": "⚠ ", "ERROR": "✗ "}
    print(f"{prefixes.get(level, '  ')}{msg}")

# ============================================================================
# VALIDIERUNG
# ============================================================================

class ValidationError(Exception):
    pass

def validate_template_structure(template_dir):
    """Prüft, ob Template-Dir existiert und die Basis-Struktur stimmt"""
    log(f"Validiere Template in: {template_dir}")

    if not os.path.isdir(template_dir):
        raise ValidationError(f"Template-Dir nicht gefunden: {template_dir}")

    required_files = ["moodle_backup.xml", "activities", "sections"]

    for item in required_files:
        path = os.path.join(template_dir, item)
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
    body = etree.tostring(tree, encoding="UTF-8", xml_declaration=False)
    data = b'<?xml version="1.0" encoding="UTF-8"?>\n' + body
    with open(filepath, "wb") as f:
        f.write(data)

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

        # Finde <question_bank_entry id=qbe_id> — falls nicht vorhanden, ersten klonen
        qbe = root.find(f".//question_bank_entry[@id='{qbe_id}']")
        if qbe is None:
            first_qbe = root.find(".//question_bank_entry")
            if first_qbe is None:
                raise ValidationError("Keine question_bank_entry im Template gefunden")
            qbe = copy.deepcopy(first_qbe)
            qbe.set("id", qbe_id)
            # Dedupliziere innere IDs um Konflikte beim Moodle-Restore zu vermeiden
            for qv in qbe.findall(".//question_versions"):
                qv.set("id", qbe_id)
            for mc in qbe.findall(".//multichoice"):
                mc.set("id", qbe_id)
            # Innere question-ID sofort auf question_id setzen — verhindert,
            # dass später eine doppelte <question> im selben Versions-Block entsteht
            inner_q = qbe.find(".//question")
            if inner_q is not None:
                inner_q.set("id", question_id)
            first_qbe.getparent().append(qbe)
            log(f"    → question_bank_entry id={qbe_id} aus Template geklont", "OK")

        # Finde <question id=question_id> — falls nicht vorhanden, erste klonen
        q = qbe.find(f".//question[@id='{question_id}']")
        if q is None:
            first_q = qbe.find(".//question")
            if first_q is None:
                raise ValidationError(f"Keine question in qbe={qbe_id} gefunden")
            q = copy.deepcopy(first_q)
            q.set("id", question_id)
            first_q.getparent().append(q)
            log(f"    → question id={question_id} geklont", "OK")
        
        # Update <name>
        name_elem = q.find("name")
        if name_elem is not None:
            name_elem.text = q_name
        
        # Update <questiontext>
        qt_elem = q.find("questiontext")
        if qt_elem is not None:
            qt_elem.text = q_text
        
        # Ersetze <answers> im plugin_qtype_multichoice_question-Block
        answers_elem = q.find(".//plugin_qtype_multichoice_question/answers")
        if answers_elem is not None:
            # Lösche alte Answers
            for old_answer in list(answers_elem):
                answers_elem.remove(old_answer)

            # Füge neue mit korrekter Moodle-4.3-Struktur ein
            for idx, answer_data in enumerate(answers, start=1):
                answer_text = answer_data.get("text_html", "")
                fraction = answer_data.get("fraction", 0.0)

                answer_elem = etree.SubElement(answers_elem, "answer")
                answer_elem.set("id", str(idx))
                etree.SubElement(answer_elem, "answertext").text = answer_text
                etree.SubElement(answer_elem, "answerformat").text = "1"
                etree.SubElement(answer_elem, "fraction").text = f"{fraction:.7f}"
                etree.SubElement(answer_elem, "feedback").text = ""
                etree.SubElement(answer_elem, "feedbackformat").text = "1"

            log(f"    → {len(answers)} Antwort(en) aktualisiert", "OK")
        else:
            log("    → <answers> in plugin_qtype_multichoice_question nicht gefunden", "WARN")
    
    write_xml_file(questions_xml_path, tree)

def patch_quiz_instances(quiz_xml_path, questions_data):
    """
    Synct <question_instances> in quiz.xml für mehrere Fragen.
    Ohne diesen Patch sieht Moodle nur die 1 Slot aus dem Template —
    alle zusätzlich geklonten Fragen wären im Quiz unsichtbar.
    Aktualisiert auch <sumgrades> auf Anzahl der Fragen.
    """
    if not os.path.exists(quiz_xml_path):
        log(f"quiz.xml nicht gefunden: {quiz_xml_path}", "WARN")
        return

    log(f"Patche Quiz-Instances: {quiz_xml_path}")
    tree = parse_xml_file(quiz_xml_path)
    root = tree.getroot()  # <activity>

    quiz_elem = root.find("quiz")
    if quiz_elem is None:
        log("  <quiz> nicht in quiz.xml gefunden", "WARN")
        return

    # Context-ID des Quiz-Moduls aus <activity contextid="...">
    using_ctx = root.get("contextid", "20")
    quiz_id = quiz_elem.get("id", "1")

    instances_elem = quiz_elem.find("question_instances")
    if instances_elem is None:
        log("  <question_instances> nicht gefunden", "WARN")
        return

    # Alte Slots löschen
    for inst in list(instances_elem):
        instances_elem.remove(inst)

    # Einen Slot pro Frage anlegen
    for slot_num, q_data in enumerate(questions_data, start=1):
        qbe_id = str(q_data.get("qbe_id", slot_num))

        inst = etree.SubElement(instances_elem, "question_instance")
        inst.set("id", str(slot_num))
        etree.SubElement(inst, "quizid").text = quiz_id
        etree.SubElement(inst, "slot").text = str(slot_num)
        etree.SubElement(inst, "page").text = str(slot_num)
        etree.SubElement(inst, "displaynumber").text = "$@NULL@$"
        etree.SubElement(inst, "requireprevious").text = "0"
        etree.SubElement(inst, "maxmark").text = "1.0000000"

        ref = etree.SubElement(inst, "question_reference")
        ref.set("id", str(slot_num))
        etree.SubElement(ref, "usingcontextid").text = using_ctx
        etree.SubElement(ref, "component").text = "mod_quiz"
        etree.SubElement(ref, "questionarea").text = "slot"
        etree.SubElement(ref, "questionbankentryid").text = qbe_id
        etree.SubElement(ref, "version").text = "$@NULL@$"

        log(f"  → slot {slot_num}: questionbankentryid={qbe_id}", "OK")

    # sumgrades = Anzahl Fragen × 1 Punkt
    sumgrades_elem = quiz_elem.find("sumgrades")
    if sumgrades_elem is not None:
        sumgrades_elem.text = f"{len(questions_data):.5f}"
        log(f"  → <sumgrades> = {len(questions_data):.5f}", "OK")

    write_xml_file(quiz_xml_path, tree)


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

def _remove_readonly(func, path, _):
    """onerror-Handler: setzt Write-Bit und wiederholt."""
    import stat
    os.chmod(path, stat.S_IWRITE)
    func(path)

def copy_template(template_dir, output_dir):
    """Kopiert Template in Output-Dir"""
    if os.path.exists(output_dir):
        log(f"Lösche alten {output_dir}")
        shutil.rmtree(output_dir, onerror=_remove_readonly)
    
    log(f"Kopiere {template_dir} → {output_dir}")
    shutil.copytree(template_dir, output_dir)
    log(f"Template kopiert", "OK")

def _iso_to_unix(date_str):
    """Konvertiert ISO-Datum ("2026-05-01") zu Unix-Timestamp (int)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def patch_course_metadata(output_dir, metadata):
    """
    Patcht course/course.xml mit Werten aus input.json course_metadata.

    Unterstützte Felder:
      fullname   str   Voller Kursname
      shortname  str   Kurzkürzel (keine Leerzeichen)
      summary    str   HTML-Beschreibung (wird auf der Kursseite angezeigt)
      lang       str   Sprachcode, z.B. "de" oder "en"
      visible    bool  Kurs sichtbar (true) oder versteckt (false)
      startdate  str   ISO-Datum "YYYY-MM-DD" → Unix-Timestamp
      enddate    str   ISO-Datum "YYYY-MM-DD" → Unix-Timestamp (0 = kein Ende)
    """
    course_xml = os.path.join(output_dir, "course", "course.xml")
    if not os.path.exists(course_xml):
        log("course/course.xml nicht gefunden, überspringe Metadata-Patch", "WARN")
        return

    log(f"Patche Kurs-Metadata: {course_xml}")
    tree = parse_xml_file(course_xml)
    root = tree.getroot()

    for tag in ("fullname", "shortname", "lang"):
        if tag in metadata:
            elem = root.find(tag)
            if elem is not None:
                elem.text = str(metadata[tag])
                log(f"  → <{tag}> = {metadata[tag]}", "OK")

    # Summary (HTML erlaubt, lxml escaped automatisch)
    if "summary" in metadata:
        elem = root.find("summary")
        if elem is not None:
            elem.text = metadata["summary"]
            log(f"  → <summary> updated ({len(metadata['summary'])} chars)", "OK")

    # Visible (bool → "1" / "0")
    if "visible" in metadata:
        elem = root.find("visible")
        if elem is not None:
            elem.text = "1" if metadata["visible"] else "0"
            log(f"  → <visible> = {elem.text}", "OK")

    # Datum-Felder: ISO-String "YYYY-MM-DD" → Unix-Timestamp
    for date_field in ("startdate", "enddate"):
        if date_field in metadata:
            raw = metadata[date_field]
            try:
                ts = _iso_to_unix(raw)
            except ValueError:
                raise ValidationError(
                    f"course_metadata.{date_field}: ungültiges Datumsformat '{raw}'. "
                    f"Erwartet: YYYY-MM-DD"
                )
            elem = root.find(date_field)
            if elem is not None:
                elem.text = str(ts)
                log(f"  → <{date_field}> = {ts} ({raw})", "OK")

    write_xml_file(course_xml, tree)


def patch_backup_manifest(output_dir, input_data, mbz_filename):
    """Patcht moodle_backup.xml, damit keine Template-Kursnamen im Restore erscheinen."""
    manifest_xml = os.path.join(output_dir, "moodle_backup.xml")
    if not os.path.exists(manifest_xml):
        log("moodle_backup.xml nicht gefunden, überspringe Manifest-Patch", "WARN")
        return

    metadata = input_data.get("course_metadata", {})
    activities = input_data.get("activities", {})
    sections = input_data.get("sections", {})
    fullname = metadata.get("fullname", "Moodle pAIpline Kurs")
    shortname = metadata.get("shortname", "moodle_paipline")
    filename = os.path.basename(mbz_filename)

    log(f"Patche Backup-Manifest: {manifest_xml}")
    tree = parse_xml_file(manifest_xml)
    root = tree.getroot()

    replacements = {
        ".//information/name": filename,
        ".//information/original_course_fullname": fullname,
        ".//information/original_course_shortname": shortname,
        ".//information/contents/course/title": shortname,
    }
    for path, value in replacements.items():
        elem = root.find(path)
        if elem is not None:
            elem.text = str(value)

    for setting in root.findall(".//settings/setting"):
        name = setting.findtext("name")
        value = setting.find("value")
        if value is not None and name == "filename":
            value.text = filename

    for activity in root.findall(".//contents/activities/activity"):
        directory = activity.findtext("directory", "")
        key = os.path.basename(directory)
        title = activity.find("title")
        if title is not None and key in activities:
            title.text = activities[key].get("name", title.text)

    for section in root.findall(".//contents/sections/section"):
        directory = section.findtext("directory", "")
        key = os.path.basename(directory)
        title = section.find("title")
        if title is not None and key in sections:
            title.text = sections[key].get("name", title.text)

    write_xml_file(manifest_xml, tree)


def patch_question_categories(output_dir, input_data):
    """Patcht questions.xml-Kategorien, damit keine Template-Namen wie Brüche bleiben."""
    questions_xml = os.path.join(output_dir, "questions.xml")
    if not os.path.exists(questions_xml):
        log("questions.xml nicht gefunden, überspringe Question-Category-Patch", "WARN")
        return

    metadata = input_data.get("course_metadata", {})
    activities = input_data.get("activities", {})
    quiz_name = next(
        (activity.get("name") for activity in activities.values() if activity.get("type") == "quiz" and activity.get("name")),
        metadata.get("fullname", "Quiz"),
    )
    course_shortname = metadata.get("shortname") or metadata.get("fullname", "Kurs")

    log(f"Patche Question-Categories: {questions_xml}")
    tree = parse_xml_file(questions_xml)
    root = tree.getroot()

    default_names = [f"Default for {quiz_name}", f"Default for {course_shortname}"]
    default_infos = [
        f"The default category for questions shared in context '{quiz_name}'.",
        f"The default category for questions shared in context '{course_shortname}'.",
    ]
    idx = 0
    for category in root.findall(".//question_category"):
        name = category.find("name")
        info = category.find("info")
        if name is None or not (name.text or "").lower().startswith("default for"):
            continue
        replacement_index = min(idx, len(default_names) - 1)
        name.text = default_names[replacement_index]
        if info is not None:
            info.text = default_infos[replacement_index]
        idx += 1

    write_xml_file(questions_xml, tree)


def patch_activity_display_metadata(output_dir, activity_key, activity_type, activity_data):
    """Patcht Activity-Titel in Modul- und Gradebook-Dateien."""
    activity_name = activity_data.get("name")
    if not activity_name:
        return

    activity_dir = os.path.join(output_dir, "activities", activity_key)
    module_xml = os.path.join(activity_dir, f"{activity_type}.xml")
    if os.path.exists(module_xml):
        tree = parse_xml_file(module_xml)
        root = tree.getroot()
        name_elem = root.find(".//name")
        if name_elem is not None:
            name_elem.text = activity_name
            log(f"  → {activity_type}.xml <name> = {activity_name}", "OK")
        if activity_type == "quiz" and activity_data.get("intro_html"):
            intro_elem = root.find(".//intro")
            if intro_elem is not None:
                intro_elem.text = activity_data["intro_html"]
        write_xml_file(module_xml, tree)

    grades_xml = os.path.join(activity_dir, "grades.xml")
    if os.path.exists(grades_xml):
        tree = parse_xml_file(grades_xml)
        root = tree.getroot()
        for itemname in root.findall(".//itemname"):
            itemname.text = activity_name
        write_xml_file(grades_xml, tree)
        log(f"  → grades.xml <itemname> = {activity_name}", "OK")


def patch_sections(output_dir, sections):
    """
    Patcht sections/section_X/section.xml mit name und summary.
    sections: {"section_6": {"name": "Einführung", "summary": "<p>...</p>"}, ...}
    """
    if not sections:
        log("Keine sections in input.json definiert", "WARN")
        return

    for section_key, section_data in sections.items():
        section_xml = os.path.join(output_dir, "sections", section_key, "section.xml")

        if not os.path.exists(section_xml):
            log(f"Section nicht gefunden: {section_key} – überspringe", "WARN")
            continue

        log(f"Patche Section: {section_key}")
        tree = parse_xml_file(section_xml)
        root = tree.getroot()

        if "name" in section_data:
            elem = root.find("name")
            if elem is not None:
                elem.text = section_data["name"]
                log(f"  → <name> = {section_data['name']}", "OK")

        if "summary" in section_data:
            elem = root.find("summary")
            if elem is not None:
                elem.text = section_data["summary"]
                log(f"  → <summary> updated ({len(section_data['summary'])} chars)", "OK")

        write_xml_file(section_xml, tree)


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
        activity_type = activity_data.get("type")
        if not activity_type:
            raise ValidationError(
                f"Activity '{activity_key}' hat kein 'type'-Feld. "
                f"Erlaubt: 'page', 'assign', 'quiz'."
            )

        log(f"\nPatche Activity: {activity_key} (Typ: {activity_type})")
        
        # Prüfe, ob Activity existiert
        if not validate_activity_in_template(output_dir, activity_key, activity_type):
            log(f"SKIPPED: {activity_key}", "WARN")
            continue
        
        try:
            patch_activity_display_metadata(output_dir, activity_key, activity_type, activity_data)

            if activity_type == "page":
                page_xml = os.path.join(output_dir, "activities", activity_key, "page.xml")
                patch_page_activity(page_xml, activity_data)
            
            elif activity_type == "assign":
                assign_xml = os.path.join(output_dir, "activities", activity_key, "assign.xml")
                patch_assign_activity(assign_xml, activity_data)
            
            elif activity_type == "quiz":
                # Versuche zuerst: questions.xml in activities/quiz_X/
                questions_xml = os.path.join(output_dir, "activities", activity_key, "questions.xml")
                # Fallback: questions.xml in Output-Root (Moodle 4.x-Standard)
                if not os.path.exists(questions_xml):
                    questions_xml = os.path.join(output_dir, "questions.xml")

                questions = activity_data.get("questions", [])
                if questions:
                    patch_quiz_questions(questions_xml, questions)
                    # quiz.xml synchronisieren: Slots für alle Fragen anlegen
                    quiz_xml = os.path.join(output_dir, "activities", activity_key, "quiz.xml")
                    patch_quiz_instances(quiz_xml, questions)
                else:
                    log(f"Keine Fragen definiert für {activity_key}", "WARN")
            
            else:
                log(f"Unbekannter Activity-Typ: {activity_type}", "WARN")
        
        except Exception as e:
            log(f"FEHLER beim Patchen von {activity_key}: {e}", "ERROR")
            raise

def validate_mbz_archive(mbz_filename):
    """Prueft, ob die erzeugte Datei als Moodle-Backup erkennbar ist."""
    required_files = {
        ".ARCHIVE_INDEX",
        "moodle_backup.xml",
        "course/course.xml",
        "files.xml",
    }
    required_dirs = {
        "activities/",
        "sections/",
        "course/",
    }

    if not tarfile.is_tarfile(mbz_filename):
        raise ValidationError(
            f"{mbz_filename} ist kein gzip-tar Moodle-Backup. "
            "Moodle Restore wuerde diese Datei wahrscheinlich nicht als Backup erkennen."
        )

    with tarfile.open(mbz_filename, "r:gz") as tf:
        members = tf.getmembers()
        names = set(member.name.rstrip("/") + ("/" if member.isdir() else "") for member in members)
        file_names = set(member.name for member in members if member.isfile())
        missing_files = sorted(required_files - names)
        missing_dirs = sorted(
            d for d in required_dirs
            if d not in names and not any(name.startswith(d) for name in names)
        )
        if missing_files or missing_dirs:
            missing = missing_files + missing_dirs
            raise ValidationError(
                "Ungueltiges Moodle-Backup: Folgende Eintraege fehlen im Archiv: "
                + ", ".join(missing)
            )

        try:
            manifest_member = tf.extractfile("moodle_backup.xml")
            if manifest_member is None:
                raise ValidationError("moodle_backup.xml ist kein Datei-Eintrag.")
            manifest_bytes = manifest_member.read()
            firstchars = manifest_bytes[:200].decode("utf-8", errors="replace")
            if (
                '<?xml version="1.0" encoding="UTF-8"?>' not in firstchars
                or "<moodle_backup>" not in firstchars
                or "<information>" not in firstchars
            ):
                raise ValidationError(
                    "moodle_backup.xml erfuellt Moodles Format-Erkennung nicht. "
                    "Erwartet werden XML-Deklaration, <moodle_backup> und <information> in den ersten 200 Zeichen."
                )
            manifest = etree.fromstring(manifest_bytes)
        except Exception as e:
            raise ValidationError(f"moodle_backup.xml im Archiv ist nicht lesbar: {e}") from e

        if manifest.tag != "moodle_backup":
            raise ValidationError("moodle_backup.xml hat keinen <moodle_backup>-Root.")

        backup_format = manifest.findtext("./information/details/detail/format")
        if backup_format != "moodle2":
            raise ValidationError(
                f"moodle_backup.xml beschreibt kein moodle2-Backup (format={backup_format!r})."
            )

        archive_index = tf.extractfile(".ARCHIVE_INDEX")
        if archive_index is None:
            raise ValidationError(".ARCHIVE_INDEX ist kein Datei-Eintrag.")
        header = archive_index.readline().decode("utf-8", errors="replace").strip()
        if not header.startswith("Moodle archive file index. Count: "):
            raise ValidationError(".ARCHIVE_INDEX hat keinen Moodle-Index-Header.")

        indexed_files = set()
        for raw_line in archive_index:
            parts = raw_line.decode("utf-8", errors="replace").rstrip("\n").split("\t")
            if len(parts) >= 2 and parts[1] == "f":
                indexed_files.add(parts[0].strip("/"))
        missing_indexed = sorted(indexed_files - file_names)
        if missing_indexed:
            raise ValidationError(
                "Ungueltiges Moodle-Backup: Dateien aus .ARCHIVE_INDEX fehlen im Tar: "
                + ", ".join(missing_indexed[:10])
            )

    log("MBZ-Archivstruktur validiert (gzip-tar mit Moodle-Backup-Inhalten)", "OK")


def create_mbz(output_dir, mbz_filename):
    """Packt output_dir als Moodle-kompatibles .mbz (gzip-tar Backup-Struktur)."""
    log(f"Erstelle .mbz-Datei: {mbz_filename}")
    
    if os.path.exists(mbz_filename):
        os.remove(mbz_filename)
    
    index_path = os.path.join(output_dir, ".ARCHIVE_INDEX")
    if not os.path.exists(index_path):
        raise ValidationError(".ARCHIVE_INDEX nicht gefunden")

    def add_file(tf, file_path, arcname, mtime=None):
        info = tf.gettarinfo(file_path, arcname=arcname)
        info.mode = 0o644
        info.uid = 0
        info.gid = 0
        info.uname = ""
        info.gname = ""
        if mtime is not None:
            info.mtime = mtime
        with open(file_path, "rb") as f:
            tf.addfile(info, f)

    def add_dir(tf, arcname):
        dirname = arcname.strip("/") + "/"
        info = tarfile.TarInfo(dirname)
        info.type = tarfile.DIRTYPE
        info.mode = 0o755
        info.uid = 0
        info.gid = 0
        info.uname = ""
        info.gname = ""
        info.mtime = 1356998400
        tf.addfile(info)

    with open(mbz_filename, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=6, mtime=0) as gz:
            with tarfile.open(mode="w", fileobj=gz, format=tarfile.USTAR_FORMAT) as tf:
                add_file(tf, index_path, ".ARCHIVE_INDEX")

                with open(index_path, "r", encoding="utf-8") as idx:
                    next(idx, None)
                    for line in idx:
                        parts = line.rstrip("\n").split("\t")
                        if len(parts) < 2:
                            continue

                        arcname = parts[0].strip("/")
                        entry_type = parts[1]
                        if not arcname:
                            continue

                        if entry_type == "d":
                            add_dir(tf, arcname)
                            continue

                        file_path = os.path.join(output_dir, *arcname.split("/"))
                        if not os.path.exists(file_path):
                            raise ValidationError(f"Datei aus .ARCHIVE_INDEX fehlt: {arcname}")

                        mtime = None
                        if len(parts) >= 4 and parts[3].isdigit():
                            mtime = int(parts[3])
                        add_file(tf, file_path, arcname, mtime)

    validate_mbz_archive(mbz_filename)
    
    file_size = os.path.getsize(mbz_filename)
    log(f"{mbz_filename} erstellt ({file_size} bytes)", "OK")

# ============================================================================
# V2: UNITS-BASIERTE STRUKTUR (Self-Study / In-Class / Abschlussquiz)
# ============================================================================

def _unit_selfstudy_html(unit):
    """HTML für Self-Study Page aus einem Unit-Objekt (pipeline.py Format)."""
    parts = []
    blocks = unit.get("contentBlocks", [])
    has_theory_blocks = any(cb.get("type") == "theory" for cb in blocks)

    # Nur ausgeben wenn keine ContentBlocks vorhanden (verhindert doppelten Inhalt)
    if unit.get("theoryContent") and not has_theory_blocks:
        parts.append(f"<p>{unit['theoryContent']}</p>")

    objectives = unit.get("learningObjectives", [])
    if objectives:
        items = "".join(f"<li>{o}</li>" for o in objectives)
        parts.append(f"<h2>Lernziele</h2><ul>{items}</ul>")

    # Theorie- und Beispiel-Blöcke (Pflichtlektüre)
    for cb in blocks:
        cb_type = cb.get("type", "")
        title = cb.get("title", "")
        content = cb.get("content", "")
        if cb_type == "theory":
            parts.append(f"<h2>{title}</h2><p>{content}</p>")
        elif cb_type == "example":
            parts.append(f"<h3>{title}</h3><p>{content}</p>")

    # Aufgaben für das Selbststudium (fällig bis zur nächsten Präsenzeinheit)
    prep_parts = []
    for cb in blocks:
        cb_type = cb.get("type", "")
        title = cb.get("title", "")
        content = cb.get("content", "")
        if cb_type == "homework":
            prep_parts.append(f"<h3>{title}</h3><p>{content}</p>")
        elif cb_type == "reflection":
            prep_parts.append(f"<h3>Reflexion: {title}</h3><p>{content}</p>")

    if prep_parts:
        parts.append("<h2>Aufgaben bis zur nächsten Präsenzeinheit</h2>")
        parts.extend(prep_parts)

    return "".join(parts) or f"<p>{unit.get('title', '')}</p>"


def _unit_inclass_html(unit):
    """HTML für In-Class Aufgabe — nur Präsenzaktivitäten (Gruppenarbeit etc.)."""
    parts = []
    for cb in unit.get("contentBlocks", []):
        cb_type = cb.get("type", "")
        title = cb.get("title", "")
        content = cb.get("content", "")
        if cb_type == "activity":
            parts.append(f"<h2>{title}</h2><p>{content}</p>")
    return "".join(parts) or f"<p>Aufgabe: {unit.get('title', '')}</p>"


def _collect_final_quiz_questions(units):
    """Sammelt single_choice Fragen aus allen Units für den Abschlussquiz."""
    questions = []
    qid = 1
    for unit in units:
        for cb in unit.get("contentBlocks", []):
            if cb.get("type") != "quiz":
                continue
            for q in cb.get("questions", []):
                if q.get("questionType") != "single_choice":
                    continue
                answers = [
                    {"text_html": f"<p>{a.get('text', '')}</p>",
                     "fraction": 1.0 if a.get("isCorrect") else 0.0}
                    for a in q.get("answers", [])
                ]
                if not answers:
                    continue
                questions.append({
                    "qbe_id": qid, "question_id": qid,
                    "name": f"Frage {qid}",
                    "questiontext_html": f"<p>{q.get('question', '')}</p>",
                    "answers": answers,
                })
                qid += 1
        for q in unit.get("questions", []):
            if q.get("questionType") != "single_choice":
                continue
            answers = [
                {"text_html": f"<p>{a.get('text', '')}</p>",
                 "fraction": 1.0 if a.get("isCorrect") else 0.0}
                for a in q.get("answers", [])
            ]
            if not answers:
                continue
            questions.append({
                "qbe_id": qid, "question_id": qid,
                "name": f"Frage {qid}",
                "questiontext_html": f"<p>{q.get('question', '')}</p>",
                "answers": answers,
            })
            qid += 1
    return questions


def _clone_activity_dir(out_dir, src_key, dst_key, new_mod_id, new_section_id, new_section_num, new_ctx_id):
    """Klont ein Activity-Verzeichnis und aktualisiert IDs in module.xml und Haupt-XML."""
    src_path = os.path.join(out_dir, "activities", src_key)
    dst_path = os.path.join(out_dir, "activities", dst_key)
    if os.path.exists(dst_path):
        shutil.rmtree(dst_path, onerror=_remove_readonly)
    shutil.copytree(src_path, dst_path)

    act_type = dst_key.split("_")[0]  # "page" oder "assign"

    module_xml = os.path.join(dst_path, "module.xml")
    if os.path.exists(module_xml):
        tree = parse_xml_file(module_xml)
        root = tree.getroot()
        root.set("id", str(new_mod_id))
        for tag, val in [("sectionid", new_section_id), ("sectionnumber", new_section_num)]:
            e = root.find(tag)
            if e is not None:
                e.text = str(val)
        write_xml_file(module_xml, tree)

    main_xml = os.path.join(dst_path, f"{act_type}.xml")
    if os.path.exists(main_xml):
        tree = parse_xml_file(main_xml)
        root = tree.getroot()
        root.set("moduleid", str(new_mod_id))
        root.set("contextid", str(new_ctx_id))
        write_xml_file(main_xml, tree)


def _patch_section_xml(section_dir, section_id, section_num, name, summary, sequence_mod_id):
    """Patcht section.xml mit neuen Werten."""
    section_xml = os.path.join(section_dir, "section.xml")
    if not os.path.exists(section_xml):
        return
    tree = parse_xml_file(section_xml)
    root = tree.getroot()
    root.set("id", str(section_id))
    for tag, val in [("number", str(section_num)), ("name", name),
                     ("summary", summary), ("sequence", str(sequence_mod_id))]:
        e = root.find(tag)
        if e is not None:
            e.text = val
    write_xml_file(section_xml, tree)


def _clone_section_dir(out_dir, src_section_id, dst_section_id, section_num, name, summary, sequence_mod_id):
    """Klont ein Section-Verzeichnis und aktualisiert section.xml."""
    src_path = os.path.join(out_dir, "sections", f"section_{src_section_id}")
    dst_path = os.path.join(out_dir, "sections", f"section_{dst_section_id}")
    if os.path.exists(dst_path):
        shutil.rmtree(dst_path, onerror=_remove_readonly)
    shutil.copytree(src_path, dst_path)
    _patch_section_xml(dst_path, dst_section_id, section_num, name, summary, sequence_mod_id)


def rebuild_archive_index(out_dir):
    """Regeneriert .ARCHIVE_INDEX aus dem tatsächlichen Verzeichnisinhalt."""
    entries = []
    mtime_fixed = 1768515358

    for dirpath, dirnames, filenames in os.walk(out_dir, topdown=True):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("__"))
        rel_dir = os.path.relpath(dirpath, out_dir).replace("\\", "/")
        if rel_dir == ".":
            rel_dir = ""
        if rel_dir:
            entries.append((rel_dir + "/", "d", 0, "?"))
        for fname in sorted(filenames):
            if fname.startswith("."):
                continue
            arcname = f"{rel_dir}/{fname}" if rel_dir else fname
            fsize = os.path.getsize(os.path.join(dirpath, fname))
            entries.append((arcname, "f", fsize, mtime_fixed))

    lines = [f"Moodle archive file index. Count: {len(entries)}"]
    lines += [f"{arc}\t{t}\t{s}\t{m}" for arc, t, s, m in entries]
    with open(os.path.join(out_dir, ".ARCHIVE_INDEX"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    log(f".ARCHIVE_INDEX regeneriert ({len(entries)} Einträge)", "OK")


def _rebuild_manifest_v2(out_dir, course_title, course_shortname, mbz_filename, units_activities, N):
    """Baut moodle_backup.xml für V2-Struktur komplett neu."""
    manifest_xml = os.path.join(out_dir, "moodle_backup.xml")
    tree = parse_xml_file(manifest_xml)
    root = tree.getroot()
    fname = os.path.basename(mbz_filename)
    quiz_section_id = 7 + N * 2

    for xpath, val in [
        (".//information/name", fname),
        (".//information/original_course_fullname", course_title),
        (".//information/original_course_shortname", course_shortname),
        (".//information/contents/course/title", course_shortname),
    ]:
        e = root.find(xpath)
        if e is not None:
            e.text = val
    for s in root.findall(".//settings/setting"):
        if s.findtext("name") == "filename":
            v = s.find("value")
            if v is not None:
                v.text = fname

    contents = root.find(".//contents")
    for tag in ("activities", "sections"):
        elem = contents.find(tag)
        if elem is not None:
            for child in list(elem):
                elem.remove(child)
        else:
            etree.SubElement(contents, tag)

    acts_elem = contents.find("activities")
    secs_elem = contents.find("sections")

    def add_act(mod_id, sec_id, modname, title, directory):
        a = etree.SubElement(acts_elem, "activity")
        etree.SubElement(a, "moduleid").text = str(mod_id)
        etree.SubElement(a, "sectionid").text = str(sec_id)
        etree.SubElement(a, "modulename").text = modname
        etree.SubElement(a, "title").text = title
        etree.SubElement(a, "directory").text = directory

    def add_sec(sec_id, title, directory):
        s = etree.SubElement(secs_elem, "section")
        etree.SubElement(s, "sectionid").text = str(sec_id)
        etree.SubElement(s, "title").text = title
        etree.SubElement(s, "directory").text = directory

    add_act(2, 6, "forum", "Announcements", "activities/forum_2")
    add_sec(6, "0", "sections/section_6")
    for ua in units_activities:
        add_act(ua["page_mod_id"], ua["ss_section_id"], "page",
                f"Self-Study: {ua['unit_title']}", f"activities/page_{ua['page_mod_id']}")
        add_sec(ua["ss_section_id"], f"Self-Study", f"sections/section_{ua['ss_section_id']}")
        add_act(ua["assign_mod_id"], ua["ic_section_id"], "assign",
                f"In-Class: {ua['unit_title']}", f"activities/assign_{ua['assign_mod_id']}")
        add_sec(ua["ic_section_id"], f"In-Class", f"sections/section_{ua['ic_section_id']}")
    add_act(5, quiz_section_id, "quiz", "Abschlussquiz", "activities/quiz_5")
    add_sec(quiz_section_id, "Abschluss", f"sections/section_{quiz_section_id}")

    settings_elem = root.find(".//settings")
    if settings_elem is not None:
        for s in list(settings_elem.findall("setting")):
            if s.findtext("level") in ("activity", "section"):
                settings_elem.remove(s)

        def add_setting(level, key, suffix):
            s = etree.SubElement(settings_elem, "setting")
            etree.SubElement(s, "level").text = level
            etree.SubElement(s, "activity" if level == "activity" else "section").text = key
            etree.SubElement(s, "name").text = f"{key}_{suffix}"
            etree.SubElement(s, "value").text = "1"

        for sfx in ("included", "userinfo"):
            add_setting("section", "section_6", sfx)
            add_setting("activity", "forum_2", sfx)
        for ua in units_activities:
            pg = f"page_{ua['page_mod_id']}"
            asg = f"assign_{ua['assign_mod_id']}"
            ss = f"section_{ua['ss_section_id']}"
            ic = f"section_{ua['ic_section_id']}"
            for sfx in ("included", "userinfo"):
                add_setting("section", ss, sfx)
                add_setting("activity", pg, sfx)
                add_setting("section", ic, sfx)
                add_setting("activity", asg, sfx)
        qs = f"section_{quiz_section_id}"
        for sfx in ("included", "userinfo"):
            add_setting("section", qs, sfx)
            add_setting("activity", "quiz_5", sfx)

    write_xml_file(manifest_xml, tree)
    log("moodle_backup.xml (V2) regeneriert", "OK")


def _build_v1_core(args, input_data):
    """V1-Kern: Template + Activities patchen (legacy activities-Format)."""
    print("\n[3] Template kopieren")
    copy_template(args.template, args.build_dir)

    print("\n[4] Kurs-Metadata patchen")
    metadata = input_data.get("course_metadata", {})
    if metadata:
        patch_course_metadata(args.build_dir, metadata)
    else:
        log("Keine course_metadata in input.json, überspringe", "WARN")

    print("\n[5] Sections patchen")
    sections = input_data.get("sections", {})
    if sections:
        patch_sections(args.build_dir, sections)
    else:
        log("Keine sections in input.json, überspringe", "WARN")

    print("\n[6] Activities patchen")
    patch_activities_v1(args.build_dir, input_data)

    print("\n[7] Backup-Metadaten patchen")
    patch_backup_manifest(args.build_dir, input_data, args.out)
    patch_question_categories(args.build_dir, input_data)

    print("\n[8] .mbz-Datei erstellen")
    create_mbz(args.build_dir, args.out)


def build_v2(args, input_data):
    """Pipeline V2: Self-Study / In-Class / Abschlussquiz Struktur."""
    units = input_data.get("units", [])
    N = len(units)
    course_title = (input_data.get("title") or
                    input_data.get("course_metadata", {}).get("fullname", "Kurs"))
    raw_short = input_data.get("course_metadata", {}).get("shortname", "")
    course_shortname = raw_short or course_title.lower().replace(" ", "_")[:20]
    lang = input_data.get("language", "de")

    log(f"V2-Modus: {N} Lerneinheiten | {course_title}")

    print("\n[3] Template kopieren")
    copy_template(args.template, args.build_dir)

    print("\n[4] Kurs-Metadata patchen")
    patch_course_metadata(args.build_dir, {
        "fullname": course_title, "shortname": course_shortname, "lang": lang,
    })

    print("\n[5] Lerneinheiten verarbeiten")
    units_activities = []

    for i, unit in enumerate(units, start=1):
        page_mod_id   = 9 + i           # 10, 11, 12, ...
        assign_mod_id = 19 + i          # 20, 21, 22, ...
        ss_section_id = 5 + i * 2       # 7, 9, 11, ...
        ic_section_id = 6 + i * 2       # 8, 10, 12, ...
        ss_section_num = 2 * i - 1      # 1, 3, 5, ...
        ic_section_num = 2 * i          # 2, 4, 6, ...
        page_ctx_id   = 100 + i
        assign_ctx_id = 200 + i
        unit_title = unit.get("title", f"Einheit {i}")

        log(f"Einheit {i}: {unit_title}")

        # Page klonen + patchen
        page_key = f"page_{page_mod_id}"
        _clone_activity_dir(args.build_dir, "page_3", page_key,
                            page_mod_id, ss_section_id, ss_section_num, page_ctx_id)
        page_xml = os.path.join(args.build_dir, "activities", page_key, "page.xml")
        patch_page_activity(page_xml, {
            "name": f"Self-Study: {unit_title}",
            "content_html": _unit_selfstudy_html(unit),
        })

        # Assign klonen + patchen
        assign_key = f"assign_{assign_mod_id}"
        _clone_activity_dir(args.build_dir, "assign_4", assign_key,
                            assign_mod_id, ic_section_id, ic_section_num, assign_ctx_id)
        assign_xml = os.path.join(args.build_dir, "activities", assign_key, "assign.xml")
        patch_assign_activity(assign_xml, {
            "name": f"In-Class: {unit_title}",
            "intro_html": _unit_inclass_html(unit),
        })
        grades_xml = os.path.join(args.build_dir, "activities", assign_key, "grades.xml")
        if os.path.exists(grades_xml):
            t = parse_xml_file(grades_xml)
            r = t.getroot()
            for e in r.findall(".//itemname"):
                e.text = f"In-Class: {unit_title}"
            write_xml_file(grades_xml, t)

        # Sections anlegen
        if i == 1:
            ss_dir = os.path.join(args.build_dir, "sections", "section_7")
            _patch_section_xml(ss_dir, 7, ss_section_num,
                               f"Self-Study 1: {unit_title}", "", page_mod_id)
            ic_dir = os.path.join(args.build_dir, "sections", "section_8")
            _patch_section_xml(ic_dir, 8, ic_section_num,
                               f"In-Class 1: {unit_title}", "", assign_mod_id)
        else:
            _clone_section_dir(args.build_dir, 7, ss_section_id, ss_section_num,
                               f"Self-Study {i}: {unit_title}", "", page_mod_id)
            _clone_section_dir(args.build_dir, 8, ic_section_id, ic_section_num,
                               f"In-Class {i}: {unit_title}", "", assign_mod_id)

        units_activities.append({
            "unit_title": unit_title,
            "page_mod_id": page_mod_id,
            "assign_mod_id": assign_mod_id,
            "ss_section_id": ss_section_id,
            "ic_section_id": ic_section_id,
        })
        log(f"  → {page_key} + {assign_key} (sections {ss_section_id}/{ic_section_id})", "OK")

    # Template-Blueprints entfernen (wurden nur als Klonquelle genutzt)
    for key in ("page_3", "assign_4"):
        p = os.path.join(args.build_dir, "activities", key)
        if os.path.exists(p):
            shutil.rmtree(p, onerror=_remove_readonly)

    print("\n[6] Abschlussquiz")
    quiz_section_id  = 7 + N * 2
    quiz_section_num = N * 2 + 1
    _clone_section_dir(args.build_dir, 8, quiz_section_id, quiz_section_num,
                       "Abschlussquiz", "", 5)

    quiz_mod_xml = os.path.join(args.build_dir, "activities", "quiz_5", "module.xml")
    if os.path.exists(quiz_mod_xml):
        t = parse_xml_file(quiz_mod_xml)
        r = t.getroot()
        for tag, val in [("sectionid", quiz_section_id), ("sectionnumber", quiz_section_num)]:
            e = r.find(tag)
            if e is not None:
                e.text = str(val)
        write_xml_file(quiz_mod_xml, t)

    quiz_questions = _collect_final_quiz_questions(units)
    if quiz_questions:
        questions_xml = os.path.join(args.build_dir, "questions.xml")
        patch_quiz_questions(questions_xml, quiz_questions)
        quiz_xml = os.path.join(args.build_dir, "activities", "quiz_5", "quiz.xml")
        patch_quiz_instances(quiz_xml, quiz_questions)
        patch_activity_display_metadata(args.build_dir, "quiz_5", "quiz",
                                        {"name": "Abschlussquiz"})
        log(f"  → {len(quiz_questions)} Frage(n) im Abschlussquiz", "OK")
    else:
        log("  Keine single_choice-Fragen gefunden – Quiz bleibt leer", "WARN")

    patch_question_categories(args.build_dir, {
        "course_metadata": {"fullname": course_title, "shortname": course_shortname},
        "activities": {"quiz_5": {"type": "quiz", "name": "Abschlussquiz"}},
    })

    print("\n[7] .ARCHIVE_INDEX regenerieren")
    rebuild_archive_index(args.build_dir)

    print("\n[8] Backup-Manifest neu bauen")
    _rebuild_manifest_v2(args.build_dir, course_title, course_shortname,
                         args.out, units_activities, N)

    print("\n[9] .mbz-Datei erstellen")
    create_mbz(args.build_dir, args.out)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Moodle pAIpline – erzeugt .mbz aus Template + input.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python build_v1.py
  python build_v1.py --input mein_kurs.json
  python build_v1.py --input kurs.json --template backup_physik/ --out physik.mbz
        """,
    )
    parser.add_argument("--input", default=DEFAULT_INPUT_FILE,
                        help=f"Input-JSON (Standard: {DEFAULT_INPUT_FILE})")
    parser.add_argument("--template", default=DEFAULT_TEMPLATE_DIR,
                        help=f"Template-Verzeichnis (Standard: {DEFAULT_TEMPLATE_DIR})")
    parser.add_argument("--out", default=DEFAULT_OUTPUT_MBZ,
                        help=f"Ausgabe-Datei (Standard: {DEFAULT_OUTPUT_MBZ})")
    parser.add_argument("--build-dir", default=DEFAULT_OUTPUT_DIR,
                        help=f"Temporäres Build-Verzeichnis (Standard: {DEFAULT_OUTPUT_DIR})")
    return parser.parse_args()


def main():
    args = parse_args()

    print("\n" + "=" * 70)
    print("Moodle pAIpline – Kurs-Generator")
    print("=" * 70 + "\n")

    try:
        print("[1] Validierung")
        validate_template_structure(args.template)

        print("\n[2] Input laden")
        input_data = load_input(args.input)

        # Format erkennen: V2 (units[]) oder V1 (activities{})
        if "units" in input_data:
            log("Format: V2 – Self-Study / In-Class / Abschlussquiz", "OK")
            build_v2(args, input_data)
        else:
            log("Format: V1 – Activities-basiert (Legacy)", "OK")
            _build_v1_core(args, input_data)

        print("\n" + "=" * 70)
        print("✅ ERFOLG! Kursdatei erzeugt: " + args.out)
        print("=" * 70)
        print("\nNächste Schritte:")
        print("  1. In Moodle: Kurs → Course administration → Restore")
        print("  2. " + args.out + " auswählen")
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
