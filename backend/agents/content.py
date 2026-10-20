import json
import time
from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from logger import logger

def _generate_with_retry(prompt: str, task_type: str = "content", retries: int = 3) -> any:
    """[ТРЕБОВАНИЕ КЕЙСА]: Защита от сбоев LLM с повторными попытками."""
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

def generate_content_pack(framework: Framework, constraints: str = None) -> dict:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Генерация полного комплекта материалов.
    [ОПТИМИЗАЦИЯ ТОКЕНОВ]: Используется минифицированный JSON и только необходимые поля.
    """
    # 1. Снижение токенов: создаем компактный словарь (только то, что нужно для контента)
    compact_data = {
        "modules": [{"title": m.title, "hours": m.total_hours} for m in framework.modules],
        "competencies": [c.name for c in framework.competencies]
    }
    # 2. Минификация: json.dumps без indent убирает лишние пробелы и переносы строк
    compact_json = json.dumps(compact_data, ensure_ascii=False)
    
    # 3. Ограничения методиста
    constraints_context = f"<constraints>{constraints}</constraints>" if constraints else ""

    # --- 1. ТЕСТЫ ---
    prompt_tests = f"""
    <role>Ты — тестолог.</role>
    <context>{compact_json}</context>
    {constraints_context}
    <task>Составь вопросы для теста. Если в constraints указано точное число (например, "10 вопросов"), ты ОБЯЗАН сделать ровно столько. Если не указано — сделай 5.</task>
    <format>[{{"question":"...", "options":["1","2","3","4"], "correct_answer":"1", "related_competency":"..."}}]</format>
    Верни ТОЛЬКО JSON-массив.
    """
    tests = _generate_with_retry(prompt_tests)
    if isinstance(tests, dict):
        for key in ["questions", "tests", "data", "items"]:
            if key in tests and isinstance(tests[key], list):
                tests = tests[key]
                break
        else:
            tests = [tests]
    if not isinstance(tests, list): tests = []

    # --- 2. СЕМИНАРЫ ---
    prompt_seminars = f"""
    <role>Ты — практик.</role>
    <context>{compact_json}</context>
    {constraints_context}
    <task>Составь 2 семинарских задания с критериями (если в constraints не указано иное).</task>
    <format>[{{"task":"...", "criteria":"...", "related_competency":"..."}}]</format>
    Верни ТОЛЬКО JSON-массив.
    """
    seminars = _generate_with_retry(prompt_seminars)
    if isinstance(seminars, dict): seminars = [seminars]
    if not isinstance(seminars, list): seminars = []

    # --- 3. ЛЕКЦИИ ---
    prompt_lectures = f"""
    <role>Ты — лектор.</role>
    <context>{compact_json}</context>
    <task>Составь развернутый план лекций (3-4 тезиса на модуль).</task>
    <format>[{{"module_title":"...", "theses":["..."]}}]</format>
    Верни ТОЛЬКО JSON-массив.
    """
    lectures = _generate_with_retry(prompt_lectures)
    if isinstance(lectures, dict) and "modules_plan" in lectures: lectures = lectures["modules_plan"]
    if not isinstance(lectures, list): lectures = []

    # --- 4. СЛАЙДЫ ---
    prompt_slides = f"""
    <role>Ты — дизайнер презентаций.</role>
    <context>{compact_json}</context>
    {constraints_context}
    <task>Составь структуру слайдов. Если в constraints указан конкретный модуль (например, "слайды для pandas"), сделай слайды ТОЛЬКО для него. Иначе — по 2 слайда на модуль.</task>
    <format>[{{"slide_title":"...", "module_title":"...", "bullets":["1","2"]}}]</format>
    Верни ТОЛЬКО JSON-массив.
    """
    slides = _generate_with_retry(prompt_slides)
    if not isinstance(slides, list): slides = []

    # --- 5. РАБОЧИЕ ПРОГРАММЫ ---
    prompt_work_programs = f"""
    <role>Ты — методист.</role>
    <context>{compact_json}</context>
    <task>Напиши краткое содержание (рабочую программу) для каждого модуля (2-3 предложения).</task>
    <format>[{{"module_title":"...", "description":"..."}}]</format>
    Верни ТОЛЬКО JSON-массив.
    """
    work_programs = _generate_with_retry(prompt_work_programs)
    if isinstance(work_programs, dict) and "work_programs" in work_programs: work_programs = work_programs["work_programs"]
    if not isinstance(work_programs, list): work_programs = []

    # --- 6. БИБЛИОГРАФИЯ ---
    prompt_bibliography = f"""
    <role>Ты — библиотекарь.</role>
    <context>{compact_json}</context>
    <task>Составь список из 3-5 реальных книг или статей для изучения этих тем.</task>
    <format>["Автор. Название. Год.", "..."]</format>
    Верни ТОЛЬКО JSON-массив строк.
    """
    bibliography = _generate_with_retry(prompt_bibliography)
    if isinstance(bibliography, dict) and "bibliography" in bibliography: bibliography = bibliography["bibliography"]
    if not isinstance(bibliography, list): bibliography = []

    return {
        "tests": tests, 
        "seminars": seminars, 
        "lectures": lectures,
        "slides": slides,
        "work_programs": work_programs,
        "bibliography": bibliography
    }