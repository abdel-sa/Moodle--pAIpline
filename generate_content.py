#!/usr/bin/env python3
"""
Optional: LLM-Integration (Konzept)
Zeigt, wie du später ein LLM nutzen kannst, um input.json automatisch zu generieren
"""

import json
import sys

# ===========================================================================
# BEISPIEL 1: Statische Test-Fragen (kein LLM-Call)
# ===========================================================================

def generate_content_static(topic: str) -> dict:
    """
    Generiert input.json basierend auf einem Topic.
    Für Test-Zwecke: statische Antworten.
    """
    
    content_map = {
        "brüche": {
            "page": {
                "name": "Einführung in Brüche",
                "content_html": "<h1>Was sind Brüche?</h1><p>Ein Bruch ist ein Teil eines Ganzen...</p>"
            },
            "assign": {
                "name": "Aufgabe: Brüche erkennen",
                "intro_html": "<p>Identifiziere die Brüche in den Bildern...</p>"
            },
            "quiz": {
                "questions": [
                    {
                        "qbe_id": 1,
                        "question_id": 1,
                        "name": "Frage 1: 1/2 + 1/2",
                        "questiontext_html": "<p>Was ist 1/2 + 1/2?</p>",
                        "answers": [
                            {"text_html": "<p>1</p>", "fraction": 1.0},
                            {"text_html": "<p>1/2</p>", "fraction": 0.0},
                        ]
                    }
                ]
            }
        }
    }
    
    topic_lower = topic.lower()
    if topic_lower in content_map:
        data = content_map[topic_lower]
    else:
        # Fallback für unbekannte Topics
        data = {
            "page": {
                "name": f"Topic: {topic}",
                "content_html": f"<h1>{topic}</h1><p>Inhalt folgt...</p>"
            },
            "assign": {
                "name": f"Aufgabe: {topic}",
                "intro_html": f"<p>Aufgabe zu {topic}</p>"
            },
            "quiz": {
                "questions": [
                    {
                        "qbe_id": 1,
                        "question_id": 1,
                        "name": f"Frage: {topic}",
                        "questiontext_html": f"<p>Frage zu {topic}?</p>",
                        "answers": [
                            {"text_html": "<p>Ja</p>", "fraction": 1.0},
                            {"text_html": "<p>Nein</p>", "fraction": 0.0},
                        ]
                    }
                ]
            }
        }
    
    return {
        "course_metadata": {
            "fullname": f"Kurs: {topic}",
            "shortname": topic.lower().replace(" ", "_")
        },
        "activities": {
            "page_3": {
                "type": "page",
                **data["page"]
            },
            "assign_4": {
                "type": "assign",
                **data["assign"]
            },
            "quiz_5": {
                "type": "quiz",
                "name": "Quiz",
                **data["quiz"]
            }
        }
    }

# ===========================================================================
# BEISPIEL 2: OpenAI API Integration (für später)
# ===========================================================================

"""
Pseudo-Code für OpenAI-Integration (benötigt: pip install openai)

import openai

def generate_content_openai(topic: str, api_key: str) -> dict:
    '''Nutzt OpenAI, um Kursinhalte zu generieren'''
    
    openai.api_key = api_key
    
    # Prompt für LLM
    prompt = f'''
    Generiere Kursinhalte für das Thema: {topic}
    
    Format: JSON
    Felder:
    - page_content: HTML-Text (Einführung)
    - assign_intro: HTML-Text (Aufgabe)
    - quiz_questions: Array mit mindestens 3 Fragen
      - name: Fragentitel
      - questiontext: Frage
      - answers: Array [
          {{"text": "Antwort", "is_correct": true/false}},
          ...
        ]
    
    Antworte nur mit JSON, kein Markdown.
    '''
    
    # API-Call
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {{"role": "user", "content": prompt}}
        ],
        temperature=0.7
    )
    
    # Parse LLM-Output
    llm_output = response.choices[0].message.content
    llm_data = json.loads(llm_output)
    
    # Transformiere zu unserem Format
    return {
        "course_metadata": {
            "fullname": f"Kurs: {topic}",
            "shortname": topic.lower().replace(" ", "_")
        },
        "activities": {
            "page_3": {
                "type": "page",
                "name": f"Einführung: {topic}",
                "content_html": llm_data["page_content"]
            },
            "assign_4": {
                "type": "assign",
                "name": f"Aufgabe: {topic}",
                "intro_html": llm_data["assign_intro"]
            },
            "quiz_5": {
                "type": "quiz",
                "name": f"Quiz: {topic}",
                "questions": [
                    {
                        "qbe_id": idx + 1,
                        "question_id": idx + 1,
                        "name": q["name"],
                        "questiontext_html": f"<p>{q['questiontext']}</p>",
                        "answers": [
                            {
                                "text_html": f"<p>{a['text']}</p>",
                                "fraction": 1.0 if a["is_correct"] else 0.0
                            }
                            for a in q["answers"]
                        ]
                    }
                    for idx, q in enumerate(llm_data["quiz_questions"])
                ]
            }
        }
    }
'''

# ===========================================================================
# BEISPIEL 3: Ollama (Open-Source LLM, lokal)
# ===========================================================================

"""
Für Ollama (benötigt: ollama >= 0.1, pip install ollama)

import ollama

def generate_content_ollama(topic: str, model: str = "llama2") -> dict:
    '''Nutzt Ollama (lokales LLM)'''
    
    prompt = f'''
    Du bist ein Lehrer. Erstelle Kursmaterialien für: {topic}
    
    Format: JSON mit folgenden Feldern:
    {{
      "page_content": "<h1>...</h1><p>...</p>",
      "assign_intro": "<p>...</p>",
      "quiz_questions": [
        {{
          "name": "Frage 1",
          "text": "Frage",
          "answers": [
            {{"text": "Antwort A", "correct": true}},
            {{"text": "Antwort B", "correct": false}}
          ]
        }}
      ]
    }}
    
    Antworte nur mit JSON.
    '''
    
    response = ollama.generate(
        model=model,
        prompt=prompt,
        stream=False
    )
    
    llm_data = json.loads(response['response'])
    
    # Wie OpenAI: transformiere zu unserem Format
    # ... (siehe oben)
'''

# ===========================================================================
# CLI-INTERFACE
# ===========================================================================

def main():
    """CLI: Generiert input.json aus Topic"""
    
    if len(sys.argv) < 2:
        print("Verwendung: python generate_content.py <TOPIC>")
        print("Beispiel: python generate_content.py brüche")
        print("\nTopics mit statischen Inhalten: brüche")
        sys.exit(1)
    
    topic = " ".join(sys.argv[1:])
    
    # Für Demo: nutze statische Generierung
    content = generate_content_static(topic)
    
    # Speichere als input.json
    output_file = "input.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
    
    print(f"✓ {output_file} erzeugt aus Topic: {topic}")
    print(f"\nNächster Schritt: python build_v1.py")

if __name__ == "__main__":
    main()
