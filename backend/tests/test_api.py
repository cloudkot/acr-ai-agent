import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from main import app
from schemas import Framework, Module, Competency
from state_store import init_db

client = TestClient(app)
init_db()

# --- МОК-ДАННЫЕ ---
MOCK_FRAMEWORK = Framework(
    goal="Программа разработана на основании 273-ФЗ",
    template_type="ДПО",
    prof_standard="Профстандарт 06.015",
    competencies=[Competency(name="DevOps", knowledge=["k"], skills=["s"], related_topics=["M1"])],
    modules=[Module(title="M1", total_hours=70, lectures=10, practice=10, labs=0, srs=50)],
    total_hours=72,
    final_assessment_hours=2
)

MOCK_CONTENT = {
    "tests": [{"question": "Q1", "options": ["A", "B"], "correct_answer": "A", "related_competency": "DevOps"}],
    "seminars": [{"module_title": "M1", "task": "T1", "criteria": "C1", "related_competency": "DevOps"}],
    "lectures": [{"module_title": "M1", "theses": ["Thesis 1"]}],
    "slides": [{"slide_title": "Intro", "module_title": "M1", "bullets": ["Bullet 1"]}],
    "work_programs": [{"module_title": "M1", "description": "Desc"}],
    "bibliography": ["Book 1"]
}

# --- ТЕСТЫ ---

def test_health_check():
    """[ТРЕБОВАНИЕ КЕЙСА]: Проверка живости API."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

@patch("agents.orchestrator.clarify_and_classify", new_callable=AsyncMock)
def test_generate_missing_hours(mock_clarify):
    """[ТРЕБОВАНИЕ КЕЙСА]: Ловушка №4 (нет часов -> clarification_needed)."""
    mock_clarify.return_value = {"template_type": "ДПО", "questions": ["Какой объем часов?"]}
    
    response = client.post("/api/generate", json={"topic": "Кибербезопасность"})
    assert response.status_code == 200
    assert response.json()["status"] == "clarification_needed"
    assert len(response.json()["questions"]) > 0

@patch("agents.orchestrator.generate_framework_json", new_callable=AsyncMock)
@patch("agents.orchestrator.generate_content_pack", new_callable=AsyncMock)
def test_full_generate_approve_export_flow(mock_content, mock_framework):
    """[ТРЕБОВАНИЕ КЕЙСА]: Сквозной сценарий (генерация -> утверждение -> экспорт)."""
    mock_framework.return_value = (MOCK_FRAMEWORK, 100, 0.05)
    mock_content.return_value = MOCK_CONTENT

    # 1. Генерация
    res = client.post("/api/generate", json={"topic": "DevOps", "hours": 72, "template_type": "ДПО"})
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