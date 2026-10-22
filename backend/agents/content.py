import json
import re
import asyncio
from cloud import ask_llm, MODEL_FAST
from schemas import Framework
from utils.json_parser import extract_json_from_text
from config import config
from logger import logger

# [АРХИТЕКТУРА]: Глобальный семафор для ограничения параллельных запросов к LLM
MAX_CONCURRENT_REQUESTS = config.MAX_CONCURRENT_REQUESTS
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

# ==========================================
# [УТИЛИТЫ]: Вспомогательные функции для работы с контентом
# ==========================================

def clean_text_field(text: str) -> str:
    """Удаляет лишние пробелы, переносы строк и артефакты markdown."""
    if not text:
        return ""
    # Удаляем возможные markdown-теги
    text = re.sub(r'```[a-z]*', '', text)
    # Заменяем множественные пробелы и переносы на один пробел
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def validate_test_format(data: list) -> list:
    """[ТРЕБОВАНИЕ КЕЙСА]: Валидация структуры тестовых вопросов."""
    valid_tests = []
    for item in data:
        if isinstance(item, dict) and item.get("question"):
            # Проверяем, что есть варианты ответов и правильный ответ
            options = item.get("options", [])
            correct = item.get("correct_answer")
            if options and correct in options:
                valid_tests.append({
                    "question": clean_text_field(item["question"]),
                    "options": [clean_text_field(opt) for opt in options],
                    "correct_answer": clean_text_field(correct),
                    "related_competency": item.get("related_competency", "Общая")
                })
    return valid_tests

def validate_seminar_format(data: list) -> list:
    """[ТРЕБОВАНИЕ КЕЙСА]: Валидация структуры семинаров."""
    valid_seminars = []
    for item in data:
        if isinstance(item, dict) and item.get("task") and item.get("task") != "None":
            valid_seminars.append({
                "module_title": clean_text_field(item.get("module_title", "")),
                "task": clean_text_field(item.get("task")),
                "criteria": clean_text_field(item.get("criteria", "Критерии не указаны")),
                "related_competency": item.get("related_competency", "Общая")
            })
    return valid_seminars

# ==========================================
# [УТИЛИТЫ]: Retry и LLM-Fallback
# ==========================================

async def _generate_async_retry(prompt: str, fallback_prompt: str = None, task_type: str = "content", retries: int = 3) -> tuple[any, int, float]:
    """
    [ТРЕБОВАНИЕ КЕЙСА]: Асинхронная обертка с ретраями и LLM-fallback.
    Используется Исполнителем (executor.py) для каждой подзадачи.
    """
    total_tokens = 0
    total_cost = 0.0
    async with semaphore:
        for attempt in range(retries):
            try:
                raw, tokens, cost = await ask_llm(prompt, task_type, True)
                total_tokens += tokens
                total_cost += cost
                data = extract_json_from_text(raw)
                if not data: raise ValueError("Пустой ответ от LLM")
                return data, total_tokens, total_cost
            except Exception as e:
                logger.warning(f"Ошибка генерации ({attempt+1}/{retries}): {e}")
                if attempt == retries - 1: 
                    # Уровень 1: LLM-Fallback (упрощенный запрос)
                    if fallback_prompt:
                        logger.info("Запуск LLM-fallback (упрощенный запрос)...")
                        try:
                            raw_fb, t_fb, c_fb = await ask_llm(fallback_prompt, MODEL_FAST, True)
                            total_tokens += t_fb
                            total_cost += c_fb
                            data_fb = extract_json_from_text(raw_fb)
                            if data_fb: return data_fb, total_tokens, total_cost
                        except Exception as e_fb:
                            logger.error(f"LLM-fallback тоже упал: {e_fb}")
                    
                    raise RuntimeError(f"Сбой после {retries} попыток: {e}")
                await asyncio.sleep(2)

# ==========================================
# [УРОВЕНЬ 2]: Rule-based Fallback (Алгоритмические заглушки)
# Вызываются из executor.py, если LLM и LLM-fallback не справились
# ==========================================

def _rule_based_fallback_seminar(framework: Framework, mod_title: str, mod_hours: int) -> dict:
    """[ТРЕБОВАНИЕ КЕЙСА]: Умная заглушка для семинара на основе компетенций модуля."""
    comps = [c.name for c in framework.competencies if any(mod_title.lower() in t.lower() for t in c.related_topics)]
    task = f"Разработать практический кейс по модулю '{mod_title}' ({mod_hours} ч.). Отработать навыки: {', '.join(comps) if comps else 'основные инструменты'}."
    return {
        "module_title": mod_title, 
        "task": task, 
        "criteria": "Критерии: 1) Работоспособность; 2) Соответствие ТЗ; 3) Защита.", 
        "related_competency": comps[0] if comps else "Общая"
    }

def _rule_based_fallback_lecture(framework: Framework, mod_title: str) -> dict:
    """[ТРЕБОВАНИЕ КЕЙСА]: Умная заглушка для лекции."""
    title_clean = mod_title.replace("Модуль", "").strip()
    theses = [
        f"Архитектура и основные концепции: {title_clean}",
        f"Обзор инструментов и практик в рамках {title_clean}",
        f"Разбор типичных ошибок и паттернов проектирования",
        f"Практическое применение {title_clean} в реальных проектах"
    ]
    return {"module_title": mod_title, "theses": theses}

def _rule_based_fallback_test(framework: Framework, index: int, mod_title: str) -> dict:
    """[ТРЕБОВАНИЕ КЕЙСА]: Умная заглушка для теста."""
    return {
        "question": f"Какой основной подход используется при работе с {mod_title}?", 
        "options": [f"Применение инструментов {mod_title}", "Ручное конфигурирование", "Отказ от автоматизации", "Использование устаревших методов"], 
        "correct_answer": f"Применение инструментов {mod_title}", 
        "related_competency": framework.competencies[0].name if framework.competencies else "Общая"
    }

def _rule_based_fallback_bibliography(framework: Framework) -> list:
    """[ТРЕБОВАНИЕ КЕЙСА]: Умная заглушка для библиографии."""
    topics = ", ".join([m.title for m in framework.modules[:2]])
    return [
        f"Практическое руководство по {topics}. 2024.", 
        f"Сборник лучших практик. 2023.", 
        f"Архитектура и паттерны проектирования. 2025."
    ]