import os
import time
from urllib.parse import urlparse
from openai import OpenAI, APITimeoutError, APIConnectionError

# [ТРЕБОВАНИЕ КЕЙСА]: Жесткая фиксация провайдера (только Cloud.ru)
# Если кто-то попытается подменить URL на OpenAI — сервер упадет при старте.
ALLOWED_DOMAINS = ["gigaschool.ru", "cloud.ru", "sber.ru"]
base_url = os.getenv("OPENAI_BASE_URL", "https://hub.gigaschool.ru/api/v1/llm/v1")

parsed_url = urlparse(base_url)
if not any(domain in parsed_url.netloc for domain in ALLOWED_DOMAINS):
    raise ValueError(
        f"КРИТИЧЕСКАЯ ОШИБКА БЕЗОПАСНОСТИ: Запрещенный провайдер LLM ({base_url}). "
        f"Разрешены только модели Cloud.ru."
    )

api_key = os.getenv("OPENAI_API_KEY", "")
# Увеличен таймаут до 120 секунд, так как большие программы генерируются долго
client = OpenAI(api_key=api_key or "dummy", base_url=base_url, timeout=120.0)

# Доступные модели
MODEL_FAST = "GigaChat/GigaChat-3-Pro"
MODEL_REASONING = "ai-sage/GigaChat3.5-432B-A28B-Reasoning"

# [ТРЕБОВАНИЕ КЕЙСА]: Актуальные цены Cloud.ru (в рублях за 1 млн токенов)
MODEL_PRICING = {
    MODEL_FAST: {"input": 73.03, "output": 176.39},
    MODEL_REASONING: {"input": 96.22, "output": 288.60}
}

class LLMServiceError(Exception):
    """[ТРЕБОВАНИЕ КЕЙСА]: Кастомное исключение для структурированной обработки ошибок."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class LLMRouter:
    """
    [АРХИТЕКТУРА]: LLM Router.
    Выбирает модель в зависимости от сложности задачи.
    """
    @staticmethod
    def get_model_for_task(task_type: str) -> str:
        # Для сложной структурной логики используем Reasoning-модель
        if task_type in ["framework", "validation", "revision", "slides"]:
            return MODEL_REASONING
        # Для простых текстов (тесты, семинары, лекции) быстрее и дешевле Fast-модель
        return MODEL_FAST

def ask_llm(prompt: str, task_type: str = "content", is_json: bool = False) -> str:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Отказоустойчивость.
    Реализованы повторные попытки (retries), таймауты и расчет стоимости токенов.
    """
    model = LLMRouter.get_model_for_task(task_type)
    
    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4000  # Увеличенный лимит для больших программ
    }
    if is_json:
        kwargs["response_format"] = {"type": "json_object"}

    # [ТРЕБОВАНИЕ КЕЙСА]: 3 попытки при сбоях
    for attempt in range(3):
        try:
            response = client.chat.completions.create(**kwargs)
            
            content = response.choices[0].message.content
            
            # [ТРЕБОВАНИЕ КЕЙСА]: Защита от пустых ответов
            if content is None or not content.strip():
                raise ValueError("Модель вернула пустой ответ.")
                
            # [УНИКАЛЬНАЯ ФИЧА]: Калькулятор стоимости генерации
            usage = response.usage
            pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
            
            input_cost = (usage.prompt_tokens / 1_000_000) * pricing["input"]
            output_cost = (usage.completion_tokens / 1_000_000) * pricing["output"]
            total_cost = input_cost + output_cost
            
            print(f"[LLM STATS] Модель: {model} | Токенов: {usage.total_tokens} | Стоимость: {total_cost:.4f} руб.")
            
            return content
            
        except (APITimeoutError, APIConnectionError) as e:
            if attempt == 2:
                raise LLMServiceError(f"Превышено время ожидания LLM: {str(e)}", status_code=504)
            time.sleep(3) # Ждем 3 секунды перед повтором
        except Exception as e:
            if attempt == 2:
                raise LLMServiceError(f"Ошибка LLM: {str(e)}", status_code=500)
            time.sleep(2)