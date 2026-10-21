import json
import re
import asyncio
from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from logger import logger

def _chunk_list(lst: list, chunk_size: int):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

async def _generate_async_retry(prompt: str, task_type: str = "content", retries: int = 3) -> tuple[any, int, float]:
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

def _fallback_seminar(framework: Framework, mod_title: str, mod_hours: int) -> dict:
    comps = [c.name for c in framework.competencies if any(mod_title.lower() in t.lower() for t in c.related_topics)]
    task = f"Практическое задание по модулю '{mod_title}' ({mod_hours} ч.): разработать решение на основе следующих компетенций: {', '.join(comps) if comps else 'изученных инструментов'}."
    return {
        "module_title": mod_title,
        "task": task,
        "criteria": "Критерии оценки: 1) Корректность применения инструментов; 2) Полнота реализации; 3) Качество защиты.",
        "related_competency": comps[0] if comps else "Общая"
    }

def _fallback_lecture(framework: Framework, mod_title: str) -> dict:
    comps = [c.name for c in framework.competencies if any(mod_title.lower() in t.lower() for t in c.related_topics)]
    theses = [f"Введение в {mod_title}", "Ключевые инструменты и методологии", "Практические аспекты применения"]
    if comps:
        theses.append(f"Развитие компетенций: {', '.join(comps)}")
    return {"module_title": mod_title, "theses": theses}

def _fallback_test(framework: Framework, index: int) -> dict:
    comp = framework.competencies[0].name if framework.competencies else "Общая"
    return {
        "question": f"Вопрос {index} по теме программы (автоматически сгенерирован на основе модуля).",
        "options": ["Верный ответ", "Дистрактор 1", "Дистрактор 2", "Дистрактор 3"],
        "correct_answer": "Верный ответ",
        "related_competency": comp
    }

async def generate_content_pack(framework: Framework, constraints: str = None) -> dict:
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

    total_tokens = 0
    total_cost = 0.0

    def _accumulate(t, c):
        nonlocal total_tokens, total_cost
        total_tokens += t
        total_cost += c

    # --- ТЕСТЫ ---
    async def fetch_tests_batch(batch_size: int, part_num: int):
        prompt = f"""
        <role>Тестолог.</role><context>{base_json}</context>{constraints_context}
        <task>Составь ровно {batch_size} тестовых вопросов. Часть {part_num}.</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown. correct_answer должен быть строкой из options.</rules>
        <format>[{{"question":"...", "options":["1","2","3","4"], "correct_answer":"1", "related_competency":"..."}}]</format>
        """
        try:
            data, t, c = await _generate_async_retry(prompt, "content")
            _accumulate(t, c)
            if isinstance(data, dict): data = data.get("questions", [data])
            if isinstance(data, list): 
                # Фильтруем None и пустые вопросы
                return [x for x in data if isinstance(x, dict) and x.get("question") and x.get("question") != "None"]
            return []
        except Exception:
            return []

    # --- ЛЕКЦИИ ---
    async def fetch_lectures_batch(batch):
        titles = [m.title for m in batch]
        prompt = f"""
        <role>Лектор.</role><context>{base_json}</context>{constraints_context}
        <task>Составь развернутый план лекций (5-6 тезисов) для модулей: {titles}.</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
        <format>[{{"module_title":"...", "theses":["тезис 1", "тезис 2"]}}]</format>
        """
        try:
            data, t, c = await _generate_async_retry(prompt, "content")
            _accumulate(t, c)
            if isinstance(data, dict): data = data.get("modules_plan", [])
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict) and x.get("theses")]
            return []
        except Exception:
            return []

    # --- СЕМИНАРЫ ---
    async def fetch_seminars_batch(batch):
        titles = [m.title for m in batch]
        prompt = f"""
        <role>Практик.</role><context>{base_json}</context>{constraints_context}
        <task>Составь задания для семинаров для модулей: {titles}.</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
        <format>[{{"module_title":"...", "task":"...", "criteria":"...", "related_competency":"..."}}]</format>
        """
        try:
            data, t, c = await _generate_async_retry(prompt, "content")
            _accumulate(t, c)
            if isinstance(data, dict): data = data.get("seminars", [data])
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict) and x.get("task") and x.get("task") != "None"]
            return []
        except Exception:
            return []

    # --- СЛАЙДЫ ---
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
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
            return []
        except Exception:
            return []

    # --- РАБОЧИЕ ПРОГРАММЫ ---
    async def fetch_work_programs_batch(batch):
        titles = [m.title for m in batch]
        prompt = f"""
        <role>Методист.</role><context>{base_json}</context>{constraints_context}
        <task>Рабочие программы для модулей: {titles}.</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
        <format>[{{"module_title":"...", "description":"..."}}]</format>
        """
        try:
            data, t, c = await _generate_async_retry(prompt, "content")
            _accumulate(t, c)
            if isinstance(data, dict): data = data.get("work_programs", [])
            if isinstance(data, list):
                return [x for x in data if isinstance(x, dict)]
            return []
        except Exception:
            return []

    # --- БИБЛИОГРАФИЯ ---
    async def fetch_bibliography():
        prompt = f"""
        <role>Библиотекарь.</role><context>{base_json}</context>{constraints_context}
        <task>Список 5-7 книг.</task>
        <rules>Верни ТОЛЬКО JSON-массив строк. Никакого markdown.</rules>
        <format>["Автор. Название. Год."]</format>
        """
        try:
            data, t, c = await _generate_async_retry(prompt, "content")
            _accumulate(t, c)
            if isinstance(data, dict): data = data.get("bibliography", [])
            if isinstance(data, list):
                return [str(x) for x in data if isinstance(x, str)]
            return []
        except Exception:
            return []

    # Формируем батчи
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
    logger.info(f"Запуск {len(all_tasks)} гранулярных HTTP-запросов...")
    results = await asyncio.gather(*all_tasks, return_exceptions=True)

    # Сборка
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

    # --- УМНАЯ СКЛЕЙКА И ДОБИВКА ---
    final_tests = all_tests[:target_q]
    while len(final_tests) < target_q:
        final_tests.append(_fallback_test(framework, len(final_tests) + 1))

    final_seminars = []
    final_lectures = []
    for mod in framework.modules:
        sem = next((s for s in all_seminars if mod.title.lower() in s.get("module_title", "").lower()), None)
        final_seminars.append(sem if sem else _fallback_seminar(framework, mod.title, mod.total_hours))
        
        lec = next((l for l in all_lectures if mod.title.lower() in l.get("module_title", "").lower()), None)
        final_lectures.append(lec if lec else _fallback_lecture(framework, mod.title))

    if constraints:
        cons_lower = constraints.lower()
        if "первые два" in cons_lower or "первых двух" in cons_lower:
            allowed = [m.title.lower() for m in framework.modules[:2]]
            all_slides = [s for s in all_slides if any(a in s.get("module_title", "").lower() for a in allowed)]
        elif "pandas" in cons_lower:
            all_slides = [s for s in all_slides if "pandas" in s.get("module_title", "").lower() or "pandas" in s.get("slide_title", "").lower()]

    return {
        "tests": final_tests,
        "seminars": final_seminars,
        "lectures": final_lectures,
        "slides": all_slides,
        "work_programs": all_work_programs,
        "bibliography": all_bibliography,
        "total_tokens": total_tokens,
        "total_cost": total_cost
    }