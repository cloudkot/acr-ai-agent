from fastapi.testclient import TestClient
from main import app
from state_store import init_db

client = TestClient(app)
init_db()

def test_health_check():
    """[ТРЕБОВАНИЕ КЕЙСА]: Проверка живости API."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_generate_missing_hours():
    """[ТРЕБОВАНИЕ КЕЙСА]: Запрос без часов должен вызывать уточнения."""
    response = client.post("/api/generate", json={"topic": "Python"})
    assert response.status_code == 200
    assert response.json()["status"] == "clarification_needed"