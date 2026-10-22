import json
import asyncio
from cloud import ask_llm, MODEL_FAST
from schemas import ExecutionPlan, Framework, ContentPack
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

def _extract_list_from_response(data: any) -> list:
    """[УТИЛИТА]: Извлекает массив из ответа LLM (даже если это батч из нескольких модулей)."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["items", "data", "results", "questions", "tasks", "content", "slides", "lectures", "seminars"]:
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]
    return []

async def _execute_single_task(task) -> tuple[str, any, int, float, bool]:
    """[АРХИТЕКТУРА]: Одна попытка выполнить задачу."""
    async with semaphore:
        try:
            raw, tokens, cost = await ask_llm(task.prompt, task_type="content", is_json=True)
            data = extract_json_from_text(raw)
            return task.target_key, data, tokens, cost, True
        except Exception as e:
            logger.warning(f"Сбой задачи [{task.target_key}]: {e}")
            return task.target_key, None, 0, 0.0, False

def _rule_based_fallback_slide(framework: Framework, mod_title: str) -> dict:
    return {
        "slide_type": "content",
        "title": f"Ошибка генерации: {mod_title}",
        "bullets": ["Нейросеть не смогла создать слайд.", "Повторите генерацию."],
        "speaker_notes": "Сбой генерации контента."
    }

async def execute_plan(plan: ExecutionPlan, framework: Framework) -> tuple[dict, int, float]:
    """
    [АРХИТЕКТУРА]: Исполнитель плана с очередью повторных попыток.
    """
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
            
        logger.info(f"Раунд выполнения {round_num + 1}. Осталось задач: {len(pending_tasks)}")
        
        tasks = [_execute_single_task(task) for task in pending_tasks]
        results = await asyncio.gather(*tasks)
        
        next_pending = []
        
        for res in results:
            key, data, tokens, cost, is_success = res
            total_tokens += tokens
            total_cost += cost
            
            if not is_success or data is None:
                failed_task = next(t for t in pending_tasks if t.target_key == key)
                next_pending.append(failed_task)
                continue
                
            # Обработка библиографии (там могут быть объекты)
            if key == "bibliography":
                if isinstance(data, dict) and "resources" in data:
                    for item in data["resources"]:
                        if isinstance(item, dict):
                            final_content[key].append(f"{item.get('author', '')}. {item.get('title', '')}. {item.get('year', '')} г.")
                        elif isinstance(item, str):
                            final_content[key].append(item)
                else:
                    items = _extract_list_from_response(data)
                    final_content[key].extend([str(x) for x in items if isinstance(x, str)])
                continue

            # Обработка остального контента (батчи лекций, семинаров)
            items = _extract_list_from_response(data)
            if key == "tests":
                final_content[key].extend(validate_test_format(items))
            elif key == "seminars":
                final_content[key].extend(validate_seminar_format(items))
            else:
                # Для лекций, слайдов и рабочих программ
                valid_items = [x for x in items if isinstance(x, dict) and x]
                final_content[key].extend(valid_items)

        pending_tasks = next_pending
        if pending_tasks:
            logger.warning(f"Пауза 5 секунд перед повторной попыткой {len(pending_tasks)} задач...")
            await asyncio.sleep(5)

    if pending_tasks:
        logger.error(f"После {max_rounds} раундов осталось {len(pending_tasks)} сбойных задач.")
        generation_errors += len(pending_tasks)

    logger.info("Проверка полноты сгенерированного контента...")
    
    # 1. Тесты
    target_q = max(config.MIN_QUESTIONS, framework.total_hours // config.QUESTIONS_PER_HOURS)
    final_content["tests"] = final_content["tests"][:target_q]
    
    for t in final_content["tests"]:
        if "category" not in t or not t["category"]:
            t["category"] = t.get("related_competency", "Общая")

    while len(final_content["tests"]) < target_q:
        mod_title = framework.modules[len(final_content["tests"]) % len(framework.modules)].title if framework.modules else "программе"
        fallback_test = _rule_based_fallback_test(framework, len(final_content["tests"]) + 1, mod_title)
        fallback_test["category"] = mod_title
        final_content["tests"].append(fallback_test)
        generation_errors += 1

    # 2. Лекции, Семинары, Слайды, Рабочие программы
    for mod in framework.modules:
        if not any(mod.title.lower() in str(l.get("module_title", "")).lower() for l in final_content["lectures"]):
            final_content["lectures"].append(_rule_based_fallback_lecture(framework, mod.title))
            generation_errors += 1
            
        if not any(mod.title.lower() in str(s.get("module_title", "")).lower() for s in final_content["seminars"]):
            final_content["seminars"].append(_rule_based_fallback_seminar(framework, mod.title, mod.total_hours))
            generation_errors += 1

        if not any(mod.title.lower() in str(sl.get("title", "")).lower() for sl in final_content["slides"]):
            final_content["slides"].append(_rule_based_fallback_slide(framework, mod.title))
            generation_errors += 1

        if not any(mod.title.lower() in str(wp.get("module_title", "")).lower() for wp in final_content["work_programs"]):
            final_content["work_programs"].append({
                "module_title": mod.title,
                "description": "ОШИБКА ГЕНЕРАЦИИ. Описание программы не было создано. Повторите генерацию."
            })
            generation_errors += 1

    if not final_content["bibliography"]:
        final_content["bibliography"] = _rule_based_fallback_bibliography(framework)
        generation_errors += 1

    if generation_errors > 0:
        logger.warning(f"Завершено с ошибками. Сбойных элементов: {generation_errors}")

    try:
        validated_pack = ContentPack(**final_content)
        final_dict = validated_pack.model_dump()
    except Exception as e:
        logger.error(f"Ошибка валидации ContentPack: {e}")
        final_dict = final_content

    return final_dict, total_tokens, total_cost