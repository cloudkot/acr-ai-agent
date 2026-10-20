from schemas import Framework
import re
from logger import logger

def auto_correct_hours(framework: Framework, target_hours: int) -> Framework:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Автокоррекция часов.
    Если сумма модулей + аттестация не равна целевому объему, 
    корректируем последний модуль (добавляем разницу в СРС).
    """
    if not framework.modules:
        return framework
        
    current_sum = sum(module.total_hours for module in framework.modules) + framework.final_assessment_hours
    diff = target_hours - current_sum
    
    if diff != 0:
        last_mod = framework.modules[-1]
        last_mod.total_hours += diff
        last_mod.srs += diff
        
        if last_mod.srs < 0: last_mod.srs = 0 
        if last_mod.total_hours < 1: last_mod.total_hours = 1
            
        framework.total_hours = sum(m.total_hours for m in framework.modules) + framework.final_assessment_hours
        logger.info(f"Автокоррекция часов: добавлено {diff} ч. в модуль '{last_mod.title}' (СРС)")
        
    return framework

def validate_coverage_with_content(framework: Framework, content: dict) -> dict:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Глубокая проверка покрытия.
    Сверяем компетенции из каркаса с тем, что реально проверяется в тестах и семинарах.
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

def check_content_constraints(framework: Framework, content: dict, constraints: str = None) -> dict:
    """
    [ТРЕБОВАНИЕ КЕЙСА / ФИКС РЕВЬЮЕРА]: Программная постпроверка ограничений.
    Проверяет, что LLM реально выполнила то, что просил методист в строке constraints.
    """
    if not constraints:
        return {"constraints_ok": True, "errors": []}
        
    errors = []
    
    # 1. Проверка количества вопросов (например, "10 вопросов")
    q_match = re.search(r'(\d+)\s*(вопрос|тест)', constraints.lower())
    if q_match:
        expected_q = int(q_match.group(1))
        actual_q = len(content.get("tests", []))
        if actual_q != expected_q:
            errors.append(f"Нарушено ограничение по тестам: ожидалось {expected_q}, сгенерировано {actual_q}.")
            
    # 2. Проверка слайдов для конкретного модуля (например, "слайды для модуля pandas")
    if "слайд" in constraints.lower() and ("модул" in constraints.lower() or "занят" in constraints.lower()):
        # Ищем название модуля в строке ограничений
        for mod in framework.modules:
            # Берем первое слово модуля (например, "pandas" или "Введение")
            mod_keyword = mod.title.split()[0].lower()
            if mod_keyword in constraints.lower():
                # Проверяем, есть ли слайды для других модулей
                for slide in content.get("slides", []):
                    slide_mod = slide.get("module_title", "").lower()
                    if mod_keyword not in slide_mod and slide_mod:
                        errors.append(f"Нарушено ограничение по слайдам: сгенерированы слайды для '{slide_mod}', а просили только для '{mod.title}'.")
                        break

    return {
        "constraints_ok": len(errors) == 0,
        "errors": errors
    }