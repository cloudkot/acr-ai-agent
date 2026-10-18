from fastapi.testclient import TestClient
from main import app
from unittest.mock import patch
from schemas import Framework, Module, Competency

client = TestClient(app)

@patch("agents.curriculum.generate_framework_json")
def test_generate_endpoint(mock_gen):
    """Проверка эндпоинта генерации."""
    mock_gen.return_value = Framework(
        goal="Test",
        competencies=[Competency(name="C1", knowledge=[], skills=[])],
        modules=[Module(title="M1", hours=72)],
        total_hours=72
    )
    
    response = client.post("/api/generate", json={"topic": "Python", "hours": 72})
    
    assert response.status_code == 200
    assert response.json()["status"] == "waiting_for_approval"
    assert "session_id" in response.json()