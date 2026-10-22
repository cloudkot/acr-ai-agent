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

# [ФИКС]: Мы больше не просим жесткий JSON. Мы просим просто текст.
SYSTEM_PROMPT_TEXT = """
Ты — экспертный методист. Твоя задача — генерировать образовательный контент.
Пиши обычным текстом. Если просят список, используй маркированные списки с дефисом.
Не используй сложные вложенные структуры.
"""

def _parse_raw_response(raw_text: str, target_key: str) -> list:
    """
    [ФИКС]: Пытаемся распарсить JSON. Если не выходит, делаем из текста список.
    Это спасает от любых ошибок нейросети.
    """
    try:
        data = extract_json_from_text(raw_text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, list):
                    return v
            return [data]
    except Exception:
        pass
        
    # Если это не JSON, значит это сырой текст. Оборачиваем его.
    logger.warning(f"Не удалось распарсить JSON для {target_key}, используем сырой текст.")
    
    if target_key == "tests":
        # Для тестов сырой текст не подойдет, отдаем пустоту (сработает fallback)
        return [] 
    elif target_key == "seminars":
        return [{"module_title": "Модуль", "task": raw_text, "criteria": "См. задание", "related_competency": "Общая"}]
    elif target_key == "work_programs":
        return [{"module_title": "Модуль", "description": raw_text}]
    elif target_key == "lectures":
        # Разбиваем текст на тезисы по переносам строк
        theses = [line.strip("- ").strip() for line in raw_text.split('\n') if line.strip()]
        return [{"module_title": "Модуль", "theses": theses if theses else [raw_text]}]
    elif target_key == "slides":
        return [{"slide_type": "content", "title": "Слайд", "bullets": [raw_text], "speaker_notes": ""}]
    elif target_key == "bibliography":
        return [line.strip("- ").strip() for line in raw_text.split('\n') if line.strip()]
        
    return []

async def _execute_single_task(task) -> tuple[any, any, int, float, bool]:
    """[ФИКС]: Выполняет задачу, используя текстовый режим."""
    async with semaphore:
        try:
            raw, tokens, cost = await ask_llm(
                prompt=task.prompt, 
                system_prompt=SYSTEM_PROMPT_TEXT,
                task_type="content", 
                is_json=False # Отключаем режим JSON на уровне API
            )
            data = _parse_raw_response(raw, task.target_key)
            return task, data, tokens, cost, True
        except Exception as e:
            logger.warning(f"Сбой задачи [{task.target_key}]: {e}")
            return task, None, 0, 0.0, False

def _force_string(val: any) -> str:
    if isinstance(val, str):
        return val
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False, indent=2)
    return str(val)

async def execute_plan(plan: ExecutionPlan, framework: Framework) -> tuple[dict, int, float]:
    logger.info(f"Запуск Исполнителя. В плане {len(plan.tasks)} задач.")
    
    final_content = {
        "tests": [], "lectures": [], "seminars": [], 
        "slides": [], "work_programs": [], "bibliography": []
    }
    
    total_tokens = 0
    total_cost = 0.0
    generation_errors = 0
    
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
            total_tokens += tokens
            total_cost += cost
            
            if not is_success or data is None:
                next_pending.append(task_obj)
                continue
                
            # --- Обработка библиографии ---
            if key == "bibliography":
                final_content[key].extend([_force_string(x) for x in data if x])
                continue

            # --- Обработка остального контента ---
            items = data
            
            if key == "tests":
                final_content[key].extend(validate_test_format(items))
            elif key == "seminars":
                final_content[key].extend(validate_seminar_format(items))
            elif key == "work_programs":
                for item in items:
                    if isinstance(item, dict):
                        mod_title = item.get("module_title", "Модуль")
                        desc = item.get("description") or item.get("content") or str(item)
                        final_content["work_programs"].append({
                            "module_title": mod_title,
                            "description": _force_string(desc)
                        })
            elif key == "lectures":
                for item in items:
                    if isinstance(item, dict):
                        final_content["lectures"].append({
                            "module_title": item.get("module_title", item.get("lecture_title", "Лекция")),
                            "theses": item.get("theses") or item.get("content") or item.get("subtopics") or [str(item)]
                        })
            elif key == "slides":
                for item in items:
                    if isinstance(item, dict):
                        final_content["slides"].append({
                            "slide_type": item.get("slide_type", "content"),
                            "title": item.get("title", item.get("header", "Слайд")),
                            "bullets": item.get("bullets") or item.get("bullet_points") or [item.get("description", "")],
                            "speaker_notes": item.get("speaker_notes", "")
                        })

        pending_tasks = next_pending
        if pending_tasks:
            logger.warning(f"Пауза 5 секунд перед повтором {len(pending_tasks)} задач...")
            await asyncio.sleep(5)

    # --- ДОБИВКА (если чего-то совсем нет) ---
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

    if not final_content["bibliography"]:
        final_content["bibliography"] = _rule_based_fallback_bibliography(framework)

    return final_content, total_tokens, total_cost