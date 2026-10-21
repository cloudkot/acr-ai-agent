import json
import re
import asyncio
from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from logger import logger

# [ФИКС]: Ограничиваем количество одновременных запросов к LLM, чтобы не ловить Rate Limit
MAX_CONCURRENT_REQUESTS = 4
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

def _chunk_list(lst: list, chunk_size: int):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

async def _generate_async_retry(prompt: str, task_type: str = "content", retries: int = 3) -> tuple[any, int, float]:
    total_tokens = 0
    total_cost = 0.0
    # Используем семафор для контроля параллельных запросов
    async with semaphore:
        for attempt in range(retries):
            try:
                raw, tokens, cost = await ask_llm(prompt, task_type, True)
                total_tokens += tokens
                total_cost += cost
                data = extract_json_from_text(raw)
                if not data: raise ValueError("Пустой ответ от LLM")
                return data, total_tokens, total_cost
            except Exception as e:
                logger.warning(f"Ошибка генерации ({attempt+1}/{retries}): {e}")
                if attempt == retries - 1: raise RuntimeError(f"Сбой после {retries} попыток: {e}")
                await asyncio.sleep(2) # Увеличили паузу перед повтором

# --- УМНЫЕ ЗАГЛУШКИ (если LLM реально упала) ---

def _fallback_seminar(framework: Framework, mod_title: str, mod_hours: int) -> dict:
    comps = [c.name for c in framework.competencies if any(mod_title.lower() in t.lower() for t in c.related_topics)]
    task = f"Разработать практический кейс по модулю '{mod_title}' ({mod_hours} ч.). Отработать навыки: {', '.join(comps) if comps else 'основные инструменты'}."
    return {
        "module_title": mod_title, "task": task,
        "criteria": "Критерии: 1) Работоспособность; 2) Соответствие ТЗ; 3) Защита.",
        "related_competency": comps[0] if comps else "Общая"
    }

def _fallback_lecture(framework: Framework, mod_title: str) -> dict:
    # Извлекаем ключевые слова из названия модуля для тезисов
    title_clean = mod_title.replace("Модуль", "").strip()
    theses = [
        f"Архитектура и основные концепции: {title_clean}",
        f"Обзор инструментов и практик в рамках {title_clean}",
        f"Разбор типичных ошибок и паттернов проектирования",
        f"Практическое применение {title_clean} в реальных проектах"
    ]
    return {"module_title": mod_title, "theses": theses}

def _fallback_test(framework: Framework, index: int, mod_title: str) -> dict:
    return {
        "question": f"Какой основной подход используется при работе с {mod_title}?",
        "options": [f"Применение инструментов {mod_title}", "Ручное конфигурирование", "Отказ от автоматизации", "Использование устаревших методов"],
        "correct_answer": f"Применение инструментов {mod_title}",
        "related_competency": framework.competencies[0].name if framework.competencies else "Общая"
    }

def _fallback_bibliography(framework: Framework) -> list:
    topics = ", ".join([m.title for m in framework.modules[:2]])
    return [
        f"Практическое руководство по {topics}. 2024.",
        f"Сборник лучших практик: {framework.prof_standard or 'Современные IT-решения'}. 2023.",
        f"Архитектура и паттерны проектирования. 2025."
    ]

async def generate_content_pack(framework: Framework, constraints: str = None) -> dict:
    compact_data = {
        "template_type": framework.template_type, "prof_standard": framework.prof_standard,
        "total_hours": framework.total_hours, "competencies": [c.name for c in framework.competencies]
    }
    base_json = json.dumps(compact_data, ensure_ascii=False, separators=(',', ':'))
    constraints_context = f"<constraints>{constraints}</constraints>" if constraints else ""

    total_hours = framework.total_hours
    target_q = max(10, total_hours // 24)
    if constraints:
        match = re.search(r'(\d+)\s*(вопрос|тест|задани)', constraints.lower())
        if match: target_q = int(match.group(1))

    total_tokens = 0
    total_cost = 0.0
    def _accumulate(t, c):
        nonlocal total_tokens, total_cost
        total_tokens += t
        total_cost += c

    # --- 1. ТЕСТЫ (по 5 штук) ---
    async def fetch_tests_batch(batch_size: int, part_num: int):
        prompt = f"""
        <role>Тестолог.</role><context>{base_json}</context>{constraints_context}
        <task>Составь ровно {batch_size} РАЗНЫХ тестовых вопросов (часть {part_num}). Один вопрос должен проверять одну конкретную компетенцию.</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown. Вопросы должны быть уникальными и специфичными.</rules>
        <format>[{{"question":"...", "options":["1","2","3","4"], "correct_answer":"1", "related_competency":"..."}}]</format>
        """
        try:
            data, t, c = await _generate_async_retry(prompt, "content")
            _accumulate(t, c)
            if isinstance(data, dict): data = data.get("questions", [data])
            if isinstance(data, list): return [x for x in data if isinstance(x, dict) and x.get("question") and x.get("question") != "None"]
            return []
        except Exception: return []

    # --- 2. ЛЕКЦИИ (по 3 модуля) ---
    async def fetch_lectures_batch(batch):
        titles = [m.title for m in batch]
        prompt = f"""
        <role>Лектор.</role><context>{base_json}</context>{constraints_context}
        <task>Составь план лекций (по 4 конкретных технических тезиса) для модулей: {titles}.</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown. Тезисы должны раскрывать конкретные технологии, а не быть общими словами.</rules>
        <format>[{{"module_title":"...", "theses":["Конкретный тезис 1", "Конкретный тезис 2"]}}]</format>
        """
        try:
            data, t, c = await _generate_async_retry(prompt, "content")
            _accumulate(t, c)
            if isinstance(data, dict): data = data.get("modules_plan", [])
            if isinstance(data, list): return [x for x in data if isinstance(x, dict) and x.get("theses")]
            return []
        except Exception: return []

    # --- 3. СЕМИНАРЫ (по 3 модуля) ---
    async def fetch_seminars_batch(batch):
        titles = [m.title for m in batch]
        prompt = f"""
        <role>Практик.</role><context>{base_json}</context>{constraints_context}
        <task>Составь практические задания для модулей: {titles}. Задание должно описывать конкретный кейс.</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
        <format>[{{"module_title":"...", "task":"...", "criteria":"...", "related_competency":"..."}}]</format>
        """
        try:
            data, t, c = await _generate_async_retry(prompt, "content")
            _accumulate(t, c)
            if isinstance(data, dict): data = data.get("seminars", [data])
            if isinstance(data, list): return [x for x in data if isinstance(x, dict) and x.get("task") and x.get("task") != "None"]
            return []
        except Exception: return []

    # --- 4. СЛАЙДЫ (по 3 модуля) ---
    async def fetch_slides_batch(batch):
        titles = [m.title for m in batch]
        prompt = f"""
        <role>Дизайнер.</role><context>{base_json}</context>{constraints_context}
        <task>Структура слайдов для модулей: {titles}.</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
        <format>[{{"slide_title":"...", "module_title":"...", "bullets":["1","2"]}}]</format>
        """
        try:
            data, t, c = await _generate_async_retry(prompt, "content")
            _accumulate(t, c)
            if isinstance(data, dict): data = data.get("slides", [])
            if isinstance(data, list): return [x for x in data if isinstance(x, dict)]
            return []
        except Exception: return []

    # --- 5. РАБОЧИЕ ПРОГРАММЫ (по 3 модуля) ---
    async def fetch_work_programs_batch(batch):
        titles = [m.title for m in batch]
        prompt = f"""
        <role>Методист.</role><context>{base_json}</context>{constraints_context}
        <task>Рабочие программы для модулей: {titles}. Напиши по 2-3 предложения о содержании.</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
        <format>[{{"module_title":"...", "description":"..."}}]</format>
        """
        try:
            data, t, c = await _generate_async_retry(prompt, "content")
            _accumulate(t, c)
            if isinstance(data, dict): data = data.get("work_programs", [])
            if isinstance(data, list): return [x for x in data if isinstance(x, dict)]
            return []
        except Exception: return []

    # --- 6. БИБЛИОГРАФИЯ ---
    async def fetch_bibliography():
        prompt = f"""
        <role>Библиотекарь.</role><context>{base_json}</context>{constraints_context}
        <task>Список 5 конкретных книг.</task>
        <rules>Верни ТОЛЬКО JSON-массив строк. Никакого markdown.</rules>
        <format>["Автор. Название. Год."]</format>
        """
        try:
            data, t, c = await _generate_async_retry(prompt, "content")
            _accumulate(t, c)
            if isinstance(data, dict): data = data.get("bibliography", [])
            if isinstance(data, list): return [str(x) for x in data if isinstance(x, str)]
            return []
        except Exception: return []

    # --- СБОРКА ЗАДАЧ ---
    test_tasks = []
    questions_left = target_q
    part = 1
    while questions_left > 0:
        take = min(5, questions_left)
        test_tasks.append(fetch_tests_batch(take, part))
        questions_left -= take
        part += 1

    module_batches = list(_chunk_list(framework.modules, 3))
    module_tasks = []
    for batch in module_batches:
        module_tasks.append(fetch_seminars_batch(batch))
        module_tasks.append(fetch_lectures_batch(batch))
        module_tasks.append(fetch_slides_batch(batch))
        module_tasks.append(fetch_work_programs_batch(batch))

    all_tasks = test_tasks + module_tasks + [fetch_bibliography()]
    
    logger.info(f"Запуск {len(all_tasks)} гранулярных запросов (с ограничением {MAX_CONCURRENT_REQUESTS} одновременно)...")
    results = await asyncio.gather(*all_tasks, return_exceptions=True)

    all_tests, all_seminars, all_lectures = [], [], []
    all_slides, all_work_programs, all_bibliography = [], [], []

    idx = 0
    for _ in test_tasks:
        res = results[idx]; idx += 1
        if isinstance(res, list): all_tests.extend(res)

    for _ in module_batches:
        sem_res = results[idx]; idx += 1
        lec_res = results[idx]; idx += 1
        sld_res = results[idx]; idx += 1
        wp_res = results[idx]; idx += 1
        
        if isinstance(sem_res, list): all_seminars.extend(sem_res)
        if isinstance(lec_res, list): all_lectures.extend(lec_res)
        if isinstance(sld_res, list): all_slides.extend(sld_res)
        if isinstance(wp_res, list): all_work_programs.extend(wp_res)

    bib_res = results[idx]
    if isinstance(bib_res, list): all_bibliography.extend(bib_res)

    # --- УМНАЯ СКЛЕЙКА ---
    final_tests = all_tests[:target_q]
    while len(final_tests) < target_q:
        mod_title = framework.modules[len(final_tests) % len(framework.modules)].title if framework.modules else "программе"
        final_tests.append(_fallback_test(framework, len(final_tests) + 1, mod_title))

    final_seminars, final_lectures = [], []
    for mod in framework.modules:
        sem = next((s for s in all_seminars if mod.title.lower() in s.get("module_title", "").lower()), None)
        final_seminars.append(sem if sem else _fallback_seminar(framework, mod.title, mod.total_hours))
        
        lec = next((l for l in all_lectures if mod.title.lower() in l.get("module_title", "").lower()), None)
        final_lectures.append(lec if lec else _fallback_lecture(framework, mod.title))

    if not all_bibliography:
        all_bibliography = _fallback_bibliography(framework)

    # Фильтрация слайдов
    if constraints:
        cons_lower = constraints.lower()
        if "первые два" in cons_lower or "первых двух" in cons_lower:
            allowed = [m.title.lower() for m in framework.modules[:2]]
            all_slides = [s for s in all_slides if any(a in s.get("module_title", "").lower() for a in allowed)]
        elif "pandas" in cons_lower:
            all_slides = [s for s in all_slides if "pandas" in s.get("module_title", "").lower() or "pandas" in s.get("slide_title", "").lower()]

    return {
        "tests": final_tests, "seminars": final_seminars, "lectures": final_lectures,
        "slides": all_slides, "work_programs": all_work_programs, "bibliography": all_bibliography,
        "total_tokens": total_tokens, "total_cost": total_cost
    }