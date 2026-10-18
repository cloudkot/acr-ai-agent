from cloud import ask_llm, MODEL_REASONING

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
    # Используем Reasoning модель для сложной структурной логики
    return ask_llm(prompt, model=MODEL_REASONING)