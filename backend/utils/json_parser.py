import json
import re
from json_repair import repair_json
from logger import logger

def extract_json_from_text(text: str):
    """
    [УЛУЧШЕНИЕ]: Извлекает и восстанавливает JSON из ответа LLM.
    Использует комбинацию регулярных выражений и библиотеки json-repair,
    чтобы справиться с любыми галлюцинациями нейросети (лишние запятые, обрезанные скобки и т.д.).
    """
    if text is None or not isinstance(text, str):
        raise ValueError("Получен пустой ответ от LLM (None)")

    # 1. Пытаемся найти markdown-блок ```json ... ```
    match = re.search(r'```(?:json)?(.*?)```', text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    else:
        # 2. Если markdown нет, ищем первую открывающую скобку { или [
        start_brace = min([i for i in [text.find('{'), text.find('[')] if i != -1], default=-1)
        if start_brace != -1:
            text = text[start_brace:]

    # 3. Быстрая попытка стандартного парсинга
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 4. [ФИКС]: Используем библиотеку json-repair для тяжелых случаев
    try:
        repaired_str = repair_json(text)
        data = json.loads(repaired_str)
        logger.info("JSON был успешно восстановлен с помощью библиотеки json-repair.")
        return data
    except Exception as e:
        logger.error(f"Не удалось восстановить JSON. Ошибка: {e}. Текст: {text[:200]}...")
        raise ValueError(f"Не удалось распарсить JSON от LLM. Ошибка: {e}")