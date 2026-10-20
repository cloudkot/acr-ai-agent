import json
import re
from logger import logger

def extract_json_from_text(text: str):
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Устойчивость к ошибкам LLM.
    Вырезает валидный JSON из ответа нейросети, даже если он обернут в markdown 
    или содержит рассуждения (Reasoning) до и после JSON.
    """
    if text is None or not isinstance(text, str):
        raise ValueError("Получен пустой ответ от LLM (None)")

    # 1. Пытаемся найти блок ```json ... ```
    match = re.search(r'```(?:json)?(.*?)```', text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    else:
        # 2. Если markdown нет, ищем первую открывающую скобку { или [
        start_brace = min([i for i in [text.find('{'), text.find('[')] if i != -1], default=-1)
        
        if start_brace != -1:
            # Используем стек для поиска парной закрывающей скобки
            brace_type = text[start_brace]
            close_brace = '}' if brace_type == '{' else ']'
            
            depth = 0
            end_brace = -1
            in_string = False
            escape_char = False
            
            for i in range(start_brace, len(text)):
                char = text[i]
                
                if escape_char:
                    escape_char = False
                    continue
                if char == '\\':
                    escape_char = True
                    continue
                if char == '"':
                    in_string = not in_string
                    continue
                    
                if not in_string:
                    if char == brace_type:
                        depth += 1
                    elif char == close_brace:
                        depth -= 1
                        if depth == 0:
                            end_brace = i
                            break
            
            if end_brace != -1:
                text = text[start_brace:end_brace + 1]
            else:
                text = text[start_brace:]

    # 3. Очистка от возможных trailing commas (например, [1, 2, 3, ])
    text = re.sub(r',\s*([}\]])', r'\1', text)

    # 4. Пытаемся распарсить
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON. Текст: {text[:200]}...")
        raise ValueError(f"Не удалось распарсить JSON от LLM. Ошибка: {e}")