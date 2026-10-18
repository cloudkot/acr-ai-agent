import os
import time
from openai import OpenAI, APITimeoutError, APIConnectionError
from fastapi import HTTPException

api_key = os.getenv("OPENAI_API_KEY", "")
base_url = os.getenv("OPENAI_BASE_URL", "https://hub.gigaschool.ru/api/v1/llm/v1")

client = OpenAI(api_key=api_key, base_url=base_url, timeout=60.0)

# [ТРЕБОВАНИЕ КЕЙСА]: Доступные модели Cloud.ru
MODEL_FAST = "GigaChat/GigaChat-3-Pro"
MODEL_REASONING = "ai-sage/GigaChat3.5-432B-A28B-Reasoning"

class LLMRouter:
    """
    [АРХИТЕКТУРА]: LLM Router. Выбирает модель в зависимости от сложности задачи.
    Экономит токены и время.
    """
    @staticmethod
    def get_model_for_task(task_type: str) -> str:
        if task_type in ["framework", "validation", "revision"]:
            return MODEL_REASONING # Для сложной логики и структуры
        return MODEL_FAST # Для простого текста (тесты, семинары)

def ask_llm(prompt: str, task_type: str = "content", is_json: bool = False) -> str:
    model = LLMRouter.get_model_for_task(task_type)
    
    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2000
    }
    if is_json:
        kwargs["response_format"] = {"type": "json_object"}

    # [ТРЕБОВАНИЕ КЕЙСА]: Отказоустойчивость (3 попытки)
    for attempt in range(3):
        try:
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except (APITimeoutError, APIConnectionError) as e:
            if attempt == 2:
                raise HTTPException(status_code=504, detail=f"LLM Timeout: {str(e)}")
            time.sleep(2)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM Error: {str(e)}")