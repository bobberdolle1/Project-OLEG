"""
Feature Toggle Middleware.

Позволяет владельцу бота включать/выключать функции через панель /owner.
"""

import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

logger = logging.getLogger(__name__)


class FeatureToggleMiddleware(BaseMiddleware):
    """
    Middleware для проверки состояния функций.
    
    Проверяет, включена ли функция перед обработкой сообщения.
    Если функция выключена, сообщение игнорируется.
    """
    
    # Маппинг команд/типов сообщений на функции
    COMMAND_FEATURES = {
        "/say": "voice_recognition",
        "/tldr": "summarizer",
        "/summary": "summarizer",
        "/dice": "games",
        "/slots": "games",
        "/roulette": "games",
        "/blackjack": "games",
        "/bj": "games",
        "/duel": "games",
        "/quote": "quotes",
        "/цитата": "quotes",
        "/q": "quotes",
        "/qs": "quotes",
        "/qd": "quotes",
    }
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        """Проверить состояние функции перед обработкой."""
        # Импортируем здесь чтобы избежать циклических импортов
        from app.handlers.owner_panel import is_feature_enabled
        
        # Проверяем команды
        if event.text and event.text.startswith("/"):
            command = event.text.split()[0].split("@")[0].lower()
            
            feature = self.COMMAND_FEATURES.get(command)
            if feature and not is_feature_enabled(feature):
                logger.debug(f"Feature '{feature}' is disabled, ignoring command {command}")
                return  # Игнорируем команду
        
        # Проверяем голосовые сообщения
        if event.voice and not is_feature_enabled("voice_recognition"):
            logger.debug("Voice recognition is disabled, ignoring voice message")
            return
        
        # Проверяем фото (vision)
        if event.photo and not is_feature_enabled("vision"):
            logger.debug("Vision is disabled, ignoring photo")
            return
        
        return await handler(event, data)


def check_feature(feature: str) -> bool:
    """
    Проверить, включена ли функция.
    
    Удобная функция для использования в хендлерах.
    
    Args:
        feature: Название функции
        
    Returns:
        True если функция включена
    """
    from app.handlers.owner_panel import is_feature_enabled
    return is_feature_enabled(feature)
