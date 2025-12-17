"""
Web Search Trigger Detection.

Определяет, когда нужен веб-поиск для ответа на вопрос пользователя.

**Feature: oleg-personality-improvements, Property 1: Search keywords trigger web search**
**Validates: Requirements 1.3**
"""

import logging

logger = logging.getLogger(__name__)

# Ключевые слова для автоматического триггера веб-поиска
WEB_SEARCH_TRIGGER_KEYWORDS = [
    # Релизы и новости
    "вышла", "вышел", "вышло", "релиз", "релизнул", "выходит", "выйдет", "когда выйдет",
    "анонс", "анонсировали", "новости", "что нового", "последние новости",
    # Цены и покупки
    "сколько стоит", "цена", "ценник", "где купить", "где заказать",
    # Характеристики и сравнения
    "характеристики", "спеки", "specs", "benchmark", "бенчмарк", "тест",
    # Актуальная информация
    "сейчас", "на данный момент", "актуальн", "свежи", "последн",
    # Версии и обновления
    "версия", "обновление", "патч", "апдейт", "update",
    # Архитектура и поколения железа — ВАЖНО для фактчекинга
    "архитектур", "поколени", "какого года", "год выпуска", "когда вышл",
    "kepler", "maxwell", "pascal", "turing", "ampere", "ada", "lovelace",
    "zen", "zen2", "zen3", "zen4", "zen5", "skylake", "alder", "raptor",
    # Модели видеокарт (триггер на номера)
    "gtx", "rtx", "rx ", "radeon", "geforce",
    # Вопросы про факты — когда человек сомневается или уточняет
    "это правда", "точно ли", "уверен", "проверь", "а не", "разве",
    "какой там", "какая там", "что там", "сколько там",
]


import re

# Паттерны для номеров видеокарт (780M, 4070, 3060 Ti, RX 7900 и т.д.)
GPU_MODEL_PATTERNS = [
    r'\b\d{3,4}m\b',  # 780M, 680M (мобильные/iGPU)
    r'\b\d{4}\b',  # 4070, 3060, 7900 (дискретные)
    r'\b\d{3,4}\s*ti\b',  # 3060 Ti, 4070 Ti
    r'\brx\s*\d{4}\b',  # RX 7900, RX 6800
    r'\bradeon\s*\d{3}m?\b',  # Radeon 780M, Radeon 680M (AMD iGPU)
    r'\bi\d-\d{4,5}\b',  # i5-12400, i7-13700
    r'\bryzen\s*\d\s*\d{4}\b',  # Ryzen 5 5600, Ryzen 7 7800
    r'\brdna\s*\d\b',  # RDNA 3, RDNA 2
]


def should_trigger_web_search(text: str) -> bool:
    """
    Определяет, нужен ли веб-поиск для ответа на вопрос.
    
    Триггерит поиск если текст содержит:
    - Ключевые слова о релизах, ценах, характеристиках
    - Номера моделей видеокарт/процессоров (780M, 4070, i7-13700)
    
    Args:
        text: Текст сообщения пользователя
        
    Returns:
        True если нужен веб-поиск
        
    **Validates: Requirements 1.3**
    """
    if not text:
        return False
    
    text_lower = text.lower()
    
    # Проверяем ключевые слова
    for keyword in WEB_SEARCH_TRIGGER_KEYWORDS:
        if keyword in text_lower:
            logger.debug(f"Web search triggered by keyword: '{keyword}' in text: '{text[:50]}...'")
            return True
    
    # Проверяем паттерны номеров моделей железа
    for pattern in GPU_MODEL_PATTERNS:
        if re.search(pattern, text_lower):
            logger.debug(f"Web search triggered by GPU/CPU model pattern in text: '{text[:50]}...'")
            return True
    
    return False
