import logging
import re
from typing import Callable, Awaitable, Dict, Any
from aiogram import BaseMiddleware
from aiogram.types import Message
from sqlalchemy import select
from datetime import timedelta, datetime

from app.database.session import get_session
from app.database.models import SpamPattern, ModerationConfig

logger = logging.getLogger(__name__)

# In-memory cache for spam patterns
_spam_patterns_cache = []
_spam_patterns_regex_cache = []

# In-memory cache for moderation configs
_moderation_configs = {}

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


async def load_moderation_configs():
    """
    Loads moderation configs from the database into the in-memory cache.
    """
    global _moderation_configs
    _moderation_configs = {}

    async_session = get_session()
    async with async_session() as session:
        configs_res = await session.execute(select(ModerationConfig))
        configs = configs_res.scalars().all()
        for config in configs:
            _moderation_configs[config.chat_id] = config
    logger.info(f"Loaded {len(_moderation_configs)} moderation configs.")


def get_moderation_config(chat_id: int) -> ModerationConfig:
    """
    Gets moderation config for a specific chat.
    If not found, returns default config.
    """
    if chat_id in _moderation_configs:
        return _moderation_configs[chat_id]

    # Return default config
    from app.database.models import ModerationConfig
    default_config = ModerationConfig(
        chat_id=chat_id,
        mode="normal",
        flood_threshold=5,
        spam_link_protection=True,
        swear_filter=True,
        auto_warn_threshold=3
    )
    return default_config


class SpamFilterMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:

        if not event.text:
            return await handler(event, data)

        # Get moderation config for this chat
        config = get_moderation_config(event.chat.id)

        # Check if moderation is disabled for this mode
        if config.mode == "disabled":
            return await handler(event, data)

        message_text_lower = event.text.lower()

        # Check against literal patterns
        for pattern in _spam_patterns_cache:
            if pattern in message_text_lower:
                return await self.handle_spam(event, pattern, config)

        # Check against regex patterns
        for regex_pattern in _spam_patterns_regex_cache:
            if regex_pattern.search(message_text_lower):
                return await self.handle_spam(event, regex_pattern.pattern, config)

        return await handler(event, data)

    async def handle_spam(self, event: Message, pattern: str, config: ModerationConfig):
        """
        Handles a detected spam message according to the moderation config.
        """
        user_id = event.from_user.id
        chat_id = event.chat.id

        logger.warning(
            f"Spam detected from user {user_id} in chat {chat_id} (pattern: '{pattern}'). Mode: {config.mode}. Message: {event.text}"
        )

        try:
            # Delete spam message based on mode
            if config.mode != "light":
                await event.delete()

            # Apply restrictions based on mode
            if config.mode == "dictatorship":
                # Full restrictions in dictatorship mode
                from aiogram.types import ChatPermissions
                until_date = utc_now() + timedelta(hours=1)
                await event.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=until_date
                )
            elif config.mode == "normal":
                # Normal restrictions
                from aiogram.types import ChatPermissions
from app.utils import utc_now
                until_date = utc_now() + timedelta(minutes=5)
                await event.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user_id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=until_date
                )

            # Notify user about the action
            if config.mode in ["normal", "dictatorship"]:
                response_msg = (
                    f"Обнаружен спам. "
                    f"Пользователь @{event.from_user.username or user_id} "
                )
                if config.mode == "dictatorship":
                    response_msg += "замучен на 1 час."
                else:
                    response_msg += "замучен на 5 минут."

                await event.answer(response_msg)
        except Exception as e:
            logger.error(f"Failed to handle spam message: {e}")
