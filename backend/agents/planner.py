import json
import asyncio
from cloud import ask_llm, MODEL_REASONING
from schemas import Framework, ExecutionPlan
from utils.json_parser import extract_json_from_text
from logger import logger

async def create_execution_plan(framework: Framework, constraints: str = None) -> tuple[ExecutionPlan, int, float]:
    """
    [НОВАЯ АРХИТЕКТУРА]: LLM-Планировщик.
    Анализирует каркас и сам решает, на какие подзадачи разбить генерацию контента.
    Возвращает план (ExecutionPlan) и затраты (токены, стоимость).
    """
    logger.info("Запуск LLM-планировщика для разбиения задач...")
    
    framework_json = framework.model_dump_json(indent=2)
    constraints_context = f"\nОСОБЫЕ ТРЕБОВАНИЯ: {constraints}" if constraints else ""

    prompt = f"""
    <role>Ты — архитектор контента. Твоя задача — разбить генерацию образовательной программы на мелкие подзадачи для LLM-воркеров.</role>
    
    <input>
    <framework>{framework_json}</framework>
    {constraints_context}
    </input>
    
    <rules>
    1. Ты должен вернуть JSON-объект с полем "reasoning" (твое обоснование) и массивом "tasks".
    2. Каждая задача в массиве "tasks" должна иметь:
       - "target_key": строковый ключ, куда сохранить результат (доступны: "tests", "lectures", "seminars", "slides", "work_programs", "bibliography").
       - "prompt": готовый, детальный промпт для воркера (включая контекст модуля и требуемый формат).
       - "expected_format": "json_array" или "json_object".
    3. Разбивай задачи так, чтобы каждая подзадача была маленькой. Например, для тестов сделай несколько задач по 5 вопросов. Для лекций — по одной задаче на модуль.
    4. Если в constraints просят "слайды только для pandas" или "только первые два занятия", создай задачи для слайдов ТОЛЬКО для этих модулей.
    5. Верни ТОЛЬКО валидный JSON без markdown.
    </rules>
    
    <example_format>
    {{
      "reasoning": "Так как программа большая, я разбиваю тесты на порции по 5 штук, а лекции — по модулям.",
      "tasks": [
        {{
          "target_key": "tests",
          "expected_format": "json_array",
          "prompt": "Составь 5 тестовых вопросов для модуля 'Введение'. Формат: [{{\\"question\\":\\"...\\", \\"options\\":[\\"...\\"], \\"correct_answer\\":\\"...\\"}}]"
        }},
        {{
          "target_key": "lectures",
          "expected_format": "json_array",
          "prompt": "Составь план лекции для модуля 'Введение'. Формат: [{{\\"module_title\\":\\"Введение\\", \\"theses\\":[\\"...\\"]}}]"
        }}
      ]
    }}
    </example_format>
    """

    total_tokens = 0
    total_cost = 0.0

    try:
        # Используем Reasoning модель для сложного планирования
        raw, tokens, cost = await ask_llm(prompt, task_type="framework", is_json=True)
        total_tokens += tokens
        total_cost += cost
        
        data = extract_json_from_text(raw)
        plan = ExecutionPlan(**data)
        
        logger.info(f"Планировщик создал {len(plan.tasks)} подзадач. Обоснование: {plan.reasoning[:100]}...")
        return plan, total_tokens, total_cost
        
    except Exception as e:
        logger.error(f"Ошибка планировщика: {e}. Применяем жесткий fallback-план.")
        # Если планировщик упал, используем жестко заданный план (чтобы система не остановилась)
        fallback_tasks = []
        
        # 1. Тесты (по 5 штук)
        target_q = max(10, framework.total_hours // 15)
        parts = (target_q + 4) // 5
        for i in range(parts):
            fallback_tasks.append({
                "target_key": "tests",
                "expected_format": "json_array",
                "prompt": f"Составь 5 тестовых вопросов (часть {i+1}) по программе '{framework.goal[:50]}'. Верни JSON-массив."
            })
            
        # 2. Лекции, семинары, рабочие программы (по модулям)
        for mod in framework.modules:
            fallback_tasks.append({
                "target_key": "lectures",
                "expected_format": "json_array",
                "prompt": f"Составь план лекции для модуля '{mod.title}'. Верни JSON-массив из одного объекта."
            })
            fallback_tasks.append({
                "target_key": "seminars",
                "expected_format": "json_array",
                "prompt": f"Составь задание для семинара по модулю '{mod.title}'. Верни JSON-массив из одного объекта."
            })
            fallback_tasks.append({
                "target_key": "work_programs",
                "expected_format": "json_array",
                "prompt": f"Напиши рабочую программу для модуля '{mod.title}'. Верни JSON-массив из одного объекта."
            })

        # 3. Слайды (с учетом ограничений)
        target_modules = framework.modules
        if constraints:
            if "pandas" in constraints.lower():
                target_modules = [m for m in framework.modules if "pandas" in m.title.lower()]
            elif "первые два" in constraints.lower():
                target_modules = framework.modules[:2]
                
        for mod in target_modules:
            fallback_tasks.append({
                "target_key": "slides",
                "expected_format": "json_array",
                "prompt": f"Составь структуру слайдов для модуля '{mod.title}'. Верни JSON-массив."
            })

        # 4. Библиография
        fallback_tasks.append({
            "target_key": "bibliography",
            "expected_format": "json_array",
            "prompt": f"Составь список литературы (5 книг) для программы '{framework.goal[:50]}'. Верни JSON-массив строк."
        })

        fallback_plan = ExecutionPlan(
            reasoning="Fallback-план из-за ошибки LLM-планировщика",
            tasks=[{"target_key": t["target_key"], "prompt": t["prompt"], "expected_format": t["expected_format"]} for t in fallback_tasks]
        )
        return fallback_plan, total_tokens, total_cost