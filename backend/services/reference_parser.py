import os, docx
from fastapi import UploadFile
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

async def save_and_parse_reference(file: UploadFile) -> str:
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    extracted_text = ""
    if file.filename.endswith(".docx"):
        doc = docx.Document(file_path)
        extracted_text = "\n".join([p.text for p in doc.paragraphs])
    elif file.filename.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f: extracted_text = f.read()
    return extracted_text[:2000]