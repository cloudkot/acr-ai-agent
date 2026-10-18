import uuid
from agents.curriculum import generate_framework_json, revise_framework_json
from agents.validator import run_full_validation, auto_correct_hours
from agents.content import generate_content_pack
from state_store import save_session, get_session
from logger import logger
from cloud import ask_llm

def clarify_request(topic: str) -> str:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Агент задает уточняющие вопросы, если не хватает данных.
    """
    prompt = f"""
    Ты — методист Академии цифрового развития. Пользователь хочет создать программу по теме: "{topic}".
    Задай ровно 3 коротких уточняющих вопроса (про аудиторию, её уровень и форму аттестации).
    Верни ТОЛЬКО список вопросов без приветствий.
    """
    return ask_llm(prompt, task_type="content")

def process_request(topic: str, hours: int, template_type: str = "ДПО"):
    """
    [СЦЕНАРИЙ КЕЙСА]: Прием запроса методиста, генерация каркаса.
    """
    session_id = str(uuid.uuid4())
    logger.info(f"Начата генерация каркаса. Тема: {topic}, Часы: {hours}, Тип: {template_type}")
    
    try:
        # Передаем template_type в агента!
        framework_obj = generate_framework_json(topic, hours, template_type)
        
        # [ТРЕБОВАНИЕ КЕЙСА]: Автоматическая коррекция часов (защита от ошибок LLM)
        framework_obj = auto_correct_hours(framework_obj, hours)
        
        # [ТРЕБОВАНИЕ КЕЙСА]: Отчет автопроверки
        report = run_full_validation(framework_obj)
        
        if not report["hours_match"]:
            logger.warning(f"Ошибка валидации часов: {report['calculated_total']} != {hours}")
            return {
                "status": "error", 
                "message": "Ошибка: сумма часов модулей не совпадает с общим объемом", 
                "report": report
            }
            
        save_session(session_id, framework_obj, "waiting_for_approval")
        
        return {
            "session_id": session_id,
            "status": "waiting_for_approval",
            "validation_report": report,
            "framework": framework_obj.model_dump()
        }
    except Exception as e:
        logger.error(f"Ошибка при генерации: {e}")
        return {"session_id": session_id, "status": "error", "message": str(e)}

def approve_and_generate(session_id: str):
    """
    [СЦЕНАРИЙ КЕЙСА]: Human-in-the-loop. Методист утвердил каркас.
    """
    session = get_session(session_id)
    if not session or session["status"] != "waiting_for_approval":
        return {"error": "Сессия не найдена или уже обработана"}
        
    logger.info(f"Каркас {session_id} утвержден. Генерация контента...")
    
    content = generate_content_pack(session["framework"])
    save_session(session_id, session["framework"], "completed", content)
    
    return {"session_id": session_id, "status": "completed", "content": content}

def revise_session(session_id: str, instruction: str):
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Точечная доработка без пересборки.
    """
    session = get_session(session_id)
    if not session:
        return {"error": "Сессия не найдена"}
        
    logger.info(f"Точечная правка сессии {session_id}: {instruction}")
    
    new_framework = revise_framework_json(session["framework"], instruction)
    
    # Сбрасываем статус обратно на утверждение
    save_session(session_id, new_framework, "waiting_for_approval")
    
    return {
        "session_id": session_id,
        "status": "waiting_for_approval",
        "message": "Каркас обновлен согласно правкам.",
        "framework": new_framework.model_dump()
    }