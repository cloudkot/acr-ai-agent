import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app
from state_store import init_db
from schemas import Framework, Module, Competency

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    """[ФИКС]: Асинхронная инициализация БД для тестов."""
    import asyncio
    asyncio.run(init_db())

# --- МОК-ДАННЫЕ ДЛЯ НИЗКОУРОВНЕВОГО ПАТЧА ask_llm ---
MOCK_FRAMEWORK_DICT = {
    "goal": "Программа разработана на основании 273-ФЗ",
    "template_type": "ДПО",
    "prof_standard": "Профстандарт 06.015",
    "competencies": [{"name": "DevOps", "knowledge": ["k"], "skills": ["s"], "related_topics": ["M1"]}],
    "modules": [{"title": "M1", "total_hours": 70, "lectures": 10, "practice": 10, "labs": 0, "srs": 50}],
    "total_hours": 72,
    "final_assessment_hours": 2
}

MOCK_PLAN_DICT = {
    "reasoning": "Разбиваем на тесты и лекции",
    "tasks": [
        {
            "target_key": "tests",
            "expected_format": "json_array",
            "prompt": "Составь 5 вопросов..."
        },
        {
            "target_key": "lectures",
            "expected_format": "json_array",
            "prompt": "Составь план лекции..."
        }
    ]
}

# Асинхронный мок для ask_llm (имитация ответов нейросети на разных этапах)
async def mock_ask_llm_side_effect(prompt: str, task_type: str = "content", is_json: bool = False):
    if "Определи тип программы" in prompt:
        return json.dumps({"template_type": "ДПО", "questions": []}), 10, 0.001
    elif "Ты — экспертный методист" in prompt:
        return json.dumps(MOCK_FRAMEWORK_DICT, ensure_ascii=False), 100, 0.01
    elif "Ты — архитектор контента" in prompt:
        return json.dumps(MOCK_PLAN_DICT, ensure_ascii=False), 100, 0.01
    else:
        # Ответы для исполнителя (тесты, лекции, семинары)
        if "вопрос" in prompt.lower():
            return json.dumps([{"question": "Q1", "options": ["A", "B"], "correct_answer": "A", "related_competency": "DevOps", "category": "M1"}], ensure_ascii=False), 50, 0.005
        elif "лекци" in prompt.lower():
            return json.dumps([{"module_title": "M1", "theses": ["Thesis 1", "Thesis 2"]}], ensure_ascii=False), 50, 0.005
        else:
            return json.dumps([{"module_title": "M1", "task": "Task 1", "criteria": "C1", "related_competency": "DevOps"}], ensure_ascii=False), 50, 0.005

# --- ТЕСТЫ ---

def test_health_check():
    """[ТРЕБОВАНИЕ КЕЙСА]: Проверка живости API."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

# [ФИКС РЕВЬЮЕРА]: Мокаем только ask_llm, а не весь пайплайн!
@patch("agents.curriculum.ask_llm", side_effect=mock_ask_llm_side_effect)
@patch("agents.planner.ask_llm", side_effect=mock_ask_llm_side_effect)
@patch("agents.executor.ask_llm", side_effect=mock_ask_llm_side_effect)
@patch("agents.orchestrator.ask_llm", side_effect=mock_ask_llm_side_effect)
def test_full_generate_approve_export_flow(mock_orch, mock_exec, mock_plan, mock_curr):
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Сквозной сценарий.
    Проверяет работу реального оркестратора, планировщика и исполнителя.
    """
    # 1. Генерация каркаса
    res = client.post("/api/generate", json={"topic": "DevOps", "hours": 72, "template_type": "ДПО"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "waiting_for_approval"
    session_id = data["session_id"]

    # 2. Утверждение (Планировщик -> Исполнитель)
    res = client.post(f"/api/approve/{session_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "completed"
    assert "analytics" in res.json()

    # 3. Проверка отчета (Валидатор)
    res = client.get(f"/api/report/{session_id}")
    assert res.status_code == 200
    report = res.json()["report"]
    assert report["hours_match"] is True
    assert "completeness_check" in report

    # 4. Экспорт DOCX
    res = client.get(f"/api/export-docx/{session_id}")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    # 5. Экспорт LMS (GIFT)
    res = client.get(f"/api/export-lms/{session_id}")
    assert res.status_code == 200
    assert res.headers["content-type"] == "text/plain"

def test_generate_missing_hours():
    """[ТРЕБОВАНИЕ КЕЙСА]: Ловушка №4 (нет часов -> clarification_needed)."""
    # Здесь мы тоже можем использовать мок, но для простоты проверим 422 ошибку Pydantic, если часы не переданы,
    # либо протестируем логику clarification, если передана только тема.
    res = client.post("/api/generate", json={"topic": "Кибербезопасность"})
    assert res.status_code == 200
    assert res.json()["status"] == "clarification_needed"