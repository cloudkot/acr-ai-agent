import json
import asyncio
from cloud import ask_llm
from schemas import Framework, ExecutionPlan, SubTask
from utils.json_parser import extract_json_from_text
from agents.prompts import (
    SYSTEM_PROMPT_PLANNER,
    get_seminar_prompt,
    get_test_prompt,
    get_work_program_prompt,
    get_lecture_prompt,
    get_slides_prompt,
    get_bibliography_prompt
)
from logger import logger

async def create_execution_plan(framework: Framework, constraints: str = None) -> tuple[ExecutionPlan, int, float]:
    """
    [УМНОЕ ПЛАНИРОВАНИЕ]: Разбивает генерацию на мелкие задачи.
    Использует готовые JSON-шаблоны из prompts.py.
    """
    logger.info("Запуск LLM-Планировщика...")
    
    framework_json = framework.model_dump_json(indent=2)
    constraints_context = f"\nОСОБЫЕ ТРЕБОВАНИЯ: {constraints}" if constraints else ""
    modules_count = len(framework.modules)
    total_hours = framework.total_hours
    
    # Расчет количества тестов (1 тест на 15 часов, минимум 10)
    total_tests = max(10, total_hours // 15)
    test_batches = (total_tests + 9) // 10 
    
    prompt = f"""
    <role>Ты — архитектор контента. Разбей генерацию на МАКСИМАЛЬНО МАЛЕНЬКИЕ подзадачи.</role>
    
    <input>
    <framework>{framework_json}</framework>
    {constraints_context}
    </input>
    
    <rules>
    1. Верни JSON-объект с полем "reasoning" и массивом "tasks".
    2. КРИТИЧЕСКИ ВАЖНО: Делай ОТДЕЛЬНУЮ задачу для КАЖДОГО модуля для семинаров, лекций и рабочих программ. Не объединяй их!
    3. Для тестов: создай ровно {test_batches} задач(и) (в каждой задаче попроси ровно 10 вопросов).
    4. Для слайдов: создай задачи, в каждой проси ровно 10 слайдов.
    5. Для рабочих программ и библиографии: используй "expected_format": "text" (но промпт все равно требует JSON, парсеры справятся).
    6. В поле "module_title" передавай точное название модуля (для тестов и слайдов пиши "Общий").
    </rules>
    
    <example_format>
    {{
      "reasoning": "Разбиваю на мелкие задачи.",
      "tasks": [
        {{
          "target_key": "seminars",
          "expected_format": "json_array",
          "module_title": "Введение в DevOps",
          "prompt": "Напиши ОДИН практический кейс..."
        }}
      ]
    }}
    </example_format>
    """

    total_tokens = 0
    total_cost = 0.0

    try:
        raw, tokens, cost = await ask_llm(prompt=prompt, system_prompt=SYSTEM_PROMPT_PLANNER, task_type="framework", is_json=False)
        total_tokens += tokens
        total_cost += cost
        
        data = extract_json_from_text(raw)
        plan = ExecutionPlan(**data)
        
        logger.info(f"Планировщик создал {len(plan.tasks)} мелких подзадач.")
        return plan, total_tokens, total_cost
        
    except Exception as e:
        logger.error(f"Ошибка планировщика: {e}. Применяем жесткий fallback-план.")
        fallback_tasks = []
        
        # --- 1. ТЕСТЫ (строго по 10 штук) ---
        for i in range(test_batches):
            fallback_tasks.append({
                "target_key": "tests",
                "expected_format": "json_array",
                "module_title": "Общий",
                "prompt": get_test_prompt(framework.goal, i+1)
            })
            
        # --- 2. СЕМИНАРЫ (строго 1 на модуль) ---
        for mod in framework.modules:
            fallback_tasks.append({
                "target_key": "seminars",
                "expected_format": "json_array",
                "module_title": mod.title,
                "prompt": get_seminar_prompt(mod.title)
            })

        # --- 3. ЛЕКЦИИ (строго 1 на модуль) ---
        for mod in framework.modules:
            fallback_tasks.append({
                "target_key": "lectures",
                "expected_format": "json_array",
                "module_title": mod.title,
                "prompt": get_lecture_prompt(mod.title)
            })

        # --- 4. РАБОЧИЕ ПРОГРАММЫ (строго 1 на модуль) ---
        for mod in framework.modules:
            fallback_tasks.append({
                "target_key": "work_programs",
                "expected_format": "json_array",
                "module_title": mod.title,
                "prompt": get_work_program_prompt(mod.title)
            })

        # --- 5. СЛАЙДЫ (строго по 10 штук) ---
        slide_batches = max(2, len(framework.modules) // 3)
        for i in range(slide_batches):
            fallback_tasks.append({
                "target_key": "slides",
                "expected_format": "json_array",
                "module_title": "Общий",
                "prompt": get_slides_prompt(framework.goal, i+1)
            })

        # --- 6. БИБЛИОГРАФИЯ ---
        fallback_tasks.append({
            "target_key": "bibliography",
            "expected_format": "json_array",
            "module_title": "Общий",
            "prompt": get_bibliography_prompt(framework.goal)
        })

        fallback_plan = ExecutionPlan(
            reasoning="Fallback-план: строгий батчинг по 10 тестов, 1 семинару, 10 слайдов",
            tasks=[{
                "target_key": t["target_key"], 
                "prompt": t["prompt"], 
                "expected_format": t["expected_format"], 
                "module_title": t["module_title"]
            } for t in fallback_tasks]
        )
        return fallback_plan, total_tokens, total_cost