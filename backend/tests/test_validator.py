import pytest
from schemas import Framework, Module, Competency
from agents.validator import run_full_validation, auto_correct_hours, validate_coverage_with_content

# --- ТЕСТЫ ВАЛИДАТОРА (АРИФМЕТИКА) ---

def test_hours_match_success():
    """[ТРЕБОВАНИЕ КЕЙСА]: Проверка успешной сходимости часов."""
    fw = Framework(
        goal="Test goal",
        competencies=[Competency(name="C1", knowledge=["k"], skills=["s"])],
        modules=[Module(title="M1", hours=36), Module(title="M2", hours=36)],
        total_hours=72
    )
    report = run_full_validation(fw)
    assert report["hours_match"] is True
    assert report["calculated_total"] == 72

def test_hours_match_fail():
    """[ТРЕБОВАНИЕ КЕЙСА]: Валидатор должен ловить расхождения в часах."""
    fw = Framework(
        goal="Test goal",
        competencies=[Competency(name="C1", knowledge=["k"], skills=["s"])],
        modules=[Module(title="M1", hours=30)],
        total_hours=72 # Ошибка!
    )
    report = run_full_validation(fw)
    assert report["hours_match"] is False
    assert report["calculated_total"] == 30

def test_auto_correct_hours():
    """[ТРЕБОВАНИЕ КЕЙСА]: Автокоррекция должна подгонять сумму под целевое значение."""
    fw = Framework(
        goal="Test goal",
        competencies=[Competency(name="C1", knowledge=["k"], skills=["s"])],
        modules=[Module(title="M1", hours=30), Module(title="M2", hours=30)],
        total_hours=60
    )
    # Передаем target_hours=72, нейросеть ошиблась на 12 часов
    corrected_fw = auto_correct_hours(fw, 72)
    assert corrected_fw.total_hours == 72
    assert sum(m.hours for m in corrected_fw.modules) == 72
    assert corrected_fw.modules[-1].hours == 42 # 30 + 12

# --- ТЕСТЫ ГЛУБОКОГО ПОКРЫТИЯ КОМПЕТЕНЦИЙ ---

def test_deep_coverage_success():
    """[ТРЕБОВАНИЕ КЕЙСА]: Проверка, что все компетенции покрыты тестами."""
    fw = Framework(
        goal="Test",
        competencies=[
            Competency(name="Python", knowledge=[], skills=[]),
            Competency(name="SQL", knowledge=[], skills=[])
        ],
        modules=[], total_hours=72
    )
    content = {
        "tests": [{"related_competency": "Python"}],
        "seminars": {"related_competency": "SQL"}
    }
    report = validate_coverage_with_content(fw, content)
    assert report["coverage_ok"] is True
    assert len(report["uncovered"]) == 0

def test_deep_coverage_fail():
    """[ТРЕБОВАНИЕ КЕЙСА]: Валидатор должен находить непокрытые компетенции."""
    fw = Framework(
        goal="Test",
        competencies=[
            Competency(name="Python", knowledge=[], skills=[]),
            Competency(name="Docker", knowledge=[], skills=[])
        ],
        modules=[], total_hours=72
    )
    content = {
        "tests": [{"related_competency": "Python"}],
        "seminars": {}
    }
    report = validate_coverage_with_content(fw, content)
    assert report["coverage_ok"] is False
    assert "docker" in report["uncovered"]