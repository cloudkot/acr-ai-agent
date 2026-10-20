from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from logger import logger

def generate_content_pack(framework: Framework) -> dict:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Генерация полного комплекта материалов, 
    включая рабочие программы и библиографию.
    """
    framework_str = framework.model_dump_json(indent=2)
    content = {
        "tests": [],
        "seminars": {},
        "lectures": [],
        "work_programs": [],
        "bibliography": []
    }
    
    # 1. Тесты
    prompt_tests = f"""
    На основе плана:\n{framework_str}\n
    Составь 3 тестовых вопроса с 4 вариантами ответов.
    ВАЖНО: Верни ТОЛЬКО JSON-МАССИВ (без оберток):
    [{{"question": "...", "options": ["1","2","3","4"], "correct_answer": "1", "related_competency": "Название компетенции"}}]
    """
    try:
        raw_tests = ask_llm(prompt_tests, task_type="content", is_json=True)
        tests = extract_json_from_text(raw_tests)
        if isinstance(tests, dict) and "questions" in tests: tests = tests["questions"]
        content["tests"] = tests
    except Exception as e:
        logger.error(f"Ошибка генерации тестов: {e}")

    # 2. Семинары
    prompt_seminars = f"""
    На основе плана:\n{framework_str}\n
    Составь 1 практическое задание для семинара. Опиши критерии оценки.
    Верни строго JSON:
    {{"task": "...", "criteria": "...", "related_competency": "..."}}
    """
    try:
        raw_seminars = ask_llm(prompt_seminars, task_type="content", is_json=True)
        content["seminars"] = extract_json_from_text(raw_seminars)
    except Exception as e:
        logger.error(f"Ошибка генерации семинаров: {e}")

    # 3. Лекции
    prompt_lectures = f"""
    На основе плана:\n{framework_str}\n
    Составь развернутый план лекций (3-4 тезиса на модуль).
    Верни строго JSON-МАССИВ:
    [{{"module_title": "Название модуля", "theses": ["тезис 1", "тезис 2"]}}]
    """
    try:
        raw_lectures = ask_llm(prompt_lectures, task_type="content", is_json=True)
        lectures = extract_json_from_text(raw_lectures)
        if isinstance(lectures, dict) and "modules_plan" in lectures: lectures = lectures["modules_plan"]
        content["lectures"] = lectures
    except Exception as e:
        logger.error(f"Ошибка генерации лекций: {e}")

    # 4. [ТРЕБОВАНИЕ КЕЙСА]: Рабочие программы модулей (на что ругался ревьюер)
    prompt_work_programs = f"""
    На основе плана:\n{framework_str}\n
    Напиши краткое содержание (рабочую программу) для каждого модуля (2-3 предложения о том, что изучается).
    Верни строго JSON-МАССИВ:
    [{{"module_title": "Название модуля", "description": "Краткое содержание"}}]
    """
    try:
        raw_wp = ask_llm(prompt_work_programs, task_type="content", is_json=True)
        content["work_programs"] = extract_json_from_text(raw_wp)
    except Exception as e:
        logger.error(f"Ошибка генерации рабочих программ: {e}")

    # 5. [ТРЕБОВАНИЕ КЕЙСА]: Библиография
    prompt_bibliography = f"""
    На основе плана:\n{framework_str}\n
    Составь список из 3-5 реальных книг или статей для изучения этих тем.
    Верни строго JSON-МАССИВ строк:
    ["Автор. Название. Год.", "Автор 2. Название 2. Год."]
    """
    try:
        raw_bib = ask_llm(prompt_bibliography, task_type="content", is_json=True)
        content["bibliography"] = extract_json_from_text(raw_bib)
    except Exception as e:
        logger.error(f"Ошибка генерации библиографии: {e}")

    return content