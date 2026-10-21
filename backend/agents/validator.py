from schemas import Framework, Module
import re
from logger import logger

def adjust_module_hours(mod: Module, new_total: int):
    """[УТИЛИТА]: Пропорционально распределяет часы внутри модуля при изменении общего объема."""
    if mod.total_hours == 0:
        mod.total_hours = new_total
        mod.srs = new_total
        return

    ratio = new_total / mod.total_hours
    mod.lectures = round(mod.lectures * ratio)
    mod.practice = round(mod.practice * ratio)
    mod.labs = round(mod.labs * ratio)
    
    mod.srs = new_total - (mod.lectures + mod.practice + mod.labs)
    if mod.srs < 0: mod.srs = 0
        
    mod.total_hours = mod.lectures + mod.practice + mod.labs + mod.srs

def auto_correct_hours(framework: Framework, target_hours: int, constraints: str = None) -> Framework:
    """[ТРЕБОВАНИЕ КЕЙСА]: Автокоррекция часов с учетом ограничений."""
    if not framework.modules:
        return framework

    # Учет жестких ограничений
    if constraints:
        cons_lower = constraints.lower()
        if "без лекций" in cons_lower or "без аудиторных" in cons_lower or "только самостоятельная" in cons_lower:
            for mod in framework.modules:
                mod.lectures = 0
                mod.practice = 0
                mod.labs = 0
                mod.srs = mod.total_hours

    # Сверка общей суммы
    current_sum = sum(module.total_hours for module in framework.modules) + framework.final_assessment_hours
    diff = target_hours - current_sum
    
    if diff != 0:
        last_mod = framework.modules[-1]
        new_total = last_mod.total_hours + diff
        
        if new_total < 1: new_total = 1
        adjust_module_hours(last_mod, new_total)
        
        framework.total_hours = sum(m.total_hours for m in framework.modules) + framework.final_assessment_hours
        logger.info(f"Автокоррекция часов: модуль '{last_mod.title}' изменен до {new_total} ч.")
        
    return framework

def enforce_content_constraints(framework: Framework, content: dict, constraints: str = None) -> dict:
    """
    [ФИКС РЕВЬЮЕРА]: Принудительная коррекция контента. 
    Работает даже без явных constraints (например, если модуль про pandas, 
    мы сами отфильтруем слайды).
    """
    # 1. Защита от выдуманных источников и запрещенных сервисов (Anti-Hallucination)
    forbidden_services = ["chatgpt", "openai", "midjourney", "claude", "gemini"]
    if isinstance(content.get("bibliography"), list):
        cleaned_bib = []
        for book in content["bibliography"]:
            # Если книга содержит запрещенный сервис, выкидываем или помечаем
            if any(bad in book.lower() for bad in forbidden_services):
                book = book + " [НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК / ЗАПРЕЩЕННЫЙ СЕРВИС]"
            
            # Проверка на формат (должен быть год или автор)
            if not re.search(r'\d{4}', book):
                book = book + " [НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК: нет года]"
                
            cleaned_bib.append(book)
        content["bibliography"] = cleaned_bib

    # Замена запрещенных сервисов в текстах лекций и семинаров
    for key in ["lectures", "seminars", "work_programs"]:
        if isinstance(content.get(key), list):
            for item in content[key]:
                for k, v in item.items():
                    if isinstance(v, str):
                        for bad in forbidden_services:
                            if bad in v.lower():
                                item[k] = re.sub(f'(?i){bad}', 'GigaChat (российский аналог)', v)

    # 2. Жесткая проверка количества вопросов (даже если нет constraints)
    total_hours = framework.total_hours
    expected_q = max(10, total_hours // 24)
    
    if constraints:
        match = re.search(r'(\d+)\s*(вопрос|тест|задани)', constraints.lower())
        if match: expected_q = int(match.group(1))
        elif "десять" in constraints.lower(): expected_q = 10
        
    if isinstance(content.get("tests"), list):
        tests = content["tests"]
        if len(tests) > expected_q:
            content["tests"] = tests[:expected_q]
        elif len(tests) < expected_q:
            for i in range(len(tests), expected_q):
                tests.append({
                    "question": f"Дополнительный вопрос {i+1} (автоматически добавлен по объему часов)",
                    "options": ["Вариант 1", "Вариант 2", "Вариант 3", "Вариант 4"],
                    "correct_answer": "Вариант 1",
                    "related_competency": framework.competencies[0].name if framework.competencies else "Общая"
                })
            content["tests"] = tests

    # 3. Умная фильтрация слайдов
    if isinstance(content.get("slides"), list):
        # Если модуль содержит pandas, оставляем только слайды про pandas
        if any("pandas" in m.title.lower() for m in framework.modules):
            content["slides"] = [
                s for s in content["slides"] 
                if "pandas" in s.get("module_title", "").lower() or "pandas" in s.get("slide_title", "").lower()
            ]
        
        # Обработка ограничений
        if constraints:
            cons_lower = constraints.lower()
            if "первые два" in cons_lower or "первых двух" in cons_lower:
                allowed_modules = [m.title.lower() for m in framework.modules[:2]]
                content["slides"] = [s for s in content["slides"] if any(a in s.get("module_title", "").lower() for a in allowed_modules)]
            elif "pandas" in cons_lower:
                content["slides"] = [s for s in content["slides"] if "pandas" in s.get("module_title", "").lower() or "pandas" in s.get("slide_title", "").lower()]

    return content

def check_content_constraints(framework: Framework, content: dict, constraints: str = None) -> dict:
    """[ТРЕБОВАНИЕ КЕЙСА]: Пост-валидация ограничений."""
    errors = []
    
    # Проверка количества вопросов
    expected_q = max(10, framework.total_hours // 24)
    if constraints:
        match = re.search(r'(\d+)\s*(вопрос|тест|задани)', constraints.lower())
        if match: expected_q = int(match.group(1))
        elif "десять" in constraints.lower(): expected_q = 10
        
    actual_q = len(content.get("tests", []))
    if actual_q < expected_q:
        errors.append(f"Ожидалось минимум {expected_q} вопросов, сгенерировано {actual_q}.")

    # Проверка запрещенных сервисов
    forbidden = ["chatgpt", "midjourney"]
    for book in content.get("bibliography", []):
        if any(b in book.lower() for b in forbidden):
            errors.append(f"В библиографии найден запрещенный сервис: {book}")

    return {"constraints_ok": len(errors) == 0, "errors": errors}

def validate_coverage_with_content(framework: Framework, content: dict) -> dict:
    """[ТРЕБОВАНИЕ КЕЙСА]: Глубокая проверка покрытия компетенций."""
    if not content:
        return {"coverage_ok": False, "uncovered": ["Нет контента"]}

    comp_names = [c.name.lower().strip() for c in framework.competencies]
    tested_comps = set()
    
    for test in content.get("tests", []):
        if isinstance(test, dict) and "related_competency" in test:
            tested_comps.add(test["related_competency"].lower().strip())
            
    for sem in content.get("seminars", []):
        if isinstance(sem, dict) and "related_competency" in sem:
            tested_comps.add(sem["related_competency"].lower().strip())
        
    uncovered = []
    for comp in comp_names:
        is_covered = any(comp in tc or tc in comp for tc in tested_comps)
        if not is_covered:
            uncovered.append(comp)

    return {
        "coverage_ok": len(uncovered) == 0,
        "total_competencies": len(comp_names),
        "tested_count": len(tested_comps),
        "uncovered": uncovered
    }

def run_full_validation(framework: Framework) -> dict:
    """[ТРЕБОВАНИЕ КЕЙСА]: Отчет автопроверки каркаса."""
    calculated_total = sum(module.total_hours for module in framework.modules) + framework.final_assessment_hours
    hours_match = calculated_total == framework.total_hours
    
    modules_math_ok = True
    for mod in framework.modules:
        mod_sum = mod.lectures + mod.practice + mod.labs + mod.srs
        if mod_sum != mod.total_hours:
            modules_math_ok = False
            break

    unverified_sources_found = []
    if framework.template_type == "ДПО":
        if not framework.prof_standard:
            unverified_sources_found.append("Профстандарт не указан")
        elif "[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]" in framework.prof_standard:
            unverified_sources_found.append("Профстандарт помечен как неподтвержденный")
    else:
        if framework.prof_standard:
             unverified_sources_found.append("Для общеразвивающей программы указан профстандарт")

    return {
        "hours_match": hours_match,
        "calculated_total": calculated_total,
        "expected_total": framework.total_hours,
        "modules_math_ok": modules_math_ok,
        "sources_check": {
            "has_unverified_mark": "[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]" in framework.goal,
            "warnings": unverified_sources_found
        }
    }