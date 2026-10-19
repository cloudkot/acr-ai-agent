import os
import uuid
import docx
import PyPDF2
from fastapi import UploadFile, HTTPException
from pathlib import Path

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

async def save_and_parse_reference(file: UploadFile) -> str:
    # [ТРЕБОВАНИЕ КЕЙСА]: Безопасная обработка имен файлов (защита от Path Traversal)
    ext = Path(file.filename).suffix.lower()
    if ext not in [".docx", ".txt", ".pdf"]:
        raise HTTPException(status_code=400, detail="Недопустимый формат файла. Разрешены: .docx, .txt, .pdf")
        
    safe_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
        
    extracted_text = ""
    try:
        if ext == ".docx":
            doc = docx.Document(file_path)
            extracted_text = "\n".join([para.text for para in doc.paragraphs])
        elif ext == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                extracted_text = f.read()
        elif ext == ".pdf":
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                extracted_text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка чтения файла: {str(e)}")
    finally:
        # Удаляем файл после парсинга, чтобы не забивать диск
        if os.path.exists(file_path):
            os.remove(file_path)
            
    return extracted_text[:3000]