import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app
from schemas import Framework, Module, Competency
from state_store import init_db

client = TestClient(app)

# Инициализируем тестовую БД
init_db()

# --- МОКИ ДЛЯ LLM ---
MOCK_FRAMEWORK = Framework(
    goal="Test goal",
    competencies=[Competency(name="Test", knowledge=["k"], skills=["s"])],
    modules=[Module(title="M1", hours=72)],
    total_hours=72
)

MOCK_CONTENT = {
    "tests": [{"question": "Q1", "options": ["A", "B"], "correct_answer": "A", "related_competency": "Test"}],
    "seminars": {"task": "T1", "criteria": "C1"},
    "lectures": [],
    "work_programs": [],
    "bibliography": []
}

# --- ТЕСТЫ УСПЕШНОГО СЦЕНАРИЯ ---

@patch("agents.orchestrator.generate_framework_json")
@patch("agents.orchestrator.generate_content_pack")
def test_full_generate_approve_export_flow(mock_content, mock_framework):
    """[ТРЕБОВАНИЕ КЕЙСА]: Сквозной сценарий (генерация -> утверждение -> экспорт)."""
    mock_framework.return_value = MOCK_FRAMEWORK
    mock_content.return_value = MOCK_CONTENT

    # 1. Генерация
    res = client.post("/api/generate", json={"topic": "Test Topic", "hours": 72, "template_type": "ДПО"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "waiting_for_approval"
    session_id = data["session_id"]

    # 2. Утверждение
    res = client.post(f"/api/approve/{session_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "completed"

    # 3. Экспорт DOCX
    res = client.get(f"/api/export-docx/{session_id}")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    # 4. Экспорт LMS
    res = client.get(f"/api/export-lms/{session_id}")
    assert res.status_code == 200
    assert res.headers["content-type"] == "text/plain"

# --- ТЕСТЫ СБОЕВ И БЕЗОПАСНОСТИ ---

def test_generate_invalid_hours():
    """[ТРЕБОВАНИЕ КЕЙСА]: Защита от неверных входных данных (часы < 16)."""
    res = client.post("/api/generate", json={"topic": "Test", "hours": 5})
    assert res.status_code == 422 # Pydantic Validation Error

def test_upload_invalid_extension():
    """[ТРЕБОВАНИЕ КЕЙСА]: Защита от загрузки вредоносных файлов."""
    # Пытаемся загрузить .exe
    res = client.post("/api/upload-reference", files={"file": ("virus.exe", b"malware", "application/x-msdownload")})
    assert res.status_code == 400
    assert "Недопустимый формат" in res.json()["detail"]

def test_upload_oversize_file():
    """[ТРЕБОВАНИЕ КЕЙСА]: Защита от DoS (файл > 5MB)."""
    big_content = b"0" * (5 * 1024 * 1024 + 10) # 5MB + 10 байт
    res = client.post("/api/upload-reference", files={"file": ("big.txt", big_content, "text/plain")})
    assert res.status_code == 413
    assert "слишком большой" in res.json()["detail"]

@patch("agents.orchestrator.generate_content_pack")
def test_approve_llm_failure(mock_content):
    """[ТРЕБОВАНИЕ КЕЙСА]: Обработка сбоя LLM при генерации контента."""
    # 1. Сначала успешно генерируем каркас
    with patch("agents.orchestrator.generate_framework_json", return_value=MOCK_FRAMEWORK):
        res = client.post("/api/generate", json={"topic": "Test", "hours": 72, "template_type": "ДПО"})
        session_id = res.json()["session_id"]

    # 2. Эмулируем ошибку при генерации контента
    mock_content.side_effect = RuntimeError("LLM упала")

    res = client.post(f"/api/approve/{session_id}")
    assert res.status_code == 200 # FastAPI вернет JSON с ошибкой
    assert "error" in res.json()
    assert "LLM упала" in res.json()["error"]

    # Проверяем, что сессия НЕ перешла в статус completed
    res = client.get(f"/api/report/{session_id}")
    assert res.json()["report"]["hours_match"] is True # Каркас жив