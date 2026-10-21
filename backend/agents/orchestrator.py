import uuid
from cloud import ask_llm
from agents.curriculum import generate_framework_json, revise_framework_json
from agents.validator import (
    run_full_validation, 
    auto_correct_hours, 
    check_content_constraints, 
    enforce_content_constraints, 
    validate_coverage_with_content
)
from agents.content import generate_content_pack
from state_store import save_session, get_session, log_action
from utils.json_parser import extract_json_from_text
from logger import logger

def clarify_and_classify(topic: str, hours: int = None, reference_text: str = None) -> dict:
    """[ТРЕБОВАНИЕ КЕЙСА]: Уточняющие вопросы и автоматический выбор шаблона."""
    ref_context = f"\nРеференс: {reference_text[:500]}" if reference_text else ""
    hours_context = f"Объем: {hours} часов." if hours else "Объем НЕ УКАЗАН."
    
    prompt = f"""
    <role>Ты — методист АЦР.</role>
    <request>{topic}</request>
    <context>{hours_context}{ref_context}</context>
    
    <task>
    1. Определи тип программы: "ДПО" или "Общеразвивающая". Выведи строго одно слово.
    2. Если не указан объем, тип программы, аудитория или форма аттестации — придумай уточняющие вопросы (не больше 4).
    Если данных достаточно, массив вопросов оставь пустым.
    </task>
    
    <format>{{"template_type": "ДПО", "questions": ["Вопрос 1", "Вопрос 2"]}}</format>
    """
    try:
        # Распаковываем кортеж от ask_llm (текст, токены, стоимость)
        raw, _, _ = ask_llm(prompt, task_type="content", is_json=True)
        data = extract_json_from_text(raw)
        return {
            "template_type": data.get("template_type", "ДПО"),
            "questions": data.get("questions", [])
        }
    except Exception as e:
        logger.error(f"Ошибка автоклассификации: {e}")
        return {"template_type": "ДПО", "questions": []}

def process_request(topic: str, hours: int = None, template_type: str = "auto", reference_text: str = None, constraints: str = None, token_limit: int = 50000):
    """[СЦЕНАРИЙ КЕЙСА]: Прием запроса и генерация каркаса с контролем токенов."""
    session_id = str(uuid.uuid4())
    logger.info(f"Запрос: {topic}, {hours} ч., лимит: {token_limit}")
    
    try:
        needs_clarification = False
        questions = []
        
        if template_type == "auto" or hours is None:
            classification = clarify_and_classify(topic, hours, reference_text)
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

        # Генерация каркаса (возвращает Framework, tokens, cost)
        framework_obj, tokens, cost = generate_framework_json(
            topic, hours, template_type, reference_text, constraints, token_limit
        )
        
        # Автокоррекция часов
        framework_obj = auto_correct_hours(framework_obj, hours, constraints)
        report = run_full_validation(framework_obj)
            
        # Сохраняем сессию, передавая потраченные токены и стоимость
        save_session(
            session_id, framework_obj, "waiting_for_approval", 
            constraints=constraints, tokens_used=tokens, cost_rub=cost
        )
        log_action(session_id, "generated")
        
        return {
            "session_id": session_id,
            "status": "waiting_for_approval",
            "template_type": template_type,
            "validation_report": report,
            "framework": framework_obj.model_dump()
        }
    except Exception as e:
        logger.error(f"Ошибка при генерации: {e}")
        return {"session_id": session_id, "status": "error", "message": str(e)}

def approve_and_generate(session_id: str, token_limit: int = 50000):
    """[СЦЕНАРИЙ КЕЙСА]: Утверждение каркаса и генерация контента."""
    session = get_session(session_id)
    if not session or session["status"] != "waiting_for_approval":
        return {"error": "Сессия не найдена или уже обработана"}
        
    logger.info(f"Каркас {session_id} утвержден. Генерация контента...")
    
    try:
        constraints = session.get("constraints")
        
        # Генерируем контент (возвращает dict с контентом, tokens, cost)
        content_data = generate_content_pack(session["framework"], constraints, token_limit)
        
        # Достаем статистику из контента
        new_tokens = content_data.pop("total_tokens", 0)
        new_cost = content_data.pop("total_cost", 0.0)
        
        if not content_data.get("tests") and not content_data.get("lectures"):
            return {"error": "Не удалось сгенерировать материалы."}

        # Принудительная коррекция
        content_data = enforce_content_constraints(session["framework"], content_data, constraints)
        constraints_report = check_content_constraints(session["framework"], content_data, constraints)
            
        # Сохраняем сессию, суммируя токены со всех этапов
        total_tokens = session.get("tokens_used", 0) + new_tokens
        total_cost = session.get("cost_rub", 0.0) + new_cost
        
        save_session(
            session_id, session["framework"], "completed", 
            content=content_data, constraints=constraints,
            tokens_used=total_tokens, cost_rub=total_cost
        )
        log_action(session_id, "approved")
        
        return {
            "session_id": session_id, 
            "status": "completed", 
            "content": content_data,
            "constraints_check": constraints_report,
            # Отдаем аналитику на фронтенд
            "analytics": {
                "tokens_spent": total_tokens,
                "cost_rub": round(total_cost, 2),
                "hours_saved": 40.0
            }
        }
    except Exception as e:
        logger.error(f"Ошибка генерации контента: {e}")
        return {"error": f"Ошибка генерации контента: {str(e)}"}

def revise_session(session_id: str, instruction: str, token_limit: int = 50000):
    session = get_session(session_id)
    if not session:
        return {"error": "Сессия не найдена"}
        
    logger.info(f"Точечная правка {session_id}: {instruction}")
    
    try:
        new_framework, tokens, cost = revise_framework_json(session["framework"], instruction, token_limit)
        
        # Сохраняем обновленный каркас и возвращаем статус waiting_for_approval
        save_session(
            session_id, new_framework, "waiting_for_approval", 
            constraints=session.get("constraints"),
            tokens_used=session.get("tokens_used", 0) + tokens, 
            cost_rub=session.get("cost_rub", 0.0) + cost
        )
        log_action(session_id, "revised")
        
        return {
            "session_id": session_id,
            "status": "waiting_for_approval", # Важно вернуть этот статус!
            "message": "Каркас успешно обновлен согласно вашим правкам.",
            "framework": new_framework.model_dump()
        }
    except Exception as e:
        logger.error(f"Ошибка при правке: {e}")
        return {"error": f"Не удалось внести правки: {str(e)}"}