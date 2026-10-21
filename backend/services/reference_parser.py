import os
import uuid
import asyncio
import docx
import PyPDF2
from fastapi import UploadFile, HTTPException
from pathlib import Path
from logger import logger

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# [ТРЕБОВАНИЕ КЕЙСА]: Защита от DoS-атак (ограничение размера файла)
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

def _parse_file_sync(file_path: str, ext: str) -> str:
    """
    [ФИКС АРХИТЕКТУРЫ]: Синхронная функция для парсинга файла.
    Выполняется в отдельном потоке (asyncio.to_thread), чтобы не блокировать event loop.
    """
    extracted_text = ""
    try:
        if ext == ".docx":
            doc = docx.Document(file_path)
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            extracted_text = "\n".join(paragraphs)
            
        elif ext == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                extracted_text = f.read()
                
        elif ext == ".pdf":
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                if reader.is_encrypted:
                    raise ValueError("PDF защищен паролем")
                    
                pages_text = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)
                extracted_text = "\n".join(pages_text)
                
    finally:
        # Обязательная очистка: удаляем файл после прочтения
        if os.path.exists(file_path):
            os.remove(file_path)
            
    return extracted_text.strip()

async def save_and_parse_reference(file: UploadFile) -> str:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Прием референсов в .docx, .pdf и .txt.
    Обеспечивает безопасное сохранение, парсинг в отдельном потоке и возврат текста.
    """
    # 1. Проверка расширения
    ext = Path(file.filename).suffix.lower()
    if ext not in [".docx", ".txt", ".pdf"]:
        raise HTTPException(
            status_code=400, 
            detail="Недопустимый формат файла. Разрешены только .docx, .txt, .pdf"
        )
        
    # 2. Чтение контента (асинхронно) и проверка размера
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413, 
            detail="Файл слишком большой. Максимальный размер — 5 МБ."
        )
        
    # 3. Генерация безопасного имени (UUID)
    safe_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    # 4. Запись файла на диск (синхронная операция, но быстрая)
    with open(file_path, "wb") as buffer:
        buffer.write(content)
        
    # 5. Парсинг в отдельном потоке (не блокирует сервер)
    try:
        extracted_text = await asyncio.to_thread(_parse_file_sync, file_path, ext)
    except Exception as e:
        logger.error(f"Ошибка парсинга файла {file.filename}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Ошибка чтения файла: {str(e)}"
        )
        
    if not extracted_text:
        raise HTTPException(
            status_code=400, 
            detail="Не удалось извлечь текст из файла (возможно, он пуст или содержит только картинки)."
        )
        
    logger.info(f"Успешно распарсен референс {file.filename}. Символов: {len(extracted_text)}")
    
    # Возвращаем первые 5000 символов (для передачи в промпт)
    return extracted_text[:5000]