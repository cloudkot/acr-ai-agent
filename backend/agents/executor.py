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

async def _execute_single_task(task, retries: int = 3) -> tuple[str, any, int, float]:
    """[АРХИТЕКТУРА]: Выполняет одну задачу из плана с ретраями и семафором."""
    total_tokens = 0
    total_cost = 0.0
    
    async with semaphore:
        for attempt in range(retries):
            try:
                raw, tokens, cost = await ask_llm(task.prompt, task_type="content", is_json=True)
                total_tokens += tokens
                total_cost += cost
                
                data = extract_json_from_text(raw)
                return task.target_key, data, total_tokens, total_cost
                
            except Exception as e:
                logger.warning(f"Ошибка задачи [{task.target_key}] ({attempt+1}/{retries}): {e}")
                if attempt == retries - 1:
                    logger.info(f"Запуск LLM-fallback для [{task.target_key}]...")
                    try:
                        fb_prompt = f"Сгенерируй данные для '{task.target_key}' в формате JSON. Контекст: {task.prompt[:200]}"
                        raw_fb, t_fb, c_fb = await ask_llm(fb_prompt, MODEL_FAST, True)
                        total_tokens += t_fb
                        total_cost += c_fb
                        data_fb = extract_json_from_text(raw_fb)
                        if data_fb:
                            return task.target_key, data_fb, total_tokens, total_cost
                    except Exception as e_fb:
                        logger.error(f"LLM-fallback тоже упал для [{task.target_key}]: {e_fb}")
                    
                    return task.target_key, None, total_tokens, total_cost
                await asyncio.sleep(2)

async def execute_plan(plan: ExecutionPlan, framework: Framework) -> tuple[dict, int, float]:
    """
    [АРХИТЕКТУРА]: Исполнитель плана.
    Выполняет задачи параллельно, валидирует через Pydantic-схему ContentPack.
    """
    logger.info(f"Запуск Исполнителя. В плане {len(plan.tasks)} задач.")
    
    final_content = {
        "tests": [], "lectures": [], "seminars": [], 
        "slides": [], "work_programs": [], "bibliography": []
    }
    
    total_tokens = 0
    total_cost = 0.0
    
    tasks = [_execute_single_task(task) for task in plan.tasks]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for res in results:
        if isinstance(res, Exception):
            logger.error(f"Критический сбой задачи: {res}")
            continue
            
        key, data, tokens, cost = res
        total_tokens += tokens
        total_cost += cost
        
        if data is not None:
            # [ФИКС БИБЛИОГРАФИИ]
            if key == "bibliography":
                if isinstance(data, dict) and "resources" in data:
                    for item in data["resources"]:
                        if isinstance(item, dict):
                            author = item.get("author", "")
                            title = item.get("title", "")
                            year = item.get("year", "")
                            final_content[key].append(f"{author}. {title}. {year} г.")
                        elif isinstance(item, str):
                            final_content[key].append(item)
                elif isinstance(data, list):
                    final_content[key].extend([str(x) for x in data if isinstance(x, str)])
                continue

            if isinstance(data, dict): 
                data = [data]
            if isinstance(data, list):
                if key == "tests":
                    final_content[key].extend(validate_test_format(data))
                elif key == "seminars":
                    final_content[key].extend(validate_seminar_format(data))
                else:
                    valid_items = [x for x in data if x and x != "None"]
                    final_content[key].extend(valid_items)

    # ==========================================
    # [ФИКС РЕВЬЮЕРА]: Умная склейка и Rule-based fallback
    # ==========================================
    logger.info("Проверка полноты сгенерированного контента...")
    
    # 1. Тесты
    target_q = max(config.MIN_QUESTIONS, framework.total_hours // config.QUESTIONS_PER_HOURS)
    final_content["tests"] = final_content["tests"][:target_q]
    
    # Добавляем категории к тестам для LMS
    for t in final_content["tests"]:
        if "category" not in t or not t["category"]:
            t["category"] = t.get("related_competency", "Общая")

    while len(final_content["tests"]) < target_q:
        mod_title = framework.modules[len(final_content["tests"]) % len(framework.modules)].title if framework.modules else "программе"
        fallback_test = _rule_based_fallback_test(framework, len(final_content["tests"]) + 1, mod_title)
        fallback_test["category"] = mod_title  # Добавляем категорию для fallback-теста
        final_content["tests"].append(fallback_test)

    # 2. Лекции и Семинары
    for mod in framework.modules:
        if not any(mod.title.lower() in str(l.get("module_title", "")).lower() for l in final_content["lectures"]):
            final_content["lectures"].append(_rule_based_fallback_lecture(framework, mod.title))
            
        if not any(mod.title.lower() in str(s.get("module_title", "")).lower() for s in final_content["seminars"]):
            final_content["seminars"].append(_rule_based_fallback_seminar(framework, mod.title, mod.total_hours))

    # 3. Библиография
    if not final_content["bibliography"]:
        final_content["bibliography"] = _rule_based_fallback_bibliography(framework)

    # 4. Рабочие программы
    if not final_content["work_programs"]:
        for mod in framework.modules:
            final_content["work_programs"].append({
                "module_title": mod.title,
                "description": f"Рабочая программа по модулю '{mod.title}' (сгенерирована автоматически)."
            })

    try:
        # Прогоняем через Pydantic-схему, чтобы гарантировать контракт
        validated_pack = ContentPack(**final_content)
        final_dict = validated_pack.model_dump()
        logger.info("Валидация ContentPack прошла успешно.")
    except Exception as e:
        logger.error(f"Ошибка валидации ContentPack: {e}. Возвращаем как есть.")
        final_dict = final_content

    logger.info(f"Сборка завершена. Потрачено токенов: {total_tokens}, Стоимость: {total_cost:.4f} руб.")
    return final_dict, total_tokens, total_cost