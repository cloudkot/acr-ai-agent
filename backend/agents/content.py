import re
import json
import asyncio
from cloud import ask_llm, MODEL_FAST
from schemas import Framework
from utils.json_parser import extract_json_from_text
from config import config
from logger import logger

# [АРХИТЕКТУРА]: Глобальный семафор для ограничения параллельных запросов к LLM
MAX_CONCURRENT_REQUESTS = config.MAX_CONCURRENT_REQUESTS
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)


def clean_text_field(text: any) -> str:
    """
    [ФИКС]: Безопасно конвертирует ЛЮБОЙ тип данных в строку.
    Защищает от падения, если LLM вернет вместо строки объект или число.
    """
    if not text:
        return ""
    if not isinstance(text, str):
        text = str(text)
    text = re.sub(r'```[a-z]*', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def validate_test_format(data: list) -> list:
    """[ТРЕБОВАНИЕ КЕЙСА]: Валидация структуры тестовых вопросов."""
    valid_tests = []
    if not isinstance(data, list):
        return valid_tests

    for item in data:
        if isinstance(item, dict) and item.get("question"):
            options = item.get("options", [])
            if not isinstance(options, list):
                options = [str(options)]
            
            correct = clean_text_field(item.get("correct_answer", ""))
            if options and correct in options:
                valid_tests.append({
                    "question": clean_text_field(item["question"]),
                    "options": [clean_text_field(opt) for opt in options],
                    "correct_answer": correct,
                    "related_competency": clean_text_field(item.get("related_competency", "Общая")),
                    "category": clean_text_field(item.get("category", "Общая"))
                })
    return valid_tests

def validate_seminar_format(data: list) -> list:
    """[ТРЕБОВАНИЕ КЕЙСА]: Валидация структуры семинаров."""
    valid_seminars = []
    if not isinstance(data, list):
        return valid_seminars

    for item in data:
        if isinstance(item, dict) and item.get("task") and item.get("task") != "None":
            valid_seminars.append({
                "module_title": clean_text_field(item.get("module_title", "")),
                "task": clean_text_field(item.get("task")),
                "criteria": clean_text_field(item.get("criteria", "Критерии не указаны")),
                "related_competency": clean_text_field(item.get("related_competency", "Общая"))
            })
    return valid_seminars



def _rule_based_fallback_seminar(framework: Framework, mod_title: str, mod_hours: int) -> dict:
    logger.warning(f"Сбой генерации семинара для модуля '{mod_title}'.")
    return {
        "module_title": mod_title, 
        "task": "ОШИБКА ГЕНЕРАЦИИ. ИИ не смог создать задание для этого модуля. Пожалуйста, нажмите «Утвердить» еще раз.", 
        "criteria": "Оценка невозможна из-за ошибки генерации.", 
        "related_competency": "Ошибка"
    }

def _rule_based_fallback_lecture(framework: Framework, mod_title: str) -> dict:
    logger.warning(f"Сбой генерации лекции для модуля '{mod_title}'.")
    return {
        "module_title": mod_title, 
        "theses": ["ОШИБКА ГЕНЕРАЦИИ. ИИ не смог создать план лекции. Пожалуйста, повторите попытку."]
    }

def _rule_based_fallback_test(framework: Framework, index: int, mod_title: str) -> dict:
    logger.warning(f"Сбой генерации теста #{index}.")
    return {
        "question": f"ОШИБКА ГЕНЕРАЦИИ. Вопрос {index} не был создан нейросетью. Повторите генерацию.", 
        "options": ["Вариант А", "Вариант Б", "Вариант В", "Вариант Г"], 
        "correct_answer": "Вариант А", 
        "related_competency": "Ошибка",
        "category": "Ошибка"
    }

def _rule_based_fallback_bibliography(framework: Framework) -> list:
    logger.warning("Сбой генерации библиографии.")
    return ["ОШИБКА ГЕНЕРАЦИИ. ИИ не смог подобрать список литературы. Пожалуйста, повторите попытку."]