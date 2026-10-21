import uuid
import asyncio
from typing import Dict, Any, List
from cloud import ask_llm
from agents.base import BaseAgent
from agents.curriculum import generate_framework_json, revise_framework_json
from agents.content import (
    generate_tests, 
    generate_lectures, 
    generate_seminars, 
    generate_slides, 
    generate_work_programs, 
    generate_bibliography
)
from agents.validator_skill import ValidationSkill
from state_store import save_session, get_session, log_action
from utils.json_parser import extract_json_from_text
from logger import logger

# ==========================================
# [АРХИТЕКТУРА GIGACOWORK]: Изолированные Навыки
# ==========================================

class CurriculumSkill(BaseAgent):
    """Навык для генерации каркаса программы."""
    def __init__(self):
        super().__init__("Curriculum Architect", "Генерирует каркас программы.")
        
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        fw, tokens, cost = await generate_framework_json(
            context["topic"], context["hours"], context["template_type"], 
            context.get("reference_text"), context.get("constraints")
        )
        context["framework"] = fw
        context["tokens"] = context.get("tokens", 0) + tokens
        context["cost"] = context.get("cost", 0.0) + cost
        return context

class TestsSkill(BaseAgent):
    def __init__(self):
        super().__init__("Tests Generator", "Генерирует тестовые вопросы.")
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        res, tokens, cost = await generate_tests(context["framework"], context.get("constraints"))
        context["tests"] = res
        context["tokens"] = context.get("tokens", 0) + tokens
        context["cost"] = context.get("cost", 0.0) + cost
        return context

class LecturesSkill(BaseAgent):
    def __init__(self):
        super().__init__("Lectures Generator", "Генерирует планы лекций.")
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        res, tokens, cost = await generate_lectures(context["framework"], context.get("constraints"))
        context["lectures"] = res
        context["tokens"] = context.get("tokens", 0) + tokens
        context["cost"] = context.get("cost", 0.0) + cost
        return context

class SeminarsSkill(BaseAgent):
    def __init__(self):
        super().__init__("Seminars Generator", "Генерирует задания для семинаров.")
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        res, tokens, cost = await generate_seminars(context["framework"], context.get("constraints"))
        context["seminars"] = res
        context["tokens"] = context.get("tokens", 0) + tokens
        context["cost"] = context.get("cost", 0.0) + cost
        return context

class SlidesSkill(BaseAgent):
    def __init__(self):
        super().__init__("Slides Generator", "Генерирует структуру слайдов.")
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        res, tokens, cost = await generate_slides(context["framework"], context.get("constraints"))
        context["slides"] = res
        context["tokens"] = context.get("tokens", 0) + tokens
        context["cost"] = context.get("cost", 0.0) + cost
        return context

class WorkProgramsSkill(BaseAgent):
    def __init__(self):
        super().__init__("Work Programs Generator", "Генерирует рабочие программы.")
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        res, tokens, cost = await generate_work_programs(context["framework"], context.get("constraints"))
        context["work_programs"] = res
        context["tokens"] = context.get("tokens", 0) + tokens
        context["cost"] = context.get("cost", 0.0) + cost
        return context

class BibliographySkill(BaseAgent):
    def __init__(self):
        super().__init__("Bibliography Generator", "Генерирует список литературы.")
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        res, tokens, cost = await generate_bibliography(context["framework"], context.get("constraints"))
        context["bibliography"] = res
        context["tokens"] = context.get("tokens", 0) + tokens
        context["cost"] = context.get("cost", 0.0) + cost
        return context

class RevisionSkill(BaseAgent):
    def __init__(self):
        super().__init__("Revision Agent", "Вносит правки в каркас.")
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        fw, tokens, cost = await revise_framework_json(context["current_framework"], context["instruction"])
        context["framework"] = fw
        context["tokens"] = context.get("tokens", 0) + tokens
        context["cost"] = context.get("cost", 0.0) + cost
        return context

# ==========================================
# [АРХИТЕКТУРА]: Динамический Оркестратор
# ==========================================

class AgentOrchestrator:
    """
    Центральный диспетчер с реестром навыков.
    Пайплайны собираются динамически из списка шагов.
    """
    def __init__(self):
        self.skills: Dict[str, BaseAgent] = {
            "curriculum": CurriculumSkill(),
            "tests": TestsSkill(),
            "lectures": LecturesSkill(),
            "seminars": SeminarsSkill(),
            "slides": SlidesSkill(),
            "work_programs": WorkProgramsSkill(),
            "bibliography": BibliographySkill(),
            "revision": RevisionSkill(),
            "validation": ValidationSkill()
        }

    async def run_steps(self, step_names: List[str], context: Dict[str, Any], parallel: bool = False) -> Dict[str, Any]:
        """[АРХИТЕКТУРА]: Динамический запуск шагов."""
        if parallel:
            logger.info(f"Параллельный запуск навыков: {step_names}")
            # Создаем копию контекста для каждой ветки
            tasks = [self.skills[name].execute(context.copy()) for name in step_names]
            results = await asyncio.gather(*tasks)
            
            # Сливаем результаты обратно
            for res in results:
                context["tokens"] = context.get("tokens", 0) + res.get("tokens", 0)
                context["cost"] = context.get("cost", 0.0) + res.get("cost", 0.0)
                for key in ["tests", "lectures", "seminars", "slides", "work_programs", "bibliography"]:
                    if key in res: context[key] = res[key]
        else:
            logger.info(f"Последовательный запуск навыков: {step_names}")
            for name in step_names:
                context = await self.skills[name].execute(context)
        return context

    async def run_generate_pipeline(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # 1. Каркас -> 2. Валидация
        context = await self.run_steps(["curriculum", "validation"], context)
        
        await save_session(
            context["session_id"], context["framework"], "waiting_for_approval", 
            constraints=context.get("constraints"), tokens_used=context["tokens"], cost_rub=context["cost"]
        )
        await log_action(context["session_id"], "generated")
        
        return {
            "session_id": context["session_id"], 
            "status": "waiting_for_approval",
            "template_type": context["template_type"], 
            "validation_report": context.get("validation_report"),
            "framework": context["framework"].model_dump()
        }

    async def run_content_pipeline(self, session_id: str) -> Dict[str, Any]:
        session = await get_session(session_id)
        if not session or session["status"] != "waiting_for_approval":
            return {"error": "Сессия не найдена или уже обработана"}
            
        context = {
            "session_id": session_id, "framework": session["framework"],
            "constraints": session.get("constraints"), "tokens": session.get("tokens_used", 0), "cost": session.get("cost_rub", 0.0)
        }
        
        # Параллельный запуск всех генераторов контента
        content_steps = ["tests", "lectures", "seminars", "slides", "work_programs", "bibliography"]
        context = await self.run_steps(content_steps, context, parallel=True)
        
        # Валидация контента
        context = await self.run_steps(["validation"], context)
        
        # Сборка итогового контента
        content = {
            "tests": context.get("tests", []),
            "lectures": context.get("lectures", []),
            "seminars": context.get("seminars", []),
            "slides": context.get("slides", []),
            "work_programs": context.get("work_programs", []),
            "bibliography": context.get("bibliography", [])
        }
        
        await save_session(
            session_id, context["framework"], "completed", 
            content=content, constraints=context.get("constraints"),
            tokens_used=context["tokens"], cost_rub=context["cost"]
        )
        await log_action(session_id, "approved")
        
        return {
            "session_id": session_id, "status": "completed", "content": content,
            "constraints_check": context.get("constraints_check"),
            "analytics": {"tokens_spent": context["tokens"], "cost_rub": round(context["cost"], 2)}
        }

    async def run_revision_pipeline(self, session_id: str, instruction: str) -> Dict[str, Any]:
        session = await get_session(session_id)
        if not session: return {"error": "Сессия не найдена"}
            
        context = {
            "session_id": session_id, "current_framework": session["framework"],
            "instruction": instruction, "tokens": session.get("tokens_used", 0), "cost": session.get("cost_rub", 0.0)
        }
        
        context = await self.run_steps(["revision"], context)
        
        await save_session(
            session_id, context["framework"], "waiting_for_approval", 
            constraints=session.get("constraints"), tokens_used=context["tokens"], cost_rub=context["cost"]
        )
        await log_action(session_id, "revised")
        
        return {
            "session_id": session_id, "status": "waiting_for_approval", "message": "Каркас обновлен.",
            "framework": context["framework"].model_dump(),
            "analytics": {"tokens_spent": context["tokens"], "cost_rub": round(context["cost"], 2)}
        }

# ==========================================
# ПУБЛИЧНЫЕ ФУНКЦИИ (Для main.py)
# ==========================================

orchestrator = AgentOrchestrator()

async def clarify_and_classify(topic: str, hours: int = None, reference_text: str = None) -> dict:
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
    return await orchestrator.run_content_pipeline(session_id)

async def revise_session(session_id: str, instruction: str):
    return await orchestrator.run_revision_pipeline(session_id, instruction)