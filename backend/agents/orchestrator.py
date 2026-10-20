import uuid
from cloud import ask_llm
from agents.curriculum import generate_framework_json, revise_framework_json
from agents.validator import run_full_validation, auto_correct_hours
from agents.content import generate_content_pack
from state_store import save_session, get_session, log_action
from logger import logger

def clarify_and_classify(topic: str, hours: int, reference_text: str = None) -> dict:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Уточняющие вопросы и автоматический выбор шаблона.
    """
    ref_context = f"\nРеференс: {reference_text[:500]}" if reference_text else ""
    prompt = f"""
    Запрос методиста: "{topic}", объем: {hours} часов.{ref_context}
    
    1. Определи тип программы: "ДПО" или "Общеразвивающая". Выведи строго одно слово.
    2. Если в запросе не хватает данных об аудитории или форме аттестации, придумай 2 коротких уточняющих вопроса.
    
    Формат JSON: {{"template_type": "ДПО", "questions": ["Вопрос 1", "Вопрос 2"]}}
    """
    raw = ask_llm(prompt, task_type="content", is_json=True)
    import json
    from utils.json_parser import extract_json_from_text
    try:
        return extract_json_from_text(raw)
    except:
        return {"template_type": "ДПО", "questions": []}

def process_request(topic: str, hours: int, template_type: str = "auto", reference_text: str = None):
    """
    [СЦЕНАРИЙ КЕЙСА]: Прием запроса, автоклассификация и генерация каркаса.
    """
    session_id = str(uuid.uuid4())
    logger.info(f"Запрос: {topic}, {hours} ч., шаблон: {template_type}, референс: {'да' if reference_text else 'нет'}")
    
    try:
        # [ТРЕБОВАНИЕ КЕЙСА]: Автоматический выбор шаблона
        if template_type == "auto":
            classification = clarify_and_classify(topic, hours, reference_text)
            template_type = classification.get("template_type", "ДПО")
            logger.info(f"Автоматически выбран шаблон: {template_type}")
            
        # Передаем reference_text в агента
        framework_obj = generate_framework_json(topic, hours, template_type, reference_text)
        
        # Автокоррекция часов
        framework_obj = auto_correct_hours(framework_obj, hours)
        report = run_full_validation(framework_obj)
            
        save_session(session_id, framework_obj, "waiting_for_approval")
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

def approve_and_generate(session_id: str):
    """
    [СЦЕНАРИЙ КЕЙСА]: Утверждение каркаса и генерация контента.
    """
    session = get_session(session_id)
    if not session or session["status"] != "waiting_for_approval":
        return {"error": "Сессия не найдена или уже обработана"}
        
    logger.info(f"Каркас {session_id} утвержден. Генерация контента...")
    
    try:
        # [ТРЕБОВАНИЕ КЕЙСА]: Генерация контента
        content = generate_content_pack(session["framework"])
        
        # [ТРЕБОВАНИЕ КЕЙСА]: Защита от пустого контента (если LLM вернула мусор)
        if not content.get("tests") and not content.get("lectures"):
            logger.error("Генерация контента не удалась: пустые тесты и лекции")
            return {"error": "Не удалось сгенерировать материалы. Попробуйте утвердить еще раз."}
            
        save_session(session_id, session["framework"], "completed", content)
        log_action(session_id, "approved")
        
        return {"session_id": session_id, "status": "completed", "content": content}
    except Exception as e:
        logger.error(f"Ошибка генерации контента: {e}")
        return {"error": f"Ошибка генерации контента: {str(e)}"}

def revise_session(session_id: str, instruction: str):
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Точечная доработка каркаса.
    """
    session = get_session(session_id)
    if not session:
        return {"error": "Сессия не найдена"}
        
    logger.info(f"Точечная правка сессии {session_id}: {instruction}")
    
    new_framework = revise_framework_json(session["framework"], instruction)
    save_session(session_id, new_framework, "waiting_for_approval")
    log_action(session_id, "revised")
    
    return {
        "session_id": session_id,
        "status": "waiting_for_approval",
        "message": "Каркас обновлен согласно правкам.",
        "framework": new_framework.model_dump()
    }