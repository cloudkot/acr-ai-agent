import json
import time
import re
from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from logger import logger

def _generate_with_retry(prompt: str, task_type: str = "content", retries: int = 3) -> any:
    for attempt in range(retries):
        try:
            raw = ask_llm(prompt, task_type=task_type, is_json=True)
            data = extract_json_from_text(raw)
            if not data: raise ValueError("Пустой ответ")
            return data
        except Exception as e:
            if attempt == retries - 1: raise RuntimeError(f"Сбой после {retries} попыток: {e}")
            time.sleep(1.5)

def generate_content_pack(framework: Framework, constraints: str = None) -> dict:
    # [ФИКС РЕВЬЮЕРА]: Добавляем template_type и prof_standard в контекст
    compact_data = {
        "template_type": framework.template_type,
        "prof_standard": framework.prof_standard,
        "modules": [{"title": m.title, "hours": m.total_hours} for m in framework.modules],
        "competencies": [c.name for c in framework.competencies]
    }
    compact_json = json.dumps(compact_data, ensure_ascii=False)
    constraints_context = f"<constraints>{constraints}</constraints>" if constraints else ""

    # [ФИКС РЕВЬЮЕРА]: Вытаскиваем число вопросов регуляркой (и цифры, и слова)
    target_q = 5
    if constraints:
        digits = re.findall(r'\b(\d+)\b', constraints)
        if digits: target_q = int(digits[0])
        elif "десять" in constraints.lower(): target_q = 10
        elif "пять" in constraints.lower(): target_q = 5

    prompt_tests = f"""
    <role>Тестолог.</role>
    <context>{compact_json}</context>
    {constraints_context}
    <task>Составь РОВНО {target_q} вопросов. Если constraints противоречат этому, следуй constraints.</task>
    <rules>Верни ТОЛЬКО JSON-массив. Без markdown. correct_answer должен быть ТОЧНОЙ СТРОКОЙ из options.</rules>
    <format>[{{"question":"...", "options":["1","2","3","4"], "correct_answer":"1", "related_competency":"..."}}]</format>
    """
    tests = _generate_with_retry(prompt_tests)
    if isinstance(tests, dict): tests = tests.get("questions", [tests])
    if not isinstance(tests, list): tests = []

    prompt_seminars = f"""
    <role>Практик.</role><context>{compact_json}</context>{constraints_context}
    <task>Составь 2 семинарских задания.</task>
    <rules>Только JSON-массив. Без markdown.</rules>
    <format>[{{"task":"...", "criteria":"...", "related_competency":"..."}}]</format>
    """
    seminars = _generate_with_retry(prompt_seminars)
    if isinstance(seminars, dict): seminars = [seminars]

    prompt_lectures = f"""
    <role>Лектор.</role><context>{compact_json}</context>{constraints_context}
    <task>План лекций (3-4 тезиса на модуль).</task>
    <rules>Только JSON-массив. Без markdown.</rules>
    <format>[{{"module_title":"...", "theses":["..."]}}]</format>
    """
    lectures = _generate_with_retry(prompt_lectures)
    if isinstance(lectures, dict): lectures = lectures.get("modules_plan", [])

    # [ФИКС РЕВЬЮЕРА]: Обработка "первые два занятия"
    prompt_slides = f"""
    <role>Дизайнер.</role><context>{compact_json}</context>{constraints_context}
    <task>Структура слайдов. Если просят "первые два занятия", сделай слайды ТОЛЬКО для первых двух модулей. Если просят конкретный модуль, делай только для него.</task>
    <rules>Только JSON-массив. Без markdown.</rules>
    <format>[{{"slide_title":"...", "module_title":"...", "bullets":["1","2"]}}]</format>
    """
    slides = _generate_with_retry(prompt_slides)
    if not isinstance(slides, list): slides = []

    # Передаем constraints в рабочие программы и библиографию (фикс ревьюера)
    prompt_wp = f"<context>{compact_json}</context>{constraints_context}<task>Рабочие программы (2-3 предложения на модуль). Только JSON-массив.</task>"
    work_programs = _generate_with_retry(prompt_wp)

    prompt_bib = f"<context>{compact_json}</context>{constraints_context}<task>Список 3-5 книг. Если не уверен в книге, пиши '[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]'. Только JSON-массив строк.</task>"
    bibliography = _generate_with_retry(prompt_bib)

    return {"tests": tests, "seminars": seminars, "lectures": lectures, "slides": slides, "work_programs": work_programs, "bibliography": bibliography}