import os
import docx
from fastapi import UploadFile

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

async def save_and_parse_reference(file: UploadFile) -> str:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Прием референсов в .docx / .txt.
    """
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
        
    extracted_text = ""
    if file.filename.endswith(".docx"):
        doc = docx.Document(file_path)
        extracted_text = "\n".join([para.text for para in doc.paragraphs])
    elif file.filename.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            extracted_text = f.read()
            
    return extracted_text[:2000]