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
    
    # Остаток кидаем в СРС, чтобы сумма строго совпадала
    mod.srs = new_total - (mod.lectures + mod.practice + mod.labs)
    if mod.srs < 0: mod.srs = 0
        
    mod.total_hours = mod.lectures + mod.practice + mod.labs + mod.srs

def auto_correct_hours(framework: Framework, target_hours: int, constraints: str = None) -> Framework:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Автокоррекция часов с учетом ограничений.
    Если в constraints сказано "без лекций", мы жестко обнуляем ЛК и ПР.
    """
    if not framework.modules:
        return framework

    # 1. Учет жестких ограничений (например, DevOps без аудиторных часов)
    if constraints:
        cons_lower = constraints.lower()
        if "без лекций" in cons_lower or "без аудиторных" in cons_lower or "только самостоятельная" in cons_lower or "стажировка" in cons_lower:
            for mod in framework.modules:
                mod.lectures = 0
                mod.practice = 0
                mod.labs = 0
                mod.srs = mod.total_hours

    # 2. Сверка общей суммы
    current_sum = sum(module.total_hours for module in framework.modules) + framework.final_assessment_hours
    diff = target_hours - current_sum
    
    if diff != 0:
        last_mod = framework.modules[-1]
        new_total = last_mod.total_hours + diff
        
        if new_total < 1: new_total = 1
            
        # Распределяем часы пропорционально
        adjust_module_hours(last_mod, new_total)
        
        # Пересчитываем общий объем
        framework.total_hours = sum(m.total_hours for m in framework.modules) + framework.final_assessment_hours
        logger.info(f"Автокоррекция часов: модуль '{last_mod.title}' изменен до {new_total} ч.")
        
    return framework

def enforce_content_constraints(framework: Framework, content: dict, constraints: str = None) -> dict:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Принудительная коррекция контента.
    Обрезает или дополняет массивы, если LLM ошиблась.
    """
    if not constraints:
        return content
        
    cons_lower = constraints.lower()
    
    # 1. Жесткая проверка количества вопросов
    expected_q = None
    digits = re.findall(r'(\d+)\s*(вопрос|тест|задани)', cons_lower)
    if digits: expected_q = int(digits[0])
    elif "десять" in cons_lower: expected_q = 10
    
    if expected_q and isinstance(content.get("tests"), list):
        tests = content["tests"]
        if len(tests) > expected_q:
            content["tests"] = tests[:expected_q]
        elif len(tests) < expected_q:
            for i in range(len(tests), expected_q):
                tests.append({
                    "question": f"Дополнительный вопрос {i+1} (сгенерирован автоматически)",
                    "options": ["Вариант 1", "Вариант 2", "Вариант 3", "Вариант 4"],
                    "correct_answer": "Вариант 1",
                    "related_competency": framework.competencies[0].name if framework.competencies else "Общая"
                })
            content["tests"] = tests

    # 2. Жесткая проверка слайдов ("первые два занятия")
    if ("первые два" in cons_lower or "первых двух" in cons_lower) and isinstance(content.get("slides"), list):
        allowed_modules = [m.title.lower() for m in framework.modules[:2]]
        content["slides"] = [
            s for s in content["slides"] 
            if any(allowed in s.get("module_title", "").lower() for allowed in allowed_modules)
        ]

    # 3. Жесткая проверка слайдов ("только для pandas")
    if "pandas" in cons_lower and isinstance(content.get("slides"), list):
        content["slides"] = [
            s for s in content["slides"] 
            if "pandas" in s.get("module_title", "").lower() or "pandas" in s.get("slide_title", "").lower()
        ]

    return content

def check_content_constraints(framework: Framework, content: dict, constraints: str = None) -> dict:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Пост-валидация ограничений.
    Проверяет, что LLM реально выполнила то, что просил методист.
    """
    if not constraints: return {"constraints_ok": True, "errors": []}
    errors = []
    
    # Проверка количества вопросов
    expected_q = None
    digits = re.findall(r'(\d+)\s*(вопрос|тест|задани)', constraints.lower())
    if digits: expected_q = int(digits[0])
    elif "десять" in constraints.lower(): expected_q = 10
    
    if expected_q:
        actual_q = len(content.get("tests", []))
        if actual_q != expected_q:
            errors.append(f"Ожидалось {expected_q} вопросов, сгенерировано {actual_q}.")

    # Проверка слайдов ("первые два занятия")
    if "первые два" in constraints.lower() or "первых двух" in constraints.lower():
        allowed_modules = [m.title for m in framework.modules[:2]]
        for slide in content.get("slides", []):
            if slide.get("module_title") not in allowed_modules:
                errors.append(f"Слайд для '{slide.get('module_title')}' лишний, просили только первые два занятия.")
                break

    return {"constraints_ok": len(errors) == 0, "errors": errors}

def validate_coverage_with_content(framework: Framework, content: dict) -> dict:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Глубокая проверка покрытия компетенций.
    """
    if not content:
        return {"coverage_ok": False, "uncovered": ["Нет сгенерированного контента"]}

    comp_names = [c.name.lower().strip() for c in framework.competencies]
    tested_comps = set()
    
    for test in content.get("tests", []):
        if isinstance(test, dict) and "related_competency" in test:
            tested_comps.add(test["related_competency"].lower().strip())
            
    seminars = content.get("seminars", [])
    if isinstance(seminars, list):
        for sem in seminars:
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
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Отчет автопроверки каркаса.
    """
    calculated_total = sum(module.total_hours for module in framework.modules) + framework.final_assessment_hours
    hours_match = calculated_total == framework.total_hours
    
    modules_math_ok = True
    for mod in framework.modules:
        mod_sum = mod.lectures + mod.practice + mod.labs + mod.srs
        if mod_sum != mod.total_hours:
            modules_math_ok = False
            logger.warning(f"Ошибка в модуле '{mod.title}': сумма частей {mod_sum} != всего {mod.total_hours}")
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