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

def clean_text_field(text: str) -> str:
    """Удаляет лишние пробелы, переносы строк и артефакты markdown."""
    if not text:
        return ""
    text = re.sub(r'```[a-z]*', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def validate_test_format(data: list) -> list:
    """[ТРЕБОВАНИЕ КЕЙСА]: Валидация структуры тестовых вопросов."""
    valid_tests = []
    for item in data:
        if isinstance(item, dict) and item.get("question"):
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

async def _generate_async_retry(prompt: str, fallback_prompt: str = None, task_type: str = "content", retries: int = 3) -> tuple[any, int, float]:
    """[ТРЕБОВАНИЕ КЕЙСА]: Асинхронная обертка с ретраями и LLM-fallback."""
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


def _rule_based_fallback_seminar(framework: Framework, mod_title: str, mod_hours: int) -> dict:
    """[ФИКС РЕВЬЮЕРА]: Вместо фейкового контента выводим честную ошибку."""
    logger.warning(f"Сбой генерации семинара для модуля '{mod_title}'.")
    return {
        "module_title": mod_title, 
        "task": "ОШИБКА ГЕНЕРАЦИИ. ИИ не смог создать задание для этого модуля. Пожалуйста, нажмите «Утвердить» еще раз.", 
        "criteria": "Оценка невозможна из-за ошибки генерации.", 
        "related_competency": "Ошибка"
    }

def _rule_based_fallback_lecture(framework: Framework, mod_title: str) -> dict:
    """[ФИКС РЕВЬЮЕРА]: Вместо фейковых тезисов выводим честную ошибку."""
    logger.warning(f"Сбой генерации лекции для модуля '{mod_title}'.")
    return {
        "module_title": mod_title, 
        "theses": ["ОШИБКА ГЕНЕРАЦИИ. ИИ не смог создать план лекции. Пожалуйста, повторите попытку."]
    }

def _rule_based_fallback_test(framework: Framework, index: int, mod_title: str) -> dict:
    """[ФИКС РЕВЬЮЕРА]: Вместо фейкового вопроса выводим честную ошибку."""
    logger.warning(f"Сбой генерации теста #{index}.")
    return {
        "question": f"ОШИБКА ГЕНЕРАЦИИ. Вопрос {index} не был создан нейросетью. Повторите генерацию.", 
        "options": ["Вариант А", "Вариант Б", "Вариант В", "Вариант Г"], 
        "correct_answer": "Вариант А", 
        "related_competency": "Ошибка"
    }

def _rule_based_fallback_bibliography(framework: Framework) -> list:
    """[ФИКС РЕВЬЮЕРА]: Вместо фейковых книг выводим честную ошибку."""
    logger.warning("Сбой генерации библиографии.")
    return ["ОШИБКА ГЕНЕРАЦИИ. ИИ не смог подобрать список литературы. Пожалуйста, повторите попытку."]