
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

# Копируем исходники и собираем
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

# [ТРЕБОВАНИЕ КЕЙСА]: Установка curl для HEALTHCHECK и системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# [ТРЕБОВАНИЕ КЕЙСА]: Создание безопасного non-root пользователя
RUN adduser --disabled-password --gecos '' appuser

# Установка Python-зависимостей
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода бэкенда
COPY backend/ ./backend

# Копирование собранного фронтенда из первого этапа
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Передаем права на папку новому пользователю
RUN chown -R appuser:appuser /app

# Переключаемся на безопасного пользователя
USER appuser

WORKDIR /app/backend
EXPOSE 8000

# [ТРЕБОВАНИЕ КЕЙСА]: HEALTHCHECK для автоматического мониторинга состояния
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Запуск
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]