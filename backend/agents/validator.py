from schemas import Framework
import re

def run_full_validation(framework: Framework) -> dict:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Отчет автопроверки (часы, покрытие, источники).
    """
    # Проверка арифметики часов
    calculated_hours = sum(module.hours for module in framework.modules)
    hours_match = calculated_hours == framework.total_hours
    
    # Проверка покрытия компетенций
    coverage_ok = len(framework.competencies) >= 3
    
    # Проверка пометок источников
    unverified_sources_found = []
    if "[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]" in framework.goal:
        unverified_sources_found.append("В цели есть неподтвержденные источники")
        
    suspicious_patterns = re.findall(r'(Приказ\s+№\s*\d+|ГОСТ\s+\d+)', framework.goal)
    if suspicious_patterns and "[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]" not in framework.goal:
         unverified_sources_found.append(f"Ссылки без пометки: {suspicious_patterns}")

    return {
        "hours_match": hours_match,
        "calculated_total": calculated_hours,
        "expected_total": framework.total_hours,
        "competency_coverage": coverage_ok,
        "total_competencies": len(framework.competencies),
        "sources_check": {
            "has_unverified_mark": "[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]" in framework.goal,
            "warnings": unverified_sources_found
        }
    }

def auto_correct_hours(framework: Framework, target_hours: int) -> Framework:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Защита от математических ошибок LLM.
    Если сумма часов не сходится, корректируем последний модуль.
    """
    if not framework.modules:
        return framework
        
    current_sum = sum(module.hours for module in framework.modules)
    diff = target_hours - current_sum
    
    if diff != 0:
        # Изменяем часы последнего модуля на разницу
        last_mod = framework.modules[-1]
        last_mod.hours += diff
        
        # Защита от отрицательных значений, если ИИ налажал с объемом
        if last_mod.hours < 1:
            last_mod.hours = 1 
            
        # Обновляем общий счетчик в каркасе
        framework.total_hours = sum(m.hours for m in framework.modules)
        
    return framework