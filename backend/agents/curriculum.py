from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from services.rag_service import search_knowledge_base
from logger import logger
import time

def generate_framework_json(topic: str, hours: int, template_type: str = "ДПО") -> Framework:
    rag_context = search_knowledge_base(topic, template_type)
    
    prompt = f"""
    Ты — методист Академии цифрового развития.
    Тип программы: {template_type}. Тема: {topic}. Объем: {hours} часов.
    
    ОБЯЗАТЕЛЬНАЯ НОРМАТИВНАЯ БАЗА:
    {rag_context}
    
    ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ:
    1. В поле "goal" обязательно укажи, что программа составлена в соответствии с 273-ФЗ и соответствующим приказом.
    2. Если ты приводишь профстандарт и не уверен в его существовании, пиши "[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]".
    
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
    
    for attempt in range(3):
        response_text = ask_llm(prompt, task_type="framework", is_json=True)
        try:
            data = extract_json_from_text(response_text)
            framework_obj = Framework(**data)
            
            # [ТРЕБОВАНИЕ КЕЙСА]: Очистка названий компетенций от лишних тегов
            for comp in framework_obj.competencies:
                comp.name = comp.name.replace("[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]", "").strip()
                
            return framework_obj
        except Exception as e:
            logger.warning(f"Ошибка парсинга JSON от LLM (попытка {attempt+1}): {e}")
            if attempt == 2:
                raise ValueError(f"LLM не смогла выдать правильный JSON после 3 попыток. Ошибка: {e}")
            time.sleep(1)

def revise_framework_json(current_framework: Framework, instruction: str) -> Framework:
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