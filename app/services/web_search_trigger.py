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


def should_trigger_web_search(text: str) -> bool:
    """
    Определяет, нужен ли веб-поиск для ответа на вопрос.
    
    Триггерит поиск если текст содержит ключевые слова о:
    - Релизах и новостях
    - Ценах и покупках  
    - Характеристиках и сравнениях
    - Актуальной информации
    
    Args:
        text: Текст сообщения пользователя
        
    Returns:
        True если нужен веб-поиск
        
    **Validates: Requirements 1.3**
    """
    if not text:
        return False
    
    text_lower = text.lower()
    
    for keyword in WEB_SEARCH_TRIGGER_KEYWORDS:
        if keyword in text_lower:
            logger.debug(f"Web search triggered by keyword: '{keyword}' in text: '{text[:50]}...'")
            return True
    
    return False
