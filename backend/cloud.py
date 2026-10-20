import os
import time
from urllib.parse import urlparse
from openai import OpenAI, APITimeoutError, APIConnectionError

# [ТРЕБОВАНИЕ КЕЙСА]: Строгая валидация домена (только Cloud.ru / GigaSchool)
base_url = os.getenv("OPENAI_BASE_URL", "https://hub.gigaschool.ru/api/v1/llm/v1")
parsed_url = urlparse(base_url)

ALLOWED_DOMAINS = ["gigaschool.ru", "cloud.ru", "sber.ru"]
if not any(domain in parsed_url.netloc for domain in ALLOWED_DOMAINS):
    raise ValueError(f"КРИТИЧЕСКАЯ ОШИБКА БЕЗОПАСНОСТИ: Запрещенный провайдер LLM ({base_url})")

api_key = os.getenv("OPENAI_API_KEY", "")
client = OpenAI(api_key=api_key or "dummy", base_url=base_url, timeout=120.0)

MODEL_FAST = "GigaChat/GigaChat-3-Pro"
MODEL_REASONING = "ai-sage/GigaChat3.5-432B-A28B-Reasoning"

class LLMServiceError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class LLMRouter:
    @staticmethod
    def get_model_for_task(task_type: str) -> str:
        if task_type in ["framework", "validation", "revision", "slides"]:
            return MODEL_REASONING
        return MODEL_FAST

def ask_llm(prompt: str, task_type: str = "content", is_json: bool = False) -> str:
    model = LLMRouter.get_model_for_task(task_type)
    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4000
    }
    if is_json:
        kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(3):
        try:
            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            if content is None or not content.strip():
                raise ValueError("Модель вернула пустой ответ.")
            usage = response.usage
            print(f"[LLM STATS] Модель: {model} | Всего токенов: {usage.total_tokens}")
            return content
        except (APITimeoutError, APIConnectionError) as e:
            if attempt == 2: raise LLMServiceError(f"Таймаут LLM: {e}", 504)
            time.sleep(3)
        except Exception as e:
            if attempt == 2: raise LLMServiceError(f"Ошибка LLM: {e}", 500)
            time.sleep(2)