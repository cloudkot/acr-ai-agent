import uuid
from agents.curriculum import generate_framework_json, revise_framework_json
from agents.validator import run_full_validation
from agents.content import generate_content_pack
from state_store import save_session, get_session
from logger import logger

def process_request(topic: str, hours: int):
    session_id = str(uuid.uuid4())
    try:
        logger.info(f"Генерация: {topic}, {hours} ч.")
        framework_obj = generate_framework_json(topic, hours)
        report = run_full_validation(framework_obj)
        
        if not report["hours_match"]:
            return {"status": "error", "message": "Часы не сходятся", "report": report}
            
        save_session(session_id, framework_obj, "waiting_for_approval")
        return {"session_id": session_id, "status": "waiting_for_approval", "validation_report": report, "framework": framework_obj.model_dump()}
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return {"session_id": session_id, "status": "error", "message": str(e)}

def approve_and_generate(session_id: str):
    session = get_session(session_id)
    if not session or session["status"] != "waiting_for_approval":
        return {"error": "Сессия не найдена"}
        
    content = generate_content_pack(session["framework"])
    save_session(session_id, session["framework"], "completed", content)
    return {"session_id": session_id, "status": "completed", "content": content}

def revise_session(session_id: str, instruction: str):
    session = get_session(session_id)
    if not session:
        return {"error": "Сессия не найдена"}
    new_framework = revise_framework_json(session["framework"], instruction)
    save_session(session_id, new_framework, "waiting_for_approval")
    return {"session_id": session_id, "status": "waiting_for_approval", "framework": new_framework.model_dump()}