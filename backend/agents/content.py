from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text

def generate_content_pack(framework: Framework) -> dict:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Генерация полного комплекта материалов.
    """
    framework_str = framework.model_dump_json(indent=2)
    
    # 1. Генерация тестов
    prompt_tests = f"""
    На основе этого учебного плана:
    {framework_str}
    
    Составь 3 тестовых вопроса с 4 вариантами ответов.
    Привяжи каждый вопрос к одной из компетенций.
    Формат JSON: [{{"question": "...", "options": ["1","2","3","4"], "correct_answer": "1", "related_competency": "..."}}]
    """
    tests_raw = ask_llm(prompt_tests, task_type="content", is_json=True)
    tests = extract_json_from_text(tests_raw)
    
    # 2. Генерация семинаров
    prompt_seminars = f"""
    На основе этого учебного плана:
    {framework_str}
    
    Составь 1 практическое задание для семинара. Опиши критерии оценки.
    Формат JSON: {{"task": "...", "criteria": "...", "related_competency": "..."}}
    """
    seminars_raw = ask_llm(prompt_seminars, task_type="content", is_json=True)
    seminars = extract_json_from_text(seminars_raw)

    # 3. Генерация лекций
    prompt_lectures = f"""
    На основе этого учебного плана:
    {framework_str}
    
    Составь развернутый план лекций (3-4 тезиса на каждый модуль).
    """
    lectures = ask_llm(prompt_lectures, task_type="content")

    return {
        "tests": tests, 
        "seminars": seminars, 
        "lectures": lectures
    }