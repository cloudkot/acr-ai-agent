from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseAgent(ABC):
    """
    [ФИКС АРХИТЕКТУРЫ]: Базовый класс для всех навыков.
    Метод execute теперь асинхронный (async def), чтобы соответствовать 
    реальным реализациям в дочерних классах и не нарушать полиморфизм.
    """
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Выполняет логику навыка асинхронно."""
        pass