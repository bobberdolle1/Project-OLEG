"""
Web Search Trigger Detection.

Определяет, когда нужен веб-поиск для ответа на вопрос пользователя.

**Feature: oleg-personality-improvements, Property 1: Search keywords trigger web search**
**Feature: anti-hallucination-v1**
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
    "почём", "за сколько", "бюджет на",
    # Характеристики и сравнения
    "характеристики", "спеки", "specs", "benchmark", "бенчмарк", "тест",
    "сколько памяти", "сколько vram", "какая шина", "какой tdp",
    "сколько ядер", "сколько потоков", "какой сокет",
    # Актуальная информация
    "сейчас", "на данный момент", "актуальн", "свежи", "последн",
    "в 2024", "в 2025", "на сегодня",
    # Версии и обновления
    "версия", "обновление", "патч", "апдейт", "update", "драйвер",
    # Архитектура и поколения железа — ВАЖНО для фактчекинга
    "архитектур", "поколени", "какого года", "год выпуска", "когда вышл",
    "kepler", "maxwell", "pascal", "turing", "ampere", "ada", "lovelace", "blackwell",
    "zen", "zen2", "zen3", "zen4", "zen5", "skylake", "alder", "raptor", "meteor", "arrow",
    "rdna", "rdna2", "rdna3", "rdna 2", "rdna 3",
    # Модели видеокарт (триггер на номера)
    "gtx", "rtx", "rx ", "radeon", "geforce", "arc a",
    # Вопросы про факты — когда человек сомневается или уточняет
    "это правда", "точно ли", "уверен", "проверь", "а не", "разве",
    "какой там", "какая там", "что там", "сколько там",
    "правда что", "верно что", "действительно",
    # Сравнения — часто требуют актуальных данных
    "что лучше", "что выбрать", "vs", "против", "или",
    "сравни", "сравнение", "разница между",
    # Проблемы и баги — нужны актуальные решения
    "не работает", "баг", "глюк", "проблема с", "ошибка",
    "как исправить", "как починить", "фикс",
    # =========================================================================
    # СОФТ И ТЮНИНГ 2025
    # =========================================================================
    # Операционные системы
    "windows 11", "windows 12", "24h2", "25h1", "win11", "win12",
    "bazzite", "nobara", "linux gaming", "steamos",
    # Тюнинг и разгон
    "разгон", "overclock", "андервольт", "undervolt", "undervolting",
    "curve optimizer", "pbo", "pbo2", "co", "кривая",
    "vf curve", "loadline", "ac loadline", "svid offset",
    # Софт для тюнинга
    "msi afterburner", "afterburner", "rtss", "rivatuner",
    "nvidia app", "geforce experience", "gfe",
    "adrenalin", "radeon software",
    "fancontrol", "fan control",
    "winutil", "chris titus", "деблоат",
    # Мониторинг
    "hwinfo", "hwinfo64", "capframex", "frametime",
    "zentimings", "тайминги", "timings",
    "1% low", "0.1% low", "статтер", "фриз", "микрофриз",
    # Стресс-тесты
    "occt", "testmem5", "tm5", "anta777",
    "cinebench", "y-cruncher", "ycruncher",
    "corecycler", "prime95", "стресс-тест", "стресс тест",
    "whea", "whea error",
    # Драйверы
    "ddu", "display driver uninstaller",
    "nvcleanstall", "чистый драйвер",
    # DDR5 тюнинг
    "trefi", "trfc", "вторички", "вторичные тайминги",
    "expo", "xmp", "xmp 3.0",
    # Термины тюнинга
    "троттлинг", "throttling", "vrm", "температура vrm",
    "power limit", "tdp limit", "ecc trap",
    "resize bar", "rebar", "sam", "smart access memory",
    "vbs", "memory integrity", "изоляция ядра",
]


import re

# Паттерны для номеров видеокарт (780M, 4070, 3060 Ti, RX 7900 и т.д.)
GPU_MODEL_PATTERNS = [
    r'\b\d{3,4}m\b',  # 780M, 680M (мобильные/iGPU)
    # Убрали голый \d{4} — слишком много ложных срабатываний
    # Вместо этого ищем конкретные паттерны видеокарт
    r'\b[234]\d{3}\b',  # 2060, 3060, 4070 (NVIDIA RTX 20/30/40)
    r'\b[567]\d{3}\b',  # 5600, 6800, 7900 (AMD RX 5000/6000/7000)
    r'\b\d{3,4}\s*ti\b',  # 3060 Ti, 4070 Ti
    r'\b\d{3,4}\s*super\b',  # 4070 Super, 4080 Super
    r'\brx\s*\d{4}\b',  # RX 7900, RX 6800
    r'\brx\s*\d{4}\s*xt[x]?\b',  # RX 7900 XT, RX 7900 XTX
    r'\bradeon\s*\d{3}m?\b',  # Radeon 780M, Radeon 680M (AMD iGPU)
    r'\bi\d-\d{4,5}[a-z]*\b',  # i5-12400, i7-13700K, i9-14900KS
    r'\bryzen\s*\d\s*\d{4}[a-z]*\b',  # Ryzen 5 5600X, Ryzen 7 7800X3D
    r'\brdna\s*\d\b',  # RDNA 3, RDNA 2
    r'\barc\s*a\d{3}\b',  # Arc A770, Arc A750
    r'\b50[789]0\b',  # 5070, 5080, 5090 (RTX 50 series)
    r'\b90[67]0\b',  # 9060, 9070 (RX 9000 series, RDNA 4)
]


# Исключения — когда НЕ нужен веб-поиск (вопросы про самого бота)
SEARCH_EXCLUSIONS = [
    "твои характеристики", "твоё железо", "твой процессор", "твоя видеокарта",
    "на чём ты работаешь", "на чем ты работаешь", "где ты крутишься",
    "какой ты", "кто ты", "что ты", "расскажи о себе",
    "твои спеки", "твои specs", "твой сервер",
]


# Высокоприоритетные триггеры — ВСЕГДА требуют поиска
HIGH_PRIORITY_TRIGGERS = [
    # Конкретные вопросы о характеристиках
    r'сколько\s+(vram|памяти|ядер|потоков)',
    r'какая\s+(архитектура|шина|частота)',
    r'какой\s+(tdp|техпроцесс|сокет)',
    # Сравнения конкретных моделей
    r'(rtx|rx|arc)\s*\d+.*vs',
    r'(rtx|rx|arc)\s*\d+.*или',
    r'что лучше.*(rtx|rx|arc)',
    # Вопросы о существовании
    r'(есть|существует|вышла?)\s*(rtx|rx)\s*\d+',
    r'(rtx|rx)\s*\d+.*(есть|существует|вышла?)',
]


def should_trigger_web_search(text: str) -> tuple[bool, str]:
    """
    Определяет, нужен ли веб-поиск для ответа на вопрос.
    
    Триггерит поиск если текст содержит:
    - Ключевые слова о релизах, ценах, характеристиках
    - Номера моделей видеокарт/процессоров (780M, 4070, i7-13700)
    - Высокоприоритетные паттерны (сравнения, вопросы о существовании)
    
    НЕ триггерит если:
    - Вопрос про самого бота ("твои характеристики", "на чём ты работаешь")
    
    Args:
        text: Текст сообщения пользователя
        
    Returns:
        Tuple (нужен_поиск: bool, причина: str)
        
    **Validates: Requirements 1.3**
    **Feature: anti-hallucination-v1**
    """
    if not text:
        return False, ""
    
    text_lower = text.lower()
    
    # Сначала проверяем исключения — вопросы про самого бота
    for exclusion in SEARCH_EXCLUSIONS:
        if exclusion in text_lower:
            logger.debug(f"Web search SKIPPED - question about bot: '{exclusion}' in text: '{text[:50]}...'")
            return False, "question_about_bot"
    
    # Высокоприоритетные паттерны — проверяем первыми
    for pattern in HIGH_PRIORITY_TRIGGERS:
        if re.search(pattern, text_lower):
            logger.info(f"Web search triggered by HIGH PRIORITY pattern: '{pattern}' in text: '{text[:50]}...'")
            return True, f"high_priority:{pattern}"
    
    # Проверяем ключевые слова
    for keyword in WEB_SEARCH_TRIGGER_KEYWORDS:
        if keyword in text_lower:
            logger.debug(f"Web search triggered by keyword: '{keyword}' in text: '{text[:50]}...'")
            return True, f"keyword:{keyword}"
    
    # Проверяем паттерны номеров моделей железа
    for pattern in GPU_MODEL_PATTERNS:
        if re.search(pattern, text_lower):
            logger.debug(f"Web search triggered by GPU/CPU model pattern in text: '{text[:50]}...'")
            return True, f"model_pattern:{pattern}"
    
    return False, ""


def should_trigger_web_search_simple(text: str) -> bool:
    """
    Упрощённая версия для обратной совместимости.
    
    Returns:
        True если нужен веб-поиск
    """
    result, _ = should_trigger_web_search(text)
    return result
