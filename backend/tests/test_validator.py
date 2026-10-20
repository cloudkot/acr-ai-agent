import pytest
from schemas import Framework, Module, Competency
from agents.validator import run_full_validation, auto_correct_hours, validate_coverage_with_content, check_content_constraints

def create_mock_framework(total_hours=72, mod_hours=70, final_hours=2):
    return Framework(
        goal="Test goal",
        template_type="ДПО",
        prof_standard="Test",
        competencies=[Competency(name="C1", knowledge=["k"], skills=["s"])],
        modules=[Module(title="M1", total_hours=mod_hours, lectures=10, practice=10, labs=0, srs=mod_hours-20)],
        total_hours=total_hours,
        final_assessment_hours=final_hours
    )

def test_hours_match_success():
    """[ТРЕБОВАНИЕ КЕЙСА]: Проверка успешной сходимости часов (модули + аттестация)."""
    fw = create_mock_framework()
    report = run_full_validation(fw)
    assert report["hours_match"] is True
    assert report["modules_math_ok"] is True

def test_hours_match_fail():
    """[ТРЕБОВАНИЕ КЕЙСА]: Валидатор должен ловить расхождения в часах."""
    fw = create_mock_framework()
    fw.total_hours = 80 # Искусственно ломаем общий объем
    report = run_full_validation(fw)
    assert report["hours_match"] is False

def test_auto_correct_hours():
    """[ТРЕБОВАНИЕ КЕЙСА]: Автокоррекция подгоняет сумму под целевое значение."""
    fw = create_mock_framework(mod_hours=60, final_hours=2) # Всего 62, а надо 72
    corrected_fw = auto_correct_hours(fw, 72)
    assert corrected_fw.total_hours == 72
    # Разница (10 часов) должна уйти в СРС последнего модуля
    assert corrected_fw.modules[-1].srs == 40 + 10 

def test_deep_coverage():
    """[ТРЕБОВАНИЕ КЕЙСА]: Глубокая проверка покрытия компетенций."""
    fw = create_mock_framework()
    content = {
        "tests": [{"related_competency": "C1"}],
        "seminars": []
    }
    report = validate_coverage_with_content(fw, content)
    assert report["coverage_ok"] is True

def test_constraints_check_fail():
    """[ТРЕБОВАНИЕ КЕЙСА / ФИКС РЕВЬЮЕРА]: Программная проверка ограничений."""
    fw = create_mock_framework()
    # Имитируем, что методист просил 10 вопросов
    constraints = "Сделай ровно 10 вопросов в тесте"
    
    # А сгенерировалось только 2
    content = {"tests": [{"q": 1}, {"q": 2}]}
    
    report = check_content_constraints(fw, content, constraints)
    assert report["constraints_ok"] is False
    assert "ожидалось 10" in report["errors"][0]