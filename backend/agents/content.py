import json
import re
import asyncio
from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from logger import logger

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
    """
    [ML-СКЛЕЙКА]: Умный fallback. Не просто шаблон, а алгоритмический поиск 
    компетенций, привязанных к этому модулю через related_topics.
    """
    related_comps = []
    for comp in framework.competencies:
        # Проверяем, есть ли этот модуль в списке тем компетенции
        if any(module_title.lower() in topic.lower() or topic.lower() in module_title.lower() for topic in comp.related_topics):
            related_comps.append(comp.name)
            
    if related_comps:
        comp_str = ", ".join(related_comps)
        task_text = f"Практическое задание по модулю '{module_title}' ({module_hours} ч.): разработать решение, демонстрирующее владение следующими компетенциями: {comp_str}. Провести защиту и обосновать архитектурные решения."
        competency_target = related_comps[0]
    else:
        task_text = f"Практическое задание по модулю '{module_title}' ({module_hours} ч.): реализовать сквозной сценарий применения изученных инструментов и методологий в рамках данного модуля."
        competency_target = "Разработка и защита проектных решений"

    return {
        "module_title": module_title,
        "task": task_text,
        "criteria": "Критерии оценки: 1) Корректность применения инструментов; 2) Полнота реализации; 3) Качество защиты решения.",
        "related_competency": competency_target
    }

async def generate_content_pack(framework: Framework, constraints: str = None) -> dict:
    """[АРХИТЕКТУРА]: Истинно параллельная генерация контента с батчингом."""
    compact_data = {
        "template_type": framework.template_type,
        "prof_standard": framework.prof_standard,
        "total_hours": framework.total_hours,
        "modules": [{"title": m.title, "hours": m.total_hours} for m in framework.modules],
        "competencies": [c.name for c in framework.competencies]
    }
    compact_json = json.dumps(compact_data, ensure_ascii=False, separators=(',', ':'))
    constraints_context = f"<constraints>{constraints}</constraints>" if constraints else ""

    total_hours = framework.total_hours
    num_modules = len(framework.modules)
    
    batch_size = 3
    target_q = max(10, total_hours // 24)
    if constraints:
        match = re.search(r'(\d+)\s*(вопрос|тест|задани)', constraints.lower())
        if match: target_q = int(match.group(1))

    async def task_tests():
        prompt = f"""
        <role>Тестолог.</role><context>{compact_json}</context>{constraints_context}
        <task>Составь РОВНО {target_q} вопросов.</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
        <format>[{{"question":"...", "options":["1","2","3","4"], "correct_answer":"1", "related_competency":"..."}}]</format>
        """
        data, t, c = await _generate_async_retry(prompt, "content")
        if isinstance(data, dict): data = data.get("questions", [data])
        if not isinstance(data, list): data = []
        return [x for x in data if isinstance(x, dict)][:target_q], t, c

    async def task_seminars():
        all_seminars = []
        total_t = 0
        total_c = 0.0
        
        for i in range(0, num_modules, batch_size):
            batch = framework.modules[i:i+batch_size]
            batch_titles = [m.title for m in batch]
            
            prompt = f"""
            <role>Практик.</role><context>{compact_json}</context>{constraints_context}
            <task>Составь практические задания ТОЛЬКО для этих модулей: {batch_titles}. По одному на каждый.</task>
            <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
            <format>[{{"module_title":"...", "task":"...", "criteria":"...", "related_competency":"..."}}]</format>
            """
            try:
                data, t, c = await _generate_async_retry(prompt, "content")
                total_t += t
                total_c += c
                
                if isinstance(data, dict): data = data.get("seminars", [data])
                if isinstance(data, list):
                    all_seminars.extend([x for x in data if isinstance(x, dict)])
            except Exception as e:
                logger.error(f"Ошибка при генерации батча семинаров: {e}")
                
        # ML-Склейка с использованием умного fallback
        final_seminars = []
        for mod in framework.modules:
            found = next((s for s in all_seminars if mod.title.lower() in s.get("module_title", "").lower()), None)
            
            if found and found.get("task") and found.get("task") != "None":
                final_seminars.append(found)
            else:
                logger.info(f"[ML-СКЛЕЙКА] Вызов умного fallback для модуля: {mod.title}")
                final_seminars.append(_generate_smart_fallback_seminar(framework, mod.title, mod.total_hours))
                
        return final_seminars, total_t, total_c

    async def task_lectures():
        prompt = f"""
        <role>Лектор.</role><context>{compact_json}</context>{constraints_context}
        <task>Составь подробный план лекций (5-6 тезисов на каждый модуль).</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
        <format>[{{"module_title":"...", "theses":["тезис 1", "тезис 2"]}}]</format>
        """
        data, t, c = await _generate_async_retry(prompt, "content")
        if isinstance(data, dict): data = data.get("modules_plan", [])
        if not isinstance(data, list): data = []
        return [x for x in data if isinstance(x, dict)], t, c

    async def task_slides():
        prompt = f"""
        <role>Дизайнер.</role><context>{compact_json}</context>{constraints_context}
        <task>Структура слайдов. Если просят конкретный модуль, делай только для него.</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
        <format>[{{"slide_title":"...", "module_title":"...", "bullets":["1","2"]}}]</format>
        """
        data, t, c = await _generate_async_retry(prompt, "content")
        if isinstance(data, dict): data = data.get("slides", [])
        if not isinstance(data, list): data = []
        return [x for x in data if isinstance(x, dict)], t, c

    async def task_work_programs():
        prompt = f"""
        <role>Методист.</role><context>{compact_json}</context>{constraints_context}
        <task>Рабочие программы (3-4 предложения на каждый модуль).</task>
        <rules>Верни ТОЛЬКО JSON-массив. Никакого markdown.</rules>
        <format>[{{"module_title":"...", "description":"..."}}]</format>
        """
        data, t, c = await _generate_async_retry(prompt, "content")
        if isinstance(data, dict): data = data.get("work_programs", [])
        if not isinstance(data, list): data = []
        return [x for x in data if isinstance(x, dict)], t, c

    async def task_bibliography():
        prompt = f"""
        <role>Библиотекарь.</role><context>{compact_json}</context>{constraints_context}
        <task>Список 5-7 книг.</task>
        <rules>Верни ТОЛЬКО JSON-массив строк. Никакого markdown.</rules>
        <format>["Автор. Название. Год."]</format>
        """
        data, t, c = await _generate_async_retry(prompt, "content")
        if isinstance(data, dict): data = data.get("bibliography", [])
        if not isinstance(data, list): data = []
        return [str(x) for x in data if isinstance(x, str)], t, c

    # [АРХИТЕКТУРА]: Одновременный запуск всех 6 задач
    logger.info(f"Запуск параллельных HTTP-запросов (6 задач) для {total_hours} ч...")
    
    results = await asyncio.gather(
        task_tests(), task_seminars(), task_lectures(),
        task_slides(), task_work_programs(), task_bibliography(),
        return_exceptions=True
    )

    final_content = {
        "tests": [], "seminars": [], "lectures": [], 
        "slides": [], "work_programs": [], "bibliography": [],
        "total_tokens": 0, "total_cost": 0.0
    }
    
    task_names = ["tests", "seminars", "lectures", "slides", "work_programs", "bibliography"]

    for i, res in enumerate(results):
        name = task_names[i]
        if isinstance(res, Exception):
            logger.error(f"Задача '{name}' упала: {res}")
            continue
        data, t_tokens, t_cost = res
        final_content[name] = data
        final_content["total_tokens"] += t_tokens
        final_content["total_cost"] += t_cost

    # Фильтрация слайдов
    if constraints:
        cons_lower = constraints.lower()
        if "первые два" in cons_lower or "первых двух" in cons_lower:
            allowed = [m.title.lower() for m in framework.modules[:2]]
            final_content["slides"] = [s for s in final_content["slides"] if any(a in s.get("module_title", "").lower() for a in allowed)]
        elif "pandas" in cons_lower:
            final_content["slides"] = [s for s in final_content["slides"] if "pandas" in s.get("module_title", "").lower() or "pandas" in s.get("slide_title", "").lower()]

    return final_content