import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from main import app
from schemas import Framework, Module, Competency
from state_store import init_db

client = TestClient(app)
init_db() # Инициализируем БД для тестов

# --- ПОДГОТОВКА МОК-ДАННЫХ (Строго по новой схеме) ---
MOCK_FRAMEWORK = Framework(
    goal="Программа разработана на основании 273-ФЗ",
    template_type="ДПО",
    prof_standard="Профстандарт 06.001",
    competencies=[Competency(name="Python", knowledge=["k"], skills=["s"])],
    # Модуль: 70 часов (10 ЛК + 10 ПР + 0 ЛБ + 50 СРС) + 2 часа аттестации = 72
    modules=[Module(title="M1", total_hours=70, lectures=10, practice=10, labs=0, srs=50)],
    total_hours=72,
    final_assessment_hours=2
)

MOCK_CONTENT = {
    "tests": [{"question": "Q1", "options": ["A", "B"], "correct_answer": "A", "related_competency": "Python"}],
    "seminars": [{"task": "T1", "criteria": "C1", "related_competency": "Python"}],
    "lectures": [{"module_title": "M1", "theses": ["Thesis 1"]}],
    "slides": [{"slide_title": "Intro", "module_title": "M1", "bullets": ["Bullet 1"]}],
    "work_programs": [{"module_title": "M1", "description": "Desc"}],
    "bibliography": ["Book 1"]
}

# --- ТЕСТЫ УСПЕШНОГО СЦЕНАРИЯ ---

@patch("agents.orchestrator.generate_framework_json")
@patch("agents.orchestrator.generate_content_pack")
def test_full_generate_approve_export_flow(mock_content, mock_framework):
    """[ТРЕБОВАНИЕ КЕЙСА]: Сквозной сценарий (генерация -> утверждение -> экспорт)."""
    mock_framework.return_value = MOCK_FRAMEWORK
    mock_content.return_value = MOCK_CONTENT

    # 1. Генерация
    res = client.post("/api/generate", json={"topic": "Python", "hours": 72, "template_type": "ДПО"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "waiting_for_approval"
    session_id = data["session_id"]

    # 2. Утверждение
    res = client.post(f"/api/approve/{session_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "completed"
    assert "constraints_check" in res.json()

    # 3. Экспорт DOCX
    res = client.get(f"/api/export-docx/{session_id}")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# --- ТЕСТЫ ОБРАБОТКИ ЛОВУШЕК И ОШИБОК ---

@patch("agents.orchestrator.clarify_and_classify")
def test_generate_missing_hours(mock_clarify):
    """[ТРЕБОВАНИЕ КЕЙСА / ФИКС РЕВЬЮЕРА]: Ловушка Запроса 4 (нет часов)."""
    mock_clarify.return_value = {"template_type": "ДПО", "questions": ["Какой объем часов?", "Кто аудитория?"]}
    
    res = client.post("/api/generate", json={"topic": "Кибербезопасность"})
    assert res.status_code == 200
    assert res.json()["status"] == "clarification_needed"
    assert len(res.json()["questions"]) > 0

def test_generate_invalid_hours():
    """[ТРЕБОВАНИЕ КЕЙСА]: Защита от неверных входных данных (часы < 16)."""
    res = client.post("/api/generate", json={"topic": "Test", "hours": 5})
    assert res.status_code == 422 # Pydantic Validation Error

def test_upload_invalid_extension():
    """[ТРЕБОВАНИЕ КЕЙСА]: Безопасность (запрет .exe)."""
    res = client.post("/api/upload-reference", files={"file": ("virus.exe", b"malware", "application/x-msdownload")})
    assert res.status_code == 400

def test_upload_oversize_file():
    """[ТРЕБОВАНИЕ КЕЙСА]: Безопасность (DoS защита, файл > 5MB)."""
    big_content = b"0" * (5 * 1024 * 1024 + 10)
    res = client.post("/api/upload-reference", files={"file": ("big.txt", big_content, "text/plain")})
    assert res.status_code == 413

@patch("agents.orchestrator.generate_content_pack")
@patch("agents.orchestrator.generate_framework_json")
def test_approve_llm_failure(mock_framework, mock_content):
    """[ТРЕБОВАНИЕ КЕЙСА]: Обработка сбоя LLM при генерации контента."""
    mock_framework.return_value = MOCK_FRAMEWORK
    mock_content.side_effect = RuntimeError("LLM упала")

    # 1. Генерация каркаса
    res = client.post("/api/generate", json={"topic": "Test", "hours": 72, "template_type": "ДПО"})
    session_id = res.json()["session_id"]

    # 2. Пытаемся утвердить (должна быть ошибка)
    res = client.post(f"/api/approve/{session_id}")
    assert res.status_code == 200
    assert "error" in res.json()
    assert "LLM упала" in res.json()["error"]

    # 3. Проверяем, что сессия НЕ перешла в статус completed
    res = client.get(f"/api/report/{session_id}")
    assert res.json()["report"]["hours_match"] is True # Каркас остался цел