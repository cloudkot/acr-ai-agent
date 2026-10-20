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
        raw = ask_llm(prompt, task_type="content", is_json=True)
        data = extract_json_from_text(raw)
        return {
            "template_type": data.get("template_type", "ДПО"),
            "questions": data.get("questions", [])
        }
    except Exception as e:
        logger.error(f"Ошибка автоклассификации: {e}")
        return {"template_type": "ДПО", "questions": []}

def process_request(topic: str, hours: int = None, template_type: str = "auto", reference_text: str = None, constraints: str = None):
    """[СЦЕНАРИЙ КЕЙСА]: Прием запроса, обработка нехватки данных и генерация каркаса."""
    session_id = str(uuid.uuid4())
    logger.info(f"Запрос: {topic}, {hours} ч., шаблон: {template_type}, ограничения: {'да' if constraints else 'нет'}")
    
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
                "message": "Не хватает данных для генерации. Ответьте на вопросы."
            }

        # 2. Генерация каркаса
        framework_obj = generate_framework_json(topic, hours, template_type, reference_text, constraints)
        
        # 3. Автокоррекция часов (теперь с учетом ограничений: например, обнуление лекций)
        framework_obj = auto_correct_hours(framework_obj, hours, constraints)
        report = run_full_validation(framework_obj)
            
        # 4. Сохранение сессии
        save_session(session_id, framework_obj, "waiting_for_approval", constraints=constraints)
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
    """[СЦЕНАРИЙ КЕЙСА]: Утверждение каркаса и генерация контента."""
    session = get_session(session_id)
    if not session or session["status"] != "waiting_for_approval":
        return {"error": "Сессия не найдена или уже обработана"}
        
    logger.info(f"Каркас {session_id} утвержден. Генерация контента...")
    
    try:
        constraints = session.get("constraints")
        
        # Генерация контента
        content = generate_content_pack(session["framework"], constraints)
        
        if not content.get("tests") and not content.get("lectures"):
            logger.error("Генерация контента не удалась: пустые тесты и лекции")
            return {"error": "Не удалось сгенерировать материалы. Попробуйте еще раз."}

        # [ФИКС РЕВЬЮЕРА]: ПРИНУДИТЕЛЬНАЯ КОРРЕКЦИЯ КОНТЕНТА
        # Обрезаем вопросы, фильтруем слайды и т.д.
        content = enforce_content_constraints(session["framework"], content, constraints)

        # Проверяем, что получилось после коррекции
        constraints_report = check_content_constraints(session["framework"], content, constraints)
        
        if not constraints_report["constraints_ok"]:
            logger.warning(f"Остались нарушения ограничений: {constraints_report['errors']}")
            
        save_session(session_id, session["framework"], "completed", content, constraints)
        log_action(session_id, "approved")
        
        return {
            "session_id": session_id, 
            "status": "completed", 
            "content": content,
            "constraints_check": constraints_report
        }
    except Exception as e:
        logger.error(f"Ошибка генерации контента: {e}")
        return {"error": f"Ошибка генерации контента: {str(e)}"}

def revise_session(session_id: str, instruction: str):
    """[ТРЕБОВАНИЕ КЕЙСА]: Точечная доработка каркаса."""
    session = get_session(session_id)
    if not session:
        return {"error": "Сессия не найдена"}
        
    logger.info(f"Точечная правка сессии {session_id}: {instruction}")
    
    new_framework = revise_framework_json(session["framework"], instruction)
    save_session(session_id, new_framework, "waiting_for_approval", constraints=session.get("constraints"))
    log_action(session_id, "revised")
    
    return {
        "session_id": session_id,
        "status": "waiting_for_approval",
        "message": "Каркас обновлен согласно правкам.",
        "framework": new_framework.model_dump()
    }