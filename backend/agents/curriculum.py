import time
from cloud import ask_llm
from schemas import Framework
from utils.json_parser import extract_json_from_text
from services.rag_service import search_knowledge_base
from logger import logger

def generate_framework_json(
    topic: str, 
    hours: int, 
    template_type: str = "ДПО", 
    reference_text: str = None,
    constraints: str = None
) -> Framework:
    """
    [АРХИТЕКТУРА]: Curriculum Architect.
    [ТРЕБОВАНИЕ КЕЙСА]: Учет шаблона, референсов, ограничений и защита от математических ошибок.
    """
    # 1. ML RAG (поиск по нормативной базе)
    rag_context = search_knowledge_base(topic, template_type)
    
    # 2. Подготовка контекста из референса и ограничений
    ref_context = ""
    if reference_text:
        ref_context = f"\nВНИМАНИЕ! УЧТИ СТРУКТУРУ ЭТОГО РЕФЕРЕНСА, НО НЕ КОПИРУЙ ИЗ НЕГО ОШИБКИ В ЧАСАХ:\n{reference_text[:4000]}\n"
    
    constraints_context = ""
    if constraints:
        constraints_context = f"\nОСОБЫЕ ТРЕБОВАНИЯ МЕТОДИСТА (СТРОГО СОБЛЮДАТЬ):\n{constraints}\n"

    # 3. Формируем строгий промпт с учетом специфики ДПО и Общеразвивающих программ
    prompt = f"""
    Ты — старший методист Академии цифрового развития (АЦР).
    
    ПАРАМЕТРЫ ЗАПРОСА:
    - Тема: {topic}
    - Общий объем: {hours} часов
    - Тип программы: {template_type}
    
    НОРМАТИВНАЯ БАЗА (Используй в поле "goal"):
    {rag_context}
    {ref_context}
    {constraints_context}
    
    ПРАВИЛА ФОРМИРОВАНИЯ КАРКАСА:
    1. Если тип "Общеразвивающая" (например, для школьников): 
       - ЗАПРЕЩЕНО указывать профстандарты и трудовые функции (оставь "prof_standard": null).
       - Сделай упор на общие навыки и проектную деятельность.
    2. Если тип "ДПО" (повышение квалификации, стажировка):
       - ОБЯЗАТЕЛЬНО укажи реальный профстандарт и код трудовой функции в поле "prof_standard" (например, "Профстандарт 06.001, код A/01.6").
    3. Если в требованиях сказано "без аудиторных занятий" или "только самостоятельная работа" (как в стажировках):
       - Поля "lectures" (лекции), "practice" (практики) и "labs" (лабораторные) должны быть равны 0.
       - Все часы перенеси в "srs" (самостоятельная работа).
    4. АРИФМЕТИКА (КРИТИЧЕСКИ ВАЖНО):
       - Сумма часов всех модулей + часы итоговой аттестации ("final_assessment_hours") ДОЛЖНА быть ровно {hours}.
       - Внутри каждого модуля: "total_hours" должно быть равно сумме (lectures + practice + labs + srs).
    
    Формат ответа — СТРОГИЙ JSON (без markdown-разметки):
    {{
        "goal": "строка с нормативной базой",
        "template_type": "{template_type}",
        "prof_standard": "строка или null",
        "final_assessment_hours": число (обычно 2 или 4),
        "modules": [
            {{
                "title": "Название модуля",
                "total_hours": число,
                "lectures": число,
                "practice": число,
                "labs": число,
                "srs": число
            }}
        ],
        "total_hours": {hours},
        "competencies": [
            {{"name": "строка", "knowledge": ["строка"], "skills": ["строка"]}}
        ]
    }}
    """
    
    # 4. Генерация с ретраями
    for attempt in range(3):
        try:
            response_text = ask_llm(prompt, task_type="framework", is_json=True)
            data = extract_json_from_text(response_text)
            
            # Принудительно выставляем общий объем и тип, чтобы LLM не обманула
            data["total_hours"] = hours
            data["template_type"] = template_type
            
            # Защита от галлюцинаций с профстандартами
            if template_type == "Общеразвивающая":
                data["prof_standard"] = None
            elif not data.get("prof_standard"):
                data["prof_standard"] = "[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК] Профстандарт не указан"
            
            framework_obj = Framework(**data)
            
            # Очистка названий компетенций от лишних тегов
            for comp in framework_obj.competencies:
                comp.name = comp.name.replace("[НЕПОДТВЕРЖДЕННЫЙ ИСТОЧНИК]", "").strip()
                
            return framework_obj
            
        except Exception as e:
            logger.warning(f"Ошибка парсинга JSON от LLM (попытка {attempt+1}): {e}")
            if attempt == 2:
                raise ValueError(f"LLM не смогла выдать правильный JSON после 3 попыток. Ошибка: {e}")
            time.sleep(1.5)

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