import json
import re

def extract_json_from_text(text: str):
    match = re.search(r'```(?:json)?(.*?)```', text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    else:
        start = min([i for i in [text.find('{'), text.find('[')] if i != -1], default=-1)
        if start != -1:
            text = text[start:]
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Не удалось распарсить JSON от LLM. Ошибка: {e}")