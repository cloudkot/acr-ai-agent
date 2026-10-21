import json
import re
import asyncio
from cloud import ask_llm, MODEL_FAST
from schemas import Framework
from utils.json_parser import extract_json_from_text
from config import config
from logger import logger

# [ФИКС РЕВЬЮЕРА]: Используем конфигурацию вместо хардкода
MAX_CONCURRENT_REQUESTS = config.MAX_CONCURRENT_REQUESTS
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

# ==========================================
# [УТИЛИТЫ]: Retry и Fallback
# ==========================================

async def _generate_async_retry(prompt: str, fallback_prompt: str = None, task_type: str = "content", retries: int = 3) -> tuple[any, int, float]:
    """[ТРЕБОВАНИЕ КЕЙСА]: Асинхронная обертка с ретраями и LLM-fallback."""
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
                if attempt == retries - 1: 
                    # Уровень 1: LLM-Fallback (упрощенный запрос)
                    if fallback_prompt:
                        logger.info("Запуск LLM-fallback (упрощенный запрос)...")
                        try:
                            raw_fb, t_fb, c_fb = await ask_llm(fallback_prompt, MODEL_FAST, True)
                            total_tokens += t_fb
                            total_cost += c_fb
                            data_fb = extract_json_from_text(raw_fb)
                            if data_fb: return data_fb, total_tokens, total_cost
                        except Exception as e_fb:
                            logger.error(f"LLM-fallback тоже упал: {e_fb}")
                    
                    raise RuntimeError(f"Сбой после {retries} попыток: {e}")
                await asyncio.sleep(2)

def _rule_based_fallback_seminar(framework: Framework, mod_title: str, mod_hours: int) -> dict:
    comps = [c.name for c in framework.competencies if any(mod_title.lower() in t.lower() for t in c.related_topics)]
    task = f"Разработать практический кейс по модулю '{mod_title}' ({mod_hours} ч.). Отработать навыки: {', '.join(comps) if comps else 'основные инструменты'}."
    return {"module_title": mod_title, "task": task, "criteria": "Критерии: 1) Работоспособность; 2) Соответствие ТЗ; 3) Защита.", "related_competency": comps[0] if comps else "Общая"}

def _rule_based_fallback_lecture(framework: Framework, mod_title: str) -> dict:
    title_clean = mod_title.replace("Модуль", "").strip()
    theses = [
        f"Архитектура и основные концепции: {title_clean}",
        f"Обзор инструментов и практик в рамках {title_clean}",
        f"Разбор типичных ошибок и паттернов проектирования",
        f"Практическое применение {title_clean} в реальных проектах"
    ]
    return {"module_title": mod_title, "theses": theses}

def _rule_based_fallback_test(framework: Framework, index: int, mod_title: str) -> dict:
    return {"question": f"Какой основной подход используется при работе с {mod_title}?", "options": [f"Применение инструментов {mod_title}", "Ручное конфигурирование", "Отказ от автоматизации", "Использование устаревших методов"], "correct_answer": f"Применение инструментов {mod_title}", "related_competency": framework.competencies[0].name if framework.competencies else "Общая"}

def _rule_based_fallback_bibliography(framework: Framework) -> list:
    topics = ", ".join([m.title for m in framework.modules[:2]])
    return [f"Практическое руководство по {topics}. 2024.", f"Сборник лучших практик. 2023.", f"Архитектура и паттерны проектирования. 2025."]

# ==========================================
# [ИЗОЛИРОВАННЫЕ ГЕНЕРАТОРЫ]: Каждый возвращает (данные, токены, стоимость)
# ==========================================

async def generate_tests(framework: Framework, constraints: str = None) -> tuple[list, int, float]:
    """Генерирует тестовые вопросы (с батчингом по 5 штук)."""
    compact_data = {"total_hours": framework.total_hours, "competencies": [c.name for c in framework.competencies]}
    base_json = json.dumps(compact_data, ensure_ascii=False, separators=(',', ':'))
    constraints_context = f"<constraints>{constraints}</constraints>" if constraints else ""

    total_hours = framework.total_hours
    target_q = max(config.MIN_QUESTIONS, total_hours // config.QUESTIONS_PER_HOURS)
    if constraints:
        match = re.search(r'(\d+)\s*(вопрос|тест|задани)', constraints.lower())
        if match: target_q = int(match.group(1))

    total_tokens = 0
    total_cost = 0.0

    async def fetch_tests_batch(batch_size: int, part_num: int):
        prompt = f"""
        <role>Тестолог.</role><context>{base_json}</context>{constraints_context}
        <task>Составь ровно {batch_size} РАЗНЫХ тестовых вопросов (часть {part_num}). Вопросы должны быть специфичными.</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
        <format>[{{"question":"...", "options":["1","2","3","4"], "correct_answer":"1", "related_competency":"..."}}]</format>
        """
        fallback_prompt = f"Составь {batch_size} тестовых вопроса по теме {framework.goal[:50]}. Формат JSON: [{{'question':'...', 'options':['1','2','3','4'], 'correct_answer':'1', 'related_competency':'...'}}]"
        try:
            data, t, c = await _generate_async_retry(prompt, fallback_prompt, "content")
            return data, t, c
        except Exception: return [], 0, 0.0

    tasks = []
    questions_left = target_q
    part = 1
    while questions_left > 0:
        take = min(5, questions_left)
        tasks.append(fetch_tests_batch(take, part))
        questions_left -= take
        part += 1

    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_tests = []
    
    for res in results:
        if isinstance(res, Exception): continue
        data, t, c = res
        total_tokens += t
        total_cost += c
        if isinstance(data, dict): data = data.get("questions", [data])
        if isinstance(data, list):
            all_tests.extend([x for x in data if isinstance(x, dict) and x.get("question") and x.get("question") != "None"])

    # Сборка с fallback
    final_tests = all_tests[:target_q]
    while len(final_tests) < target_q:
        mod_title = framework.modules[len(final_tests) % len(framework.modules)].title if framework.modules else "программе"
        final_tests.append(_rule_based_fallback_test(framework, len(final_tests) + 1, mod_title))
        
    return final_tests, total_tokens, total_cost

async def generate_lectures(framework: Framework, constraints: str = None) -> tuple[list, int, float]:
    """Генерирует планы лекций (по одному на модуль)."""
    compact_data = {"competencies": [c.name for c in framework.competencies]}
    base_json = json.dumps(compact_data, ensure_ascii=False, separators=(',', ':'))
    constraints_context = f"<constraints>{constraints}</constraints>" if constraints else ""

    async def fetch_single_lecture(mod_title: str):
        prompt = f"""
        <role>Лектор.</role><context>{base_json}</context>{constraints_context}
        <task>Составь подробный план лекции для модуля "{mod_title}". Напиши 3-4 тезиса, каждый по 2-3 предложения.</task>
        <rules>Верни ТОЛЬКО JSON-массив из одного объекта. module_title = "{mod_title}".</rules>
        <format>[{{"module_title":"{mod_title}", "theses":["...", "..."]}}]</format>
        """
        fallback_prompt = f"Напиши 3 тезиса для лекции по теме '{mod_title}'. Формат JSON: [{{'module_title':'{mod_title}', 'theses':['...', '...']}}]"
        try:
            data, t, c = await _generate_async_retry(prompt, fallback_prompt, "content")
            if isinstance(data, dict): data = data.get("modules_plan", [])
            if isinstance(data, list) and len(data) > 0: return data[0], t, c
            return None, t, c
        except Exception: return None, 0, 0.0

    tasks = [fetch_single_lecture(mod.title) for mod in framework.modules]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    final_lectures = []
    total_tokens, total_cost = 0, 0.0
    for res in results:
        if isinstance(res, Exception): continue
        data, t, c = res
        total_tokens += t
        total_cost += c
        if data: final_lectures.append(data)

    for mod in framework.modules:
        if not any(mod.title.lower() in l.get("module_title", "").lower() for l in final_lectures):
            final_lectures.append(_rule_based_fallback_lecture(framework, mod.title))

    return final_lectures, total_tokens, total_cost

async def generate_seminars(framework: Framework, constraints: str = None) -> tuple[list, int, float]:
    """Генерирует задания для семинаров (по одному на модуль)."""
    compact_data = {"competencies": [c.name for c in framework.competencies]}
    base_json = json.dumps(compact_data, ensure_ascii=False, separators=(',', ':'))
    constraints_context = f"<constraints>{constraints}</constraints>" if constraints else ""

    async def fetch_single_seminar(mod_title: str, mod_hours: int):
        prompt = f"""
        <role>Практик.</role><context>{base_json}</context>{constraints_context}
        <task>Составь ОДНО практическое задание (кейс) для модуля "{mod_title}" ({mod_hours} ч.).</task>
        <rules>Верни ТОЛЬКО JSON-массив из одного объекта. module_title = "{mod_title}".</rules>
        <format>[{{"module_title":"{mod_title}", "task":"...", "criteria":"...", "related_competency":"..."}}]</format>
        """
        fallback_prompt = f"Придумай 1 практическое задание для модуля '{mod_title}'. Формат JSON: [{{'module_title':'{mod_title}', 'task':'...', 'criteria':'...', 'related_competency':'...'}}]"
        try:
            data, t, c = await _generate_async_retry(prompt, fallback_prompt, "content")
            if isinstance(data, dict): data = data.get("seminars", [data])
            if isinstance(data, list) and len(data) > 0: return data[0], t, c
            return None, t, c
        except Exception: return None, 0, 0.0

    tasks = [fetch_single_seminar(mod.title, mod.total_hours) for mod in framework.modules]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    final_seminars = []
    total_tokens, total_cost = 0, 0.0
    for res in results:
        if isinstance(res, Exception): continue
        data, t, c = res
        total_tokens += t
        total_cost += c
        if data: final_seminars.append(data)

    for mod in framework.modules:
        if not any(mod.title.lower() in s.get("module_title", "").lower() for s in final_seminars):
            final_seminars.append(_rule_based_fallback_seminar(framework, mod.title, mod.total_hours))

    return final_seminars, total_tokens, total_cost

async def generate_slides(framework: Framework, constraints: str = None) -> tuple[list, int, float]:
    """Генерирует структуру слайдов (с учетом ограничений)."""
    compact_data = {"competencies": [c.name for c in framework.competencies]}
    base_json = json.dumps(compact_data, ensure_ascii=False, separators=(',', ':'))
    constraints_context = f"<constraints>{constraints}</constraints>" if constraints else ""

    async def fetch_single_slides(mod_title: str):
        prompt = f"""
        <role>Дизайнер.</role><context>{base_json}</context>{constraints_context}
        <task>Структура слайдов для модуля "{mod_title}".</task>
        <rules>Верни ТОЛЬКО JSON-массив. module_title = "{mod_title}".</rules>
        <format>[{{"slide_title":"...", "module_title":"{mod_title}", "bullets":["1","2"]}}]</format>
        """
        fallback_prompt = f"Придумай 2 слайда для модуля '{mod_title}'. Формат JSON: [{{'slide_title':'...', 'module_title':'{mod_title}', 'bullets':['1','2']}}]"
        try:
            data, t, c = await _generate_async_retry(prompt, fallback_prompt, "content")
            if isinstance(data, dict): data = data.get("slides", [])
            if isinstance(data, list): return [x for x in data if isinstance(x, dict)], t, c
            return [], t, c
        except Exception: return [], 0, 0.0

    # Ограничения на модули для слайдов
    target_modules = framework.modules
    if constraints:
        cons_lower = constraints.lower()
        if config.SLIDES_RESTRICTION_KEYWORD in cons_lower:
            target_modules = [m for m in framework.modules if config.SLIDES_RESTRICTION_KEYWORD in m.title.lower()]
        elif config.FIRST_LESSONS_KEYWORD in cons_lower:
            target_modules = framework.modules[:2]

    tasks = [fetch_single_slides(mod.title) for mod in target_modules]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_slides = []
    total_tokens, total_cost = 0, 0.0
    for res in results:
        if isinstance(res, Exception): continue
        data, t, c = res
        total_tokens += t
        total_cost += c
        all_slides.extend(data)

    return all_slides, total_tokens, total_cost

async def generate_work_programs(framework: Framework, constraints: str = None) -> tuple[list, int, float]:
    """Генерирует рабочие программы (по одной на модуль)."""
    compact_data = {"competencies": [c.name for c in framework.competencies]}
    base_json = json.dumps(compact_data, ensure_ascii=False, separators=(',', ':'))
    constraints_context = f"<constraints>{constraints}</constraints>" if constraints else ""

    async def fetch_single_wp(mod_title: str):
        prompt = f"""
        <role>Методист.</role><context>{base_json}</context>{constraints_context}
        <task>Рабочая программа для модуля "{mod_title}". Напиши 3-4 предложения.</task>
        <rules>Верни ТОЛЬКО JSON-массив из одного объекта. module_title = "{mod_title}".</rules>
        <format>[{{"module_title":"{mod_title}", "description":"..."}}]</format>
        """
        fallback_prompt = f"Напиши краткое описание программы для модуля '{mod_title}'. Формат JSON: [{{'module_title':'{mod_title}', 'description':'...'}}]"
        try:
            data, t, c = await _generate_async_retry(prompt, fallback_prompt, "content")
            if isinstance(data, dict): data = data.get("work_programs", [])
            if isinstance(data, list) and len(data) > 0: return data[0], t, c
            return None, t, c
        except Exception: return None, 0, 0.0

    tasks = [fetch_single_wp(mod.title) for mod in framework.modules]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    final_wp = []
    total_tokens, total_cost = 0, 0.0
    for res in results:
        if isinstance(res, Exception): continue
        data, t, c = res
        total_tokens += t
        total_cost += c
        if data: final_wp.append(data)

    return final_wp, total_tokens, total_cost

async def generate_bibliography(framework: Framework, constraints: str = None) -> tuple[list, int, float]:
    """Генерирует список литературы."""
    compact_data = {"goal": framework.goal[:100]}
    base_json = json.dumps(compact_data, ensure_ascii=False, separators=(',', ':'))
    constraints_context = f"<constraints>{constraints}</constraints>" if constraints else ""

    prompt = f"""
    <role>Библиотекарь.</role><context>{base_json}</context>{constraints_context}
    <task>Список 5-7 книг.</task>
    <rules>Верни ТОЛЬКО JSON-массив строк.</rules>
    <format>["Автор. Название. Год."]</format>
    """
    fallback_prompt = "Дай список из 5 книг по IT. Формат JSON: ['Автор. Название. Год.', ...]"
    
    try:
        data, t, c = await _generate_async_retry(prompt, fallback_prompt, "content")
        if isinstance(data, dict): data = data.get("bibliography", [])
        if isinstance(data, list): 
            res = [str(x) for x in data if isinstance(x, str)]
            if res: return res, t, c
    except Exception: pass
    
    return _rule_based_fallback_bibliography(framework), 0, 0.0