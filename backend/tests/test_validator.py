# backend/tests/test_validator.py
import pytest
from schemas import Framework, Module, Competency
from agents.validator import run_full_validation

def test_hours_validation_success():
    """Проверка, что валидатор пропускает корректные часы."""
    fw = Framework(
        goal="Test",
        competencies=[Competency(name="C1", knowledge=["k"], skills=["s"])],
        modules=[Module(title="M1", hours=36), Module(title="M2", hours=36)],
        total_hours=72
    )
    report = run_full_validation(fw)
    assert report["hours_match"] is True
    assert report["calculated_total"] == 72

def test_hours_validation_fail():
    """[ТРЕБОВАНИЕ КЕЙСА]: Проверка на ошибки в арифметике (как 246 != 66+6)."""
    fw = Framework(
        goal="Test",
        competencies=[],
        modules=[Module(title="M1", hours=30), Module(title="M2", hours=30)],
        total_hours=72 # Ошибка!
    )
    report = run_full_validation(fw)
    assert report["hours_match"] is False
    assert report["calculated_total"] == 60