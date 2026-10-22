import json
import asyncio
from cloud import ask_llm, MODEL_FAST
from schemas import (
    ExecutionPlan, Framework, ContentPack,
    TestQuestion, SeminarTask, LecturePlan, Slide, WorkProgram
)
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

# [УЛУЧШЕНИЕ]: Генерируем строгие JSON-схемы из Pydantic-моделей
SCHEMAS = {
    "tests": {"type": "array", "items": TestQuestion.model_json_schema()},
    "lectures": {"type": "array", "items": LecturePlan.model_json_schema()},
    "seminars": {"type": "array", "items": SeminarTask.model_json_schema()},
    "slides": {"type": "array", "items": Slide.model_json_schema()},
    "work_programs": {"type": "array", "items": WorkProgram.model_json_schema()},
    "bibliography": {"type": "array", "items": {"type": "string"}}
}

def _extract_list_from_response(data: any) -> list:
    """[УТИЛИТА]: Извлекает массив из ответа LLM, если он обернут в объект."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["items", "data", "results", "questions", "tasks", "content", "slides"]:
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]
    return []

async def _execute_single_task(task, retries: int = 3) -> tuple[str, any, int, float]:
    """[АРХИТЕКТУРА]: Выполняет одну задачу с использованием Strict JSON Schema."""
    total_tokens = 0
    total_cost = 0.0
    
    # Получаем схему для конкретного типа контента
    schema = SCHEMAS.get(task.target_key)
    schema_name = f"{task.target_key}_schema"

    async with semaphore:
        for attempt in range(retries):
            try:
                # [ФИКС]: Передаем схему в ask_llm для нативного Structured Output
                raw, tokens, cost = await ask_llm(
                    task.prompt, 
                    task_type="content", 
                    is_json=True,
                    json_schema=schema,
                    schema_name=schema_name
                )
                total_tokens += tokens
                total_cost += cost
                
                data = extract_json_from_text(raw)
                return task.target_key, data, total_tokens, total_cost
                
            except Exception as e:
                logger.warning(f"Ошибка задачи [{task.target_key}] ({attempt+1}/{retries}): {e}")
                if attempt == retries - 1:
                    logger.info(f"Запуск LLM-fallback для [{task.target_key}]...")
                    try:
                        # Фоллбэк без строгой схемы (просто просим JSON)
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

def _rule_based_fallback_slide(framework: Framework, mod_title: str) -> dict:
    """[ФИКС]: Заглушка для слайда, если LLM не справилась."""
    return {
        "slide_type": "content",
        "title": f"Ошибка генерации: {mod_title}",
        "bullets": ["Нейросеть не смогла создать слайд.", "Повторите генерацию."],
        "speaker_notes": "Сбой генерации контента."
    }

async def execute_plan(plan: ExecutionPlan, framework: Framework) -> tuple[dict, int, float]:
    """
    [АРХИТЕКТУРА]: Исполнитель плана.
    Выполняет задачи параллельно, валидирует и собирает контент.
    """
    logger.info(f"Запуск Исполнителя. В плане {len(plan.tasks)} задач.")
    
    final_content = {
        "tests": [], "lectures": [], "seminars": [], 
        "slides": [], "work_programs": [], "bibliography": []
    }
    
    total_tokens = 0
    total_cost = 0.0
    generation_errors = 0
    
    tasks = [_execute_single_task(task) for task in plan.tasks]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for res in results:
        if isinstance(res, Exception):
            logger.error(f"Критический сбой задачи: {res}")
            generation_errors += 1
            continue
            
        key, data, tokens, cost = res
        total_tokens += tokens
        total_cost += cost
        
        if data is not None:
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

            items = _extract_list_from_response(data)
            
            if key == "tests":
                final_content[key].extend(validate_test_format(items))
            elif key == "seminars":
                final_content[key].extend(validate_seminar_format(items))
            else:
                valid_items = [x for x in items if isinstance(x, dict) and x]
                final_content[key].extend(valid_items)
        else:
            generation_errors += 1

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

    # 3. Библиография
    if not final_content["bibliography"]:
        final_content["bibliography"] = _rule_based_fallback_bibliography(framework)
        generation_errors += 1

    if generation_errors > 0:
        logger.warning(f"Завершено с ошибками генерации. Количество сбойных элементов: {generation_errors}")

    try:
        validated_pack = ContentPack(**final_content)
        final_dict = validated_pack.model_dump()
        logger.info("Валидация ContentPack прошла успешно.")
    except Exception as e:
        logger.error(f"Ошибка валидации ContentPack: {e}. Возвращаем очищенный словарь.")
        final_dict = final_content

    logger.info(f"Сборка завершена. Потрачено токенов: {total_tokens}, Стоимость: {total_cost:.4f} руб.")
    return final_dict, total_tokens, total_cost