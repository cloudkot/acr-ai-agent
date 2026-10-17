from cloud import ask_llm, MODEL_REASONING

def generate_framework_text(topic: str, hours: int, template_type: str = "ДПО") -> str:
    """
    [АРХИТЕКТУРА]: Curriculum Architect.
    [ТРЕБОВАНИЕ КЕЙСА]: Поддержка двух шаблонов АЦР (ДПО и общеразвивающая).
    [ТРЕБОВАНИЕ КЕЙСА]: Любое ИТ-направление и любой объем часов.
    """
    prompt = f"""
    Ты — методист Академии цифрового развития.
    Тип программы: {template_type}. 
    Тема: {topic}. 
    Объем: {hours} часов.
    
    Составь каркас программы, включающий:
    1. Цель.
    2. Карту компетенций (знания, умения, навыки).
    3. Учебный план (модули и часы). Сумма часов должна быть ровно {hours}.
    """
    # Используем Reasoning модель для сложной структурной логики
    return ask_llm(prompt, model=MODEL_REASONING)