from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from services.rag_service import search_knowledge_base

def generate_framework_json(topic: str, hours: int, template_type: str = "ДПО") -> Framework:
    """
    [АРХИТЕКТУРА]: Curriculum Architect.
    [ТРЕБОВАНИЕ КЕЙСА]: Поддержка двух шаблонов АЦР и любого объема часов.
    """
    # [ТРЕБОВАНИЕ КЕЙСА]: Поиск по базе знаний (RAG)
    rag_context = search_knowledge_base(topic)
    
    prompt = f"""
    Ты — методист Академии цифрового развития.
    Тип программы: {template_type}. Тема: {topic}. Объем: {hours} часов.
    
    ИСПОЛЬЗУЙ ЭТУ НОРМАТИВНУЮ БАЗУ (RAG):
    {rag_context}
    
    ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ:
    1. Опирайся на 273-ФЗ и приказ Минобрнауки № 499 (для ДПО) или приказ № 629 (для общеразвивающих).
    2. Если ты приводишь источник или профстандарт, и не уверен в его существовании, ОБЯЗАТЕЛЬНО пиши в начале строки "[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]".
    
    Составь каркас программы в формате строгого JSON. 
    Формат JSON:
    {{
        "goal": "строка",
        "competencies": [
            {{"name": "строка", "knowledge": ["строка"], "skills": ["строка"]}}
        ],
        "modules": [
            {{"title": "строка", "hours": число}}
        ],
        "total_hours": {hours}
    }}
    
    ВАЖНО: Сумма часов всех модулей ДОЛЖНА быть ровно {hours}. Верни ТОЛЬКО валидный JSON без markdown-разметки.
    """
    
    response_text = ask_llm(prompt, task_type="framework", is_json=True)
    data = extract_json_from_text(response_text) 
    return Framework(**data)

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
    return Framework(**data)