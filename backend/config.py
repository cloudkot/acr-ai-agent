import os

class Config:
    # [ФИКС РЕВЬЮЕРА]: Вынесли жестко заданные параметры в конфигурацию
    MAX_CONCURRENT_REQUESTS = int(os.getenv("LLM_MAX_CONCURRENT", 5))
    
    # Формула расчета вопросов (по умолчанию: 1 вопрос на каждые 15 часов, но не менее 10)
    QUESTIONS_PER_HOURS = int(os.getenv("QUESTIONS_PER_HOURS", 15))
    MIN_QUESTIONS = int(os.getenv("MIN_QUESTIONS", 10))
    
    # Специфичные ограничения (можно менять через .env)
    SLIDES_RESTRICTION_KEYWORD = os.getenv("SLIDES_RESTRICTION_KEYWORD", "pandas")
    FIRST_LESSONS_KEYWORD = os.getenv("FIRST_LESSONS_KEYWORD", "первые два")

config = Config()