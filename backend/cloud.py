import os
from openai import OpenAI

# [ОГРАНИЧЕНИЕ КЕЙСА]: Использование инфраструктуры Cloud.ru (GigaSchool).
# На ВМ переменные OPENAI_BASE_URL и OPENAI_API_KEY заданы системой.
api_key = os.getenv("OPENAI_API_KEY", "")
base_url = os.getenv("OPENAI_BASE_URL", "https://hub.gigaschool.ru/api/v1/llm/v1")

client = OpenAI(api_key=api_key, base_url=base_url)

# [АРХИТЕКТУРА]: LLM Router. Выбор модели под задачу.
MODEL_FAST = "GigaChat/GigaChat-3-Pro"                    # Для простых задач
MODEL_REASONING = "ai-sage/GigaChat3.5-432B-A28B-Reasoning" # Для сложной логики

def ask_llm(prompt: str, model: str = MODEL_FAST) -> str:
    """
    [ОГРАНИЧЕНИЕ КЕЙСА]: Потоковая выдача (stream) не поддерживается шлюзом.
    [ТРЕБОВАНИЕ КЕЙСА]: Материалы готовятся на русском языке.
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500 # Для Reasoning-модели задаем запас токенов
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка LLM: {str(e)}"