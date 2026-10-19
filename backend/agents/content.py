import json
from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text

def generate_content_pack(framework: Framework) -> dict:
    framework_str = framework.model_dump_json(indent=2)
    
    # 1. Тесты
    prompt_tests = f"""
    На основе плана:\n{framework_str}\n
    Составь 3 тестовых вопроса с 4 вариантами ответов.
    Привяжи каждый вопрос к одной из компетенций из плана.
    ВАЖНО: Верни ТОЛЬКО валидный JSON-МАССИВ строго в таком формате (без оберток вроде "questions"):
    [
        {{
            "question": "Текст вопроса?",
            "options": ["Вариант 1", "Вариант 2", "Вариант 3", "Вариант 4"],
            "correct_answer": "Вариант 1",
            "related_competency": "Название компетенции (без лишних тегов!)"
        }}
    ]
    """
    tests_raw = ask_llm(prompt_tests, task_type="content", is_json=True)
    tests_data = extract_json_from_text(tests_raw)
    
    # [ТРЕБОВАНИЕ КЕЙСА]: Защита от того, что LLM вернет объект вместо массива
    if isinstance(tests_data, dict):
        for key in ["questions", "tests", "data", "items"]:
            if key in tests_data and isinstance(tests_data[key], list):
                tests_data = tests_data[key]
                break
        else:
            tests_data = [tests_data] # Если это просто один объект, оборачиваем в массив

    # 2. Семинары
    prompt_seminars = f"""
    На основе плана:\n{framework_str}\n
    Составь 1 практическое задание для семинара. Опиши критерии оценки.
    Верни строго JSON (без оберток):
    {{
        "task": "...",
        "criteria": "...",
        "related_competency": "..."
    }}
    """
    seminars_raw = ask_llm(prompt_seminars, task_type="content", is_json=True)
    seminars = extract_json_from_text(seminars_raw)

    # 3. Лекции
    prompt_lectures = f"""
    На основе плана:\n{framework_str}\n
    Составь развернутый план лекций (3-4 тезиса на модуль).
    Верни строго JSON-МАССИВ (без оберток):
    [
        {{
            "module_title": "Название модуля",
            "theses": ["тезис 1", "тезис 2", "тезис 3"]
        }}
    ]
    """
    lectures_raw = ask_llm(prompt_lectures, task_type="content", is_json=True)
    lectures = extract_json_from_text(lectures_raw)
    
    if isinstance(lectures, dict) and "modules_plan" in lectures:
        lectures = lectures["modules_plan"]

    return {
        "tests": tests_data, 
        "seminars": seminars, 
        "lectures": lectures
    }