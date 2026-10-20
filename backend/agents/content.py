import time
from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from logger import logger

def _generate_with_retry(prompt: str, task_type: str = "content", retries: int = 3) -> any:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Защита от сбоев LLM.
    """
    for attempt in range(retries):
        try:
            raw = ask_llm(prompt, task_type=task_type, is_json=True)
            data = extract_json_from_text(raw)
            if not data:
                raise ValueError("Пустой ответ от LLM")
            return data
        except Exception as e:
            logger.warning(f"Ошибка генерации контента ({attempt+1}/{retries}): {e}")
            if attempt == retries - 1:
                raise RuntimeError(f"Не удалось сгенерировать артефакт после {retries} попыток. Ошибка: {e}")
            time.sleep(1.5)

def generate_content_pack(framework: Framework, constraints: str = None) -> dict:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Генерация полного комплекта материалов.
    Учитывает специфические требования методиста (количество вопросов, выбор модулей для слайдов).
    """
    framework_str = framework.model_dump_json(indent=2)
    constraints_str = f"\nОСОБЫЕ ТРЕБОВАНИЯ: {constraints}\n" if constraints else ""
    
    # 1. Тесты (учитываем количество вопросов из ограничений)
    prompt_tests = f"""
    На основе плана:\n{framework_str}\n
    {constraints_str}
    Составь тестовые вопросы с 4 вариантами ответов (если в требованиях не указано иное, сделай 5 вопросов).
    Привяжи каждый вопрос к одной из компетенций.
    Верни ТОЛЬКО JSON-МАССИВ (без оберток):
    [{{"question": "...", "options": ["1","2","3","4"], "correct_answer": "1", "related_competency": "Название компетенции"}}]
    """
    tests = _generate_with_retry(prompt_tests)
    if isinstance(tests, dict):
        for key in ["questions", "tests", "data", "items"]:
            if key in tests and isinstance(tests[key], list):
                tests = tests[key]
                break
        else:
            tests = [tests]
    if not isinstance(tests, list):
        raise ValueError("LLM вернула тесты в неверном формате (не список)")

    # 2. Семинары (массив)
    prompt_seminars = f"""
    На основе плана:\n{framework_str}\n
    {constraints_str}
    Составь 2 практических задания для семинаров (если в требованиях не указано иное). Для каждого опиши критерии оценки.
    Верни строго JSON-МАССИВ:
    [{{"task": "...", "criteria": "...", "related_competency": "..."}}]
    """
    seminars = _generate_with_retry(prompt_seminars)
    if isinstance(seminars, dict): 
        seminars = [seminars] # Если LLM вернула один объект, оборачиваем в массив
    if not isinstance(seminars, list):
        seminars = []

    # 3. Лекции
    prompt_lectures = f"""
    На основе плана:\n{framework_str}\n
    Составь развернутый план лекций (3-4 тезиса на модуль).
    Верни строго JSON-МАССИВ:
    [{{"module_title": "Название модуля", "theses": ["тезис 1", "тезис 2"]}}]
    """
    lectures = _generate_with_retry(prompt_lectures)
    if isinstance(lectures, dict) and "modules_plan" in lectures:
        lectures = lectures["modules_plan"]
    if not isinstance(lectures, list):
        raise ValueError("LLM вернула лекции в неверном формате (не список)")

    # 4. [ТРЕБОВАНИЕ КЕЙСА]: Структура слайдов для PPTX (учитываем ограничения, например "слайды для модуля pandas")
    prompt_slides = f"""
    На основе плана:\n{framework_str}\n
    {constraints_str}
    Сформируй структуру презентации для лекций.
    Если в требованиях указан конкретный модуль (например, "слайды для модуля pandas"), сделай слайды ТОЛЬКО для него.
    Иначе сделай по 2 слайда для каждого модуля.
    Верни строго JSON-МАССИВ:
    [{{"slide_title": "Заголовок", "module_title": "Название модуля", "bullets": ["тезис 1", "тезис 2"]}}]
    """
    slides = _generate_with_retry(prompt_slides)
    if not isinstance(slides, list):
        slides = []

    # 5. Рабочие программы модулей
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

    # 6. Библиография
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
        "slides": slides, # <-- Добавили слайды
        "work_programs": work_programs,
        "bibliography": bibliography
    }