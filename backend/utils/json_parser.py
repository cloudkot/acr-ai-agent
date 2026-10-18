import json
import re

def extract_json_from_text(text: str) -> dict or list:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Устойчивость к ошибкам LLM.
    Вырезает валидный JSON из ответа нейросети, даже если он обернут в markdown.
    """
    # 1. Пытаемся найти блок ```json ... ```
    match = re.search(r'```(?:json)?(.*?)```', text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    else:
        # 2. Если markdown нет, ищем первую { или [
        start = min([i for i in [text.find('{'), text.find('[')] if i != -1], default=-1)
        if start != -1:
            text = text[start:]

    # 3. Пытаемся распарсить
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Не удалось распарсить JSON от LLM. Ошибка: {e}. Текст: {text[:100]}...")