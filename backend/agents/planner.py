import json
import asyncio
from cloud import ask_llm, MODEL_REASONING
from schemas import Framework, ExecutionPlan
from utils.json_parser import extract_json_from_text
from logger import logger

async def create_execution_plan(framework: Framework, constraints: str = None) -> tuple[ExecutionPlan, int, float]:
    """
    [НОВАЯ АРХИТЕКТУРА]: LLM-Планировщик.
    Генерирует ДЕТАЛЬНЫЕ промпты для воркеров, чтобы они не падали.
    """
    logger.info("Запуск LLM-планировщика...")
    
    framework_json = framework.model_dump_json(indent=2)
    constraints_context = f"\nОСОБЫЕ ТРЕБОВАНИЯ: {constraints}" if constraints else ""

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
       - "prompt": ГОТОВЫЙ, ДЕТАЛЬНЫЙ промпт для воркера.
    3. КРИТИЧЕСКИ ВАЖНО: Промпт для воркера должен содержать полный контекст (название модуля, часы), иначе воркер не справится.
    4. Для слайдов требуй строго: `[{{"slide_type": "title|content", "title": "...", "bullets": ["..."], "speaker_notes": "..."}}]`.
    5. Верни ТОЛЬКО валидный JSON без markdown.
    </rules>
    
    <example_format>
    {{
      "reasoning": "Разбиваю лекции по модулям, передаю контекст в каждый промпт.",
      "tasks": [
        {{
          "target_key": "lectures",
          "expected_format": "json_array",
          "prompt": "Ты — лектор. Составь подробный план лекции для модуля 'Введение в DevOps' (40 часов). Верни ТОЛЬКО JSON-массив: [{{\\"module_title\\": \\"Введение в DevOps\\", \\"theses\\": [\\"Подробный тезис 1\\", \\"Подробный тезис 2\\"]}}]"
        }},
        {{
          "target_key": "seminars",
          "expected_format": "json_array",
          "prompt": "Ты — практик. Составь практический кейс для модуля 'Введение в DevOps' (40 часов). Верни ТОЛЬКО JSON-массив: [{{\\"module_title\\": \\"Введение в DevOps\\", \\"task\\": \\"Описание конкретного кейса\\", \\"criteria\\": \\"Критерии оценки\\", \\"related_competency\\": \\"Название компетенции\\"}}]"
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
        logger.error(f"Ошибка планировщика: {e}. Применяем жесткий fallback-план.")
        fallback_tasks = []
        
        # 1. Тесты
        target_q = max(10, framework.total_hours // 15)
        parts = (target_q + 4) // 5
        for i in range(parts):
            fallback_tasks.append({
                "target_key": "tests",
                "expected_format": "json_array",
                "prompt": f"Ты — тестолог. Составь 5 тестовых вопросов (часть {i+1}) по программе '{framework.goal[:50]}'. Верни ТОЛЬКО JSON-массив: [{{\"question\":\"...\", \"options\":[\"1\",\"2\",\"3\",\"4\"], \"correct_answer\":\"1\", \"related_competency\":\"...\"}}]"
            })
            
        # 2. Контент по модулям (с передачей контекста в промпт)
        for mod in framework.modules:
            # Лекции
            fallback_tasks.append({
                "target_key": "lectures",
                "expected_format": "json_array",
                "prompt": f"Ты — лектор. Составь подробный план лекции для модуля '{mod.title}' ({mod.total_hours} часов). Верни ТОЛЬКО JSON-массив: [{{\"module_title\":\"{mod.title}\", \"theses\":[\"Конкретный тезис 1\", \"Конкретный тезис 2\"]}}]"
            })
            # Семинары
            fallback_tasks.append({
                "target_key": "seminars",
                "expected_format": "json_array",
                "prompt": f"Ты — практик. Составь практический кейс для модуля '{mod.title}' ({mod.total_hours} часов). Верни ТОЛЬКО JSON-массив: [{{\"module_title\":\"{mod.title}\", \"task\":\"Подробное описание кейса\", \"criteria\":\"Критерии оценки\", \"related_competency\":\"...\"}}]"
            })
            # Рабочие программы
            fallback_tasks.append({
                "target_key": "work_programs",
                "expected_format": "json_array",
                "prompt": f"Ты — методист. Напиши рабочую программу (3-4 предложения) для модуля '{mod.title}'. Верни ТОЛЬКО JSON-массив: [{{\"module_title\":\"{mod.title}\", \"description\":\"Подробное описание\"}}]"
            })

        # 3. Слайды
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
                "prompt": f"Ты — дизайнер презентаций. Составь 3 слайда для модуля '{mod.title}'. Верни ТОЛЬКО JSON-массив: [{{\"slide_type\":\"content\", \"title\":\"Заголовок\", \"bullets\":[\"Тезис 1\", \"Тезис 2\"], \"speaker_notes\":\"Текст для лектора\"}}]"
            })

        # 4. Библиография
        fallback_tasks.append({
            "target_key": "bibliography",
            "expected_format": "json_array",
            "prompt": f"Ты — библиотекарь. Составь список из 5 реальных книг для программы '{framework.goal[:50]}'. Верни ТОЛЬКО JSON-массив строк: [\"Автор. Название. Год.\", \"...\"]"
        })

        fallback_plan = ExecutionPlan(
            reasoning="Fallback-план из-за ошибки LLM-планировщика",
            tasks=[{"target_key": t["target_key"], "prompt": t["prompt"], "expected_format": t["expected_format"]} for t in fallback_tasks]
        )
        return fallback_plan, total_tokens, total_cost