from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text

def generate_content_pack(framework: Framework) -> dict:
    framework_str = framework.model_dump_json(indent=2)
    
    # 1. Тесты
    prompt_tests = f"На основе плана:\n{framework_str}\n\nСоставь 3 тестовых вопроса. Формат JSON: [{{\"question\": \"...\", \"options\": [\"1\",\"2\",\"3\",\"4\"], \"correct_answer\": \"1\", \"related_competency\": \"...\"}}]"
    tests = extract_json_from_text(ask_llm(prompt_tests, task_type="content", is_json=True))
    
    # 2. Семинары
    prompt_seminars = f"На основе плана:\n{framework_str}\n\nСоставь 1 задание для семинара. Формат JSON: {{\"task\": \"...\", \"criteria\": \"...\", \"related_competency\": \"...\"}}"
    seminars = extract_json_from_text(ask_llm(prompt_seminars, task_type="content", is_json=True))

    # 3. Структурированные лекции (для генерации слайдов)
    prompt_lectures = f"""
    На основе плана:\n{framework_str}\n
    Составь развернутый план лекций для каждого модуля (3-4 тезиса на модуль).
    Формат JSON: [{{"module_title": "Название", "theses": ["тезис 1", "тезис 2"]}}]
    """
    lectures = extract_json_from_text(ask_llm(prompt_lectures, task_type="content", is_json=True))

    return {"tests": tests, "seminars": seminars, "lectures": lectures}