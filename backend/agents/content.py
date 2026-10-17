from cloud import ask_llm, MODEL_FAST

def generate_content_pack(framework_text: str) -> dict:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Генерация полного комплекта материалов.
    """
    # Генерируем тесты
    prompt_tests = f"""
    На основе этого учебного плана:
    {framework_text}
    
    Составь 3 тестовых вопроса с 4 вариантами ответов и укажи правильный. 
    Привяжи каждый вопрос к одной из компетенций.
    """
    tests = ask_llm(prompt_tests, model=MODEL_FAST)
    
    # Генерируем семинары
    prompt_seminars = f"""
    На основе этого учебного плана:
    {framework_text}
    
    Составь 1 практическое задание для семинара с четкими критериями оценки.
    """
    seminars = ask_llm(prompt_seminars, model=MODEL_FAST)
    
    return {
        "tests": tests,
        "seminars": seminars,
        "lectures": "План лекций будет сгенерирован отдельным шагом (Slide Generator)."
    }