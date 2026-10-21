from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseAgent(ABC):
    """
    [АРХИТЕКТУРА]: Базовый класс для всех навыков (по принципу GigaCowork).
    Каждый агент имеет имя, описание и метод execute.
    """
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Выполняет логику навыка.
        Принимает контекст (state), возвращает обновленный контекст.
        """
        pass