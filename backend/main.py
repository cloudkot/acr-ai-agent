from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from agents.orchestrator import process_request, approve_and_generate, revise_session
from state_store import get_session, init_db
from export import export_to_docx, export_to_pptx, export_tests_to_lms
from services.reference_parser import save_and_parse_reference
from agents.validator import run_full_validation
from schemas import GenerateRequest, RevisionRequest
from cloud import LLMServiceError
import os

app = FastAPI(title="ACR AI Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

@app.exception_handler(LLMServiceError)
async def llm_exception_handler(request: Request, exc: LLMServiceError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "LLM Error", "detail": exc.message}
    )

@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "acr-ai-agent", "version": "1.0.0"}

@app.post("/api/generate")
def generate_framework_endpoint(req: GenerateRequest):
    return process_request(req.topic, req.hours, req.template_type)

@app.post("/api/revise/{session_id}")
def revise_endpoint(session_id: str, req: RevisionRequest):
    return revise_session(session_id, req.instruction)

@app.post("/api/approve/{session_id}")
def approve_endpoint(session_id: str):
    return approve_and_generate(session_id)

@app.get("/api/report/{session_id}")
def get_validation_report(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    report = run_full_validation(session["framework"])
    return {"session_id": session_id, "report": report}

@app.post("/api/upload-reference")
async def upload_reference(file: UploadFile = File(...)):
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
    if not session or not session["content"]:
        raise HTTPException(status_code=400, detail="Контент не сгенерирован")
    filename = f"presentation_{session_id[:8]}.pptx"
    export_to_pptx(session["framework"], session["content"], filename)
    return FileResponse(path=filename, filename=filename, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")

@app.post("/api/export-lms/{session_id}")
def export_lms_endpoint(session_id: str):
    session = get_session(session_id)
    if not session or not session["content"]:
        raise HTTPException(status_code=400, detail="Контент не сгенерирован")
    filename = f"tests_{session_id[:8]}.txt"
    export_tests_to_lms(session["content"].get("tests", []), filename)
    return FileResponse(path=filename, filename=filename, media_type="text/plain")

frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    @app.get("/")
    def no_frontend():
        return {"message": "Frontend not built yet."}
