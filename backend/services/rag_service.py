import json
import os

KB_PATH = "data/knowledge_base.json"

def search_knowledge_base(query: str) -> str:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Поиск по нормативной базе (имитация Managed RAG).
    """
    if not os.path.exists(KB_PATH):
        return ""
        
    with open(KB_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    results = []
    for item in data:
        if any(word.lower() in query.lower() for word in item["keywords"]):
            results.append(f"- {item['title']}: {item['content']}")
            
    return "\n".join(results)