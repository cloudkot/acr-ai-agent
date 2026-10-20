import time
from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from logger import logger

def _generate_with_retry(prompt: str, task_type: str = "content", retries: int = 3) -> any:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Защита от сбоев LLM.
    Вспомогательная функция, которая делает 3 попытки парсинга JSON.
    Если все 3 попытки провалились — выбрасывает исключение (не глушит ошибку).
    """
    for attempt in range(retries):
        try:
            raw = ask_llm(prompt, task_type=task_type, is_json=True)
            data = extract_json_from_text(raw)
            if not data:
                raise ValueError("Пустой ответ от LLM")
            return data
        except Exception as e:
            logger.warning(f"Ошибка генерации ({attempt+1}/{retries}): {e}")
            if attempt == retries - 1:
                raise RuntimeError(f"Не удалось сгенерировать артефакт после {retries} попыток. Ошибка: {e}")
            time.sleep(1.5)

def generate_content_pack(framework: Framework) -> dict:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Генерация полного комплекта материалов.
    Включает тесты, семинары, лекции, рабочие программы и библиографию.
    """
    framework_str = framework.model_dump_json(indent=2)
    
    # 1. Тесты
    prompt_tests = f"""
    На основе плана:\n{framework_str}\n
    Составь 3 тестовых вопроса с 4 вариантами ответов.
    ВАЖНО: Верни ТОЛЬКО JSON-МАССИВ строго в таком формате (без оберток вроде "questions"):
    [{{"question": "...", "options": ["1","2","3","4"], "correct_answer": "1", "related_competency": "Название компетенции"}}]
    """
    tests = _generate_with_retry(prompt_tests)
    # Защита от того, что LLM вернет объект вместо массива
    if isinstance(tests, dict):
        for key in ["questions", "tests", "data", "items"]:
            if key in tests and isinstance(tests[key], list):
                tests = tests[key]
                break
        else:
            tests = [tests]
    if not isinstance(tests, list):
        raise ValueError("LLM вернула тесты в неверном формате (не список)")

    # 2. Семинары
    prompt_seminars = f"""
    На основе плана:\n{framework_str}\n
    Составь 1 практическое задание для семинара. Опиши критерии оценки.
    Верни строго JSON (без оберток):
    {{"task": "...", "criteria": "...", "related_competency": "..."}}
    """
    seminars = _generate_with_retry(prompt_seminars)
    if isinstance(seminars, list) and len(seminars) > 0:
        seminars = seminars[0] # Если вернул массив из одного объекта

    # 3. Лекции
    prompt_lectures = f"""
    На основе плана:\n{framework_str}\n
    Составь развернутый план лекций (3-4 тезиса на модуль).
    Верни строго JSON-МАССИВ (без оберток):
    [{{"module_title": "Название модуля", "theses": ["тезис 1", "тезис 2"]}}]
    """
    lectures = _generate_with_retry(prompt_lectures)
    if isinstance(lectures, dict) and "modules_plan" in lectures:
        lectures = lectures["modules_plan"]
    if not isinstance(lectures, list):
        raise ValueError("LLM вернула лекции в неверном формате (не список)")

    # 4. Рабочие программы модулей
    prompt_work_programs = f"""
    На основе плана:\n{framework_str}\n
    Напиши краткое содержание (рабочую программу) для каждого модуля (2-3 предложения).
    Верни строго JSON-МАССИВ:
    [{{"module_title": "Название модуля", "description": "Краткое содержание"}}]
    """
    work_programs = _generate_with_retry(prompt_work_programs)
    if isinstance(work_programs, dict) and "work_programs" in work_programs:
        work_programs = work_programs["work_programs"]
    if not isinstance(work_programs, list):
        work_programs = []

    # 5. Библиография
    prompt_bibliography = f"""
    На основе плана:\n{framework_str}\n
    Составь список из 3-5 реальных книг или статей для изучения этих тем.
    Верни строго JSON-МАССИВ строк:
    ["Автор. Название. Год.", "Автор 2. Название 2. Год."]
    """
    bibliography = _generate_with_retry(prompt_bibliography)
    if isinstance(bibliography, dict) and "bibliography" in bibliography:
        bibliography = bibliography["bibliography"]
    if not isinstance(bibliography, list):
        bibliography = []

    return {
        "tests": tests, 
        "seminars": seminars, 
        "lectures": lectures,
        "work_programs": work_programs,
        "bibliography": bibliography
    }