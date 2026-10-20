# ЭТАП 1: Сборка React-фронтенда
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

# Копируем манифесты и используем npm ci для детерминированной сборки
COPY frontend/package*.json ./
RUN npm ci

# Копируем исходники и собираем
COPY frontend/ ./
RUN npm run build

# ЭТАП 2: Сборка Python-бэкенда
FROM python:3.11-slim
WORKDIR /app

# [ТРЕБОВАНИЕ КЕЙСА]: Установка curl для HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# [ТРЕБОВАНИЕ КЕЙСА]: Создание безопасного non-root пользователя
RUN adduser --disabled-password --gecos '' appuser

# Установка Python-зависимостей
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода бэкенда и собранного фронтенда
COPY backend/ ./backend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Права для пользователя
RUN chown -R appuser:appuser /app
USER appuser

WORKDIR /app/backend
EXPOSE 8000

# [ТРЕБОВАНИЕ КЕЙСА]: HEALTHCHECK
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]