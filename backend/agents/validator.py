from schemas import Framework
import re

def run_full_validation(framework: Framework) -> dict:
    calculated_hours = sum(module.hours for module in framework.modules)
    hours_match = calculated_hours == framework.total_hours
    coverage_ok = len(framework.competencies) >= 3
    
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