import pytest
from fastapi.testclient import TestClient
from main import app
from unittest.mock import patch
from schemas import Framework, Module, Competency

client = TestClient(app)

# [ТРЕБОВАНИЕ КЕЙСА]: Тестирование сквозного сценария
@patch("agents.curriculum.generate_framework_json")
@patch("agents.content.generate_content_pack")
def test_full_generate_approve_export_flow(mock_content, mock_framework):
    """Тест: Генерация -> Утверждение -> Экспорт"""
    
    # 1. Мокаем ответы LLM
    mock_framework.return_value = Framework(
        goal="Тестовая цель",
        competencies=[Competency(name="C1", knowledge=["k"], skills=["s"])],
        modules=[Module(title="M1", hours=72)],
        total_hours=72
    )
    mock_content.return_value = {"tests": [], "seminars": {}, "lectures": "Текст лекций"}

    # 2. Шаг 1: Генерация
    response = client.post("/api/generate", json={"topic": "Python", "hours": 72})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "waiting_for_approval"
    session_id = data["session_id"]

    # 3. Шаг 2: Утверждение
    response = client.post(f"/api/approve/{session_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    # 4. Шаг 3: Экспорт (проверяем, что отдается файл)
    response = client.post(f"/api/export-docx/{session_id}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"