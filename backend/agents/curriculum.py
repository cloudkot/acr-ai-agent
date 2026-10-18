from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from services.rag_service import search_knowledge_base

def generate_framework_json(topic: str, hours: int, template_type: str = "ДПО") -> Framework:
    rag_context = search_knowledge_base(topic)
    prompt = f"""
    Ты — методист Академии цифрового развития.
    Тип программы: {template_type}. Тема: {topic}. Объем: {hours} часов.
    
    ИСПОЛЬЗУЙ ЭТУ НОРМАТИВНУЮ БАЗУ (RAG):
    {rag_context}
    
    ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ:
    1. Опирайся на 273-ФЗ и приказ Минобрнауки № 499.
    2. Неподтвержденные источники помечай "[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]".
    
    Составь каркас программы в формате строгого JSON. 
    {{
        "goal": "строка",
        "competencies": [{{"name": "строка", "knowledge": ["строка"], "skills": ["строка"]}}],
        "modules": [{{"title": "строка", "hours": число}}],
        "total_hours": {hours}
    }}
    Сумма часов ДОЛЖНА быть ровно {hours}. Верни ТОЛЬКО JSON.
    """
    response_text = ask_llm(prompt, task_type="framework", is_json=True)
    data = extract_json_from_text(response_text) 
    return Framework(**data)

def revise_framework_json(current_framework: Framework, instruction: str) -> Framework:
    current_json = current_framework.model_dump_json(indent=2)
    prompt = f"""
    Ты — методист. Вот текущий учебный план:
    {current_json}
    Внеси правку: "{instruction}". Измени только то, что просят. Верни ТОЛЬКО JSON в том же формате. Сумма часов должна остаться прежней.
    """
    response_text = ask_llm(prompt, task_type="revision", is_json=True)
    data = extract_json_from_text(response_text)
    return Framework(**data)