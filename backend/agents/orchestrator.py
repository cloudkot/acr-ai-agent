import uuid
from agents.curriculum import generate_framework_text
from agents.content import generate_content_pack

# [АРХИТЕКТУРА]: State Store (хранилище сессий).
# В MVP храним в памяти. В продакшене здесь будет Redis или PostgreSQL.
SESSIONS = {}

def process_request(topic: str, hours: int):
    """
    [АРХИТЕКТУРА]: Orchestrator.
    [СЦЕНАРИЙ КЕЙСА]: Прием запроса, генерация каркаса и остановка на утверждение.
    """
    session_id = str(uuid.uuid4())
    
    # Генерируем каркас через LLM
    framework_text = generate_framework_text(topic, hours)
    
    # Сохраняем в State Store
    SESSIONS[session_id] = {
        "topic": topic,
        "hours": hours,
        "framework": framework_text,
        "status": "waiting_for_approval",
        "content": None
    }
    
    return {
        "session_id": session_id,
        "status": "waiting_for_approval",
        "message": "Каркас сгенерирован. Требуется утверждение методиста.",
        "framework_draft": framework_text
    }

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