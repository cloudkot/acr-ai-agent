from schemas import Framework, Module, Competency
from agents.validator import run_full_validation
def test_hours_match():
    fw = Framework(goal="T", competencies=[Competency(name="C", knowledge=[], skills=[])], modules=[Module(title="M", hours=72)], total_hours=72)
    assert run_full_validation(fw)["hours_match"] is True