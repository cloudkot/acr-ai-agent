import json
import os

KB_PATH = "data/knowledge_base.json"

def search_knowledge_base(query: str, template_type: str = "ДПО") -> str:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Поиск по нормативной базе (имитация Managed RAG).
    Всегда подтягивает 273-ФЗ и нужный приказ (499 или 629).
    """
    if not os.path.exists(KB_PATH):
        return ""
        
    with open(KB_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    results = []
    
    # 1. Всегда добавляем 273-ФЗ
    law = next((item for item in data if "273-ФЗ" in item["title"]), None)
    if law:
        results.append(f"[ЗАКОН] {law['title']}: {law['content']}")
        
    # 2. Добавляем приказ в зависимости от типа программы
    order_keyword = "499" if template_type == "ДПО" else "629"
    order = next((item for item in data if order_keyword in item["title"]), None)
    if order:
        results.append(f"[ПРИКАЗ] {order['title']}: {order['content']}")

    # 3. Ищем предметную базу по ключевым словам
    for item in data:
        if item["title"] not in [r.split(':')[0].replace('[ЗАКОН] ', '').replace('[ПРИКАЗ] ', '') for r in results]:
            if any(word.lower() in query.lower() for word in item["keywords"]):
                results.append(f"[ПРЕДМЕТНАЯ ОБЛАСТЬ] {item['title']}: {item['content']}")
                
    return "\n\n".join(results)