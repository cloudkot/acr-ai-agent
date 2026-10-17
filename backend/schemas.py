from pydantic import BaseModel
from typing import List

# [ТРЕБОВАНИЕ КЕЙСА]: Карта компетенций с разбивкой на знания, умения и навыки.
class Competency(BaseModel):
    name: str
    knowledge: List[str]  # Знания
    skills: List[str]     # Умения и навыки

# [ТРЕБОВАНИЕ КЕЙСА]: Учебный план с часами по модулям.
class Module(BaseModel):
    title: str
    hours: int

# [ТРЕБОВАНИЕ КЕЙСА]: Каркас программы (цель, компетенции, план, общий объем).
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
    related_competency: str # Привязка к компетенции