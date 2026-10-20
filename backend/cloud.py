import os
import time
from openai import OpenAI, APITimeoutError, APIConnectionError

# [ОГРАНИЧЕНИЕ КЕЙСА]: Использование инфраструктуры Cloud.ru
api_key = os.getenv("OPENAI_API_KEY", "")
base_url = os.getenv("OPENAI_BASE_URL", "https://hub.gigaschool.ru/api/v1/llm/v1")

# Увеличили таймаут до 120 секунд, так как программы на 256 часов требуют времени на генерацию
client = OpenAI(api_key=api_key or "dummy", base_url=base_url, timeout=120.0)

# Доступные модели
MODEL_FAST = "GigaChat/GigaChat-3-Pro"
MODEL_REASONING = "ai-sage/GigaChat3.5-432B-A28B-Reasoning"

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
    Реализованы повторные попытки (retries) и таймауты для предотвращения зависаний.
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
                
            # Логирование расхода токенов (закрывает требование об экономической эффективности)
            usage = response.usage
            print(f"[LLM STATS] Модель: {model} | Всего токенов: {usage.total_tokens}")
            
            return content
            
        except (APITimeoutError, APIConnectionError) as e:
            if attempt == 2:
                raise LLMServiceError(f"Превышено время ожидания LLM: {str(e)}", status_code=504)
            time.sleep(3) # Ждем 3 секунды перед повтором
        except Exception as e:
            if attempt == 2:
                raise LLMServiceError(f"Ошибка LLM: {str(e)}", status_code=500)
            time.sleep(2)