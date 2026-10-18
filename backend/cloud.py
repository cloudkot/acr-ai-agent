import os
import time
from openai import OpenAI, APITimeoutError, APIConnectionError
from fastapi import HTTPException

api_key = os.getenv("OPENAI_API_KEY", "")
base_url = os.getenv("OPENAI_BASE_URL", "https://hub.gigaschool.ru/api/v1/llm/v1")

# [ТРЕБОВАНИЕ КЕЙСА]: Обработка ошибок и сбоев (таймаут)
client = OpenAI(api_key=api_key, base_url=base_url, timeout=60.0)

MODEL_FAST = "GigaChat/GigaChat-3-Pro"
MODEL_REASONING = "ai-sage/GigaChat3.5-432B-A28B-Reasoning"

def ask_llm(prompt: str, model: str = MODEL_FAST, is_json: bool = False) -> str:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Отказоустойчивость. Retry при сбоях.
    """
    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2000
    }
    if is_json:
        kwargs["response_format"] = {"type": "json_object"}

    # [ТРЕБОВАНИЕ КЕЙСА]: Retries (3 попытки)
    for attempt in range(3):
        try:
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except (APITimeoutError, APIConnectionError) as e:
            if attempt == 2:
                # [ТРЕБОВАНИЕ КЕЙСА]: Структурированная ошибка вместо строки
                raise HTTPException(status_code=504, detail=f"LLM Timeout after 3 attempts: {str(e)}")
            time.sleep(2) # Ждем 2 секунды перед повтором
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM Error: {str(e)}")