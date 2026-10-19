from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class Competency(BaseModel):
    name: str
    knowledge: List[str]
    skills: List[str]

class Module(BaseModel):
    title: str
    hours: int

class Framework(BaseModel):
    goal: str
    competencies: List[Competency]
    modules: List[Module]
    total_hours: int

# [ТРЕБОВАНИЕ КЕЙСА]: Структурированный тест
class TestQuestion(BaseModel):
    question: str
    options: List[str]
    correct_answer: str
    related_competency: str
    is_source_unverified: bool = False # Флаг, что источник не подтвержден

class SeminarTask(BaseModel):
    task: str
    criteria: str
    related_competency: str

class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=3)
    hours: int = Field(..., ge=16, le=500)
    template_type: Literal["ДПО", "Общеразвивающая"] = Field(default="ДПО")

class RevisionRequest(BaseModel):
    instruction: str = Field(..., min_length=5)