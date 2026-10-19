from fastapi.testclient import TestClient
from main import app
from unittest.mock import patch
from schemas import Framework, Module, Competency
from state_store import init_db

# [ТРЕБОВАНИЕ КЕЙСА]: Инициализируем БД перед тестами
init_db()

client = TestClient(app)

# [АРХИТЕКТУРА]: Важно патчить функцию там, где она ИСПОЛЬЗУЕТСЯ (в оркестраторе), а не там, где объявлена!
@patch("agents.orchestrator.generate_framework_json")
def test_generate_endpoint(mock_gen):
    """Проверка эндпоинта генерации (сквозной сценарий)."""
    
    # Подкладываем фейковый ответ вместо реального вызова LLM
    mock_gen.return_value = Framework(
        goal="Test Goal",
        competencies=[Competency(name="C1", knowledge=[], skills=[])],
        modules=[Module(title="M1", hours=72)],
        total_hours=72
    )
    
    response = client.post("/api/generate", json={"topic": "Python", "hours": 72})
    
    assert response.status_code == 200
    assert response.json()["status"] == "waiting_for_approval"
    assert "session_id" in response.json()

def test_generate_invalid_hours():
    """[ТРЕБОВАНИЕ КЕЙСА]: Тест на обработку сбоев (невалидные часы)."""
    response = client.post("/api/generate", json={"topic": "Test", "hours": -5})
    # Так как у нас стоит валидация Pydantic, FastAPI сам вернет 422
    assert response.status_code == 422

def test_generate_invalid_hours():
    """[ТРЕБОВАНИЕ КЕЙСА]: Тест на сбой (слишком мало часов)."""
    response = client.post("/api/generate", json={"topic": "Test", "hours": 5, "template_type": "ДПО"})
    assert response.status_code == 422 # FastAPI автоматически отклонит

def test_upload_invalid_file():
    """[ТРЕБОВАНИЕ КЕЙСА]: Тест на загрузку вредоносного файла."""
    response = client.post("/api/upload-reference", files={"file": ("exploit.exe", b"malware", "application/x-msdownload")})
    assert response.status_code == 400 # Разрешены только docx/txt/pdf