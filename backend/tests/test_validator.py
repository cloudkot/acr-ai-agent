from schemas import Framework, Module, Competency
from agents.validator import auto_correct_hours

def test_math_auto_correction():
    """[ТРЕБОВАНИЕ КЕЙСА]: Проверка автокоррекции часов."""
    fw = Framework(
        goal="Test", template_type="ДПО", prof_standard="Test",
        competencies=[Competency(name="C1", knowledge=["k"], skills=["s"])],
        modules=[Module(title="M1", total_hours=50, lectures=10, practice=10, labs=0, srs=30)],
        total_hours=50, final_assessment_hours=2
    )
    # Просим 72 часа, на входе 52
    corrected = auto_correct_hours(fw, 72)
    assert corrected.total_hours == 72
    assert sum(m.total_hours for m in corrected.modules) + corrected.final_assessment_hours == 72