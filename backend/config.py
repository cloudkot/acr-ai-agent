import os

class Config:
    """
    [АРХИТЕКТУРА]: Централизованная конфигурация.
    Позволяет менять параметры генерации без изменения кода.
    """
    # Максимальное количество одновременных HTTP-запросов к GigaChat.
    # Если ВМ начинает падать по памяти (OOM), уменьшите до 3.
    MAX_CONCURRENT_REQUESTS = int(os.getenv("LLM_MAX_CONCURRENT", 4))
    
    # Количество вопросов: 1 вопрос на каждые N часов, но не менее MIN_QUESTIONS.
    QUESTIONS_PER_HOURS = int(os.getenv("QUESTIONS_PER_HOURS", 15))
    MIN_QUESTIONS = int(os.getenv("MIN_QUESTIONS", 10))
    
    # Ключевые слова для фильтрации слайдов (ловушки кейса).
    SLIDES_RESTRICTION_KEYWORD = os.getenv("SLIDES_RESTRICTION_KEYWORD", "pandas")
    FIRST_LESSONS_KEYWORD = os.getenv("FIRST_LESSONS_KEYWORD", "первые два")

config = Config()