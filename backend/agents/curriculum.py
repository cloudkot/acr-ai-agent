import asyncio
from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from services.rag_service import search_knowledge_base
from logger import logger

async def generate_framework_json(
    topic: str, 
    hours: int, 
    template_type: str = "ДПО", 
    reference_text: str = None, 
    constraints: str = None
) -> tuple[Framework, int, float]:
    """
    [АРХИТЕКТУРА]: Curriculum Architect (Асинхронный).
    Возвращает кортеж: (Framework, потрачено_токенов, стоимость_в_рублях).
    """
    # 1. Поиск по базе знаний (RAG)
    rag_context = search_knowledge_base(topic, template_type)
    
    # 2. Подготовка контекста
    ref_context = f"<reference>{reference_text[:1500]}</reference>" if reference_text else ""
    constraints_context = f"<constraints>{constraints}</constraints>" if constraints else ""

    # 3. Формирование строгого промпта
    prompt = f"""
    <role>Ты — экспертный методист Академии цифрового развития (АЦР).</role>
    
    <input>
    <topic>{topic}</topic>
    <hours>{hours}</hours>
    <template_type>{template_type}</template_type>
    {constraints_context}
    {ref_context}
    </input>
    
    <normative_base>
    {rag_context}
    </normative_base>
    
    <rules>
    1. Если template_type = "Общеразвивающая", поле "prof_standard" СТРОГО null.
    2. Если template_type = "ДПО", ты ОБЯЗАН указать реальный профстандарт в поле "prof_standard". 
       Например, для DevOps используй "Профстандарт 06.015", для Data Science — "06.043", для учителей — "01.001".
    3. Если в constraints есть требование (например, "без лекций"), строго ставь 0 в соответствующие поля (лекции=0).
    4. ИГНОРИРУЙ математические ошибки в reference. Сумма модулей + final_assessment_hours = {hours}. 
       Внутри модуля: lectures+practice+labs+srs = total_hours.
    5. [ДОМЕННОЕ ПРАВИЛО 1]: Если тема связана с учителями, используй ТОЛЬКО российские ИИ (GigaChat, YandexGPT). 
       Запрещено упоминать ChatGPT, Midjourney.
    6. [ДОМЕННОЕ ПРАВИЛО 2]: Если тема про анализ данных, не копируй текст из reference дословно.
    7. [ПРАВИЛО СЛАЙДОВ]: Если в constraints просят "слайды для первых двух занятий", это означает, что нужно сделать слайды для ПЕРВЫХ ДВУХ МОДУЛЕЙ.
    8. [СВЯЗЬ С ТЕМАМИ]: В каждой компетенции ОБЯЗАТЕЛЬНО добавь поле "related_topics" (массив строк). Туда нужно вписать названия модулей из твоего учебного плана, в которых эта компетенция формируется.
    9. Верни ТОЛЬКО сырой JSON. Никаких markdown-тегов, без ```json.
    </rules>
    
    <few_shot_example>
    {{
      "goal": "Программа на основе 273-ФЗ",
      "template_type": "ДПО",
      "prof_standard": "Профстандарт 06.001",
      "final_assessment_hours": 2,
      "modules": [
        {{"title": "Введение", "total_hours": 34, "lectures": 10, "practice": 10, "labs": 0, "srs": 14}}
      ],
      "total_hours": 36,
      "competencies": [
        {{"name": "Python", "knowledge": ["Синтаксис"], "skills": ["Писать код"], "related_topics": ["Введение"]}}
      ]
    }}
    </few_shot_example>
    
    Сгенерируй JSON, строго соблюдая <rules>.
    """
    
    total_tokens = 0
    total_cost = 0.0
    
    # 4. Генерация с ретраями
    for attempt in range(3):
        try:
            # [ФИКС]: Асинхронный вызов, возвращающий текст, токены, стоимость
            response_text, tokens, cost = await ask_llm(
                prompt, task_type="framework", is_json=True
            )
            total_tokens += tokens
            total_cost += cost
            
            data = extract_json_from_text(response_text)
            
            # Принудительно перезаписываем критичные поля
            data["total_hours"] = hours
            data["template_type"] = template_type
            if template_type == "Общеразвивающая":
                data["prof_standard"] = None
            elif not data.get("prof_standard"):
                data["prof_standard"] = "[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК] Профстандарт не указан"
                
            framework_obj = Framework(**data)
            
            # Очистка компетенций от случайных тегов
            for comp in framework_obj.competencies:
                comp.name = comp.name.replace("[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]", "").strip()
                
            return framework_obj, total_tokens, total_cost
            
        except Exception as e:
            logger.warning(f"Ошибка парсинга JSON от LLM (попытка {attempt+1}): {e}")
            if attempt == 2:
                raise ValueError(f"LLM не смогла выдать правильный JSON после 3 попыток. Ошибка: {e}")
            await asyncio.sleep(1.5)

async def revise_framework_json(
    current_framework: Framework, 
    instruction: str
) -> tuple[Framework, int, float]:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Точечная доработка каркаса (Асинхронная).
    Возвращает кортеж: (Framework, потрачено_токенов, стоимость_в_рублях).
    """
    current_json = current_framework.model_dump_json(indent=2)
    
    prompt = f"""
    <role>Ты — методист АЦР.</role>
    <current_plan>{current_json}</current_plan>
    <task>Внеси правку: "{instruction}". Измени только то, что просят.</task>
    <rules>
    Сумма модулей + аттестация = {current_framework.total_hours}. Верни ТОЛЬКО JSON.
    </rules>
    """
    
    # [ФИКС]: Асинхронный вызов
    response_text, tokens, cost = await ask_llm(
        prompt, task_type="revision", is_json=True
    )
    
    data = extract_json_from_text(response_text)
    
    # Защита от галлюцинаций LLM при правках
    data["total_hours"] = current_framework.total_hours
    data["template_type"] = current_framework.template_type
    
    framework_obj = Framework(**data)
    
    for comp in framework_obj.competencies:
        comp.name = comp.name.replace("[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]", "").strip()
        
    return framework_obj, tokens, cost