from pydantic import BaseModel, Field, field_validator
from typing import List, Literal, Optional
import re

class Competency(BaseModel):
    name: str
    knowledge: List[str]
    skills: List[str]
    related_topics: List[str] = Field(default_factory=list)

class Module(BaseModel):
    title: str = Field(..., min_length=3)
    total_hours: int = Field(..., gt=0)
    lectures: int = Field(default=0, ge=0)
    practice: int = Field(default=0, ge=0)
    labs: int = Field(default=0, ge=0)
    srs: int = Field(default=0, ge=0)

class Framework(BaseModel):
    goal: str = Field(..., min_length=10)
    template_type: Literal["ДПО", "Общеразвивающая"]
    prof_standard: Optional[str] = Field(default=None)
    competencies: List[Competency] = Field(..., min_items=1)
    modules: List[Module] = Field(..., min_items=1)
    total_hours: int = Field(..., ge=16, le=500)
    final_assessment_hours: int = Field(default=2, ge=0)

class TestQuestion(BaseModel):
    question: str
    options: List[str]
    correct_answer: str
    related_competency: str
    category: str = Field(default="Общая")

class SeminarTask(BaseModel):
    module_title: str
    task: str
    criteria: str
    related_competency: str

class LecturePlan(BaseModel):
    module_title: str
    theses: List[str]

class Slide(BaseModel):
    slide_type: Literal["title", "content", "two_columns", "summary"] = "content"
    title: str
    bullets: List[str] = Field(default_factory=list)
    speaker_notes: str = Field(default="")

class WorkProgram(BaseModel):
    module_title: str
    description: str

class ContentPack(BaseModel):
    tests: List[TestQuestion] = Field(default_factory=list)
    seminars: List[SeminarTask] = Field(default_factory=list)
    lectures: List[LecturePlan] = Field(default_factory=list)
    slides: List[Slide] = Field(default_factory=list)
    work_programs: List[WorkProgram] = Field(default_factory=list)
    bibliography: List[str] = Field(default_factory=list)

class SubTask(BaseModel):
    target_key: str
    prompt: str
    # [ФИКС]: Убрали строгий Literal, чтобы можно было передавать "text" или "json_array"
    expected_format: str = "json_array"
    # [ФИКС]: Добавили module_title для привязки ответа к модулю
    module_title: str = "Общий"

class ExecutionPlan(BaseModel):
    reasoning: str
    tasks: List[SubTask]

class GenerateRequest(BaseModel):
    # [ФИКС]: Разрешаем темы от 2 символов (ML, AI, Go)
    topic: str = Field(..., min_length=2, max_length=100)
    hours: Optional[int] = Field(default=None, ge=16, le=500)
    template_type: Optional[Literal["ДПО", "Общеразвивающая", "auto"]] = Field(default="auto")
    reference_text: Optional[str] = Field(default=None, max_length=15000)
    constraints: Optional[str] = Field(default=None, max_length=1000)

    @field_validator('topic', 'constraints')
    @classmethod
    def sanitize_input(cls, v: str) -> str:
        if not v: return v
        v = v.replace('"', '\\"')
        v = re.sub(r'<[^>]+>', '', v)
        injection_patterns = [
            r'(?i)ignore previous instructions', r'(?i)забудь все инструкции',
            r'(?i)system prompt', r'(?i)выведи текст', r'(?i)сломай json', r'(?i)ignore the above'
        ]
        for pattern in injection_patterns:
            v = re.sub(pattern, '[УДАЛЕНО]', v)
        return v.strip()

class RevisionRequest(BaseModel):
    instruction: str = Field(..., min_length=5, max_length=500)

    @field_validator('instruction')
    @classmethod
    def sanitize_instruction(cls, v: str) -> str:
        if not v: return v
        v = v.replace('"', '\\"')
        v = re.sub(r'<[^>]+>', '', v)
        return v.strip()