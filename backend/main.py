from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
from urllib.parse import urlparse

# Импорты наших модулей
from agents.orchestrator import process_request, approve_and_generate, revise_session, clarify_and_classify
from state_store import get_session, init_db
from export import export_to_docx, export_to_pptx, export_tests_to_lms, export_to_json
from services.reference_parser import save_and_parse_reference
from agents.validator import run_full_validation, validate_coverage_with_content
from schemas import GenerateRequest, RevisionRequest
from cloud import LLMServiceError

app = FastAPI(title="ACR AI Agent", version="1.0.0")

# [ТРЕБОВАНИЕ КЕЙСА]: Безопасный CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://tochka-sborki-2026-team-058.hub.gigaschool.ru"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# [ТРЕБОВАНИЕ КЕЙСА]: Security Headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# [ТРЕБОВАНИЕ КЕЙСА]: Обработка ошибок LLM
@app.exception_handler(LLMServiceError)
async def llm_exception_handler(request: Request, exc: LLMServiceError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "LLM Error", "detail": exc.message}
    )

# [ТРЕБОВАНИЕ КЕЙСА]: Валидация URL моделей при старте
@app.on_event("startup")
def startup_event():
    init_db()
    base_url = os.getenv("OPENAI_BASE_URL", "")
    if base_url:
        parsed = urlparse(base_url)
        if not all([parsed.scheme, parsed.netloc]):
            raise ValueError(f"Некорректный OPENAI_BASE_URL: {base_url}")
    print("✅ База данных инициализирована. Валидация URL пройдена.")

# --- СЛУЖЕБНЫЕ ЭНДПОИНТЫ ---

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "acr-ai-agent", "version": "1.0.0"}

class ClarifyRequest(BaseModel):
    topic: str
    hours: int | None = None

@app.post("/api/clarify")
def clarify_endpoint(req: ClarifyRequest):
    """[ТРЕБОВАНИЕ КЕЙСА]: Уточняющие вопросы и автовыбор шаблона до генерации."""
    return clarify_and_classify(req.topic, req.hours)

# --- ОСНОВНОЙ СЦЕНАРИЙ ---

@app.post("/api/generate")
def generate_framework_endpoint(req: GenerateRequest):
    """
    Шаг 1: Прием запроса, референсов, ограничений и генерация каркаса.
    Если часа нет — вернет статус clarification_needed.
    """
    return process_request(
        topic=req.topic, 
        hours=req.hours, 
        template_type=req.template_type, 
        reference_text=req.reference_text,
        constraints=req.constraints
    )

@app.post("/api/revise/{session_id}")
def revise_endpoint(session_id: str, req: RevisionRequest):
    """[ТРЕБОВАНИЕ КЕЙСА]: Точечная доработка."""
    return revise_session(session_id, req.instruction)

@app.post("/api/approve/{session_id}")
def approve_endpoint(session_id: str):
    """Шаг 2: Human-in-the-loop. Утверждение каркаса и генерация контента."""
    return approve_and_generate(session_id)

@app.get("/api/report/{session_id}")
def get_validation_report(session_id: str):
    """[ТРЕБОВАНИЕ КЕЙСА]: Расширенный отчет автопроверки."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    
    base_report = run_full_validation(session["framework"])
    
    if session["status"] == "completed" and session["content"]:
        coverage = validate_coverage_with_content(session["framework"], session["content"])
        base_report["deep_coverage"] = coverage
        
    return {"session_id": session_id, "report": base_report}

@app.post("/api/upload-reference")
async def upload_reference(file: UploadFile = File(...)):
    """[ТРЕБОВАНИЕ КЕЙСА]: Прием референсов (.docx / .pdf / .txt)."""
    text = await save_and_parse_reference(file)
    return {
        "status": "success", 
        "filename": file.filename,
        "text_preview": text[:200],
        "full_text": text
    }

# --- ЭКСПОРТ ФАЙЛОВ (Строго GET для прямых ссылок) ---

@app.get("/api/export-docx/{session_id}")
def export_docx_endpoint(session_id: str):
    session = get_session(session_id)
    if not session or session["status"] != "completed":
        raise HTTPException(status_code=400, detail="Сессия не готова")
    filename = f"program_{session_id[:8]}.docx"
    export_to_docx(session["framework"], session["content"], filename)
    return FileResponse(filename, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=filename)

@app.get("/api/export-pptx/{session_id}")
def export_pptx_endpoint(session_id: str):
    session = get_session(session_id)
    if not session or session["status"] != "completed":
        raise HTTPException(status_code=400, detail="Контент не сгенерирован")
    filename = f"presentation_{session_id[:8]}.pptx"
    export_to_pptx(session["framework"], session["content"], filename)
    return FileResponse(filename, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", filename=filename)

@app.get("/api/export-lms/{session_id}")
def export_lms_endpoint(session_id: str):
    session = get_session(session_id)
    if not session or session["status"] != "completed":
        raise HTTPException(status_code=400, detail="Контент не сгенерирован")
    filename = f"tests_{session_id[:8]}.txt"
    export_tests_to_lms(session["content"].get("tests", []), filename)
    return FileResponse(filename, media_type="text/plain", filename=filename)

@app.get("/api/export-json/{session_id}")
def export_json_endpoint(session_id: str):
    """[ТРЕБОВАНИЕ КЕЙСА]: Выгрузка всего комплекта в JSON."""
    session = get_session(session_id)
    if not session or not session["content"]:
        raise HTTPException(status_code=400, detail="Контент не сгенерирован")
    filename = f"bundle_{session_id[:8]}.json"
    export_to_json(session["framework"], session["content"], filename)
    return FileResponse(filename, media_type="application/json", filename=filename)

# --- РАЗДАЧА ФРОНТЕНДА ---
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    @app.get("/")
    def no_frontend():
        return {"message": "Frontend not built yet."}