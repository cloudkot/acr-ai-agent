#!/bin/bash
# Скрипт для запуска бэкенда на ВМ
cd backend
pkill -9 -f uvicorn || true
rm -f sessions.db
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &
echo "🚀 Сервер запущен на порту 8000"