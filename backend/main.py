from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agents.orchestrator import process_request, approve_and_generate, SESSIONS
from export import export_to_docx
from cloud import ask_llm
from export import export_to_docx, export_to_pptx
from fastapi.responses import FileResponse

app = FastAPI(title="ACR AI Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class GenerateReq(BaseModel):
    topic: str
    hours: int

@app.get("/")
def root():
    return {"status": "ok", "team": "VlPKteam"}

@app.get("/api/test-llm")
def test_llm():
    return {"llm_response": ask_llm("Скажи 'Привет'")}

@app.post("/api/generate")
def generate_framework_endpoint(req: GenerateReq):
    """Шаг 1: Генерация каркаса."""
    return process_request(req.topic, req.hours)

@app.post("/api/approve/{session_id}")
def approve_endpoint(session_id: str):
    """Шаг 2: Утверждение каркаса и генерация контента."""
    result = approve_and_generate(session_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@app.post("/api/export/{session_id}")
def export_endpoint(session_id: str):
    """Шаг 3: Экспорт в .docx."""
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
        
    session = SESSIONS[session_id]
    if session["status"] != "completed":
        raise HTTPException(status_code=400, detail="Контент еще не сгенерирован (сначала утвердите каркас)")
        
    filename = export_to_docx(session["framework"], session["content"])
    
    return {
        "status": "success",
        "message": f"Файл {filename} успешно сгенерирован на сервере.",
        "filename": filename
    }

@app.post("/api/export-pptx/{session_id}")
def export_pptx_endpoint(session_id: str):
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    
    session = SESSIONS[session_id]
    filename = f"presentation_{session_id[:8]}.pptx"
    
    export_to_pptx(session["framework"], filename)
    
    return FileResponse(
        path=filename, 
        filename=filename, 
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )