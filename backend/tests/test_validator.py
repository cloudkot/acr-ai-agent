import pytest
from schemas import Framework, Module, Competency
from agents.validator import (
    auto_correct_hours, 
    enforce_content_constraints, 
    validate_coverage_with_content
)
from agents.content import _generate_smart_fallback_seminar

def create_mock_framework(total_hours=72, mod_hours=70, final_hours=2):
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
    fw = create_mock_framework(total_hours=256, mod_hours=250, final_hours=2)
    # Ограничение "без лекций"
    corrected = auto_correct_hours(fw, 256, constraints="без лекций, только самостоятельная")
    
    assert corrected.total_hours == 256
    assert corrected.modules[-1].lectures == 0 # Лекции должны быть обнулены
    assert corrected.modules[-1].practice == 0 # Практики тоже
    assert corrected.modules[-1].srs == 254 # Все ушло в СРС

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
    
    # Передаем ограничение
    result = enforce_content_constraints(fw, content, constraints="сделай слайды только для pandas")
    assert len(result["slides"]) == 1
    assert result["slides"][0]["module_title"] == "Pandas"

def test_smart_fallback_seminar():
    """[ML-СКЛЕЙКА]: Проверка, что fallback использует компетенции из каркаса."""
    fw = create_mock_framework()
    # У нашей компетенции C1 в related_topics указан модуль M1
    fallback = _generate_smart_fallback_seminar(fw, "M1", 70)
    
    assert fallback["module_title"] == "M1"
    assert "C1" in fallback["task"] # Компетенция должна быть в тексте задания!
    assert fallback["related_competency"] == "C1"

def test_validate_coverage():
    """[ТРЕБОВАНИЕ КЕЙСА]: Проверка покрытия компетенций тестами."""
    fw = create_mock_framework()
    content = {"tests": [{"related_competency": "C1"}], "seminars": []}
    
    report = validate_coverage_with_content(fw, content)
    assert report["coverage_ok"] is True
    assert report["tested_count"] == 1