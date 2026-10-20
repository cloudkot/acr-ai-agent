import os
import uuid
import docx
import PyPDF2
from fastapi import UploadFile, HTTPException
from pathlib import Path
from logger import logger

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# [ТРЕБОВАНИЕ КЕЙСА]: Защита от DoS-атак (ограничение размера файла)
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

async def save_and_parse_reference(file: UploadFile) -> str:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Прием референсов в .docx, .pdf и .txt.
    Обеспечивает безопасное сохранение, парсинг и возврат текста 
    для дальнейшей передачи в LLM (через эндпоинт /api/generate).
    """
    # 1. Проверка расширения (белый список)
    ext = Path(file.filename).suffix.lower()
    if ext not in [".docx", ".txt", ".pdf"]:
        raise HTTPException(
            status_code=400, 
            detail="Недопустимый формат файла. Разрешены только .docx, .txt, .pdf"
        )
        
    # 2. Чтение контента и проверка размера (защита от переполнения диска)
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413, 
            detail="Файл слишком большой. Максимальный размер — 5 МБ."
        )
        
    # 3. Генерация безопасного имени (защита от Path Traversal)
    safe_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    with open(file_path, "wb") as buffer:
        buffer.write(content)
        
    extracted_text = ""
    
    # 4. Парсинг файла в зависимости от формата
    try:
        if ext == ".docx":
            doc = docx.Document(file_path)
            # Извлекаем текст из параграфов и таблиц (если есть)
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            extracted_text = "\n".join(paragraphs)
            
        elif ext == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                extracted_text = f.read()
                
        elif ext == ".pdf":
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                # Проверка на зашифрованный PDF
                if reader.is_encrypted:
                    raise ValueError("PDF защищен паролем")
                    
                pages_text = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)
                extracted_text = "\n".join(pages_text)
                
    except Exception as e:
        logger.error(f"Ошибка парсинга файла {file.filename}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Ошибка чтения файла: {str(e)}"
        )
    finally:
        # 5. Обязательная очистка: удаляем файл после прочтения
        if os.path.exists(file_path):
            os.remove(file_path)
            
    # 6. Валидация результата
    if not extracted_text.strip():
        raise HTTPException(
            status_code=400, 
            detail="Не удалось извлечь текст из файла (возможно, он пуст или содержит только картинки)."
        )
        
    logger.info(f"Успешно распарсен референс {file.filename}. Символов: {len(extracted_text)}")
    
    # [ТРЕБОВАНИЕ КЕЙСА]: Ограничиваем размер контекста для LLM (первые 3000 символов)
    # Этого достаточно для понимания сути, но не переполнит контекстное окно.
    return extracted_text[:3000].strip()