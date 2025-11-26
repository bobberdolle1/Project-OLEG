import logging
from typing import Callable, Awaitable, Dict, Any
from aiogram import BaseMiddleware
from aiogram.types import Message
from datetime import timedelta

from app.database.session import get_session
from app.services.toxicity_analyzer import analyze_toxicity
from app.config import settings

logger = logging.getLogger(__name__)

# This would be better in settings
TOXICITY_THRESHOLD = 75 

class ToxicityFilterMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        
        if not event.text or not settings.toxicity_analysis_enabled:
            return await handler(event, data)

        async_session = get_session()
        async with async_session() as session:
            toxicity_score = await analyze_toxicity(session, event.text)

        if toxicity_score > settings.toxicity_threshold:
            return await self.handle_toxic_message(event, toxicity_score)
        
        return await handler(event, data)

    async def handle_toxic_message(self, event: Message, score: int):
        """
        Handles a detected toxic message.
        """
        user_id = event.from_user.id
        chat_id = event.chat.id
        
        logger.warning(
            f"Toxic message detected from user {user_id} in chat {chat_id} (score: {score}). Message: {event.text}"
        )

        try:
            # Delete toxic message
            await event.delete()
            
            # Mute user for a configurable period (e.g., 2 minutes)
            await event.chat.restrict(
                user_id=user_id,
                permissions={}, # No permissions = mute
                until_date=timedelta(minutes=2)
            )

            # Notify user about the mute
            await event.answer(
                f"Обнаружено токсичное сообщение (уровень: {score}), "
                f"пользователь @{event.from_user.username or user_id} замучен на 2 минуты."
            )
        except Exception as e:
            logger.error(f"Failed to handle toxic message: {e}")
