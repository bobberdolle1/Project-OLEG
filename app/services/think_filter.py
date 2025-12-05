"""
Think Tag Filter - фильтр для удаления thinking-тегов из LLM ответов.

Удаляет теги <think>...</think> из ответов моделей типа DeepSeek,
которые используют эти теги для внутренних рассуждений.
"""

import re
from typing import Optional


class ThinkTagFilter:
    """Фильтр для удаления thinking-тегов из LLM ответов."""
    
    # Regex pattern для удаления <think>...</think> тегов
    # Флаги: DOTALL - точка матчит переносы строк, IGNORECASE - регистронезависимо
    THINK_PATTERN = re.compile(r'<think>.*?</think>', re.DOTALL | re.IGNORECASE)
    
    # Паттерн для незакрытых тегов (malformed) - <think> без </think>
    UNCLOSED_THINK_PATTERN = re.compile(r'<think>.*$', re.DOTALL | re.IGNORECASE)
    
    # Паттерн для незакрытых тегов в начале - </think> без <think>
    UNOPENED_THINK_PATTERN = re.compile(r'^.*?</think>', re.DOTALL | re.IGNORECASE)
    
    DEFAULT_FALLBACK = "Олег завис. Перезагружаюсь..."
    
    def __init__(self, fallback_message: Optional[str] = None):
        """
        Инициализация фильтра.
        
        Args:
            fallback_message: Сообщение для возврата если результат пустой
        """
        self.fallback_message = fallback_message or self.DEFAULT_FALLBACK
    
    def filter(self, text: str) -> str:
        """
        Удаляет все think-теги из текста.
        
        Args:
            text: Исходный текст с возможными think-тегами
            
        Returns:
            Очищенный текст без think-тегов или fallback если результат пустой
        """
        if not text:
            return self.fallback_message
        
        # Шаг 1: Удаляем все закрытые <think>...</think> теги
        result = self.THINK_PATTERN.sub('', text)
        
        # Шаг 2: Удаляем незакрытые теги (malformed) - <think> без </think>
        result = self.UNCLOSED_THINK_PATTERN.sub('', result)
        
        # Шаг 3: Удаляем незакрытые теги в начале - </think> без <think>
        result = self.UNOPENED_THINK_PATTERN.sub('', result)
        
        # Очищаем лишние пробелы и переносы строк
        result = result.strip()
        
        # Убираем множественные пробелы/переносы, оставшиеся после удаления тегов
        result = re.sub(r'\n{3,}', '\n\n', result)
        result = re.sub(r' {2,}', ' ', result)
        
        # Если результат пустой - возвращаем fallback
        if not result:
            return self.fallback_message
        
        return result
    
    def is_empty_after_filter(self, text: str) -> bool:
        """
        Проверяет, останется ли текст после фильтрации.
        
        Args:
            text: Текст для проверки
            
        Returns:
            True если после фильтрации текст будет пустым
        """
        if not text:
            return True
        
        # Применяем те же паттерны что и в filter()
        result = self.THINK_PATTERN.sub('', text)
        result = self.UNCLOSED_THINK_PATTERN.sub('', result)
        result = self.UNOPENED_THINK_PATTERN.sub('', result)
        
        return not result.strip()
    
    def contains_think_tags(self, text: str) -> bool:
        """
        Проверяет, содержит ли текст think-теги.
        
        Args:
            text: Текст для проверки
            
        Returns:
            True если текст содержит think-теги
        """
        if not text:
            return False
        
        text_lower = text.lower()
        return '<think>' in text_lower or '</think>' in text_lower


# Глобальный экземпляр фильтра для удобства использования
think_filter = ThinkTagFilter()
