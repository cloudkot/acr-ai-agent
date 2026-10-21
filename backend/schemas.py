from pydantic import BaseModel, Field, field_validator
from typing import List, Literal, Optional
import re

class Competency(BaseModel):
    name: str = Field(..., description="Название компетенции")
    knowledge: List[str] = Field(..., min_items=1)
    skills: List[str] = Field(..., min_items=1)

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

class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=100)
    hours: Optional[int] = Field(default=None, ge=16, le=500)
    template_type: Optional[Literal["ДПО", "Общеразвивающая", "auto"]] = Field(default="auto")
    reference_text: Optional[str] = Field(default=None, max_length=15000)
    constraints: Optional[str] = Field(default=None, max_length=1000)

    # [ТРЕБОВАНИЕ КЕЙСА / БЕЗОПАСНОСТЬ]: Санитайзер ввода (Защита от Prompt Injection и разрыва JSON)
    @field_validator('topic', 'constraints')
    @classmethod
    def sanitize_input(cls, v: str) -> str:
        if not v:
            return v
        
        # 1. Экранируем кавычки, чтобы не сломать JSON
        v = v.replace('"', '\\"')
        
        # 2. Удаляем XML-теги, чтобы не сломать структуру промпта (<topic>, <constraints>)
        v = re.sub(r'<[^>]+>', '', v)
        
        # 3. Блокируем попытки инъекций (prompt injection)
        injection_patterns = [
            r'(?i)ignore previous instructions',
            r'(?i)забудь все инструкции',
            r'(?i)system prompt',
            r'(?i)выведи текст',
            r'(?i)сломай json',
            r'(?i)ignore the above'
        ]
        for pattern in injection_patterns:
            v = re.sub(pattern, '[УДАЛЕНО]', v)
            
        return v.strip()

class RevisionRequest(BaseModel):
    instruction: str = Field(..., min_length=5, max_length=500)

    @field_validator('instruction')
    @classmethod
    def sanitize_instruction(cls, v: str) -> str:
        if not v:
            return v
        v = v.replace('"', '\\"')
        v = re.sub(r'<[^>]+>', '', v)
        return v.strip()