from fastapi.testclient import TestClient
from main import app
from unittest.mock import patch
from schemas import Framework, Module, Competency
client = TestClient(app)
@patch("agents.curriculum.generate_framework_json")
def test_flow(mock_gen):
    mock_gen.return_value = Framework(goal="T", competencies=[Competency(name="C", knowledge=[], skills=[])], modules=[Module(title="M", hours=72)], total_hours=72)
    res = client.post("/api/generate", json={"topic": "Test", "hours": 72})
    assert res.status_code == 200