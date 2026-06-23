import os
import sys
import json
import re
import asyncio
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="Moodle pAIpline API")

# Allow CORS for local Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with specific frontend origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("out_build")
COURSES_DIR = Path("courses")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
COURSES_DIR.mkdir(exist_ok=True)


def _valid_course_id(course_id: str) -> bool:
    """Validates a course ID to prevent path traversal attacks."""
    return bool(re.match(r'^[a-zA-Z0-9_][a-zA-Z0-9_-]{0,63}$', course_id))

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

# Global state to keep track of the running process for interacting with stdin or stopping it
running_process: Optional[subprocess.Popen] = None

def _reset_if_dead():
    """Clears running_process if the subprocess has already exited."""
    global running_process
    if running_process is not None and running_process.poll() is not None:
        running_process = None

def _kill_running():
    """Terminates any running process unconditionally."""
    global running_process
    if running_process is not None:
        try:
            running_process.terminate()
        except Exception:
            pass
        running_process = None

async def stream_subprocess(cmd: List[str], cwd: str = ".", extra_env: dict = {}) -> int:
    """
    Runs cmd as a subprocess and streams stdout line-by-line to all WebSocket clients.
    Uses subprocess.Popen + run_in_executor to avoid asyncio event loop issues on Windows
    (SelectorEventLoop does not support create_subprocess_exec).
    """
    global running_process

    await manager.broadcast(f"> Running command: {' '.join(cmd)}\n")

    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env.update(extra_env)

        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
        )
        running_process = proc

        loop = asyncio.get_event_loop()

        while True:
            line = await loop.run_in_executor(None, proc.stdout.readline)
            if not line:
                break
            await manager.broadcast(line.decode("utf-8", errors="replace"))

        proc.wait()
        await manager.broadcast(f"\n[Process finished with exit code {proc.returncode}]\n")
        return int(proc.returncode or 0)

    except Exception as e:
        import traceback
        await manager.broadcast(f"\n[Error running process: {repr(e)}\n{traceback.format_exc()}]\n")
        return 1
    finally:
        running_process = None

@app.websocket("/ws/logs")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Receive input from user (e.g. "a", "r", "s" for interactive mode)
            data = await websocket.receive_text()
            global running_process
            if running_process and running_process.stdin:
                running_process.stdin.write((data + "\n").encode('utf-8'))
                running_process.stdin.flush()
                await manager.broadcast(f"> [Input sent: {data}]\n")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"filename": file.filename, "path": str(file_path)}

class WorkflowARequest(BaseModel):
    filename: str
    title: str
    category: str
    model: str = "mistral"

@app.post("/api/workflow/doc-to-questions")
async def run_workflow_a(req: WorkflowARequest, background_tasks: BackgroundTasks):
    global running_process
    _kill_running()
    
    file_path = UPLOAD_DIR / req.filename
    if not file_path.exists():
        return JSONResponse(status_code=404, content={"message": "File not found"})
    
    plan_out = UPLOAD_DIR / f"plan_{req.filename}.json"
    xml_out = OUTPUT_DIR / f"questions_{req.filename}.xml"
    
    # We will write a small wrapper script or just run them sequentially
    async def task():
        # Step 1: Plan
        cmd_plan = [sys.executable, "pipeline.py", "plan", 
                    "--chapter", str(file_path), 
                    "--title", req.title, 
                    "--base-category", req.category, 
                    "--out", str(plan_out), 
                    "--model", req.model]
        await stream_subprocess(cmd_plan)
        
        # Step 2: Generate
        if plan_out.exists():
            cmd_gen = [sys.executable, "pipeline.py", "generate", 
                       "--plan", str(plan_out), 
                       "--out", str(xml_out), 
                       "--interactive", 
                       "--model", req.model]
            await stream_subprocess(cmd_gen)

    background_tasks.add_task(task)
    return {"message": "Workflow A started"}

class WorkflowBRequest(BaseModel):
    topic: str
    provider: str = "ollama"
    model: str = "llama3.2"
    groq_api_key: str = ""
    gemini_api_key: str = ""
    cerebras_api_key: str = ""
    num_units: int = 5          # Number of teaching units (0 = old single-activity mode)
    ects: str = ""              # e.g. "3"
    target_audience: str = ""   # e.g. "Studierende im 1. Semester"
    extra_wishes: str = ""      # Optional extra instructions for the LLM
    detail: str = "compact"
    language: str = "de"

class CoursePlanRequest(WorkflowBRequest):
    pass

class GenerateUnitRequest(BaseModel):
    provider: str = "gemini"
    model: str = ""
    groq_api_key: str = ""
    gemini_api_key: str = ""
    cerebras_api_key: str = ""
    extra_wishes: str = ""
    detail: str = "compact"
    language: str = "de"

class CourseExportResponse(BaseModel):
    message: str
    filename: str
    download_url: str

def _safe_slug(text: str, max_len: int = 60) -> str:
    return re.sub(r'[^a-zA-Z0-9_-]', '_', text.replace(' ', '_'))[:max_len] or "course"

def _next_course_slug(base: str) -> str:
    base = _safe_slug(base, 48)
    idx = 1
    while (COURSES_DIR / f"{base}_v{idx}.json").exists():
        idx += 1
    return f"{base}_v{idx}"

def _provider_env(req) -> dict:
    extra_env = {}
    if getattr(req, "groq_api_key", ""):
        extra_env["GROQ_API_KEY"] = req.groq_api_key
    if getattr(req, "gemini_api_key", ""):
        extra_env["GEMINI_API_KEY"] = req.gemini_api_key
    if getattr(req, "cerebras_api_key", ""):
        extra_env["CEREBRAS_API_KEY"] = req.cerebras_api_key
    return extra_env

def _normalize_model(provider: str, model: str) -> str:
    if provider == "gemini" and model in ("gemini-3.5-flash", "gemini-3.5-flash-latest"):
        return "gemini-2.5-flash"
    return model

def _stamp_course_file(course_json: Path, course_id: str) -> None:
    if not course_json.exists():
        return
    data = json.loads(course_json.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).isoformat()
    data.setdefault("id", course_id)
    data.setdefault("createdAt", now)
    data["updatedAt"] = now
    course_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _course_warnings(data: dict) -> list[str]:
    warnings: list[str] = []
    units = data.get("units", [])
    if not units:
        return ["Keine Lerneinheiten vorhanden."]
    subject_text = f"{data.get('subject', '')} {data.get('title', '')}".lower()
    programming_topic = any(
        term in subject_text
        for term in ("python", "java", "javascript", "typescript", "programmier", "informatik", "coding", "software")
    )
    has_quiz = False
    has_assignment = False
    for idx, unit in enumerate(units, 1):
        prefix = f"Einheit {idx}"
        if not unit.get("learningObjectives"):
            warnings.append(f"{prefix}: keine Lernziele definiert.")
        blocks = unit.get("contentBlocks") or []
        if not blocks and not unit.get("theoryContent"):
            warnings.append(f"{prefix}: noch keine Inhalte/Aktivitaeten generiert.")
        content_length = sum(len(str(b.get("content", ""))) for b in blocks)
        if blocks and content_length < 900:
            warnings.append(f"{prefix}: Inhalte wirken noch zu knapp fuer eine vollstaendige Lehrveranstaltung.")
        block_text = " ".join(
            f"{b.get('type', '')} {b.get('title', '')} {b.get('content', '')}"
            for b in blocks
        ).lower()
        if not blocks:
            continue
        if not any(b.get("type") in ("activity", "quiz", "homework", "reflection") for b in blocks):
            warnings.append(f"{prefix}: keine Moodle-Aktivitaet gefunden.")
        if "self study" not in block_text and "self-study" not in block_text and "homework" not in block_text:
            warnings.append(f"{prefix}: Self-Study-Anteil fehlt oder ist nicht klar benannt.")
        if any(b.get("type") == "quiz" for b in blocks) or unit.get("questions"):
            has_quiz = True
        if "assignment" in block_text or "abgabe" in block_text or "hand-in" in block_text:
            has_assignment = True
        for q in unit.get("questions", []):
            if q.get("questionType") == "coderunner" and not programming_topic:
                warnings.append(f"{prefix}: CodeRunner-Frage passt nicht zum Fachgebiet.")
    if not has_quiz:
        warnings.append("Kein Quiz- oder Pruefungsbestandteil gefunden.")
    if not has_assignment:
        warnings.append("Keine Assignment-/Abgabe-Aktivitaet erkennbar.")
    return warnings

def _html_text(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("\n", "<br>")

def _answer_to_moodle(answer: object, fallback_correct: Optional[object] = None) -> dict:
    if isinstance(answer, dict):
        text = answer.get("text", answer.get("answer", answer.get("label", "")))
        is_correct = bool(answer.get("isCorrect", answer.get("correct", False)))
    else:
        text = answer
        is_correct = fallback_correct is not None and str(answer).strip() == str(fallback_correct).strip()

    return {
        "text_html": f"<p>{_html_text(text)}</p>",
        "fraction": 1.0 if is_correct else 0.0,
    }

def _question_to_moodle(q: dict, qbe_id: int) -> Optional[dict]:
    if not isinstance(q, dict):
        return None

    q_type = q.get("questionType", "")
    question = q.get("question", "").strip()
    if not question:
        return None

    if q_type == "true_false":
        answers = [
            {"text_html": "<p>Wahr</p>", "fraction": 1.0 if q.get("isTrue") else 0.0},
            {"text_html": "<p>Falsch</p>", "fraction": 0.0 if q.get("isTrue") else 1.0},
        ]
    elif q.get("answers"):
        correct_answer = q.get("correctAnswer")
        answers = [_answer_to_moodle(a, correct_answer) for a in q.get("answers", [])]
    elif q.get("correctAnswer"):
        answers = [{"text_html": f"<p>{_html_text(q.get('correctAnswer'))}</p>", "fraction": 1.0}]
    else:
        return None

    if not answers:
        return None

    return {
        "qbe_id": qbe_id,
        "question_id": qbe_id,
        "name": question[:60],
        "questiontext_html": f"<p>{_html_text(question)}</p>",
        "answers": answers,
    }

def _course_editor_to_moodle_input(course: dict) -> dict:
    topic = course.get("subject") or course.get("title") or "Kurs"
    units = course.get("units", [])
    all_questions = []
    theory_parts = []
    assignment_parts = []
    seen_question_ids = set()

    for unit in units:
        unit_title = _html_text(unit.get("title", "Einheit"))
        theory_parts.append(f"<h2>{unit_title}</h2>")
        if unit.get("description"):
            theory_parts.append(f"<p>{_html_text(unit.get('description'))}</p>")
        if unit.get("theoryContent"):
            theory_parts.append(f"<p>{_html_text(unit.get('theoryContent'))}</p>")

        for block in unit.get("contentBlocks") or []:
            block_title = _html_text(block.get("title", "Block"))
            block_type = block.get("type", "")
            if block_type == "quiz":
                for q in block.get("questions") or []:
                    q_key = q.get("id") or f"{unit.get('id')}-{q.get('question')}"
                    if q_key in seen_question_ids:
                        continue
                    seen_question_ids.add(q_key)
                    moodle_q = _question_to_moodle(q, len(all_questions) + 1)
                    if moodle_q:
                        all_questions.append(moodle_q)
                continue

            content = _html_text(block.get("content", ""))
            if content:
                theory_parts.append(f"<h3>{block_title}</h3><p>{content}</p>")
            if block_type in {"activity", "homework", "reflection"} and content:
                assignment_parts.append(f"<h3>{unit_title}: {block_title}</h3><p>{content}</p>")

        for q in unit.get("questions") or []:
            q_key = q.get("id") or f"{unit.get('id')}-{q.get('question')}"
            if q_key in seen_question_ids:
                continue
            seen_question_ids.add(q_key)
            moodle_q = _question_to_moodle(q, len(all_questions) + 1)
            if moodle_q:
                all_questions.append(moodle_q)

    shortname = re.sub(r"[^a-z0-9_]", "", topic.lower().replace(" ", "_"))[:20] or "kurs"
    assignment_html = "".join(assignment_parts) or f"<p>Bearbeite die Aufgaben zum Kurs <strong>{_html_text(topic)}</strong>.</p>"

    return {
        "course_metadata": {
            "fullname": course.get("title", topic),
            "shortname": shortname,
            "summary": f"<p>{_html_text(course.get('description', ''))}</p>",
            "lang": course.get("language", "de"),
            "visible": True,
        },
        "sections": {
            "section_6": {"name": "Einführung", "summary": "<p>Kursübersicht.</p>"},
            "section_7": {"name": "Theorie", "summary": "<p>Alle Lerneinheiten.</p>"},
            "section_8": {"name": "Übungen & Quiz", "summary": "<p>Aufgaben und Lerncheck.</p>"},
        },
        "activities": {
            "page_3": {
                "type": "page",
                "name": f"Theorie: {topic}",
                "content_html": "".join(theory_parts) or "<p>Kein Inhalt.</p>",
            },
            "assign_4": {
                "type": "assign",
                "name": f"Aufgabe: {topic}",
                "intro_html": assignment_html,
            },
            "quiz_5": {
                "type": "quiz",
                "name": f"Quiz: {topic}",
                "questions": all_questions[:12],
            },
        },
    }

@app.post("/api/workflow/topic-to-course")
async def run_workflow_b(req: WorkflowBRequest, background_tasks: BackgroundTasks):
    global running_process
    _kill_running()

    slug        = _safe_slug(req.topic)
    export_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    input_json  = UPLOAD_DIR   / f"input_{slug}.json"
    mbz_out     = OUTPUT_DIR   / f"course_{slug}_{export_stamp}.mbz"
    build_dir   = OUTPUT_DIR   / f"build_{slug}"
    course_json = COURSES_DIR  / f"{slug}.json"

    extra_env = _provider_env(req)

    async def task():
        # Step 1: Generate Content (supports both single-activity and multi-unit modes)
        cmd_gen = [
            sys.executable, "generate_content.py", req.topic,
            "--provider", req.provider,
            "--model", _normalize_model(req.provider, req.model),
            "--out", str(input_json),
        ]
        if req.num_units > 0:
            cmd_gen += ["--num-units", str(req.num_units)]
        if req.ects:
            cmd_gen += ["--ects", req.ects]
        if req.target_audience:
            cmd_gen += ["--audience", req.target_audience]
        if req.extra_wishes:
            cmd_gen += ["--extra", req.extra_wishes]
        cmd_gen += ["--detail", req.detail, "--language", req.language]
        if req.num_units > 0:
            cmd_gen += ["--course-out", str(course_json)]

        await stream_subprocess(cmd_gen, extra_env=extra_env)

        # Step 2: Build MBZ — use V2 course JSON when available, else V1 input
        build_input = course_json if (req.num_units > 0 and course_json.exists()) else input_json
        if build_input.exists():
            cmd_build = [sys.executable, "build_v1.py",
                         "--input", str(build_input),
                         "--out", str(mbz_out),
                         "--build-dir", str(build_dir)]
            await stream_subprocess(cmd_build)

        # Step 3: If running in classic mode (num_units=0), still create a courses/ JSON
        if req.num_units == 0 and input_json.exists():
            try:
                raw = json.loads(input_json.read_text(encoding="utf-8"))
                course_data = _convert_input_to_course(raw, req.topic)
                course_json.write_text(
                    json.dumps(course_data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                await manager.broadcast(f"✓ Kurs-Editor JSON gespeichert: courses/{slug}.json\n")
            except Exception as e:
                await manager.broadcast(f"⚠ Konnte courses/-JSON nicht speichern: {e}\n")

        # Step 4: For multi-unit mode, stamp id/timestamps into the saved course JSON
        if req.num_units > 0 and course_json.exists():
            try:
                data = json.loads(course_json.read_text(encoding="utf-8"))
                now = datetime.now(timezone.utc).isoformat()
                data.setdefault("id", slug)
                data.setdefault("createdAt", now)
                data["updatedAt"] = now
                course_json.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                await manager.broadcast(f"✓ Kurs-Editor JSON gespeichert: courses/{slug}.json\n")
            except Exception as e:
                await manager.broadcast(f"⚠ Konnte Course-JSON nicht finalisieren: {e}\n")

    background_tasks.add_task(task)
    return {"message": "Workflow B started"}


@app.post("/api/workflow/course-plan")
async def create_course_plan(req: CoursePlanRequest, background_tasks: BackgroundTasks):
    """Generate only a Course Plan Preview and save it as a versioned course JSON."""
    global running_process
    _kill_running()

    course_id = _next_course_slug(req.topic)
    course_json = COURSES_DIR / f"{course_id}.json"
    input_json = UPLOAD_DIR / f"input_{course_id}.json"
    extra_env = _provider_env(req)

    async def task():
        cmd = [
            sys.executable, "generate_content.py", req.topic,
            "--provider", req.provider,
            "--model", _normalize_model(req.provider, req.model),
            "--out", str(input_json),
            "--num-units", str(req.num_units),
            "--course-out", str(course_json),
            "--plan-only",
            "--detail", req.detail,
            "--language", req.language,
        ]
        if req.ects:
            cmd += ["--ects", req.ects]
        if req.target_audience:
            cmd += ["--audience", req.target_audience]
        if req.extra_wishes:
            cmd += ["--extra", req.extra_wishes]

        await stream_subprocess(cmd, extra_env=extra_env)
        try:
            _stamp_course_file(course_json, course_id)
            await manager.broadcast(f"✓ Course Plan gespeichert: courses/{course_id}.json\n")
        except Exception as e:
            await manager.broadcast(f"⚠ Konnte Course Plan nicht finalisieren: {e}\n")

    background_tasks.add_task(task)
    return {"message": "Course plan generation started", "course_id": course_id}


@app.post("/api/courses/{course_id}/generate-unit/{unit_id}")
async def generate_course_unit(course_id: str, unit_id: str, req: GenerateUnitRequest):
    """Generate or regenerate a single unit and save the course immediately."""
    if not _valid_course_id(course_id):
        return JSONResponse(status_code=400, content={"message": "Ungültige Kurs-ID"})
    course_json = COURSES_DIR / f"{course_id}.json"
    if not course_json.exists():
        return JSONResponse(status_code=404, content={"message": "Kurs nicht gefunden"})

    raw = json.loads(course_json.read_text(encoding="utf-8"))
    topic = raw.get("subject") or raw.get("title") or course_id
    extra_env = _provider_env(req)

    cmd = [
        sys.executable, "generate_content.py", topic,
        "--provider", req.provider,
        "--model", _normalize_model(req.provider, req.model),
        "--course-in", str(course_json),
        "--course-out", str(course_json),
        "--generate-unit", unit_id,
        "--detail", req.detail or raw.get("detailLevel", "compact"),
        "--language", req.language or raw.get("language", "de"),
    ]
    if req.extra_wishes:
        cmd += ["--extra", req.extra_wishes]

    loop = asyncio.get_event_loop()

    def run_unit():
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env.update(extra_env)
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        print(result.stdout, flush=True)  # sichtbar im uvicorn-Terminal
        return result

    # Retry once on failure (handles transient LLM API errors)
    for attempt in range(2):
        result = await loop.run_in_executor(None, run_unit)
        await manager.broadcast(result.stdout)
        if result.returncode == 0:
            break
        if attempt == 0:
            await manager.broadcast(f"⚠ Einheit {unit_id}: Versuch 1 fehlgeschlagen (Code {result.returncode}), starte erneut…\n")

    if result.returncode != 0:
        return JSONResponse(
            status_code=500,
            content={"message": f"Einheit konnte nicht generiert werden. Prozess endete mit Code {result.returncode}."},
        )
    try:
        _stamp_course_file(course_json, course_id)
    except Exception as e:
        await manager.broadcast(f"⚠ Konnte Einheit nicht finalisieren: {e}\n")

    data = json.loads(course_json.read_text(encoding="utf-8"))
    data["_warnings"] = _course_warnings(data)
    return data

@app.post("/api/courses/{course_id}/export-mbz", response_model=CourseExportResponse)
async def export_course_mbz(course_id: str):
    """Build a Moodle .mbz backup from a saved Course Editor JSON."""
    if not _valid_course_id(course_id):
        return JSONResponse(status_code=400, content={"message": "Ungültige Kurs-ID"})

    course_json = COURSES_DIR / f"{course_id}.json"
    if not course_json.exists():
        return JSONResponse(status_code=404, content={"message": "Kurs nicht gefunden"})

    export_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"course_{course_id}_{export_stamp}.mbz"
    mbz_out = OUTPUT_DIR / filename
    build_dir = OUTPUT_DIR / f"build_{course_id}"

    await manager.broadcast(f"> Moodle-Backup wird erstellt: {filename}\n")

    cmd = [
        sys.executable,
        "build_v1.py",
        "--input",
        str(course_json),
        "--out",
        str(mbz_out),
        "--build-dir",
        str(build_dir),
    ]

    loop = asyncio.get_event_loop()

    def run_build():
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

    result = await loop.run_in_executor(None, run_build)
    await manager.broadcast(result.stdout)

    if result.returncode != 0 or not mbz_out.exists():
        await manager.broadcast(f"\n[MBZ export failed with exit code {result.returncode}]\n")
        return JSONResponse(
            status_code=500,
            content={"message": "Moodle-Backup konnte nicht erstellt werden."},
        )

    await manager.broadcast(f"\n✓ Moodle-Backup bereit: {filename}\n")
    return {
        "message": "Moodle-Backup erstellt",
        "filename": filename,
        "download_url": f"/api/download/{filename}",
    }

@app.post("/api/workflow/stop")
async def stop_workflow():
    global running_process
    if running_process is not None:
        try:
            running_process.terminate()
            await manager.broadcast("\n[Process terminated by user]\n")
            running_process = None
            return {"message": "Process terminated"}
        except Exception as e:
            return JSONResponse(status_code=500, content={"message": str(e)})
    return {"message": "No process running"}

@app.get("/api/download/{filename}")
async def download_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        # Check in uploads too if they want to download the plan or input.json
        file_path = UPLOAD_DIR / filename
        if not file_path.exists():
            return JSONResponse(status_code=404, content={"message": "File not found"})
    return FileResponse(file_path, filename=filename)


# ─── Converter: input.json format → Course Editor JSON ───────────────────────

def _convert_input_to_course(data: dict, topic: str) -> dict:
    """
    Converts the generate_content.py output format (input.json) to the
    comprehensive Course JSON format used by the Course Editor.
    """
    now = datetime.now(timezone.utc).isoformat()
    course_id = re.sub(r'[^a-zA-Z0-9_-]', '_', topic.replace(' ', '_'))[:60]
    meta = data.get("course_metadata", {})
    activities = data.get("activities", {})

    # Build a single main unit from page + assign + quiz activities
    questions = []
    quiz = activities.get("quiz_5", {})
    for i, q in enumerate(quiz.get("questions", []), 1):
        html = q.get("questiontext_html", "")
        # Strip simple <p>...</p> wrapper
        text = re.sub(r'^<p>|</p>$', '', html.strip())
        answers = []
        for j, ans in enumerate(q.get("answers", [])):
            ans_html = ans.get("text_html", "")
            ans_text = re.sub(r'^<p>|</p>$', '', ans_html.strip())
            answers.append({
                "id": f"a-{i:02d}-{j+1:02d}",
                "text": ans_text,
                "isCorrect": ans.get("fraction", 0.0) == 1.0,
            })
        questions.append({
            "id": f"q-{i:02d}",
            "questionType": "multiple-choice",
            "question": text,
            "answers": answers,
        })

    # Extract theory text from page_3
    page = activities.get("page_3", {})
    theory_html = page.get("content_html", "")

    # Build the units list with one comprehensive unit
    units = [{
        "id": "u01",
        "title": f"Einführung: {topic}",
        "description": meta.get("summary", "").replace("<p>", "").replace("</p>", "").strip(),
        "learningObjectives": [
            f"Die Grundbegriffe von {topic} kennen und erklären können",
            f"Wichtige Konzepte und Prinzipien von {topic} anwenden",
            f"Typische Aufgaben zu {topic} selbstständig lösen",
            "Verbindungen zwischen Theorie und Praxis herstellen",
        ],
        "theoryContent": re.sub(r'<[^>]+>', '', theory_html).strip(),
        "estimatedDuration": 90,
        "questions": questions,
    }]

    # If there's a separate assign, add it as a second unit
    assign = activities.get("assign_4", {})
    if assign:
        assign_html = assign.get("intro_html", "")
        units.append({
            "id": "u02",
            "title": f"Aufgaben: {topic}",
            "description": f"Praktische Übungsaufgaben zu {topic}",
            "learningObjectives": [
                f"Erlernte Konzepte zu {topic} praktisch anwenden",
                "Lösungsschritte nachvollziehbar dokumentieren",
            ],
            "theoryContent": re.sub(r'<[^>]+>', '', assign_html).strip(),
            "estimatedDuration": 60,
            "questions": [],
        })

    return {
        "id": course_id,
        "title": meta.get("fullname", topic),
        "description": meta.get("summary", "").replace("<p>", "").replace("</p>", "").strip(),
        "subject": topic,
        "targetAudience": "Schüler/innen und Lernende",
        "units": units,
        "createdAt": now,
        "updatedAt": now,
    }


# ─── Course CRUD API ──────────────────────────────────────────────────────────

@app.get("/api/courses")
async def list_courses():
    """Return a lightweight list of all courses (no full unit content)."""
    courses = []
    for f in sorted(COURSES_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            units = data.get("units", [])
            generated = sum(1 for u in units if u.get("contentBlocks"))
            courses.append({
                "id": data.get("id", f.stem),
                "title": data.get("title", "Untitled"),
                "description": data.get("description", ""),
                "subject": data.get("subject", ""),
                "unitCount": len(units),
                "generatedUnitCount": generated,
                "generationStatus": data.get("generationStatus", "complete" if generated == len(units) and units else "plan"),
                "updatedAt": data.get("updatedAt", ""),
            })
        except Exception:
            pass
    return courses


@app.get("/api/courses/{course_id}")
async def get_course(course_id: str):
    """Return the full course including all units and questions."""
    if not _valid_course_id(course_id):
        return JSONResponse(status_code=400, content={"message": "Ungültige Kurs-ID"})
    f = COURSES_DIR / f"{course_id}.json"
    if not f.exists():
        return JSONResponse(status_code=404, content={"message": "Kurs nicht gefunden"})
    data = json.loads(f.read_text(encoding="utf-8"))
    data["_warnings"] = _course_warnings(data)
    return data


@app.post("/api/courses")
async def create_course(request: Request):
    """Create a new course. Assigns a new UUID as ID."""
    data = await request.json()
    course_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    data["id"] = course_id
    data["createdAt"] = now
    data["updatedAt"] = now
    f = COURSES_DIR / f"{course_id}.json"
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


@app.put("/api/courses/{course_id}")
async def update_course(course_id: str, request: Request):
    """Replace the full course document (units + questions included)."""
    if not _valid_course_id(course_id):
        return JSONResponse(status_code=400, content={"message": "Ungültige Kurs-ID"})
    f = COURSES_DIR / f"{course_id}.json"
    if not f.exists():
        return JSONResponse(status_code=404, content={"message": "Kurs nicht gefunden"})
    data = await request.json()
    data["id"] = course_id
    data["updatedAt"] = datetime.now(timezone.utc).isoformat()
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


@app.delete("/api/courses/{course_id}")
async def delete_course(course_id: str):
    """Delete a course file permanently."""
    if not _valid_course_id(course_id):
        return JSONResponse(status_code=400, content={"message": "Ungültige Kurs-ID"})
    f = COURSES_DIR / f"{course_id}.json"
    if not f.exists():
        return JSONResponse(status_code=404, content={"message": "Kurs nicht gefunden"})
    f.unlink()
    return {"message": "Kurs gelöscht"}

if __name__ == "__main__":
    import uvicorn
    if sys.platform == "win32":
        # SelectorEventLoop (Windows default) doesn't support subprocesses.
        # Explicitly create a ProactorEventLoop and run uvicorn on it.
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        config = uvicorn.Config(app, host="127.0.0.1", port=8000, reload=False)
        server_instance = uvicorn.Server(config)
        loop.run_until_complete(server_instance.serve())
    else:
        uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
