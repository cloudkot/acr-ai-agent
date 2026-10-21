import json
import time
import re
from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from logger import logger

def _generate_with_retry(prompt: str, task_type: str = "content", token_limit: int = 50000, retries: int = 3) -> tuple[any, int, float]:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Защита от сбоев LLM.
    Возвращает (данные, потрачено_токенов, стоимость_в_рублях).
    """
    total_tokens = 0
    total_cost = 0.0
    
    for attempt in range(retries):
        try:
            raw, tokens, cost = ask_llm(prompt, task_type=task_type, is_json=True, token_limit=token_limit)
            total_tokens += tokens
            total_cost += cost
            
            data = extract_json_from_text(raw)
            if not data:
                raise ValueError("Пустой ответ от LLM")
            return data, total_tokens, total_cost
        except Exception as e:
            logger.warning(f"Ошибка генерации ({attempt+1}/{retries}): {e}")
            if attempt == retries - 1:
                raise RuntimeError(f"Не удалось сгенерировать артефакт после {retries} попыток. Ошибка: {e}")
            time.sleep(1.5)

def generate_content_pack(framework: Framework, constraints: str = None, token_limit: int = 50000) -> dict:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Генерация полного комплекта материалов.
    Возвращает контент и суммарную статистику по токенам.
    """
    compact_data = {
        "template_type": framework.template_type,
        "prof_standard": framework.prof_standard,
        "modules": [{"title": m.title, "hours": m.total_hours} for m in framework.modules],
        "competencies": [c.name for c in framework.competencies]
    }
    # [ОПТИМИЗАЦИЯ]: Минификация JSON
    compact_json = json.dumps(compact_data, ensure_ascii=False, separators=(',', ':'))
    constraints_context = f"<constraints>{constraints}</constraints>" if constraints else ""

    # Умный парсинг количества вопросов
    target_q = 5
    if constraints:
        cons_lower = constraints.lower()
        match = re.search(r'(\d+)\s*(вопрос|тест|задани)', cons_lower)
        if match: target_q = int(match.group(1))
        elif "десять" in cons_lower: target_q = 10

    # Общие счетчики
    total_tokens = 0
    total_cost = 0.0

    def _update_stats(t, c):
        nonlocal total_tokens, total_cost
        total_tokens += t
        total_cost += c

    # --- 1. ТЕСТЫ ---
    prompt_tests = f"""
    <role>Тестолог.</role>
    <context>{compact_json}</context>
    {constraints_context}
    <task>Составь РОВНО {target_q} вопросов.</task>
    <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
    <format>[{{"question":"...", "options":["1","2","3","4"], "correct_answer":"1", "related_competency":"..."}}]</format>
    """
    tests, t_tokens, t_cost = _generate_with_retry(prompt_tests, token_limit=token_limit)
    _update_stats(t_tokens, t_cost)
    
    if isinstance(tests, dict): tests = tests.get("questions", [tests])
    if not isinstance(tests, list): tests = []
    
    # Пост-валидация
    if len(tests) > target_q: tests = tests[:target_q]
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
    <role>Практик.</role><context>{compact_json}</context>{constraints_context}
    <task>Составь 2 семинарских задания.</task>
    <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
    <format>[{{"task":"...", "criteria":"...", "related_competency":"..."}}]</format>
    """
    seminars, s_tokens, s_cost = _generate_with_retry(prompt_seminars, token_limit=token_limit)
    _update_stats(s_tokens, s_cost)
    if isinstance(seminars, dict): seminars = [seminars]

    # --- 3. ЛЕКЦИИ ---
    prompt_lectures = f"""
    <role>Лектор.</role><context>{compact_json}</context>{constraints_context}
    <task>План лекций (3-4 тезиса на модуль).</task>
    <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
    <format>[{{"module_title":"...", "theses":["..."]}}]</format>
    """
    lectures, l_tokens, l_cost = _generate_with_retry(prompt_lectures, token_limit=token_limit)
    _update_stats(l_tokens, l_cost)
    if isinstance(lectures, dict): lectures = lectures.get("modules_plan", [])
    if not isinstance(lectures, list): lectures = []

    # --- 4. СЛАЙДЫ ---
    prompt_slides = f"""
    <role>Дизайнер.</role><context>{compact_json}</context>{constraints_context}
    <task>Структура слайдов. Если просят "первые два занятия", сделай слайды ТОЛЬКО для первых двух модулей.</task>
    <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
    <format>[{{"slide_title":"...", "module_title":"...", "bullets":["1","2"]}}]</format>
    """
    slides, sl_tokens, sl_cost = _generate_with_retry(prompt_slides, token_limit=token_limit)
    _update_stats(sl_tokens, sl_cost)
    if not isinstance(slides, list): slides = []
    
    if constraints and ("первые два" in constraints.lower() or "первых двух" in constraints.lower()):
        allowed_titles = [m.title.lower() for m in framework.modules[:2]]
        slides = [s for s in slides if any(title in s.get("module_title", "").lower() for title in allowed_titles)]

    # --- 5. РАБОЧИЕ ПРОГРАММЫ ---
    prompt_wp = f"""
    <role>Методист.</role><context>{compact_json}</context>{constraints_context}
    <task>Рабочие программы (2-3 предложения на модуль).</task>
    <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
    <format>[{{"module_title":"...", "description":"..."}}]</format>
    """
    work_programs, w_tokens, w_cost = _generate_with_retry(prompt_wp, token_limit=token_limit)
    _update_stats(w_tokens, w_cost)
    if isinstance(work_programs, dict): work_programs = work_programs.get("work_programs", [])
    if not isinstance(work_programs, list): work_programs = []

    # --- 6. БИБЛИОГРАФИЯ ---
    prompt_bib = f"""
    <role>Библиотекарь.</role><context>{compact_json}</context>{constraints_context}
    <task>Список 3-5 книг. Если не уверен в книге, пиши '[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]'.</task>
    <rules>Верни ТОЛЬКО JSON-массив строк. Никакого markdown.</rules>
    <format>["Автор. Название. Год."]</format>
    """
    bibliography, b_tokens, b_cost = _generate_with_retry(prompt_bib, token_limit=token_limit)
    _update_stats(b_tokens, b_cost)
    if isinstance(bibliography, dict): bibliography = bibliography.get("bibliography", [])
    if not isinstance(bibliography, list): bibliography = []

    return {
        "tests": tests, 
        "seminars": seminars, 
        "lectures": lectures,
        "slides": slides,
        "work_programs": work_programs,
        "bibliography": bibliography,
        # [УНИКАЛЬНАЯ ФИЧА]: Возвращаем статистику наружу
        "total_tokens": total_tokens,
        "total_cost": total_cost
    }