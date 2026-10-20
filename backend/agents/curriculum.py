import time
from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from services.rag_service import search_knowledge_base
from logger import logger

def def generate_framework_json(
    topic: str, hours: int, template_type: str = "ДПО", reference_text: str = None, constraints: str = None
) -> Framework:
    
    # 1. Снижение токенов: передаем только суть референса (первые 1500 символов)
    ref_context = f"<reference>{reference_text[:1500]}</reference>" if reference_text else ""
    constraints_context = f"<constraints>{constraints}</constraints>" if constraints else ""
    rag_context = search_knowledge_base(topic, template_type)

    # 2. Промпт-инжиниринг: четкая структура, роли, запреты и пример
    prompt = f"""
    <role>Ты — экспертный методист Академии цифрового развития (АЦР).</role>
    
    <input>
    <topic>{topic}</topic>
    <hours>{hours}</hours>
    <template_type>{template_type}</template_type>
    {constraints_context}
    {ref_context}
    </input>
    
    <normative_base>
    {rag_context}
    </normative_base>
    
    <rules>
    1. Если template_type = "Общеразвивающая", поле "prof_standard" СТРОГО null.
    2. Если в constraints есть требование к часам (например, "без лекций"), распредели часы ТОЛЬКО в указанные поля (лекции, практики, лабораторные, СРС).
    3. АРИФМЕТИКА: Сумма модулей + final_assessment_hours = {hours}. Внутри модуля: lectures+practice+labs+srs = total_hours.
    4. НЕ пиши ничего, кроме JSON. Никаких "Вот ваш JSON:" или markdown-тегов ```json. Только сырой JSON.
    </rules>
    
    <few_shot_example>
    {{
      "goal": "Программа на основе 273-ФЗ",
      "template_type": "ДПО",
      "prof_standard": "Профстандарт 06.001",
      "final_assessment_hours": 2,
      "modules": [
        {{"title": "Введение", "total_hours": 34, "lectures": 10, "practice": 10, "labs": 0, "srs": 14}}
      ],
      "total_hours": 36,
      "competencies": [{{"name": "Python", "knowledge": ["Синтаксис"], "skills": ["Писать код"]}}]
    }}
    </few_shot_example>
    
    Сгенерируй JSON по аналогии с few_shot_example, соблюдая все <rules>.
    """

def revise_framework_json(current_framework: Framework, instruction: str) -> Framework:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Точечная доработка каркаса.
    """
    current_json = current_framework.model_dump_json(indent=2)
    
    prompt = f"""
    Ты — методист. Вот текущий учебный план в JSON:
    {current_json}
    
    Внеси следующую правку: "{instruction}".
    Измени только то, что просят. Остальное оставь без изменений. 
    Сохрани все правила арифметики (сумма модулей + итоговая аттестация = {current_framework.total_hours}).
    Верни ТОЛЬКО валидный JSON в том же формате.
    """
    
    response_text = ask_llm(prompt, task_type="revision", is_json=True)
    data = extract_json_from_text(response_text)
    
    # Принудительно возвращаем правильный общий объем
    data["total_hours"] = current_framework.total_hours
    data["template_type"] = current_framework.template_type
    
    framework_obj = Framework(**data)
    
    for comp in framework_obj.competencies:
        comp.name = comp.name.replace("[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]", "").strip()
        
    return framework_obj