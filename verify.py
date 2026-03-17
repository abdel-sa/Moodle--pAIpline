#!/usr/bin/env python3
import os

def main():
    """
    Displays the status of the current working directory for the Moodle pAIpline.
    Lists the number and names of text files (.txt), plan files (.json), and Moodle XML output files (.xml).
    """
    print("\n" + "=" * 50)
    print("MOODLE PIPELINE - STATUS")
    print("=" * 50)
    
    txt_files = [f for f in os.listdir(".") if f.endswith(".txt") and not f.startswith("_")]
    json_files = [f for f in os.listdir(".") if f.endswith("_plan.json") or f.endswith("plan.json")]
    xml_files = [f for f in os.listdir(".") if f.endswith(".xml") and not f.startswith("_")]
    
    print(f"\nTextdateien:        {len(txt_files)}")
    if txt_files:
        for txt in txt_files[:5]:
            print(f"  - {txt}")
        if len(txt_files) > 5:
            print(f"  ... und {len(txt_files) - 5} weitere")
    
    print(f"\nPlan-Dateien (.json): {len(json_files)}")
    if json_files:
        for json_f in json_files[:5]:
            print(f"  - {json_f}")
        if len(json_files) > 5:
            print(f"  ... und {len(json_files) - 5} weitere")
    
    print(f"\nXML-Dateien (.xml):  {len(xml_files)}")
    if xml_files:
        for xml_f in xml_files[:5]:
            print(f"  - {xml_f}")
        if len(xml_files) > 5:
            print(f"  ... und {len(xml_files) - 5} weitere")
    
    print("\n" + "=" * 50 + "\n")

if __name__ == "__main__":
    main()
