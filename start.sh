#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Запуск ACR AI Agent на виртуальной машине...${NC}"

# 1. Переходим в папку проекта
cd ~/project || { echo -e "${RED}Папка ~/project не найдена${NC}"; exit 1; }

# 2. Обновляем код из Gitea (на ВМ origin - это Gitea)
echo "Обновление кода..."
git fetch origin
git reset --hard origin/main

# 3. Пересобираем фронтенд (чтобы интерфейс был актуальным)
echo "Сборка фронтенда..."
cd frontend
npm run build || { echo -e "${RED}Ошибка сборки фронтенда${NC}"; exit 1; }

# 4. Переходим в бэкенд и устанавливаем зависимости
echo "Установка Python-зависимостей..."
cd ../backend
pip install -r requirements.txt --quiet

# 5. Очищаем старую базу данных (чтобы применились новые миграции)
echo "Очистка старой базы данных..."
rm -f sessions.db

# 6. Убиваем старые процессы uvicorn
echo "Перезапуск сервера..."
pkill -9 -f uvicorn || true

# 7. Запускаем сервер в фоне
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &

# 8. Ждем пару секунд и проверяем здоровье
sleep 3
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo -e "${GREEN}Сервер успешно запущен на порту 8000!${NC}"
    echo "Логи: tail -f ~/project/backend/uvicorn.log"
else
    echo -e "${RED}Ошибка запуска сервера. Проверьте логи:${NC}"
    tail -n 20 uvicorn.log
fi