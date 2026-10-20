from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class Competency(BaseModel):
    name: str = Field(..., description="Название компетенции")
    knowledge: List[str] = Field(..., min_items=1)
    skills: List[str] = Field(..., min_items=1)

# [ТРЕБОВАНИЕ КЕЙСА]: Детализация часов по видам работ
class Module(BaseModel):
    title: str = Field(..., min_length=3)
    total_hours: int = Field(..., gt=0)
    lectures: int = Field(default=0, ge=0)
    practice: int = Field(default=0, ge=0)
    labs: int = Field(default=0, ge=0)
    srs: int = Field(default=0, ge=0) # Самостоятельная работа

class Framework(BaseModel):
    goal: str = Field(..., min_length=10)
    template_type: Literal["ДПО", "Общеразвивающая"]
    prof_standard: Optional[str] = Field(default=None, description="Код и название профстандарта (только для ДПО)")
    competencies: List[Competency] = Field(..., min_items=1)
    modules: List[Module] = Field(..., min_items=1)
    total_hours: int = Field(..., ge=16, le=500)
    final_assessment_hours: int = Field(default=2, ge=0)

class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=3)
    hours: Optional[int] = Field(default=None, ge=16, le=500)
    template_type: Optional[Literal["ДПО", "Общеразвивающая", "auto"]] = Field(default="auto")
    reference_text: Optional[str] = Field(default=None, max_length=15000)
    constraints: Optional[str] = Field(default=None, description="Доп. требования, например '10 вопросов', 'только отечественные сервисы'")

class ClarifyResponse(BaseModel):
    status: str = "clarification_needed"
    questions: List[str]
    session_id: str

class RevisionRequest(BaseModel):
    instruction: str = Field(..., min_length=5)