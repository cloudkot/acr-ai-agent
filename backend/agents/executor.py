import json
import asyncio
import re
from cloud import ask_llm, MODEL_FAST
from schemas import ExecutionPlan, Framework
from utils.json_parser import extract_json_from_text
from agents.content import (
    _rule_based_fallback_test, 
    _rule_based_fallback_lecture, 
    _rule_based_fallback_seminar, 
    _rule_based_fallback_bibliography,
    validate_test_format,
    validate_seminar_format
)
from config import config
from logger import logger

MAX_CONCURRENT_REQUESTS = config.MAX_CONCURRENT_REQUESTS
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

SYSTEM_PROMPT_JSON = """
Ты — программный API. Твоя единственная задача — возвращать валидный JSON.
СТРОГИЕ ПРАВИЛА:
1. Возвращай ТОЛЬКО JSON. Никакого текста до или после.
2. Не используй markdown-разметку (без ```json).
3. Не добавляй комментарии внутри JSON.
4. Строго соблюдай запрошенные поля. Если просят массив — возвращай массив.
"""

def _extract_list_from_response(data: any) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["items", "data", "results", "questions", "tasks", "content", "slides", "lectures", "seminars"]:
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]
    return []

def _force_string(val: any) -> str:
    if isinstance(val, str):
        return val
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False, indent=2)
    return str(val)

async def _execute_single_task(task) -> tuple[any, any, int, float, bool]:
    async with semaphore:
        try:
            raw, tokens, cost = await ask_llm(
                prompt=task.prompt, 
                system_prompt=SYSTEM_PROMPT_JSON,
                task_type="content", 
                is_json=False
            )
            data = extract_json_from_text(raw)
            return task, data, tokens, cost, True
        except Exception as e:
            logger.warning(f"Сбой задачи [{task.target_key}]: {e}")
            return task, None, 0, 0.0, False

async def execute_plan(plan: ExecutionPlan, framework: Framework) -> tuple[dict, int, float]:
    logger.info(f"Запуск Исполнителя. В плане {len(plan.tasks)} задач.")
    
    final_content = {
        "tests": [], "lectures": [], "seminars": [], 
        "slides": [], "work_programs": [], "bibliography": []
    }
    
    total_tokens = 0
    total_cost = 0.0
    
    pending_tasks = list(plan.tasks)
    max_rounds = 3
    
    for round_num in range(max_rounds):
        if not pending_tasks:
            break
            
        logger.info(f"Раунд {round_num + 1}/{max_rounds}. Задач в очереди: {len(pending_tasks)}")
        
        tasks = [_execute_single_task(task) for task in pending_tasks]
        results = await asyncio.gather(*tasks)
        
        next_pending = []
        
        for res in results:
            task_obj, data, tokens, cost, is_success = res
            key = task_obj.target_key
            mod_title = task_obj.module_title # <--- Берем название модуля из задачи
            total_tokens += tokens
            total_cost += cost
            
            if not is_success or data is None:
                next_pending.append(task_obj)
                continue
                
            items = _extract_list_from_response(data)
            
            if key == "bibliography":
                final_content[key].extend([_force_string(x) for x in items if x])
            elif key == "tests":
                final_content[key].extend(validate_test_format(items))
            elif key == "seminars":
                # [ФИКС]: Принудительно подставляем правильное название модуля
                for item in items:
                    if isinstance(item, dict):
                        final_content["seminars"].append({
                            "module_title": mod_title,
                            "task": _force_string(item.get("task", str(item))),
                            "criteria": _force_string(item.get("criteria", "Критерии не указаны")),
                            "related_competency": item.get("related_competency", "Общая")
                        })
            elif key == "work_programs":
                for item in items:
                    if isinstance(item, dict):
                        desc = item.get("description") or item.get("content") or str(item)
                        final_content["work_programs"].append({
                            "module_title": mod_title,
                            "description": _force_string(desc)
                        })
            elif key == "lectures":
                for item in items:
                    if isinstance(item, dict):
                        theses = item.get("theses") or item.get("content") or item.get("subtopics")
                        if not isinstance(theses, list): theses = [str(theses)]
                        final_content["lectures"].append({
                            "module_title": mod_title,
                            "theses": [_force_string(t) for t in theses]
                        })
            elif key == "slides":
                for item in items:
                    if isinstance(item, dict):
                        final_content["slides"].append({
                            "slide_type": item.get("slide_type", "content"),
                            "title": item.get("title", item.get("header", f"Слайд: {mod_title}")),
                            "bullets": item.get("bullets") or item.get("bullet_points") or [item.get("description", "")],
                            "speaker_notes": item.get("speaker_notes", "")
                        })

        pending_tasks = next_pending
        if pending_tasks:
            logger.warning(f"Пауза 5 секунд перед повтором {len(pending_tasks)} задач...")
            await asyncio.sleep(5)

    # --- ДОБИВКА (если чего-то нет) ---
    target_q = max(config.MIN_QUESTIONS, framework.total_hours // config.QUESTIONS_PER_HOURS)
    while len(final_content["tests"]) < target_q:
        mod_title = framework.modules[len(final_content["tests"]) % len(framework.modules)].title if framework.modules else "программе"
        fallback_test = _rule_based_fallback_test(framework, len(final_content["tests"]) + 1, mod_title)
        fallback_test["category"] = mod_title
        final_content["tests"].append(fallback_test)

    for mod in framework.modules:
        if not any(mod.title.lower() in str(l.get("module_title", "")).lower() for l in final_content["lectures"]):
            final_content["lectures"].append(_rule_based_fallback_lecture(framework, mod.title))
            
        if not any(mod.title.lower() in str(s.get("module_title", "")).lower() for s in final_content["seminars"]):
            final_content["seminars"].append(_rule_based_fallback_seminar(framework, mod.title, mod.total_hours))
            
        if not any(mod.title.lower() in str(wp.get("module_title", "")).lower() for wp in final_content["work_programs"]):
            final_content["work_programs"].append({"module_title": mod.title, "description": "ОШИБКА ГЕНЕРАЦИИ."})
            
        if not any(mod.title.lower() in str(sl.get("title", "")).lower() or mod.title.lower() in str(sl.get("module_title", "")).lower() for sl in final_content["slides"]):
            final_content["slides"].append({
                "slide_type": "content",
                "title": f"Модуль: {mod.title}",
                "bullets": ["Сбой генерации слайда.", "Повторите генерацию."],
                "speaker_notes": "Автоматическая заглушка."
            })

    if not final_content["bibliography"]:
        final_content["bibliography"] = _rule_based_fallback_bibliography(framework)

    return final_content, total_tokens, total_cost