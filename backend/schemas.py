from pydantic import BaseModel, Field, field_validator
from typing import List, Literal, Optional
import re

class Competency(BaseModel):
    name: str = Field(..., description="Название компетенции")
    knowledge: List[str] = Field(..., min_items=1)
    skills: List[str] = Field(..., min_items=1)
    related_topics: List[str] = Field(default_factory=list, description="Модули, где формируется компетенция")

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

# [НОВАЯ СХЕМА]: Заставляем ИИ генерировать структурированные слайды
class Slide(BaseModel):
    slide_type: Literal["title", "content", "two_columns", "summary"] = Field(
        default="content", 
        description="Тип слайда. title - титульный, content - обычный список, two_columns - два столбца, summary - итоги"
    )
    title: str = Field(..., description="Заголовок слайда")
    bullets: List[str] = Field(default_factory=list, description="Тезисы для слайда (не более 5)")
    speaker_notes: str = Field(default="", description="Текст для озвучивания лектором (то, что не видно на экране)")

class SubTask(BaseModel):
    target_key: str = Field(..., description="Ключ, куда сохранить результат (например, 'tests', 'seminars', 'lectures', 'slides')")
    prompt: str = Field(..., description="Готовый промпт для отправки в LLM")
    expected_format: str = Field(default="json_array", description="Ожидаемый формат ответа (json_array или json_object)")

class ExecutionPlan(BaseModel):
    reasoning: str = Field(..., description="Обоснование того, как разбить задачи")
    tasks: List[SubTask] = Field(..., description="Список задач для параллельного выполнения")

class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=100)
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