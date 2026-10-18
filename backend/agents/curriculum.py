import json
from cloud import ask_llm, MODEL_REASONING
from schemas import Framework
from utils.json_parser import extract_json_from_text


def generate_framework_json(topic: str, hours: int, template_type: str = "ДПО") -> Framework:
    prompt = f"""
    Ты — методист Академии цифрового развития.
    Тип программы: {template_type}. Тема: {topic}. Объем: {hours} часов.
    
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
    """[ТРЕБОВАНИЕ КЕЙСА]: Точечная доработка отдельной части."""
    current_json = current_framework.model_dump_json(indent=2)
    prompt = f"""
    Ты — методист. Вот текущий учебный план в JSON:
    {current_json}
    
    Внеси следующую правку: "{instruction}".
    Измени только то, что просят. Остальное оставь без изменений. 
    Верни ТОЛЬКО валидный JSON в том же формате. Сумма часов должна остаться прежней.
    """
    response_text = ask_llm(prompt, model=MODEL_REASONING, is_json=True)
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()
    
    data = json.loads(response_text)
    return Framework(**data)