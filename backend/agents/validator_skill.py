from typing import Dict, Any
from agents.base import BaseAgent
from agents.validator import (
    auto_correct_hours, 
    run_full_validation, 
    enforce_content_constraints, 
    check_content_constraints
)
from logger import logger

class ValidationSkill(BaseAgent):
    """
    [ФИКС РЕВЬЮЕРА]: Валидация вынесена в отдельный навык (Skill).
    Теперь оркестратор не вызывает бизнес-логику напрямую.
    """
    def __init__(self):
        super().__init__("Validation Agent", "Проверяет математику часов, ограничения и покрытие компетенций.")

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Базовый метод, требуемый интерфейсом BaseAgent.
        Поскольку валидация вызывается специфичными методами (для каркаса и контента),
        мы оставляем этот метод как заглушку, возвращающую контекст.
        """
        return context

    async def execute_framework_validation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация и автокоррекция каркаса программы."""
        logger.info("Выполнение навыка: Валидация каркаса")
        fw = context["framework"]
        hours = context["hours"]
        constraints = context.get("constraints")
        
        # Автокоррекция и проверка
        corrected_fw = auto_correct_hours(fw, hours, constraints)
        report = run_full_validation(corrected_fw)
        
        context["framework"] = corrected_fw
        context["validation_report"] = report
        return context

    async def execute_content_validation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация и принудительная коррекция контента."""
        logger.info("Выполнение навыка: Валидация контента")
        fw = context["framework"]
        content = context["content"]
        constraints = context.get("constraints")
        
        # Принудительная коррекция и проверка
        corrected_content = enforce_content_constraints(fw, content, constraints)
        report = check_content_constraints(fw, corrected_content, constraints)
        
        context["content"] = corrected_content
        context["constraints_check"] = report
        return context