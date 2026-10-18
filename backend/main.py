from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from agents.orchestrator import process_request, approve_and_generate, revise_session
from state_store import get_session, init_db
from export import export_to_docx, export_to_pptx, export_tests_to_lms
from cloud import ask_llm
from services.reference_parser import save_and_parse_reference

app = FastAPI(title="ACR AI Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    # [ТРЕБОВАНИЕ КЕЙСА]: Инициализация персистентного State Store
    init_db()

class GenerateReq(BaseModel):
    topic: str
    hours: int

class RevisionReq(BaseModel):
    instruction: str

@app.get("/")
def root():
    return {"status": "ok", "team": "VlPKteam"}

@app.post("/api/generate")
def generate_framework_endpoint(req: GenerateReq):
    """Шаг 1: Генерация каркаса."""
    return process_request(req.topic, req.hours)

@app.post("/api/revise/{session_id}")
def revise_endpoint(session_id: str, req: RevisionReq):
    """[ТРЕБОВАНИЕ КЕЙСА]: Точечная доработка."""
    return revise_session(session_id, req.instruction)

@app.post("/api/approve/{session_id}")
def approve_endpoint(session_id: str):
    """Шаг 2: Утверждение каркаса и генерация контента."""
    return approve_and_generate(session_id)

@app.post("/api/upload-reference")
async def upload_reference(file: UploadFile = File(...)):
    """[ТРЕБОВАНИЕ КЕЙСА]: Прием референсов в .docx / .txt."""
    text = await save_and_parse_reference(file)
    return {"status": "success", "text_preview": text[:200]}

@app.post("/api/export-docx/{session_id}")
def export_docx_endpoint(session_id: str):
    session = get_session(session_id)
    if not session or session["status"] != "completed":
        raise HTTPException(status_code=400, detail="Сессия не готова")
    filename = f"program_{session_id[:8]}.docx"
    export_to_docx(session["framework"], session["content"], filename)
    return FileResponse(path=filename, filename=filename, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

@app.post("/api/export-pptx/{session_id}")
def export_pptx_endpoint(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    filename = f"presentation_{session_id[:8]}.pptx"
    export_to_pptx(session["framework"], filename)
    return FileResponse(path=filename, filename=filename, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")

@app.post("/api/export-lms/{session_id}")
def export_lms_endpoint(session_id: str):
    session = get_session(session_id)
    if not session or not session["content"]:
        raise HTTPException(status_code=400, detail="Контент не сгенерирован")
    filename = f"tests_{session_id[:8]}.csv"
    export_tests_to_lms(session["content"].get("tests", []), filename)
    return FileResponse(path=filename, filename=filename, media_type="text/csv")