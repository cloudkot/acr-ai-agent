import json
import re
import asyncio
from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from logger import logger

# [ФИКС]: Снижаем до 3, чтобы виртуалка не падала по памяти (OOM Killed)
MAX_CONCURRENT_REQUESTS = 3
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

async def _generate_async_retry(prompt: str, task_type: str = "content", retries: int = 3) -> tuple[any, int, float]:
    total_tokens = 0
    total_cost = 0.0
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
                if attempt == retries - 1: raise RuntimeError(f"Сбой: {e}")
                await asyncio.sleep(3)

# Заглушки (оставляем как есть, они хорошие)
def _fallback_seminar(framework: Framework, mod_title: str, mod_hours: int) -> dict:
    comps = [c.name for c in framework.competencies if any(mod_title.lower() in t.lower() for t in c.related_topics)]
    task = f"Разработать практический кейс по модулю '{mod_title}' ({mod_hours} ч.). Отработать навыки: {', '.join(comps) if comps else 'основные инструменты'}."
    return {"module_title": mod_title, "task": task, "criteria": "Критерии: 1) Работоспособность; 2) Соответствие ТЗ; 3) Защита.", "related_competency": comps[0] if comps else "Общая"}

def _fallback_lecture(framework: Framework, mod_title: str) -> dict:
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
    
    # [ФИКС]: 1 вопрос на каждые 15 часов (для 500 ч = 33 вопроса)
    target_q = max(10, total_hours // 15)
    if constraints:
        match = re.search(r'(\d+)\s*(вопрос|тест|задани)', constraints.lower())
        if match: target_q = int(match.group(1))

    total_tokens = 0
    total_cost = 0.0
    def _accumulate(t, c):
        nonlocal total_tokens, total_cost
        total_tokens += t
        total_cost += c

    async def fetch_tests_batch(batch_size: int, part_num: int):
        prompt = f"""
        <role>Тестолог.</role><context>{base_json}</context>{constraints_context}
        <task>Составь ровно {batch_size} РАЗНЫХ тестовых вопросов (часть {part_num}). Вопросы должны быть сложными и специфичными.</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown. correct_answer должен быть строкой из options.</rules>
        <format>[{{"question":"...", "options":["1","2","3","4"], "correct_answer":"1", "related_competency":"..."}}]</format>
        """
        try:
            data, t, c = await _generate_async_retry(prompt, "content")
            _accumulate(t, c)
            if isinstance(data, dict): data = data.get("questions", [data])
            if isinstance(data, list): return [x for x in data if isinstance(x, dict) and x.get("question") and x.get("question") != "None"]
            return []
        except Exception: return []

    async def fetch_single_lecture(mod_title: str):
        # [ФИКС]: Просим развернутые абзацы, а не просто заголовки
        prompt = f"""
        <role>Лектор.</role><context>{base_json}</context>{constraints_context}
        <task>Составь подробный план лекции для модуля "{mod_title}". Напиши 3-4 тезиса, каждый из которых состоит из 2-3 предложений. Раскрой конкретные технологии и методы.</task>
        <rules>Верни ТОЛЬКО JSON-массив из одного объекта. Поле module_title должно быть ровно "{mod_title}".</rules>
        <format>[{{"module_title":"{mod_title}", "theses":["Подробный тезис с объяснением 1...", "Подробный тезис 2..."]}}]</format>
        """
        try:
            data, t, c = await _generate_async_retry(prompt, "content")
            _accumulate(t, c)
            if isinstance(data, dict): data = data.get("modules_plan", [])
            if isinstance(data, list) and len(data) > 0: return data[0]
            return None
        except Exception: return None

    async def fetch_single_seminar(mod_title: str, mod_hours: int):
        prompt = f"""
        <role>Практик.</role><context>{base_json}</context>{constraints_context}
        <task>Составь ОДНО практическое задание (кейс) для модуля "{mod_title}" ({mod_hours} ч.). Опиши конкретную ситуацию, проблему и шаги решения.</task>
        <rules>Верни ТОЛЬКО JSON-массив из одного объекта. Поле module_title должно быть ровно "{mod_title}".</rules>
        <format>[{{"module_title":"{mod_title}", "task":"...", "criteria":"...", "related_competency":"..."}}]</format>
        """
        try:
            data, t, c = await _generate_async_retry(prompt, "content")
            _accumulate(t, c)
            if isinstance(data, dict): data = data.get("seminars", [data])
            if isinstance(data, list) and len(data) > 0: return data[0]
            return None
        except Exception: return None

    async def fetch_single_slides(mod_title: str):
        prompt = f"""
        <role>Дизайнер.</role><context>{base_json}</context>{constraints_context}
        <task>Структура слайдов для модуля "{mod_title}".</task>
        <rules>Верни ТОЛЬКО JSON-массив. Поле module_title должно быть ровно "{mod_title}".</rules>
        <format>[{{"slide_title":"...", "module_title":"{mod_title}", "bullets":["1","2"]}}]</format>
        """
        try:
            data, t, c = await _generate_async_retry(prompt, "content")
            _accumulate(t, c)
            if isinstance(data, dict): data = data.get("slides", [])
            if isinstance(data, list): return [x for x in data if isinstance(x, dict)]
            return []
        except Exception: return []

    async def fetch_single_work_program(mod_title: str):
        prompt = f"""
        <role>Методист.</role><context>{base_json}</context>{constraints_context}
        <task>Рабочая программа для модуля "{mod_title}". Напиши 3-4 предложения о том, что будет изучено и какие практические навыки будут получены.</task>
        <rules>Верни ТОЛЬКО JSON-массив из одного объекта. Поле module_title должно быть ровно "{mod_title}".</rules>
        <format>[{{"module_title":"{mod_title}", "description":"..."}}]</format>
        """
        try:
            data, t, c = await _generate_async_retry(prompt, "content")
            _accumulate(t, c)
            if isinstance(data, dict): data = data.get("work_programs", [])
            if isinstance(data, list) and len(data) > 0: return data[0]
            return None
        except Exception: return None

    async def fetch_bibliography():
        prompt = f"""
        <role>Библиотекарь.</role><context>{base_json}</context>{constraints_context}
        <task>Список 5-7 конкретных книг или статей.</task>
        <rules>Верни ТОЛЬКО JSON-массив строк.</rules>
        <format>["Автор. Название. Год."]</format>
        """
        try:
            data, t, c = await _generate_async_retry(prompt, "content")
            _accumulate(t, c)
            if isinstance(data, dict): data = data.get("bibliography", [])
            if isinstance(data, list): return [str(x) for x in data if isinstance(x, str)]
            return []
        except Exception: return []

    # Формируем задачи
    test_tasks = []
    questions_left = target_q
    part = 1
    while questions_left > 0:
        take = min(5, questions_left)
        test_tasks.append(fetch_tests_batch(take, part))
        questions_left -= take
        part += 1

    lecture_tasks = [fetch_single_lecture(mod.title) for mod in framework.modules]
    seminar_tasks = [fetch_single_seminar(mod.title, mod.total_hours) for mod in framework.modules]
    wp_tasks = [fetch_single_work_program(mod.title) for mod in framework.modules]
    
    slide_tasks = []
    if constraints and ("pandas" in constraints.lower()):
        slide_tasks = [fetch_single_slides(mod.title) for mod in framework.modules if "pandas" in mod.title.lower()]
    elif constraints and ("первые два" in constraints.lower()):
        slide_tasks = [fetch_single_slides(mod.title) for mod in framework.modules[:2]]
    else:
        slide_tasks = [fetch_single_slides(mod.title) for mod in framework.modules]

    all_tasks = test_tasks + lecture_tasks + seminar_tasks + wp_tasks + slide_tasks + [fetch_bibliography()]
    
    logger.info(f"Запуск {len(all_tasks)} задач (семафор {MAX_CONCURRENT_REQUESTS})...")
    results = await asyncio.gather(*all_tasks, return_exceptions=True)

    # Сборка результатов
    all_tests, final_lectures, final_seminars = [], [], []
    all_work_programs, all_slides, all_bibliography = [], [], []

    idx = 0
    for _ in test_tasks:
        res = results[idx]; idx += 1
        if isinstance(res, list): all_tests.extend(res)

    for _ in lecture_tasks:
        res = results[idx]; idx += 1
        if isinstance(res, dict): final_lectures.append(res)

    for _ in seminar_tasks:
        res = results[idx]; idx += 1
        if isinstance(res, dict): final_seminars.append(res)

    for _ in wp_tasks:
        res = results[idx]; idx += 1
        if isinstance(res, dict): all_work_programs.append(res)

    for _ in slide_tasks:
        res = results[idx]; idx += 1
        if isinstance(res, list): all_slides.extend(res)

    bib_res = results[idx]
    if isinstance(bib_res, list): all_bibliography.extend(bib_res)

    # --- СКЛЕЙКА ---
    final_tests = all_tests[:target_q]
    while len(final_tests) < target_q:
        mod_title = framework.modules[len(final_tests) % len(framework.modules)].title if framework.modules else "программе"
        final_tests.append(_fallback_test(framework, len(final_tests) + 1, mod_title))

    for mod in framework.modules:
        if not any(mod.title.lower() in l.get("module_title", "").lower() for l in final_lectures):
            final_lectures.append(_fallback_lecture(framework, mod.title))
            
        if not any(mod.title.lower() in s.get("module_title", "").lower() for s in final_seminars):
            final_seminars.append(_fallback_seminar(framework, mod.title, mod.total_hours))

    if not all_bibliography:
        all_bibliography = _fallback_bibliography(framework)

    return {
        "tests": final_tests, "seminars": final_seminars, "lectures": final_lectures,
        "slides": all_slides, "work_programs": all_work_programs, "bibliography": all_bibliography,
        "total_tokens": total_tokens, "total_cost": total_cost
    }