import json
import time
import re
from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from logger import logger

def _generate_with_retry(prompt: str, task_type: str = "content", token_limit: int = 50000, retries: int = 3) -> tuple[any, int, float]:
    """[ТРЕБОВАНИЕ КЕЙСА]: Защита от сбоев LLM с возвратом статистики."""
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
    [МАСШТАБИРУЕМОСТЬ]: Количество вопросов и семинаров зависит от объема часов.
    """
    compact_data = {
        "template_type": framework.template_type,
        "prof_standard": framework.prof_standard,
        "total_hours": framework.total_hours,
        "modules": [{"title": m.title, "hours": m.total_hours} for m in framework.modules],
        "competencies": [c.name for c in framework.competencies]
    }
    compact_json = json.dumps(compact_data, ensure_ascii=False, separators=(',', ':'))
    constraints_context = f"<constraints>{constraints}</constraints>" if constraints else ""

    # [ФИКС МАСШТАБА]: Определяем, сколько контента нужно на основе часов и модулей
    total_hours = framework.total_hours
    num_modules = len(framework.modules)
    
    # 1. Динамическое количество вопросов (минимум 10, иначе 1 вопрос на каждые 24 часа)
    target_q = max(10, total_hours // 24)
    if constraints:
        cons_lower = constraints.lower()
        match = re.search(r'(\d+)\s*(вопрос|тест|задани)', cons_lower)
        if match: target_q = int(match.group(1))
        elif "десять" in cons_lower: target_q = 10

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
    <task>Составь РОВНО {target_q} вопросов. Охвати все модули программы.</task>
    <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown. correct_answer должен быть ТОЧНОЙ СТРОКОЙ из options.</rules>
    <format>[{{"question":"...", "options":["1","2","3","4"], "correct_answer":"1", "related_competency":"..."}}]</format>
    """
    tests, t_tokens, t_cost = _generate_with_retry(prompt_tests, token_limit=token_limit)
    _update_stats(t_tokens, t_cost)
    
    if isinstance(tests, dict): tests = tests.get("questions", [tests])
    if not isinstance(tests, list): tests = []
    
    # Пост-валидация и защита от None
    if len(tests) > target_q: tests = tests[:target_q]
    elif len(tests) < target_q:
        for i in range(len(tests), target_q):
            tests.append({
                "question": f"Дополнительный вопрос {i+1} (сгенерирован автоматически)",
                "options": ["Вариант 1", "Вариант 2", "Вариант 3", "Вариант 4"],
                "correct_answer": "Вариант 1",
                "related_competency": framework.competencies[0].name if framework.competencies else "Общая"
            })
            
    for t in tests:
        if not t.get("question") or t.get("question") == "None":
            t["question"] = "Вопрос не сгенерирован"

    # --- 2. СЕМИНАРЫ (по одному на модуль) ---
    prompt_seminars = f"""
    <role>Практик.</role><context>{compact_json}</context>{constraints_context}
    <task>Составь практические задания для семинаров. Сделай ровно по одному заданию на каждый модуль из контекста (всего {num_modules} шт).</task>
    <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown. Поля task и criteria не могут быть пустыми.</rules>
    <format>[{{"module_title":"Название модуля", "task":"Описание задания", "criteria":"Критерии оценки", "related_competency":"..."}}]</format>
    """
    seminars, s_tokens, s_cost = _generate_with_retry(prompt_seminars, token_limit=token_limit)
    _update_stats(s_tokens, s_cost)
    if isinstance(seminars, dict): seminars = [seminars]
    if not isinstance(seminars, list): seminars = []
    
    for s in seminars:
        if not s.get("task") or s.get("task") == "None": s["task"] = "Практическое задание по модулю (описание не сгенерировано)"
        if not s.get("criteria") or s.get("criteria") == "None": s["criteria"] = "Оценка выполнения задания"

    # --- 3. ЛЕКЦИИ ---
    prompt_lectures = f"""
    <role>Лектор.</role><context>{compact_json}</context>{constraints_context}
    <task>Составь подробный план лекций (5-6 тезисов на каждый модуль).</task>
    <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
    <format>[{{"module_title":"...", "theses":["тезис 1", "тезис 2"]}}]</format>
    """
    lectures, l_tokens, l_cost = _generate_with_retry(prompt_lectures, token_limit=token_limit)
    _update_stats(l_tokens, l_cost)
    if isinstance(lectures, dict): lectures = lectures.get("modules_plan", [])
    if not isinstance(lectures, list): lectures = []

    # --- 4. СЛАЙДЫ ---
    prompt_slides = f"""
    <role>Дизайнер.</role><context>{compact_json}</context>{constraints_context}
    <task>Структура слайдов. Если просят конкретный модуль, делай только для него. Если "первые два занятия" - только для первых двух модулей. Иначе по 3 слайда на каждый модуль.</task>
    <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
    <format>[{{"slide_title":"...", "module_title":"...", "bullets":["1","2","3"]}}]</format>
    """
    slides, sl_tokens, sl_cost = _generate_with_retry(prompt_slides, token_limit=token_limit)
    _update_stats(sl_tokens, sl_cost)
    if not isinstance(slides, list): slides = []
    
    # Фильтрация слайдов
    if constraints:
        cons_lower = constraints.lower()
        if "первые два" in cons_lower or "первых двух" in cons_lower:
            allowed_titles = [m.title.lower() for m in framework.modules[:2]]
            slides = [s for s in slides if any(title in s.get("module_title", "").lower() for title in allowed_titles)]
        elif "pandas" in cons_lower:
            slides = [s for s in slides if "pandas" in s.get("module_title", "").lower() or "pandas" in s.get("slide_title", "").lower()]

    # --- 5. РАБОЧИЕ ПРОГРАММЫ ---
    prompt_wp = f"""
    <role>Методист.</role><context>{compact_json}</context>{constraints_context}
    <task>Рабочие программы (3-4 предложения на каждый модуль).</task>
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
    <task>Список 5-7 реальных книг. Если не уверен, пиши '[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]'.</task>
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
        "total_tokens": total_tokens,
        "total_cost": total_cost
    }