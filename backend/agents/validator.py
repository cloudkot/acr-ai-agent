from schemas import Framework
import re

def run_full_validation(framework: Framework) -> dict:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Отчет автопроверки.
    Проверяет часы, покрытие компетенций и наличие неподтвержденных источников.
    """
    calculated_hours = sum(module.hours for module in framework.modules)
    hours_match = calculated_hours == framework.total_hours
    coverage_ok = len(framework.competencies) >= 3
    
    # [ТРЕБОВАНИЕ КЕЙСА]: Программная проверка источников в тексте цели
    unverified_sources_found = []
    if "[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]" in framework.goal:
        # Находим все упоминания
        unverified_sources_found.append("В цели программы есть неподтвержденные источники")
        
    # Ищем паттерны типа "Приказ №123", "ГОСТ", "Профстандарт" в тексте
    # (Упрощенная эвристика для демонстрации)
    suspicious_patterns = re.findall(r'(Приказ\s+№\s*\d+|ГОСТ\s+\d+|Профстандарт\s+\d+)', framework.goal)
    if suspicious_patterns and "[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]" not in framework.goal:
         unverified_sources_found.append(f"Найдены ссылки без пометки: {suspicious_patterns}")

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