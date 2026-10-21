# [ТРЕБОВАНИЕ КЕЙСА]: Трекер расхода токенов и бюджета для конкретной сессии
import threading

class TokenTracker:
    def __init__(self):
        self._local = threading.local()

    def reset(self):
        """Сбрасывает счетчики перед новой сессией."""
        self._local.tokens = 0
        self._local.cost = 0.0
        self._local.budget = 50000  # Дефолтный лимит в токенах

    def set_budget(self, budget: int):
        if budget:
            self._local.budget = budget

    def add_usage(self, tokens: int, cost: float):
        """Добавляет потраченные токены и рубли."""
        self._local.tokens += tokens
        self._local.cost += cost
        
        # [БЕЗОПАСНОСТЬ]: Если бюджет превышен, выбрасываем ошибку
        if self._local.tokens > self._local.budget:
            raise ValueError(f"Превышен лимит бюджета! Потрачено {self._local.tokens} из {self._local.budget} токенов.")

    def get_stats(self) -> dict:
        """Возвращает текущую статистику для UI."""
        tokens = getattr(self._local, 'tokens', 0)
        cost = getattr(self._local, 'cost', 0.0)
        budget = getattr(self._local, 'budget', 50000)
        return {
            "tokens_spent": tokens,
            "budget": budget,
            "cost_rub": round(cost, 4),
            # Экономия: 1 программа заменяет 40 часов работы методиста
            "hours_saved": 40 if tokens > 0 else 0 
        }

tracker = TokenTracker()
tracker.reset()