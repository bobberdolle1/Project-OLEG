import logging
import json
from typing import Callable, Awaitable, Dict, Any
from aiogram import BaseMiddleware
from aiogram.types import Message
from sqlalchemy import select
from datetime import timedelta

from app.database.session import get_session
from app.database.models import ToxicityConfig, ToxicityLog, User
from app.services.ollama_client import analyze_toxicity

logger = logging.getLogger(__name__)

class ToxicityAnalysisMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        
        if not event.text:
            return await handler(event, data)

        async_session = get_session()
        async with async_session() as session:
            config_res = await session.execute(
                select(ToxicityConfig).filter_by(chat_id=event.chat.id)
            )
            config = config_res.scalars().first()

            if not config or not config.is_enabled:
                return await handler(event, data)

            try:
                toxicity_result = await analyze_toxicity(event.text)
                if toxicity_result and toxicity_result.get("is_toxic") and toxicity_result.get("score", 0) >= config.threshold:
                    await self.handle_toxic_message(event, config, toxicity_result)
                    return # Stop further processing
            except Exception as e:
                logger.error(f"Error during toxicity analysis: {e}")
        
        return await handler(event, data)

    async def handle_toxic_message(self, event: Message, config: ToxicityConfig, result: dict):
        user_id = event.from_user.id
        chat_id = event.chat.id
        
        logger.warning(
            f"Toxic message detected from user {user_id} in chat {chat_id} (score: {result.get('score')}, category: {result.get('category')}). Message: {event.text}"
        )
        
        async_session = get_session()
        async with async_session() as session:
            # Log the toxic message
            log_entry = ToxicityLog(
                chat_id=chat_id,
                user_id=user_id,
                message_text=event.text,
                score=result.get("score", 0),
                category=result.get("category", "unknown"),
                action_taken=config.action
            )
            session.add(log_entry)
            
            try:
                if config.action == "delete":
                    await event.delete()
                    await event.answer(f"Обнаружено токсичное сообщение от @{event.from_user.username or user_id}, сообщение удалено.")
                elif config.action == "mute":
                    await event.delete()
                    await event.chat.restrict(
                        user_id=user_id,
                        permissions={}, # No permissions = mute
                        until_date=timedelta(minutes=config.mute_duration)
                    )
                    await event.answer(
                        f"Обнаружено токсичное сообщение от @{event.from_user.username or user_id}. "
                        f"Пользователь замучен на {config.mute_duration} минут."
                    )
                elif config.action == "warn":
                    await event.reply(
                        f"@{event.from_user.username or user_id}, ваше сообщение было сочтено токсичным. Пожалуйста, будьте вежливы."
                    )
                await session.commit()
            except Exception as e:
                logger.error(f"Failed to handle toxic message: {e}")
                await session.rollback()
