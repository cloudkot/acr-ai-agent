import time
from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from services.rag_service import search_knowledge_base
from logger import logger

def generate_framework_json(topic: str, hours: int, template_type: str = "ДПО", reference_text: str = None) -> Framework:
    """
    [АРХИТЕКТУРА]: Curriculum Architect.
    [ТРЕБОВАНИЕ КЕЙСА]: Использование референсов и автоматический выбор шаблона.
    """
    # 1. Поиск по базе знаний (ML RAG)
    rag_context = search_knowledge_base(topic, template_type)
    
    # 2. Подготовка контекста из загруженного референса
    ref_context = ""
    if reference_text:
        # Берем первые 1500 символов, чтобы не переполнить контекст
        ref_context = f"\nВАЖНО! УЧТИ ЭТОТ РЕФЕРЕНС ПРИ СОЗДАНИИ ПРОГРАММЫ:\n{reference_text[:1500]}\n"
    
    prompt = f"""
    Ты — методист Академии цифрового развития.
    Тип программы: {template_type}. Тема: {topic}. Объем: {hours} часов.
    
    ОБЯЗАТЕЛЬНАЯ НОРМАТИВНАЯ БАЗА:
    {rag_context}
    {ref_context}
    
    ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ:
    1. В поле "goal" обязательно укажи, что программа составлена в соответствии с 273-ФЗ и соответствующим приказом.
    2. Если ты приводишь профстандарт и не уверен в его существовании, пиши "[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]".
    3. Учти содержание референса (если он есть), чтобы не дублировать материал.
    
    Составь каркас программы в формате строгого JSON. 
    Формат JSON:
    {{
        "goal": "строка (до 150 символов, с нормативной базой)",
        "competencies": [
            {{"name": "строка", "knowledge": ["строка"], "skills": ["строка"]}}
        ],
        "modules": [
            {{"title": "строка", "hours": число}}
        ],
        "total_hours": {hours}
    }}
    
    ВАЖНО: Сумма часов всех модулей ДОЛЖНА быть ровно {hours}. Верни ТОЛЬКО валидный JSON.
    """
    
    # 3. Генерация с ретраями
    for attempt in range(3):
        response_text = ask_llm(prompt, task_type="framework", is_json=True)
        try:
            data = extract_json_from_text(response_text)
            framework_obj = Framework(**data)
            
            # [ТРЕБОВАНИЕ КЕЙСА]: Очистка названий компетенций от лишних тегов для UI
            for comp in framework_obj.competencies:
                comp.name = comp.name.replace("[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]", "").strip()
                
            return framework_obj
        except Exception as e:
            logger.warning(f"Ошибка парсинга JSON от LLM (попытка {attempt+1}): {e}")
            if attempt == 2:
                raise ValueError(f"LLM не смогла выдать правильный JSON после 3 попыток. Ошибка: {e}")
            time.sleep(1)

def revise_framework_json(current_framework: Framework, instruction: str) -> Framework:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Точечная доработка отдельной части.
    """
    current_json = current_framework.model_dump_json(indent=2)
    
    prompt = f"""
    Ты — методист. Вот текущий учебный план в JSON:
    {current_json}
    
    Внеси следующую правку: "{instruction}".
    Измени только то, что просят. Остальное оставь без изменений. 
    Верни ТОЛЬКО валидный JSON в том же формате. Сумма часов должна остаться прежней.
    """
    
    response_text = ask_llm(prompt, task_type="revision", is_json=True)
    data = extract_json_from_text(response_text)
    framework_obj = Framework(**data)
    
    for comp in framework_obj.competencies:
        comp.name = comp.name.replace("[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]", "").strip()
        
    return framework_obj