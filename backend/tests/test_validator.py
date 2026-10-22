import pytest
from schemas import Framework, Module, Competency
from agents.validator import (
    auto_correct_hours, 
    enforce_content_constraints, 
    validate_coverage_with_content
)

def create_mock_framework(total_hours=72, mod_hours=70, final_hours=2):
    """[УТИЛИТА]: Создает тестовый каркас программы."""
    return Framework(
        goal="Test goal",
        template_type="ДПО",
        prof_standard="Test",
        competencies=[Competency(name="C1", knowledge=["k"], skills=["s"], related_topics=["M1"])],
        modules=[Module(title="M1", total_hours=mod_hours, lectures=10, practice=10, labs=0, srs=mod_hours-20)],
        total_hours=total_hours,
        final_assessment_hours=final_hours
    )

def test_auto_correct_hours_devops_trap():
    """[ТРЕБОВАНИЕ КЕЙСА]: Ловушка №5 (DevOps 256ч, без лекций)."""
    # Создаем каркас, где ИИ ошибся с часами (например, сделал 250 вместо 256)
    fw = create_mock_framework(total_hours=256, mod_hours=248, final_hours=2)
    
    # Передаем ограничение "без лекций"
    constraints = "без лекций, только самостоятельная работа"
    corrected = auto_correct_hours(fw, 256, constraints)
    
    assert corrected.total_hours == 256
    assert corrected.modules[-1].lectures == 0 # Лекции обнулены
    assert corrected.modules[-1].practice == 0 # Практики обнулены
    assert corrected.modules[-1].srs == 254 # Все ушло в СРС (256 - 2)

def test_auto_correct_hours_math_error():
    """[ТРЕБОВАНИЕ КЕЙСА]: Исправление математических ошибок ИИ."""
    # ИИ сгенерировал 60 часов в модуле и 2 часа аттестации, а просили 72
    fw = create_mock_framework(total_hours=62, mod_hours=60, final_hours=2)
    
    corrected = auto_correct_hours(fw, 72, None)
    
    # Общий объем должен стать 72, разница (10 часов) уходит в последний модуль
    assert corrected.total_hours == 72
    assert sum(m.total_hours for m in corrected.modules) + corrected.final_assessment_hours == 72

def test_enforce_content_constraints_pandas():
    """[ТРЕБОВАНИЕ КЕЙСА]: Ловушка №3 (Слайды только для pandas)."""
    fw = Framework(
        goal="Data Analysis", template_type="ДПО", prof_standard=None,
        competencies=[], modules=[Module(title="Pandas", total_hours=20, lectures=0, practice=0, labs=0, srs=20)],
        total_hours=20, final_assessment_hours=2
    )
    content = {
        "slides": [
            {"slide_title": "Pandas Intro", "module_title": "Pandas"},
            {"slide_title": "Other Topic", "module_title": "Other"}
        ],
        "tests": [], "bibliography": [], "seminars": [], "lectures": [], "work_programs": []
    }
    
    # Передаем ограничение на pandas
    result = enforce_content_constraints(fw, content, constraints="сделай слайды только для pandas")
    
    # Должен остаться только 1 слайд (для Pandas)
    assert len(result["slides"]) == 1
    assert result["slides"][0]["module_title"] == "Pandas"

def test_validate_coverage():
    """[ТРЕБОВАНИЕ КЕЙСА]: Проверка покрытия компетенций тестами."""
    fw = create_mock_framework()
    
    # В тестах проверяется компетенция C1
    content_valid = {
        "tests": [{"related_competency": "C1"}], 
        "seminars": []
    }
    report_valid = validate_coverage_with_content(fw, content_valid)
    assert report_valid["coverage_ok"] is True
    assert report_valid["tested_count"] == 1

    # В тестах проверяется неизвестная компетенция
    content_invalid = {
        "tests": [{"related_competency": "Unknown"}], 
        "seminars": []
    }
    report_invalid = validate_coverage_with_content(fw, content_invalid)
    assert report_invalid["coverage_ok"] is False
    assert "c1" in report_invalid["uncovered"]