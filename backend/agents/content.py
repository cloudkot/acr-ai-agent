import json
from cloud import ask_llm
from schemas import Framework

def generate_content_pack(framework: Framework) -> dict:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Генерация полного комплекта материалов.
    Возвращает структурированные данные для дальнейшего экспорта.
    """
    framework_str = framework.model_dump_json(indent=2)
    
    # 1. Генерация тестов (строгий JSON)
    prompt_tests = f"""
    На основе этого учебного плана:
    {framework_str}
    
    Составь 3 тестовых вопроса с 4 вариантами ответов.
    Привяжи каждый вопрос к одной из компетенций из плана.
    Формат ответа — строгий JSON:
    [
        {{
            "question": "Текст вопроса?",
            "options": ["Вариант 1", "Вариант 2", "Вариант 3", "Вариант 4"],
            "correct_answer": "Вариант 1",
            "related_competency": "Название компетенции"
        }}
    ]
    """
    tests_raw = ask_llm(prompt_tests, task_type="content", is_json=True)
    try:
        if "```json" in tests_raw:
            tests_raw = tests_raw.split("```json")[1].split("```")[0].strip()
        tests = json.loads(tests_raw)
    except:
        tests = [{"question": tests_raw, "options": [], "correct_answer": "", "related_competency": ""}]

    # 2. Генерация семинаров
    prompt_seminars = f"""
    На основе этого учебного плана:
    {framework_str}
    
    Составь 1 практическое задание для семинара. Обязательно опиши критерии оценки (от 0 до 10 баллов).
    Формат ответа — строгий JSON:
    {{
        "task": "Описание задания",
        "criteria": "Критерии оценки",
        "related_competency": "Название компетенции"
    }}
    """
    seminars_raw = ask_llm(prompt_seminars, task_type="content", is_json=True)
    try:
        if "```json" in seminars_raw:
            seminars_raw = seminars_raw.split("```json")[1].split("```")[0].strip()
        seminars = json.loads(seminars_raw)
    except:
        seminars = {"task": seminars_raw, "criteria": "Не удалось сгенерировать", "related_competency": ""}

    # 3. Генерация планов лекций
    prompt_lectures = f"""
    На основе этого учебного плана:
    {framework_str}
    
    Составь развернутый план лекций. Для каждого модуля опиши 3-4 ключевых тезиса.
    """
    lectures = ask_llm(prompt_lectures, task_type="content")

    return {
        "tests": tests,
        "seminars": seminars,
        "lectures": lectures
    }