from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel
import os
import time
from urllib.parse import urlparse

# Импорты модулей
from agents.orchestrator import process_request, approve_and_generate, revise_session, clarify_and_classify
from state_store import get_session, init_db, get_analytics
from export import (
    export_to_docx, export_to_pptx, export_tests_to_lms, 
    export_to_json, export_tests_to_moodle_xml
)
from services.reference_parser import save_and_parse_reference
from agents.validator import run_full_validation, validate_coverage_with_content, check_content_constraints
from schemas import GenerateRequest, RevisionRequest
from cloud import LLMServiceError
from logger import logger

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

# ==========================================
# ЕДИНЫЙ ФОРМАТ ОШИБОК
# ==========================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "error_code": "VALIDATION_ERROR",
            "message": "Неверный формат входных данных",
            "details": exc.errors()
        }
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "error_code": f"HTTP_{exc.status_code}",
            "message": exc.detail
        }
    )

@app.exception_handler(LLMServiceError)
async def llm_exception_handler(request: Request, exc: LLMServiceError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "error_code": "LLM_SERVICE_ERROR",
            "message": exc.message
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Критическая ошибка на {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "Внутренняя ошибка сервера.",
            "details": str(exc)
        }
    )

# [ТРЕБОВАНИЕ КЕЙСА]: Инициализация БД и валидация URL при старте
@app.on_event("startup")
async def startup_event():
    await init_db()
    base_url = os.getenv("OPENAI_BASE_URL", "")
    if base_url:
        parsed = urlparse(base_url)
        if not all([parsed.scheme, parsed.netloc]):
            raise ValueError(f"Некорректный OPENAI_BASE_URL: {base_url}")
    print("База данных инициализирована. Валидация URL пройдена.")

# --- СЛУЖЕБНЫЕ ЭНДПОИНТЫ ---

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "acr-ai-agent", "version": "1.0.0"}

class ClarifyRequest(BaseModel):
    topic: str
    hours: int | None = None

@app.post("/api/clarify")
async def clarify_endpoint(req: ClarifyRequest):
    """[ТРЕБОВАНИЕ КЕЙСА]: Уточняющие вопросы и автовыбор шаблона."""
    return await clarify_and_classify(req.topic, req.hours)

@app.get("/api/analytics")
async def analytics_endpoint():
    """[УНИКАЛЬНАЯ ФИЧА]: Глобальная аналитика для дашборда."""
    return await get_analytics()

# --- ОСНОВНОЙ СЦЕНАРИЙ ---

@app.post("/api/generate")
async def generate_framework_endpoint(req: GenerateRequest):
    """Шаг 1: Прием запроса и генерация каркаса."""
    return await process_request(
        topic=req.topic, 
        hours=req.hours, 
        template_type=req.template_type, 
        reference_text=req.reference_text,
        constraints=req.constraints
    )

@app.post("/api/revise/{session_id}")
async def revise_endpoint(session_id: str, req: RevisionRequest):
    """[ТРЕБОВАНИЕ КЕЙСА]: Точечная доработка каркаса."""
    return await revise_session(session_id, req.instruction)

@app.post("/api/approve/{session_id}")
async def approve_endpoint(session_id: str):
    """Шаг 2: Human-in-the-loop. Асинхронная генерация контента."""
    return await approve_and_generate(session_id)

@app.get("/api/report/{session_id}")
async def get_validation_report(session_id: str):
    """[ТРЕБОВАНИЕ КЕЙСА]: Расширенный отчет автопроверки."""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    
    base_report = run_full_validation(session["framework"])
    
    if session["status"] == "completed" and session["content"]:
        # 1. Проверка покрытия компетенций
        coverage = validate_coverage_with_content(session["framework"], session["content"])
        base_report["deep_coverage"] = coverage
        
        # 2. Проверка ограничений
        c_check = check_content_constraints(session["framework"], session["content"], session.get("constraints"))
        base_report["constraints_check"] = c_check
        
        # 3. Проверка полноты разделов
        completeness = {
            "has_tests": len(session["content"].get("tests", [])) > 0,
            "has_lectures": len(session["content"].get("lectures", [])) > 0,
            "has_seminars": len(session["content"].get("seminars", [])) > 0,
            "has_slides": len(session["content"].get("slides", [])) > 0,
            "has_work_programs": len(session["content"].get("work_programs", [])) > 0,
            "has_bibliography": len(session["content"].get("bibliography", [])) > 0
        }
        completeness["all_sections_present"] = all(completeness.values())
        base_report["completeness_check"] = completeness
        
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

# --- ЭКСПОРТ ФАЙЛОВ (Строго GET и Асинхронно) ---

@app.get("/api/export-docx/{session_id}")
async def export_docx_endpoint(session_id: str):
    start_time = time.time()
    session = await get_session(session_id)
    if not session or session["status"] != "completed":
        raise HTTPException(status_code=400, detail="Сессия не готова")
    c_check = check_content_constraints(session["framework"], session["content"], session.get("constraints"))
    filename = f"program_{session_id[:8]}.docx"
    
    generation_time = time.time() - start_time
    await export_to_docx(session["framework"], session["content"], filename, constraints_check=c_check, generation_time=generation_time)
    return FileResponse(filename, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=filename)

@app.get("/api/export-pptx/{session_id}")
async def export_pptx_endpoint(session_id: str):
    session = await get_session(session_id)
    if not session or session["status"] != "completed":
        raise HTTPException(status_code=400, detail="Контент не сгенерирован")
    c_check = check_content_constraints(session["framework"], session["content"], session.get("constraints"))
    filename = f"presentation_{session_id[:8]}.pptx"
    await export_to_pptx(session["framework"], session["content"], filename, constraints_check=c_check)
    return FileResponse(filename, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation", filename=filename)

@app.get("/api/export-lms/{session_id}")
async def export_lms_endpoint(session_id: str):
    session = await get_session(session_id)
    if not session or session["status"] != "completed":
        raise HTTPException(status_code=400, detail="Контент не сгенерирован")
    filename = f"tests_{session_id[:8]}.txt"
    await export_tests_to_lms(session["content"].get("tests", []), filename)
    return FileResponse(filename, media_type="text/plain", filename=filename)

@app.get("/api/export-moodle/{session_id}")
async def export_moodle_endpoint(session_id: str):
    session = await get_session(session_id)
    if not session or session["status"] != "completed":
        raise HTTPException(status_code=400, detail="Контент не сгенерирован")
    filename = f"moodle_{session_id[:8]}.xml"
    await export_tests_to_moodle_xml(session["content"].get("tests", []), filename)
    return FileResponse(filename, media_type="application/xml", filename=filename)

@app.get("/api/export-json/{session_id}")
async def export_json_endpoint(session_id: str):
    start_time = time.time()
    session = await get_session(session_id)
    if not session or not session["content"]:
        raise HTTPException(status_code=400, detail="Контент не сгенерирован")
    c_check = check_content_constraints(session["framework"], session["content"], session.get("constraints"))
    filename = f"bundle_{session_id[:8]}.json"
    
    generation_time = time.time() - start_time
    await export_to_json(session["framework"], session["content"], filename, constraints_check=c_check, generation_time=generation_time)
    return FileResponse(filename, media_type="application/json", filename=filename)

# --- РАЗДАЧА ФРОНТЕНДА ---
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    @app.get("/")
    def no_frontend():
        return {"message": "Frontend not built yet."}