import os

class Config:
    """
    [АРХИТЕКТУРА]: Централизованная конфигурация.
    Позволяет менять параметры генерации без изменения кода.
    """
    # [ФИКС RATE LIMIT]: Снижаем до 1, чтобы шлюз GigaChat не блокировал запросы.
    # Генерация будет идти последовательно, но стабильно.
    MAX_CONCURRENT_REQUESTS = int(os.getenv("LLM_MAX_CONCURRENT", 1))
    
    # Количество вопросов: 1 вопрос на каждые N часов, но не менее MIN_QUESTIONS.
    QUESTIONS_PER_HOURS = int(os.getenv("QUESTIONS_PER_HOURS", 15))
    MIN_QUESTIONS = int(os.getenv("MIN_QUESTIONS", 10))
    
    # Ключевые слова для фильтрации слайдов (ловушки кейса).
    SLIDES_RESTRICTION_KEYWORD = os.getenv("SLIDES_RESTRICTION_KEYWORD", "pandas")
    FIRST_LESSONS_KEYWORD = os.getenv("FIRST_LESSONS_KEYWORD", "первые два")

config = Config()