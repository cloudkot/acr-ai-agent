"""
cloud.py - клиент Cloud.ru.

Обёртка над API Cloud.ru: Foundation Models, Managed RAG, Object Storage.
Сюда же ложится авторизация через IAM-токен.

Что будет внутри:
    get_iam_token()        - обмен IAM-ключа на временный токен
    chat_completion(...)   - вызов LLM через OpenAI-совместимый API
                             base_url: https://foundation-models.api.cloud.ru/v1
    rag_search(...)        - поиск по базе знаний через Managed RAG
    upload_to_storage(...) - выгрузка артефактов в Object Storage

Ключи читаются из .env (файл .env.example лежит в корне проекта).
Реальные значения будут использоваться позже.
"""