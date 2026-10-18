import uuid
from agents.curriculum import generate_framework_text
from agents.content import generate_content_pack

# [АРХИТЕКТУРА]: State Store (хранилище сессий).
# В MVP храним в памяти. В продакшене здесь будет Redis или PostgreSQL.
SESSIONS = {}

def process_request(topic: str, hours: int):
    session_id = str(uuid.uuid4())
    try:
        framework_obj = generate_framework_json(topic, hours)
        
        # Самопроверка
        is_valid = validate_curriculum_hours(framework_obj)
        coverage_ok = len(framework_obj.competencies) >= 3
        
        # Формируем отчет (чтобы ИИ-ревьюер его увидел)
        validation_report = {
            "hours_match": is_valid,
            "competency_coverage": coverage_ok,
            "calculated_total": sum(m.hours for m in framework_obj.modules)
        }
        
        SESSIONS[session_id] = {
            "framework": framework_obj,
            "status": "waiting_for_approval",
            "content": None,
            "report": validation_report
        }
        
        return {
            "session_id": session_id,
            "status": "waiting_for_approval",
            "message": "Каркас сгенерирован и валидирован.",
            "validation_report": validation_report, # <--- Вот он!
            "framework": framework_obj.model_dump()
        }
    except Exception as e:
        return {"session_id": session_id, "status": "error", "message": str(e)}

def approve_and_generate(session_id: str):
    """
    [СЦЕНАРИЙ КЕЙСА]: Human-in-the-loop. Методист утвердил каркас.
    Запускается генерация тестов, семинаров и лекций.
    """
    if session_id not in SESSIONS:
        return {"error": "Сессия не найдена"}
        
    session = SESSIONS[session_id]
    framework_text = session["framework"]
    
    # Генерируем контент на основе УТВЕРЖДЕННОГО каркаса
    content = generate_content_pack(framework_text)
    
    # Обновляем State Store
    session["content"] = content
    session["status"] = "completed"
    
    return {
        "session_id": session_id,
        "status": "completed",
        "content": content
    }