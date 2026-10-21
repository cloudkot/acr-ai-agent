import uuid
from typing import Dict, Any
from cloud import ask_llm
from agents.base import BaseAgent
from agents.curriculum import generate_framework_json, revise_framework_json
from agents.validator import (
    run_full_validation, 
    auto_correct_hours, 
    check_content_constraints, 
    enforce_content_constraints
)
from agents.content import generate_content_pack
from state_store import save_session, get_session, log_action
from utils.json_parser import extract_json_from_text
from logger import logger

# ==========================================
# [АРХИТЕКТУРА GIGACOWORK]: Навыки (Skills)
# ==========================================

class CurriculumSkill(BaseAgent):
    def __init__(self):
        super().__init__("Curriculum Architect", "Генерирует каркас программы, распределяет часы и компетенции.")
        
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
    def __init__(self):
        super().__init__("Content Generator", "Параллельно генерирует тесты, семинары, лекции, слайды и библиографию.")
        
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Выполнение навыка: Content Generator")
        content = await generate_content_pack(context["framework"], context.get("constraints"))
        
        tokens = content.pop("total_tokens", 0)
        cost = content.pop("total_cost", 0.0)
        
        context["content"] = content
        context["tokens"] = context.get("tokens", 0) + tokens
        context["cost"] = context.get("cost", 0.0) + cost
        return context

class RevisionSkill(BaseAgent):
    def __init__(self):
        super().__init__("Revision Agent", "Вносит точечные правки в существующий каркас.")
        
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
# [АРХИТЕКТУРА]: Оркестратор
# ==========================================

class AgentOrchestrator:
    """
    Центральный диспетчер. Управляет контекстом и передает его 
    между независимыми асинхронными навыками.
    """
    def __init__(self):
        self.curriculum_skill = CurriculumSkill()
        self.content_skill = ContentSkill()
        self.revision_skill = RevisionSkill()

    async def run_generate_pipeline(self, context: Dict[str, Any]) -> Dict[str, Any]:
        context = await self.curriculum_skill.execute(context)
        
        context["framework"] = auto_correct_hours(context["framework"], context["hours"], context.get("constraints"))
        report = run_full_validation(context["framework"])
        
        save_session(
            context["session_id"], context["framework"], "waiting_for_approval", 
            constraints=context.get("constraints"), tokens_used=context["tokens"], cost_rub=context["cost"]
        )
        log_action(context["session_id"], "generated")
        
        return {
            "session_id": context["session_id"],
            "status": "waiting_for_approval",
            "template_type": context["template_type"],
            "validation_report": report,
            "framework": context["framework"].model_dump()
        }

    async def run_content_pipeline(self, session_id: str) -> Dict[str, Any]:
        session = get_session(session_id)
        if not session or session["status"] != "waiting_for_approval":
            return {"error": "Сессия не найдена или уже обработана"}
            
        context = {
            "session_id": session_id, 
            "framework": session["framework"],
            "constraints": session.get("constraints"), 
            "tokens": session.get("tokens_used", 0), 
            "cost": session.get("cost_rub", 0.0)
        }
        
        context = await self.content_skill.execute(context)
        
        context["content"] = enforce_content_constraints(context["framework"], context["content"], context.get("constraints"))
        constraints_report = check_content_constraints(context["framework"], context["content"], context.get("constraints"))
        
        save_session(
            session_id, context["framework"], "completed", 
            content=context["content"], constraints=context.get("constraints"),
            tokens_used=context["tokens"], cost_rub=context["cost"]
        )
        log_action(session_id, "approved")
        
        return {
            "session_id": session_id, 
            "status": "completed", 
            "content": context["content"],
            "constraints_check": constraints_report,
            "analytics": {
                "tokens_spent": context["tokens"], 
                "cost_rub": round(context["cost"], 2), 
                "hours_saved": 40.0
            }
        }

    async def run_revision_pipeline(self, session_id: str, instruction: str) -> Dict[str, Any]:
        session = get_session(session_id)
        if not session:
            return {"error": "Сессия не найдена"}
            
        context = {
            "session_id": session_id,
            "current_framework": session["framework"],
            "instruction": instruction,
            "tokens": session.get("tokens_used", 0),
            "cost": session.get("cost_rub", 0.0)
        }
        
        context = await self.revision_skill.execute(context)
        
        save_session(
            session_id, context["framework"], "waiting_for_approval", 
            constraints=session.get("constraints"),
            tokens_used=context["tokens"], cost_rub=context["cost"]
        )
        log_action(session_id, "revised")
        
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
# ПУБЛИЧНЫЕ АСИНХРОННЫЕ ФУНКЦИИ
# ==========================================

orchestrator = AgentOrchestrator()

async def clarify_and_classify(topic: str, hours: int = None, reference_text: str = None) -> dict:
    """Уточняющие вопросы и автовыбор шаблона."""
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
            "session_id": session_id, "topic": topic, "hours": hours,
            "template_type": template_type, "reference_text": reference_text,
            "constraints": constraints, "tokens": 0, "cost": 0.0
        }
        
        return await orchestrator.run_generate_pipeline(context)
        
    except Exception as e:
        logger.error(f"Ошибка при генерации: {e}")
        return {"session_id": session_id, "status": "error", "message": str(e)}

async def approve_and_generate(session_id: str):
    """Шаг 2: Утверждение и асинхронная генерация контента."""
    return await orchestrator.run_content_pipeline(session_id)

async def revise_session(session_id: str, instruction: str):
    """Точечная доработка каркаса."""
    return await orchestrator.run_revision_pipeline(session_id, instruction)