SYSTEM_PROMPT_STRICT_JSON = """
Ты — строгий программный API. Твоя единственная задача — возвращать валидный JSON.
ЗАПРЕЩЕНО писать любой текст до или после JSON. ЗАПРЕЩЕНО использовать markdown (```json).
Твой ответ должен начинаться с [ или { и заканчиваться на ] или }.
"""

SYSTEM_PROMPT_PLANNER = """
Ты — архитектор контента. Твоя задача — вернуть валидный JSON-объект с планом задач.
Формат: {"reasoning": "строка", "tasks": [{"target_key": "строка", "expected_format": "строка", "prompt": "строка", "module_title": "строка"}]}
"""
def get_seminar_prompt(module_title: str) -> str:
    return f"""
    Модуль: "{module_title}"
    Задание: Напиши ОДИН практический кейс для этого модуля.
    
    Верни ответ СТРОГО в формате JSON-массива:
    [
      {{
        "module_title": "{module_title}",
        "task": "Подробное описание задания",
        "criteria": "Критерии оценки (списком через запятую)",
        "related_competency": "Название компетенции"
      }}
    ]
    """

def get_test_prompt(goal: str, part_num: int) -> str:
    return f"""
    Тема программы: "{goal}". Часть {part_num}.
    Задание: Составь РОВНО 10 тестовых вопросов.
    
    Верни ответ СТРОГО в формате JSON-массива:
    [
      {{
        "question": "Текст вопроса?",
        "options": ["Вариант 1", "Вариант 2", "Вариант 3", "Вариант 4"],
        "correct_answer": "Вариант 1",
        "related_competency": "Название компетенции"
      }}
    ]
    """

def get_work_program_prompt(module_title: str) -> str:
    return f"""
    Модуль: "{module_title}"
    Задание: Напиши рабочую программу (5-7 предложений). Опиши цели, темы и навыки.
    
    Верни ответ СТРОГО в формате JSON-массива:
    [
      {{
        "module_title": "{module_title}",
        "description": "Текст рабочей программы"
      }}
    ]
    """

def get_lecture_prompt(module_title: str) -> str:
    return f"""
    Модуль: "{module_title}"
    Задание: Составь подробный план лекции.
    
    Верни ответ СТРОГО в формате JSON-массива:
    [
      {{
        "module_title": "{module_title}",
        "theses": ["Первый тезис", "Второй тезис", "Третий тезис"]
      }}
    ]
    """

def get_slides_prompt(goal: str, part_num: int) -> str:
    return f"""
    Тема программы: "{goal}". Часть {part_num}.
    Задание: Составь РОВНО 10 слайдов для презентации.
    
    Верни ответ СТРОГО в формате JSON-массива:
    [
      {{
        "slide_type": "content",
        "title": "Заголовок слайда",
        "bullets": ["Тезис 1", "Тезис 2"],
        "speaker_notes": "Текст для лектора"
      }}
    ]
    """

def get_bibliography_prompt(goal: str) -> str:
    return f"""
    Тема программы: "{goal}"
    Задание: Составь список из 5 реальных книг.
    
    Верни ответ СТРОГО в формате JSON-массива строк:
    [
      "Автор. Название. Год.",
      "Автор. Название. Год."
    ]
    """