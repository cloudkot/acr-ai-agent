import json
import asyncio
from cloud import ask_llm, MODEL_REASONING
from schemas import Framework, ExecutionPlan
from utils.json_parser import extract_json_from_text
from logger import logger

async def create_execution_plan(framework: Framework, constraints: str = None) -> tuple[ExecutionPlan, int, float]:
    """
    [НОВАЯ АРХИТЕКТУРА]: LLM-Планировщик.
    Генерирует по одной задаче на каждый модуль, чтобы избежать обрезки JSON.
    """
    logger.info("Запуск LLM-планировщика...")
    
    framework_json = framework.model_dump_json(indent=2)
    constraints_context = f"\nОСОБЫЕ ТРЕБОВАНИЯ: {constraints}" if constraints else ""
    modules_count = len(framework.modules)

    prompt = f"""
    <role>Ты — архитектор контента. Твоя задача — разбить генерацию образовательной программы на подзадачи для воркеров.</role>
    
    <input>
    <framework>{framework_json}</framework>
    {constraints_context}
    </input>
    
    <rules>
    1. Верни JSON-объект с полем "reasoning" (обоснование) и массивом "tasks".
    2. Каждая задача в "tasks" должна иметь:
       - "target_key": "tests", "lectures", "seminars", "slides", "work_programs" или "bibliography".
       - "expected_format": "json_array".
       - "prompt": ГОТОВЫЙ промпт для воркера.
    3. КРИТИЧЕСКИ ВАЖНО: Делай ОТДЕЛЬНУЮ задачу для КАЖДОГО модуля (в программе {modules_count} модулей). Не объединяй модули в одну задачу.
    4. В поле "prompt" пиши обычный текст, проси вернуть JSON-массив объектов с полями.
    5. Верни ТОЛЬКО валидный JSON без markdown.
    </rules>
    
    <example_format>
    {{
      "reasoning": "Создаю по одной задаче на каждый модуль для надежности.",
      "tasks": [
        {{
          "target_key": "lectures",
          "expected_format": "json_array",
          "prompt": "Ты — лектор. Составь подробный план лекции для модуля 'Введение'. Верни ТОЛЬКО JSON-массив объектов с полями: module_title, theses (массив строк)."
        }}
      ]
    }}
    </example_format>
    """

    total_tokens = 0
    total_cost = 0.0

    try:
        raw, tokens, cost = await ask_llm(prompt, task_type="framework", is_json=True)
        total_tokens += tokens
        total_cost += cost
        
        data = extract_json_from_text(raw)
        plan = ExecutionPlan(**data)
        
        logger.info(f"Планировщик создал {len(plan.tasks)} подзадач.")
        return plan, total_tokens, total_cost
        
    except Exception as e:
        logger.error(f"Ошибка планировщика: {e}. Применяем fallback-план.")
        fallback_tasks = []
        
        # --- 1. ТЕСТЫ (по 5 штук на задачу) ---
        target_q = max(10, framework.total_hours // 15)
        parts = (target_q + 4) // 5
        for i in range(parts):
            fallback_tasks.append({
                "target_key": "tests",
                "expected_format": "json_array",
                "prompt": f"Ты — тестолог. Составь 5 тестовых вопросов (часть {i+1}) по программе '{framework.goal[:50]}'. Верни ТОЛЬКО JSON-массив объектов. В каждом объекте должны быть поля: question, options (массив из 4 строк), correct_answer, related_competency."
            })
            
        # --- 2. ГЕНЕРАЦИЯ ПО МОДУЛЯМ (1 задача = 1 модуль) ---
        for mod in framework.modules:
            # Лекции
            fallback_tasks.append({
                "target_key": "lectures",
                "expected_format": "json_array",
                "prompt": f"Ты — лектор. Составь подробный план лекции для модуля '{mod.title}' ({mod.total_hours} часов). Верни ТОЛЬКО JSON-массив из одного объекта с полями: module_title, theses (массив конкретных тезисов)."
            })
            # Семинары
            fallback_tasks.append({
                "target_key": "seminars",
                "expected_format": "json_array",
                "prompt": f"Ты — практик. Составь практический кейс для модуля '{mod.title}' ({mod.total_hours} часов). Верни ТОЛЬКО JSON-массив из одного объекта с полями: module_title, task (описание), criteria (критерии), related_competency."
            })
            # Рабочие программы
            fallback_tasks.append({
                "target_key": "work_programs",
                "expected_format": "json_array",
                "prompt": f"Ты — методист. Напиши рабочую программу (3-4 предложения) для модуля '{mod.title}'. Верни ТОЛЬКО JSON-массив из одного объекта с полями: module_title, description."
            })

        # --- 3. СЛАЙДЫ (1 задача = 1 модуль, с учетом ограничений) ---
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
                "prompt": f"Ты — дизайнер презентаций. Составь 3 слайда для модуля '{mod.title}'. Верни ТОЛЬКО JSON-массив объектов с полями: slide_type (title или content), title, bullets (массив строк), speaker_notes (текст для лектора)."
            })

        # --- 4. БИБЛИОГРАФИЯ (1 запрос) ---
        fallback_tasks.append({
            "target_key": "bibliography",
            "expected_format": "json_array",
            "prompt": f"Ты — библиотекарь. Составь список из 5 реальных книг для программы '{framework.goal[:50]}'. Верни ТОЛЬКО JSON-массив строк в формате 'Автор. Название. Год.'."
        })

        fallback_plan = ExecutionPlan(
            reasoning="Fallback-план: 1 задача = 1 модуль для предотвращения обрезки JSON",
            tasks=[{"target_key": t["target_key"], "prompt": t["prompt"], "expected_format": t["expected_format"]} for t in fallback_tasks]
        )
        return fallback_plan, total_tokens, total_cost