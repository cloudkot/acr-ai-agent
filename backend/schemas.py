from pydantic import BaseModel
from typing import List

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

class TestQuestion(BaseModel):
    question: str
    options: List[str]
    correct_answer: str
    related_competency: str

class SeminarTask(BaseModel):
    task: str
    criteria: str
    related_competency: str