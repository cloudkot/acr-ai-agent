from pydantic import BaseModel, Field
from typing import List, Literal

# [ТРЕБОВАНИЕ КЕЙСА]: Карта компетенций с разбивкой на знания, умения и навыки.
class Competency(BaseModel):
    name: str
    knowledge: List[str]
    skills: List[str]

# [ТРЕБОВАНИЕ КЕЙСА]: Учебный план с часами по модулям.
class Module(BaseModel):
    title: str
    hours: int

# [ТРЕБОВАНИЕ КЕЙСА]: Каркас программы.
class Framework(BaseModel):
    goal: str
    competencies: List[Competency]
    modules: List[Module]
    total_hours: int

# [ТРЕБОВАНИЕ КЕЙСА]: Тестовые вопросы с привязкой к результатам обучения.
class TestQuestion(BaseModel):
    question: str
    options: List[str]
    correct_answer: str
    related_competency: str

# [ТРЕБОВАНИЕ КЕЙСА]: Задания для семинаров с критериями оценки.
class SeminarTask(BaseModel):
    task: str
    criteria: str
    related_competency: str

class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=3, description="Тема программы")
    hours: int = Field(..., ge=16, le=500, description="Объем программы от 16 до 500 часов")
    template_type: Literal["ДПО", "Общеразвивающая"] = Field(default="ДПО", description="Тип программы по шаблону АЦР")

class RevisionRequest(BaseModel):
    instruction: str = Field(..., min_length=5, description="Инструкция по правке каркаса")