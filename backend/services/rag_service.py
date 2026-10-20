import json
import os

KB_PATH = "data/knowledge_base.json"

def search_knowledge_base(query: str, template_type: str = "ДПО") -> str:
    if not os.path.exists(KB_PATH):
        return ""
    with open(KB_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    results = []
    # Всегда добавляем законы
    law = next((item for item in data if "273-ФЗ" in item["title"]), None)
    if law: results.append(f"[ЗАКОН] {law['title']}: {law['content']}")
    order_keyword = "499" if template_type == "ДПО" else "629"
    order = next((item for item in data if order_keyword in item["title"]), None)
    if order: results.append(f"[ПРИКАЗ] {order['title']}: {order['content']}")
    # Простой поиск по совпадению слов
    for item in data:
        if item not in [law, order] and any(word.lower() in query.lower() for word in item["keywords"]):
            results.append(f"[ТЕМА] {item['title']}: {item['content']}")
    return "\n\n".join(results)
