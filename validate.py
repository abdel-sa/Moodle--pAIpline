#!/usr/bin/env python3
import os
import sys
from pathlib import Path

def main():
    """
    Validates the setup for the Moodle pAIpline.
    Checks if required scripts, Python dependencies (lxml, requests), and the local Ollama instance are available.
    Returns 0 if all checks pass, otherwise 1.
    """
    all_ok = True
    missing = []
    
    print("\n[1] Pipeline-Scripts")
    for fname in ["pipeline.py", "validate.py", "verify.py"]:
        ok = os.path.isfile(fname)
        print(f"  {'✓' if ok else '✗'} {fname}")
        if not ok:
            missing.append(fname)
            all_ok = False
    
    print("\n[2] Dependencies")
    for dep in ["lxml", "requests"]:
        try:
            __import__(dep)
            print(f"  ✓ {dep}")
        except ImportError:
            print(f"  ✗ {dep}")
            all_ok = False
    
    print("\n[3] Ollama")
    try:
        import requests
        requests.get("http://localhost:11434/api/tags", timeout=2)
        print(f"  ✓ Ollama läuft")
    except:
        print(f"  ✗ Ollama nicht erreichbar")
    
    print("\n" + "=" * 40)
    if missing:
        print(f"FEHLER: Dateien fehlen: {', '.join(missing)}")
        return 1
    elif all_ok:
        print("OK - Alles bereit!")
    print("=" * 40 + "\n")
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
