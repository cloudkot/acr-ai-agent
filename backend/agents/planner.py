import json
import asyncio
from cloud import ask_llm, MODEL_REASONING
from schemas import Framework, ExecutionPlan
from utils.json_parser import extract_json_from_text
from logger import logger

SYSTEM_PROMPT_PLANNER = """
Ты — строгий программный API. Твоя задача — вернуть валидный JSON-объект с планом задач.
КРИТИЧЕСКИЕ ПРАВИЛА:
1. Возвращай ТОЛЬКО JSON. Никакого текста до или после.
2. Не используй markdown-разметку (без ```json).
3. Каждая задача должна иметь поля: target_key, expected_format, prompt, module_title.
"""

async def create_execution_plan(framework: Framework, constraints: str = None) -> tuple[ExecutionPlan, int, float]:
    """
    [НОВАЯ АРХИТЕКТУРА]: LLM-Планировщик.
    Строгий батчинг: 10 тестов, 1 семинар, 10 слайдов за запрос.
    """
    logger.info("Запуск LLM-Планировщика...")
    
    framework_json = framework.model_dump_json(indent=2)
    constraints_context = f"\nОСОБЫЕ ТРЕБОВАНИЯ: {constraints}" if constraints else ""
    modules_count = len(framework.modules)
    total_hours = framework.total_hours
    
    # Рассчитываем количество тестов (например, 1 тест на 15 часов)
    total_tests = max(10, total_hours // 15)
    test_batches = (total_tests + 9) // 10 # Округляем вверх

    prompt = f"""
    <role>Ты — архитектор контента. Разбей генерацию на МАКСИМАЛЬНО МАЛЕНЬКИЕ подзадачи.</role>
    
    <input>
    <framework>{framework_json}</framework>
    {constraints_context}
    </input>
    
    <rules>
    1. Верни JSON-объект с полем "reasoning" и массивом "tasks".
    2. КРИТИЧЕСКИ ВАЖНО: Не объединяй разные модули в одну задачу для семинаров и лекций.
    3. Для тестов: создай ровно {test_batches} задач(и) (по 10 вопросов в каждой).
    4. Для слайдов: создай задачи по 10 слайдов в каждой.
    5. В поле "prompt" пиши обычный текст. Только массивы строк или простые строки.
    </rules>
    
    <example_format>
    {{
      "reasoning": "Создаю задачи строго по лимитам: 10 тестов, 1 семинар, 10 слайдов.",
      "tasks": [
        {{
          "target_key": "tests",
          "expected_format": "json_array",
          "module_title": "Общий",
          "prompt": "Составь РОВНО 10 тестовых вопросов (часть 1). Верни JSON-массив. Поля: question, options, correct_answer, related_competency."
        }},
        {{
          "target_key": "seminars",
          "expected_format": "json_array",
          "module_title": "Введение в DevOps",
          "prompt": "Составь РОВНО 1 практический кейс для модуля 'Введение в DevOps'. Верни JSON-массив из одного объекта. Поля: task, criteria, related_competency."
        }},
        {{
          "target_key": "slides",
          "expected_format": "json_array",
          "module_title": "Общий",
          "prompt": "Составь РОВНО 10 слайдов (часть 1) по программе. Верни JSON-массив объектов. Поля: slide_type, title, bullets, speaker_notes."
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
        
        logger.info(f"Планировщик создал {len(plan.tasks)} подзадач.")
        return plan, total_tokens, total_cost
        
    except Exception as e:
        logger.error(f"Ошибка планировщика: {e}. Применяем fallback-план.")
        fallback_tasks = []
        
        # --- 1. ТЕСТЫ (строго по 10 штук) ---
        for i in range(test_batches):
            fallback_tasks.append({
                "target_key": "tests",
                "expected_format": "json_array",
                "module_title": "Общий",
                "prompt": f"Составь РОВНО 10 тестовых вопросов (часть {i+1}) по программе. Верни ТОЛЬКО JSON-массив из 10 объектов. Поля: question, options (4 строки), correct_answer, related_competency."
            })
            
        # --- 2. СЕМИНАРЫ (строго 1 на модуль) ---
        for mod in framework.modules:
            fallback_tasks.append({
                "target_key": "seminars",
                "expected_format": "json_array",
                "module_title": mod.title,
                "prompt": f"Составь РОВНО 1 практический кейс для модуля '{mod.title}'. Верни ТОЛЬКО JSON-массив из одного объекта. Поля: task, criteria, related_competency."
            })

        # --- 3. ЛЕКЦИИ (строго 1 на модуль) ---
        for mod in framework.modules:
            fallback_tasks.append({
                "target_key": "lectures",
                "expected_format": "json_array",
                "module_title": mod.title,
                "prompt": f"Составь план лекции для модуля '{mod.title}'. Верни ТОЛЬКО JSON-массив из одного объекта. Поля: module_title, theses (массив строк)."
            })

        # --- 4. РАБОЧИЕ ПРОГРАММЫ (строго 1 на модуль) ---
        for mod in framework.modules:
            fallback_tasks.append({
                "target_key": "work_programs",
                "expected_format": "json_array",
                "module_title": mod.title,
                "prompt": f"Напиши рабочую программу (3-4 предложения) для модуля '{mod.title}'. Верни ТОЛЬКО JSON-массив из одного объекта. Поля: description (строка с текстом)."
            })

        # --- 5. СЛАЙДЫ (строго по 10 штук) ---
        # Для 500-часовой программы нужно около 20-30 слайдов
        slide_batches = max(2, len(framework.modules) // 3)
        for i in range(slide_batches):
            fallback_tasks.append({
                "target_key": "slides",
                "expected_format": "json_array",
                "module_title": "Общий",
                "prompt": f"Составь РОВНО 10 слайдов (часть {i+1}) по программе. Верни ТОЛЬКО JSON-массив из 10 объектов. Поля: slide_type, title, bullets (массив строк), speaker_notes."
            })

        # --- 6. БИБЛИОГРАФИЯ ---
        fallback_tasks.append({
            "target_key": "bibliography",
            "expected_format": "json_array",
            "module_title": "Общий",
            "prompt": f"Составь список из 5 реальных книг. Верни ТОЛЬКО JSON-массив строк."
        })

        fallback_plan = ExecutionPlan(
            reasoning="Fallback-план: строгий батчинг по 10 тестов, 1 семинару, 10 слайдов",
            tasks=[{"target_key": t["target_key"], "prompt": t["prompt"], "expected_format": t["expected_format"], "module_title": t["module_title"]} for t in fallback_tasks]
        )
        return fallback_plan, total_tokens, total_cost