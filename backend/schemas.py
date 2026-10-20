from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class Competency(BaseModel):
    name: str = Field(..., description="Название компетенции")
    knowledge: List[str] = Field(..., min_items=1)
    skills: List[str] = Field(..., min_items=1)

class Module(BaseModel):
    title: str = Field(..., min_length=3)
    hours: int = Field(..., gt=0)

class Framework(BaseModel):
    goal: str = Field(..., min_length=10, max_length=300)
    competencies: List[Competency] = Field(..., min_items=1)
    modules: List[Module] = Field(..., min_items=1)
    total_hours: int = Field(..., ge=16, le=500)

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
    topic: str = Field(..., min_length=3, max_length=100)
    hours: int = Field(..., ge=16, le=500, description="Объем программы")
    # [ТРЕБОВАНИЕ КЕЙСА]: По умолчанию 'auto', чтобы включить автоклассификатор
    template_type: Literal["ДПО", "Общеразвивающая", "auto"] = Field(default="auto")
    # [ТРЕБОВАНИЕ КЕЙСА]: Поле для передачи распарсенного текста референса
    reference_text: Optional[str] = Field(default=None, max_length=5000)

class RevisionRequest(BaseModel):
    instruction: str = Field(..., min_length=5)