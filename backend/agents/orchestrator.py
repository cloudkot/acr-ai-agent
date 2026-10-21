import uuid
from typing import Dict, Any
from cloud import ask_llm
from agents.base import BaseAgent
from agents.curriculum import generate_framework_json, revise_framework_json
from agents.content import generate_content_pack
from agents.validator_skill import ValidationSkill
from state_store import save_session, get_session, log_action
from utils.json_parser import extract_json_from_text
from logger import logger

# ==========================================
# [АРХИТЕКТУРА GIGACOWORK]: Навыки (Skills)
# ==========================================

class CurriculumSkill(BaseAgent):
    """Навык для генерации каркаса программы, распределения часов и компетенций."""
    def __init__(self):
        super().__init__("Curriculum Architect", "Генерирует каркас программы.")
        
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Выполнение навыка: Curriculum Architect")
        fw, tokens, cost = await generate_framework_json(
            context["topic"], 
            context["hours"], 
            context["template_type"], 
            context.get("reference_text"), 
            context.get("constraints")
        )
        context["framework"] = fw
        context["tokens"] = context.get("tokens", 0) + tokens
        context["cost"] = context.get("cost", 0.0) + cost
        return context

class ContentSkill(BaseAgent):
    """Навык для гранулярной (порционной) генерации контента."""
    def __init__(self):
        super().__init__("Content Generator", "Генерирует контент.")
        
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Выполнение навыка: Content Generator")
        content = await generate_content_pack(context["framework"], context.get("constraints"))
        
        # Извлекаем статистику токенов
        tokens = content.pop("total_tokens", 0)
        cost = content.pop("total_cost", 0.0)
        
        context["content"] = content
        context["tokens"] = context.get("tokens", 0) + tokens
        context["cost"] = context.get("cost", 0.0) + cost
        return context

class RevisionSkill(BaseAgent):
    """Навык для точечной доработки существующего каркаса."""
    def __init__(self):
        super().__init__("Revision Agent", "Вносит правки в каркас.")
        
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Выполнение навыка: Revision Agent")
        fw, tokens, cost = await revise_framework_json(
            context["current_framework"], 
            context["instruction"]
        )
        context["framework"] = fw
        context["tokens"] = context.get("tokens", 0) + tokens
        context["cost"] = context.get("cost", 0.0) + cost
        return context

# ==========================================
# [АРХИТЕКТУРА]: Оркестратор с реестром
# ==========================================

class AgentOrchestrator:
    """
    Центральный диспетчер с динамическим реестром навыков.
    Позволяет добавлять новые навыки без изменения кода оркестратора.
    """
    def __init__(self):
        # Реестр навыков (Dependency Injection)
        self.skills: Dict[str, BaseAgent] = {
            "curriculum": CurriculumSkill(),
            "content": ContentSkill(),
            "revision": RevisionSkill(),
            "validation": ValidationSkill()
        }

    async def run_generate_pipeline(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Пайплайн генерации каркаса: генерация -> валидация -> сохранение."""
        # 1. Генерация каркаса
        context = await self.skills["curriculum"].execute(context)
        
        # 2. Валидация (автокоррекция часов и проверка математики)
        context = await self.skills["validation"].execute_framework_validation(context)
        
        # 3. Сохранение состояния
        await save_session(
            context["session_id"], context["framework"], "waiting_for_approval", 
            constraints=context.get("constraints"), tokens_used=context["tokens"], cost_rub=context["cost"]
        )
        await log_action(context["session_id"], "generated")
        
        return {
            "session_id": context["session_id"], 
            "status": "waiting_for_approval",
            "template_type": context["template_type"], 
            "validation_report": context["validation_report"],
            "framework": context["framework"].model_dump()
        }

    async def run_content_pipeline(self, session_id: str) -> Dict[str, Any]:
        """Пайплайн генерации контента: генерация -> валидация -> сохранение."""
        session = await get_session(session_id)
        if not session or session["status"] != "waiting_for_approval":
            return {"error": "Сессия не найдена или уже обработана"}
            
        context = {
            "session_id": session_id, 
            "framework": session["framework"],
            "constraints": session.get("constraints"), 
            "tokens": session.get("tokens_used", 0), 
            "cost": session.get("cost_rub", 0.0)
        }
        
        # 1. Генерация контента
        context = await self.skills["content"].execute(context)
        
        # 2. Валидация контента (фильтрация слайдов, проверка количества вопросов)
        context = await self.skills["validation"].execute_content_validation(context)
        
        # 3. Сохранение результата
        await save_session(
            session_id, context["framework"], "completed", 
            content=context["content"], constraints=context.get("constraints"),
            tokens_used=context["tokens"], cost_rub=context["cost"]
        )
        await log_action(session_id, "approved")
        
        return {
            "session_id": session_id, 
            "status": "completed", 
            "content": context["content"],
            "constraints_check": context["constraints_check"],
            "analytics": {
                "tokens_spent": context["tokens"], 
                "cost_rub": round(context["cost"], 2)
            }
        }

    async def run_revision_pipeline(self, session_id: str, instruction: str) -> Dict[str, Any]:
        """Пайплайн точечной доработки каркаса."""
        session = await get_session(session_id)
        if not session:
            return {"error": "Сессия не найдена"}
            
        context = {
            "session_id": session_id, 
            "current_framework": session["framework"],
            "instruction": instruction, 
            "tokens": session.get("tokens_used", 0), 
            "cost": session.get("cost_rub", 0.0)
        }
        
        # 1. Внесение правок
        context = await self.skills["revision"].execute(context)
        
        # 2. Сохранение обновленного каркаса
        await save_session(
            session_id, context["framework"], "waiting_for_approval", 
            constraints=session.get("constraints"), 
            tokens_used=context["tokens"], 
            cost_rub=context["cost"]
        )
        await log_action(session_id, "revised")
        
        return {
            "session_id": session_id, 
            "status": "waiting_for_approval", 
            "message": "Каркас успешно обновлен.",
            "framework": context["framework"].model_dump(),
            "analytics": {
                "tokens_spent": context["tokens"], 
                "cost_rub": round(context["cost"], 2)
            }
        }

# ==========================================
# ПУБЛИЧНЫЕ АСИНХРОННЫЕ ФУНКЦИИ (Для main.py)
# ==========================================

orchestrator = AgentOrchestrator()

async def clarify_and_classify(topic: str, hours: int = None, reference_text: str = None) -> dict:
    """[ТРЕБОВАНИЕ КЕЙСА]: Уточняющие вопросы и автовыбор шаблона."""
    ref_context = f"\nРеференс: {reference_text[:500]}" if reference_text else ""
    hours_context = f"Объем: {hours} часов." if hours else "Объем НЕ УКАЗАН."
    
    prompt = f"""
    <role>Ты — методист АЦР.</role>
    <request>{topic}</request>
    <context>{hours_context}{ref_context}</context>
    <task>
    1. Определи тип программы: "ДПО" или "Общеразвивающая". Выведи строго одно слово.
    2. Если не указан объем, тип программы, аудитория или форма аттестации — придумай уточняющие вопросы (не больше 4).
    </task>
    <format>{{"template_type": "ДПО", "questions": ["Вопрос 1"]}}</format>
    """
    try:
        raw, _, _ = await ask_llm(prompt, task_type="content", is_json=True)
        data = extract_json_from_text(raw)
        return {
            "template_type": data.get("template_type", "ДПО"),
            "questions": data.get("questions", [])
        }
    except Exception as e:
        logger.error(f"Ошибка автоклассификации: {e}")
        return {"template_type": "ДПО", "questions": []}

async def process_request(topic: str, hours: int = None, template_type: str = "auto", reference_text: str = None, constraints: str = None):
    """Шаг 1: Запуск асинхронного пайплайна генерации каркаса."""
    session_id = str(uuid.uuid4())
    logger.info(f"Запрос: {topic}, {hours} ч.")
    
    try:
        needs_clarification = False
        questions = []
        
        if template_type == "auto" or hours is None:
            classification = await clarify_and_classify(topic, hours, reference_text)
            if template_type == "auto":
                template_type = classification["template_type"]
            questions = classification["questions"]
            
            if hours is None:
                needs_clarification = True

        if needs_clarification:
            return {
                "session_id": session_id,
                "status": "clarification_needed",
                "questions": questions,
                "message": "Не хватает данных для генерации."
            }

        context = {
            "session_id": session_id, 
            "topic": topic, 
            "hours": hours,
            "template_type": template_type, 
            "reference_text": reference_text,
            "constraints": constraints, 
            "tokens": 0, 
            "cost": 0.0
        }
        
        return await orchestrator.run_generate_pipeline(context)
        
    except Exception as e:
        logger.error(f"Ошибка при генерации: {e}")
        return {"session_id": session_id, "status": "error", "message": str(e)}

async def approve_and_generate(session_id: str):
    """Шаг 2: Утверждение каркаса и гранулярная генерация контента."""
    return await orchestrator.run_content_pipeline(session_id)

async def revise_session(session_id: str, instruction: str):
    """Точечная доработка каркаса без пересборки всего комплекта."""
    return await orchestrator.run_revision_pipeline(session_id, instruction)