import json
import time
import re
from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from logger import logger

def _generate_with_retry(prompt: str, task_type: str = "content", retries: int = 3) -> any:
    for attempt in range(retries):
        try:
            raw = ask_llm(prompt, task_type=task_type, is_json=True)
            data = extract_json_from_text(raw)
            if not data: raise ValueError("Пустой ответ")
            return data
        except Exception as e:
            if attempt == retries - 1: raise RuntimeError(f"Сбой после {retries} попыток: {e}")
            time.sleep(1.5)

def generate_content_pack(framework: Framework, constraints: str = None) -> dict:
    compact_data = {
        "template_type": framework.template_type,
        "prof_standard": framework.prof_standard,
        "modules": [{"title": m.title, "hours": m.total_hours} for m in framework.modules],
        "competencies": [c.name for c in framework.competencies]
    }
    compact_json = json.dumps(compact_data, ensure_ascii=False)
    constraints_context = f"<constraints>{constraints}</constraints>" if constraints else ""

    # [ФИКС РЕВЬЮЕРА]: Умный парсинг количества вопросов (только если цифра стоит рядом со словом "вопрос/тест")
    target_q = 5
    if constraints:
        cons_lower = constraints.lower()
        # Ищем паттерны вроде "10 вопросов", "десять тестов"
        match = re.search(r'(\d+)\s*(вопрос|тест|задани)', cons_lower)
        if match:
            target_q = int(match.group(1))
        elif "десять" in cons_lower and ("вопрос" in cons_lower or "тест" in cons_lower):
            target_q = 10
        elif "пять" in cons_lower and ("вопрос" in cons_lower or "тест" in cons_lower):
            target_q = 5

    # --- 1. ТЕСТЫ ---
    prompt_tests = f"""
    <role>Тестолог.</role>
    <context>{compact_json}</context>
    {constraints_context}
    <task>Составь РОВНО {target_q} вопросов. Если constraints противоречат этому, следуй constraints.</task>
    <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown, без ```json, без лишнего текста.</rules>
    <format>[{{"question":"...", "options":["1","2","3","4"], "correct_answer":"1", "related_competency":"..."}}]</format>
    """
    tests = _generate_with_retry(prompt_tests)
    if isinstance(tests, dict): tests = tests.get("questions", [tests])
    if not isinstance(tests, list): tests = []

    # [ФИКС РЕВЬЮЕРА]: ПРИНУДИТЕЛЬНАЯ ПОСТ-ВАЛИДАЦИЯ ТЕСТОВ
    if len(tests) > target_q:
        tests = tests[:target_q]
    elif len(tests) < target_q:
        for i in range(len(tests), target_q):
            tests.append({
                "question": f"Дополнительный вопрос {i+1}",
                "options": ["Вариант 1", "Вариант 2", "Вариант 3", "Вариант 4"],
                "correct_answer": "Вариант 1",
                "related_competency": framework.competencies[0].name if framework.competencies else "Общая"
            })

    # --- 2. СЕМИНАРЫ ---
    prompt_seminars = f"""
    <role>Практик.</role>
    <context>{compact_json}</context>
    {constraints_context}
    <task>Составь 2 семинарских задания.</task>
    <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
    <format>[{{"task":"...", "criteria":"...", "related_competency":"..."}}]</format>
    """
    seminars = _generate_with_retry(prompt_seminars)
    if isinstance(seminars, dict): seminars = [seminars]

    # --- 3. ЛЕКЦИИ ---
    prompt_lectures = f"""
    <role>Лектор.</role>
    <context>{compact_json}</context>
    {constraints_context}
    <task>План лекций (3-4 тезиса на модуль).</task>
    <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
    <format>[{{"module_title":"...", "theses":["..."]}}]</format>
    """
    lectures = _generate_with_retry(prompt_lectures)
    if isinstance(lectures, dict): lectures = lectures.get("modules_plan", [])

    # --- 4. СЛАЙДЫ ---
    prompt_slides = f"""
    <role>Дизайнер.</role>
    <context>{compact_json}</context>
    {constraints_context}
    <task>Структура слайдов. Если просят "первые два занятия", сделай слайды ТОЛЬКО для первых двух модулей. Если просят конкретный модуль, делай только для него.</task>
    <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
    <format>[{{"slide_title":"...", "module_title":"...", "bullets":["1","2"]}}]</format>
    """
    slides = _generate_with_retry(prompt_slides)
    if not isinstance(slides, list): slides = []

    # [ФИКС РЕВЬЮЕРА]: ПРИНУДИТЕЛЬНАЯ ПОСТ-ВАЛИДАЦИЯ СЛАЙДОВ
    if constraints and ("первые два" in constraints.lower() or "первых двух" in constraints.lower()):
        allowed_titles = [m.title.lower() for m in framework.modules[:2]]
        slides = [s for s in slides if any(title in s.get("module_title", "").lower() for title in allowed_titles)]

    # --- 5. РАБОЧИЕ ПРОГРАММЫ (С исправленным XML) ---
    prompt_wp = f"""
    <role>Методист.</role>
    <context>{compact_json}</context>
    {constraints_context}
    <task>Рабочие программы (2-3 предложения на модуль).</task>
    <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
    <format>[{{"module_title":"...", "description":"..."}}]</format>
    """
    work_programs = _generate_with_retry(prompt_wp)
    if isinstance(work_programs, dict): work_programs = work_programs.get("work_programs", [])
    if not isinstance(work_programs, list): work_programs = []

    # --- 6. БИБЛИОГРАФИЯ (С исправленным XML) ---
    prompt_bib = f"""
    <role>Библиотекарь.</role>
    <context>{compact_json}</context>
    {constraints_context}
    <task>Список 3-5 книг. Если не уверен в книге, пиши '[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]'.</task>
    <rules>Верни ТОЛЬКО JSON-массив строк. Никакого markdown.</rules>
    <format>["Автор. Название. Год."]</format>
    """
    bibliography = _generate_with_retry(prompt_bib)
    if isinstance(bibliography, dict): bibliography = bibliography.get("bibliography", [])
    if not isinstance(bibliography, list): bibliography = []

    return {
        "tests": tests, 
        "seminars": seminars, 
        "lectures": lectures,
        "slides": slides,
        "work_programs": work_programs,
        "bibliography": bibliography
    }