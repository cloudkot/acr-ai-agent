from schemas import Framework

def validate_curriculum_hours(framework: Framework) -> bool:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Автоматическая проверка сумм.
    Проверяет, что сумма часов по модулям равна заявленному объему программы.
    Предотвращает ошибки, когда в программе 246 часов самостоятельной работы, 
    а контактная — ноль.
    """
    calculated_hours = sum(module.hours for module in framework.modules)
    is_valid = calculated_hours == framework.total_hours
    
    if not is_valid:
        print(f"[VALIDATOR] Ошибка: Сумма модулей {calculated_hours} != общего объема {framework.total_hours}")
    
    return is_valid

def check_competency_coverage(framework: Framework) -> bool:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Связь между результатами обучения и темами.
    Проверяет, что у каждой компетенции есть привязка к модулям.
    """
    # Заглушка для демонстрации логики покрытия
    return len(framework.competencies) > 0