import json
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

KB_PATH = "data/knowledge_base.json"

def search_knowledge_base(query: str, template_type: str = "ДПО") -> str:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Умный поиск по базе знаний (RAG).
    [ML-ФИШКА]: Используем TF-IDF и косинусное сходство вместо тупого поиска по словам.
    """
    if not os.path.exists(KB_PATH):
        return ""
        
    with open(KB_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    results = []
    
    # 1. Всегда добавляем 273-ФЗ и приказ
    law = next((item for item in data if "273-ФЗ" in item["title"]), None)
    if law: results.append(f"[ЗАКОН] {law['title']}: {law['content']}")
    
    order_keyword = "499" if template_type == "ДПО" else "629"
    order = next((item for item in data if order_keyword in item["title"]), None)
    if order: results.append(f"[ПРИКАЗ] {order['title']}: {order['content']}")

    # 2. ML-поиск по остальным документам
    docs = [f"{item['title']} {item['content']}" for item in data if item not in [law, order]]
    if docs:
        # Векторизация текста (TF-IDF)
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(docs + [query])
        
        # Считаем косинусное сходство между запросом и документами
        cosine_similarities = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1]).flatten()
        
        # Берем самый релевантный документ, если сходство выше 0.1
        best_match_idx = cosine_similarities.argmax()
        if cosine_similarities[best_match_idx] > 0.1:
            best_item = [item for item in data if item not in [law, order]][best_match_idx]
            results.append(f"[ПРЕДМЕТНАЯ ОБЛАСТЬ] {best_item['title']}: {best_item['content']}")
                
    return "\n\n".join(results)