import uuid
from agents.curriculum import generate_framework_json, revise_framework_json
from agents.validator import run_full_validation, auto_correct_hours
from agents.content import generate_content_pack
# [ТРЕБОВАНИЕ КЕЙСА]: Импортируем функцию логирования
from state_store import save_session, get_session, log_action
from logger import logger
from cloud import ask_llm

def clarify_and_classify(topic: str, hours: int) -> dict:
    """[ТРЕБОВАНИЕ КЕЙСА]: Уточняющие вопросы и автоматический выбор шаблона."""
    prompt = f"""
    Запрос методиста: "{topic}", объем: {hours} часов.
    1. Определи тип программы: "ДПО" или "Общеразвивающая". Выведи строго одно слово.
    2. Если в запросе не хватает данных об аудитории (кто учится) или форме аттестации, придумай 2 коротких уточняющих вопроса.
    Формат JSON: {{"template_type": "ДПО", "questions": ["Вопрос 1", "Вопрос 2"]}}
    """
    raw = ask_llm(prompt, task_type="content", is_json=True)
    import json
    from utils.json_parser import extract_json_from_text
    try:
        return extract_json_from_text(raw)
    except:
        return {"template_type": "ДПО", "questions": []}

def process_request(topic: str, hours: int, template_type: str = "auto"):
    session_id = str(uuid.uuid4())
    
    try:
        # [ТРЕБОВАНИЕ КЕЙСА]: Автоматический выбор шаблона
        if template_type == "auto" or not template_type:
            classification = clarify_and_classify(topic, hours)
            template_type = classification.get("template_type", "ДПО")
            logger.info(f"Автоматически выбран шаблон: {template_type}")
            
        framework_obj = generate_framework_json(topic, hours, template_type)
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
        logger.error(f"Ошибка: {e}")
        return {"status": "error", "message": str(e)}
        
def approve_and_generate(session_id: str):
    session = get_session(session_id)
    if not session or session["status"] != "waiting_for_approval":
        return {"error": "Сессия не найдена или уже обработана"}
        
    logger.info(f"Каркас {session_id} утвержден. Генерация контента...")
    
    content = generate_content_pack(session["framework"])
    save_session(session_id, session["framework"], "completed", content)
    
    # [ТРЕБОВАНИЕ КЕЙСА]: Логируем утверждение
    log_action(session_id, "approved")
    
    return {"session_id": session_id, "status": "completed", "content": content}

def revise_session(session_id: str, instruction: str):
    session = get_session(session_id)
    if not session:
        return {"error": "Сессия не найдена"}
        
    logger.info(f"Точечная правка сессии {session_id}: {instruction}")
    
    new_framework = revise_framework_json(session["framework"], instruction)
    save_session(session_id, new_framework, "waiting_for_approval")
    
    # [ТРЕБОВАНИЕ КЕЙСА]: Логируем правку
    log_action(session_id, "revised")
    
    return {
        "session_id": session_id,
        "status": "waiting_for_approval",
        "message": "Каркас обновлен согласно правкам.",
        "framework": new_framework.model_dump()
    }