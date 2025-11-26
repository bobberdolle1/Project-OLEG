import logging
import re
from typing import Callable, Awaitable, Dict, Any
from aiogram import BaseMiddleware
from aiogram.types import Message
from sqlalchemy import select
from datetime import timedelta

from app.database.session import get_session
from app.database.models import SpamPattern

logger = logging.getLogger(__name__)

# In-memory cache for spam patterns
_spam_patterns_cache = []
_spam_patterns_regex_cache = []

async def load_spam_patterns():
    """
    Loads active spam patterns from the database into the in-memory cache.
    """
    global _spam_patterns_cache, _spam_patterns_regex_cache
    _spam_patterns_cache = []
    _spam_patterns_regex_cache = []

    async_session = get_session()
    async with async_session() as session:
        patterns_res = await session.execute(
            select(SpamPattern).filter_by(is_active=True)
        )
        patterns = patterns_res.scalars().all()
        for p in patterns:
            if p.is_regex:
                _spam_patterns_regex_cache.append(re.compile(p.pattern))
            else:
                _spam_patterns_cache.append(p.pattern)
    logger.info(f"Loaded {len(_spam_patterns_cache)} literal and {len(_spam_patterns_regex_cache)} regex spam patterns.")

class SpamFilterMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        
        if not event.text:
            return await handler(event, data)

        message_text_lower = event.text.lower()
        
        # Check against literal patterns
        for pattern in _spam_patterns_cache:
            if pattern in message_text_lower:
                return await self.handle_spam(event, pattern)
        
        # Check against regex patterns
        for regex_pattern in _spam_patterns_regex_cache:
            if regex_pattern.search(message_text_lower):
                return await self.handle_spam(event, regex_pattern.pattern)
        
        return await handler(event, data)

    async def handle_spam(self, event: Message, pattern: str):
        """
        Handles a detected spam message.
        """
        user_id = event.from_user.id
        chat_id = event.chat.id
        
        logger.warning(
            f"Spam detected from user {user_id} in chat {chat_id} (pattern: '{pattern}'). Message: {event.text}"
        )

        try:
            # Delete spam message
            await event.delete()
            
            # Mute user for a configurable period (e.g., 5 minutes)
            await event.chat.restrict(
                user_id=user_id,
                permissions={}, # No permissions = mute
                until_date=timedelta(minutes=5)
            )

            # Notify user about the mute
            await event.answer(
                f"Обнаружен спам, пользователь @{event.from_user.username or user_id} замучен на 5 минут."
            )
        except Exception as e:
            logger.error(f"Failed to handle spam message: {e}")
