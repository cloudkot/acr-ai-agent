import json
import re
import asyncio
from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from logger import logger

def _chunk_list(lst: list, chunk_size: int):
    """[УТИЛИТА]: Разбивает список на подсписки заданного размера."""
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

async def _generate_async_retry(prompt: str, task_type: str = "content", retries: int = 3) -> tuple[any, int, float]:
    """[ТРЕБОВАНИЕ КЕЙСА]: Асинхронная обертка с ретраями."""
    total_tokens = 0
    total_cost = 0.0
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
            await asyncio.sleep(1.5)

def _generate_smart_fallback_seminar(framework: Framework, module_title: str, module_hours: int) -> dict:
    """[ML-СКЛЕЙКА]: Умный fallback для семинара на основе компетенций."""
    related_comps = []
    for comp in framework.competencies:
        if any(module_title.lower() in topic.lower() or topic.lower() in module_title.lower() for topic in comp.related_topics):
            related_comps.append(comp.name)
            
    if related_comps:
        comp_str = ", ".join(related_comps)
        task_text = f"Практическое задание по модулю '{module_title}' ({module_hours} ч.): разработать решение, демонстрирующее владение компетенциями: {comp_str}."
        competency_target = related_comps[0]
    else:
        task_text = f"Практическое задание по модулю '{module_title}' ({module_hours} ч.): реализовать сквозной сценарий применения изученных инструментов."
        competency_target = "Разработка и защита проектных решений"

    return {
        "module_title": module_title,
        "task": task_text,
        "criteria": "Критерии оценки: 1) Корректность применения инструментов; 2) Полнота реализации; 3) Качество защиты.",
        "related_competency": competency_target
    }

async def generate_content_pack(framework: Framework, constraints: str = None) -> dict:
    """
    [АРХИТЕКТУРА]: Гранулярная параллельная генерация контента.
    Оркестратор дробит задачи на мелкие порции, каждая из которых уходит отдельным запросом.
    """
    compact_data = {
        "template_type": framework.template_type,
        "prof_standard": framework.prof_standard,
        "total_hours": framework.total_hours,
        "competencies": [c.name for c in framework.competencies]
    }
    base_json = json.dumps(compact_data, ensure_ascii=False, separators=(',', ':'))
    constraints_context = f"<constraints>{constraints}</constraints>" if constraints else ""

    total_hours = framework.total_hours
    target_q = max(10, total_hours // 24)
    if constraints:
        match = re.search(r'(\d+)\s*(вопрос|тест|задани)', constraints.lower())
        if match: target_q = int(match.group(1))

    # Контейнеры для результатов
    all_tests, all_seminars, all_lectures = [], [], []
    all_slides, all_work_programs, all_bibliography = [], [], []
    
    total_tokens = 0
    total_cost = 0.0

    def _accumulate(t, c):
        nonlocal total_tokens, total_cost
        total_tokens += t
        total_cost += c

    # --- 1. ТЕСТЫ (порциями по 5 штук) ---
    async def fetch_tests_batch(batch_size: int, part_num: int):
        prompt = f"""
        <role>Тестолог.</role><context>{base_json}</context>{constraints_context}
        <task>Составь ровно {batch_size} тестовых вопросов (часть {part_num}).</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
        <format>[{{"question":"...", "options":["1","2","3","4"], "correct_answer":"1", "related_competency":"..."}}]</format>
        """
        data, t, c = await _generate_async_retry(prompt, "content")
        _accumulate(t, c)
        if isinstance(data, dict): data = data.get("questions", [data])
        if isinstance(data, list): return [x for x in data if isinstance(x, dict)]
        return []

    test_tasks = []
    questions_left = target_q
    part = 1
    while questions_left > 0:
        take = min(5, questions_left)
        test_tasks.append(fetch_tests_batch(take, part))
        questions_left -= take
        part += 1

    # --- 2-5. ГЕНЕРАЦИЯ ПО МОДУЛЯМ (порциями по 3 модуля) ---
    module_batches = list(_chunk_list(framework.modules, 3))

    async def fetch_seminars_batch(batch):
        titles = [m.title for m in batch]
        prompt = f"""
        <role>Практик.</role><context>{base_json}</context>{constraints_context}
        <task>Составь задания для семинаров ТОЛЬКО для модулей: {titles}.</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
        <format>[{{"module_title":"...", "task":"...", "criteria":"...", "related_competency":"..."}}]</format>
        """
        data, t, c = await _generate_async_retry(prompt, "content")
        _accumulate(t, c)
        if isinstance(data, dict): data = data.get("seminars", [data])
        return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []

    async def fetch_lectures_batch(batch):
        titles = [m.title for m in batch]
        prompt = f"""
        <role>Лектор.</role><context>{base_json}</context>{constraints_context}
        <task>Составь подробный план лекций (5-6 тезисов) ТОЛЬКО для модулей: {titles}.</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
        <format>[{{"module_title":"...", "theses":["тезис 1", "тезис 2"]}}]</format>
        """
        data, t, c = await _generate_async_retry(prompt, "content")
        _accumulate(t, c)
        if isinstance(data, dict): data = data.get("modules_plan", [])
        return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []

    async def fetch_slides_batch(batch):
        titles = [m.title for m in batch]
        prompt = f"""
        <role>Дизайнер.</role><context>{base_json}</context>{constraints_context}
        <task>Составь структуру слайдов ТОЛЬКО для модулей: {titles}.</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
        <format>[{{"slide_title":"...", "module_title":"...", "bullets":["1","2"]}}]</format>
        """
        data, t, c = await _generate_async_retry(prompt, "content")
        _accumulate(t, c)
        if isinstance(data, dict): data = data.get("slides", [])
        return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []

    async def fetch_work_programs_batch(batch):
        titles = [m.title for m in batch]
        prompt = f"""
        <role>Методист.</role><context>{base_json}</context>{constraints_context}
        <task>Составь рабочие программы (3-4 предложения) ТОЛЬКО для модулей: {titles}.</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
        <format>[{{"module_title":"...", "description":"..."}}]</format>
        """
        data, t, c = await _generate_async_retry(prompt, "content")
        _accumulate(t, c)
        if isinstance(data, dict): data = data.get("work_programs", [])
        return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []

    module_tasks = []
    for batch in module_batches:
        module_tasks.append(fetch_seminars_batch(batch))
        module_tasks.append(fetch_lectures_batch(batch))
        module_tasks.append(fetch_slides_batch(batch))
        module_tasks.append(fetch_work_programs_batch(batch))

    # --- 6. БИБЛИОГРАФИЯ (1 запрос) ---
    async def fetch_bibliography():
        prompt = f"""
        <role>Библиотекарь.</role><context>{base_json}</context>{constraints_context}
        <task>Список 5-7 книг.</task>
        <rules>Верни ТОЛЬКО JSON-массив строк. Никакого markdown.</rules>
        <format>["Автор. Название. Год."]</format>
        """
        data, t, c = await _generate_async_retry(prompt, "content")
        _accumulate(t, c)
        if isinstance(data, dict): data = data.get("bibliography", [])
        return [str(x) for x in data if isinstance(x, str)] if isinstance(data, list) else []

    # --- ЗАПУСК ВСЕХ ГРАНУЛЯРНЫХ ЗАПРОСОВ ---
    logger.info(f"Запуск {len(test_tasks) + len(module_tasks) + 1} гранулярных HTTP-запросов...")
    
    all_tasks = test_tasks + module_tasks + [fetch_bibliography()]
    results = await asyncio.gather(*all_tasks, return_exceptions=True)

    # --- СБОРКА РЕЗУЛЬТАТОВ ---
    idx = 0
    # Тесты
    for _ in test_tasks:
        res = results[idx]; idx += 1
        if isinstance(res, list): all_tests.extend(res)
    # Модульные задачи
    for _ in module_batches:
        sem_res = results[idx]; idx += 1
        lec_res = results[idx]; idx += 1
        sld_res = results[idx]; idx += 1
        wp_res = results[idx]; idx += 1
        
        if isinstance(sem_res, list): all_seminars.extend(sem_res)
        if isinstance(lec_res, list): all_lectures.extend(lec_res)
        if isinstance(sld_res, list): all_slides.extend(sld_res)
        if isinstance(wp_res, list): all_work_programs.extend(wp_res)
    # Библиография
    bib_res = results[idx]
    if isinstance(bib_res, list): all_bibliography.extend(bib_res)

    # --- ML-СКЛЕЙКА (Smart Fallback) ---
    final_seminars = []
    for mod in framework.modules:
        found = next((s for s in all_seminars if mod.title.lower() in s.get("module_title", "").lower()), None)
        if found and found.get("task") and found.get("task") != "None":
            final_seminars.append(found)
        else:
            final_seminars.append(_generate_smart_fallback_seminar(framework, mod.title, mod.total_hours))

    # Фильтрация слайдов
    if constraints:
        cons_lower = constraints.lower()
        if "первые два" in cons_lower or "первых двух" in cons_lower:
            allowed = [m.title.lower() for m in framework.modules[:2]]
            all_slides = [s for s in all_slides if any(a in s.get("module_title", "").lower() for a in allowed)]
        elif "pandas" in cons_lower:
            all_slides = [s for s in all_slides if "pandas" in s.get("module_title", "").lower() or "pandas" in s.get("slide_title", "").lower()]

    return {
        "tests": all_tests[:target_q],
        "seminars": final_seminars,
        "lectures": all_lectures,
        "slides": all_slides,
        "work_programs": all_work_programs,
        "bibliography": all_bibliography,
        "total_tokens": total_tokens,
        "total_cost": total_cost
    }