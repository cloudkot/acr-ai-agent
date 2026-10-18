from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from agents.orchestrator import process_request, approve_and_generate, revise_session
from state_store import get_session, init_db
from export import export_to_docx, export_to_pptx, export_tests_to_lms
from cloud import ask_llm
from services.reference_parser import save_and_parse_reference

app = FastAPI(title="ACR AI Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def startup_event(): init_db()

class GenerateReq(BaseModel): topic: str; hours: int
class RevisionReq(BaseModel): instruction: str

@app.get("/")
def root(): return {"status": "ok"}

@app.post("/api/generate")
def gen(req: GenerateReq): return process_request(req.topic, req.hours)

@app.post("/api/approve/{session_id}")
def appr(session_id: str): return approve_and_generate(session_id)

@app.post("/api/revise/{session_id}")
def rev(session_id: str, req: RevisionReq): return revise_session(session_id, req.instruction)

@app.post("/api/upload-reference")
async def up_ref(file: UploadFile = File(...)):
    text = await save_and_parse_reference(file)
    return {"status": "ok", "preview": text[:100]}

@app.post("/api/export-docx/{session_id}")
def exp_docx(session_id: str):
    s = get_session(session_id)
    if not s or s["status"] != "completed": raise HTTPException(400)
    fn = f"program_{session_id[:8]}.docx"; export_to_docx(s["framework"], s["content"], fn)
    return FileResponse(fn, filename=fn)

@app.post("/api/export-pptx/{session_id}")
def exp_pptx(session_id: str):
    s = get_session(session_id)
    if not s: raise HTTPException(404)
    fn = f"presentation_{session_id[:8]}.pptx"; export_to_pptx(s["framework"], fn)
    return FileResponse(fn, filename=fn)

@app.post("/api/export-lms/{session_id}")
def exp_lms(session_id: str):
    s = get_session(session_id)
    if not s or not s["content"]: raise HTTPException(400)
    fn = f"tests_{session_id[:8]}.csv"; export_tests_to_lms(s["content"].get("tests", []), fn)
    return FileResponse(fn, filename=fn)