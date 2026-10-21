import os
import asyncio
from urllib.parse import urlparse
from openai import AsyncOpenAI, APITimeoutError, APIConnectionError

# [ТРЕБОВАНИЕ КЕЙСА]: Жесткая фиксация провайдера (только Cloud.ru)
ALLOWED_DOMAINS = ["gigaschool.ru", "cloud.ru", "sber.ru"]
base_url = os.getenv("OPENAI_BASE_URL", "https://hub.gigaschool.ru/api/v1/llm/v1")

parsed_url = urlparse(base_url)
if not any(domain in parsed_url.netloc for domain in ALLOWED_DOMAINS):
    raise ValueError(f"КРИТИЧЕСКАЯ ОШИБКА: Запрещенный провайдер LLM ({base_url}).")

api_key = os.getenv("OPENAI_API_KEY", "")

# [АРХИТЕКТУРА]: Используем AsyncOpenAI для истинно параллельных HTTP-запросов
client = AsyncOpenAI(api_key=api_key or "dummy", base_url=base_url, timeout=180.0)

MODEL_FAST = "GigaChat/GigaChat-3-Pro"
MODEL_REASONING = "ai-sage/GigaChat3.5-432B-A28B-Reasoning"

# [ТРЕБОВАНИЕ КЕЙСА]: Цены Cloud.ru
MODEL_PRICING = {
    MODEL_FAST: {"input": 73.03, "output": 176.39},
    MODEL_REASONING: {"input": 96.22, "output": 288.60}
}

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

async def ask_llm(prompt: str, task_type: str = "content", is_json: bool = False) -> tuple[str, int, float]:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Асинхронный вызов LLM.
    Позволяет отправлять десятки запросов одновременно через asyncio.gather.
    """
    model = LLMRouter.get_model_for_task(task_type)
    
    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 8000
    }
    if is_json:
        kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(3):
        try:
            # await client.chat.completions.create - это асинхронный HTTP запрос
            response = await client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            
            if content is None or not content.strip():
                raise ValueError("Модель вернула пустой ответ.")
                
            usage = response.usage
            
            # Калькулятор стоимости
            pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
            input_cost = (usage.prompt_tokens / 1_000_000) * pricing["input"]
            output_cost = (usage.completion_tokens / 1_000_000) * pricing["output"]
            total_cost = input_cost + output_cost
            
            print(f"[LLM STATS] {model} | Токенов: {usage.total_tokens} | Стоимость: {total_cost:.4f} руб.")
            
            return content, usage.total_tokens, total_cost
            
        except (APITimeoutError, APIConnectionError) as e:
            if attempt == 2: raise LLMServiceError(f"Таймаут LLM: {str(e)}", status_code=504)
            await asyncio.sleep(3)
        except Exception as e:
            if attempt == 2: raise LLMServiceError(f"Ошибка LLM: {str(e)}", status_code=500)
            await asyncio.sleep(2)