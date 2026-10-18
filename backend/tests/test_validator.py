from schemas import Framework, Module, Competency
from agents.validator import run_full_validation

def test_hours_match():
    """Проверка корректной суммы часов."""
    fw = Framework(
        goal="Test",
        competencies=[Competency(name="C1", knowledge=["k"], skills=["s"])],
        modules=[Module(title="M1", hours=72)],
        total_hours=72
    )
    assert run_full_validation(fw)["hours_match"] is True

def test_hours_mismatch():
    """Проверка ошибки в арифметике."""
    fw = Framework(
        goal="Test",
        competencies=[],
        modules=[Module(title="M1", hours=30)],
        total_hours=72
    )
    assert run_full_validation(fw)["hours_match"] is False