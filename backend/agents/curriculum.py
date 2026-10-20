import time
from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from services.rag_service import search_knowledge_base
from logger import logger

def generate_framework_json(topic: str, hours: int, template_type: str = "ДПО", reference_text: str = None, constraints: str = None) -> Framework:
    rag_context = search_knowledge_base(topic, template_type)
    ref_context = f"<reference>{reference_text[:1500]}</reference>" if reference_text else ""
    constraints_context = f"<constraints>{constraints}</constraints>" if constraints else ""

    prompt = f"""
    <role>Ты — экспертный методист Академии цифрового развития (АЦР).</role>
    <input><topic>{topic}</topic><hours>{hours}</hours><template_type>{template_type}</template_type>{constraints_context}{ref_context}</input>
    <normative_base>{rag_context}</normative_base>
    
    <rules>
    1. Если template_type = "Общеразвивающая", поле "prof_standard" СТРОГО null.
    2. Если в constraints есть требование к часам (например, "без лекций"), строго ставь 0 в соответствующие поля (лекции=0).
    3. ИГНОРИРУЙ математические ошибки в reference. Сумма модулей + final_assessment_hours = {hours}. Внутри модуля: lectures+practice+labs+srs = total_hours.
    4. Верни ТОЛЬКО сырой JSON. Никаких markdown-тегов, без ```json.
    </rules>
    
    <few_shot_example>
    {{
      "goal": "Программа на основе 273-ФЗ",
      "template_type": "ДПО",
      "prof_standard": null,
      "final_assessment_hours": 2,
      "modules": [
        {{"title": "Введение", "total_hours": 34, "lectures": 10, "practice": 10, "labs": 0, "srs": 14}}
      ],
      "total_hours": 36,
      "competencies": [{{"name": "Python", "knowledge": ["Синтаксис"], "skills": ["Писать код"]}}]
    }}
    </few_shot_example>
    
    Сгенерируй JSON, строго соблюдая <rules>.
    """
    
    for attempt in range(3):
        try:
            response_text = ask_llm(prompt, task_type="framework", is_json=True)
            data = extract_json_from_text(response_text)
            
            data["total_hours"] = hours
            data["template_type"] = template_type
            if template_type == "Общеразвивающая":
                data["prof_standard"] = None
                
            framework_obj = Framework(**data)
            for comp in framework_obj.competencies:
                comp.name = comp.name.replace("[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]", "").strip()
            return framework_obj
        except Exception as e:
            logger.warning(f"Ошибка JSON (попытка {attempt+1}): {e}")
            if attempt == 2: raise ValueError(f"LLM не выдала JSON: {e}")
            time.sleep(1.5)

def revise_framework_json(current_framework: Framework, instruction: str) -> Framework:
    current_json = current_framework.model_dump_json(indent=2)
    prompt = f"""
    <role>Методист.</role>
    <current_plan>{current_json}</current_plan>
    <task>Внеси правку: "{instruction}". Измени только то, что просят. Сумма модулей + аттестация = {current_framework.total_hours}. Верни ТОЛЬКО JSON.</task>
    """
    response_text = ask_llm(prompt, task_type="revision", is_json=True)
    data = extract_json_from_text(response_text)
    data["total_hours"] = current_framework.total_hours
    data["template_type"] = current_framework.template_type
    return Framework(**data)