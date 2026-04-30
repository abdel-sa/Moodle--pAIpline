import os
import sys
import asyncio
import shutil
from pathlib import Path

# Windows: SelectorEventLoop doesn't support subprocesses — ProactorEventLoop required
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, WebSocket, WebSocketDisconnect
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
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

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
running_process: Optional[asyncio.subprocess.Process] = None

async def stream_subprocess(cmd: List[str], cwd: str = "."):
    global running_process
    
    await manager.broadcast(f"> Running command: {' '.join(cmd)}\n")
    
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        running_process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            stdin=asyncio.subprocess.PIPE
        )
        
        while True:
            # Read line by line
            line = await running_process.stdout.readline()
            if not line:
                break
            
            decoded_line = line.decode('utf-8', errors='replace')
            await manager.broadcast(decoded_line)
            
        await running_process.wait()
        await manager.broadcast(f"\n[Process finished with exit code {running_process.returncode}]\n")
        
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        await manager.broadcast(f"\n[Error running process: {repr(e)}\n{err_msg}]\n")
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
                await running_process.stdin.drain()
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
    if running_process is not None:
        return JSONResponse(status_code=400, content={"message": "A process is already running"})
    
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

@app.post("/api/workflow/topic-to-course")
async def run_workflow_b(req: WorkflowBRequest, background_tasks: BackgroundTasks):
    global running_process
    if running_process is not None:
        return JSONResponse(status_code=400, content={"message": "A process is already running"})
    
    input_json = UPLOAD_DIR / f"input_{req.topic.replace(' ', '_')}.json"
    mbz_out = OUTPUT_DIR / f"course_{req.topic.replace(' ', '_')}.mbz"
    
    async def task():
        # Step 1: Generate Content
        cmd_gen = [sys.executable, "generate_content.py", req.topic,
                   "--provider", req.provider,
                   "--model", req.model,
                   "--out", str(input_json)]
        await stream_subprocess(cmd_gen)
        
        # Step 2: Build MBZ
        if input_json.exists():
            cmd_build = [sys.executable, "build_v1.py",
                         "--input", str(input_json),
                         "--out", str(mbz_out)]
            await stream_subprocess(cmd_build)

    background_tasks.add_task(task)
    return {"message": "Workflow B started"}

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
