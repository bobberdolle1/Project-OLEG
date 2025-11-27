"""Middleware для проверки черного списка пользователей."""

import logging
from typing import Callable, Awaitable, Dict, Any
from aiogram import BaseMiddleware
from aiogram.types import Message

from app.database.session import get_session
from app.database.models import Blacklist
from sqlalchemy import select


logger = logging.getLogger(__name__)


class BlacklistMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        # Пропускаем служебные сообщения (входы/выходы и т.д.)
        if not event.text and not event.caption and not hasattr(event, 'location'):
            return await handler(event, data)

        # Проверяем, находится ли пользователь в черном списке
        user_id = event.from_user.id
        chat_id = event.chat.id if event.chat else None

        is_blacklisted = await self.is_user_blacklisted(user_id, chat_id)

        if is_blacklisted:
            # Если пользователь в черном списке, игнорируем его сообщения
            logger.info(f"User {user_id} is blacklisted in chat {chat_id}, ignoring message.")
            
            # В личных сообщениях можно послать предупреждение
            if event.chat.type == 'private':
                try:
                    await event.reply("❌ Ты в черном списке. Твои сообщения игнорируются.")
                except Exception:
                    pass  # Игнорируем ошибки при отправке сообщения
            
            return  # Не передаем дальше, игнорируем сообщение

        # Если пользователь не в черном списке, продолжаем обработку
        return await handler(event, data)

    async def is_user_blacklisted(self, user_id: int, chat_id: int) -> bool:
        """
        Проверяет, находится ли пользователь в черном списке.
        
        Args:
            user_id: ID пользователя
            chat_id: ID чата (если None, проверяет глобальный бан)
            
        Returns:
            True, если пользователь в черном списке
        """
        async_session = get_session()
        
        async with async_session() as session:
            # Сначала проверяем локальный бан (для конкретного чата)
            if chat_id:
                local_ban_res = await session.execute(
                    select(Blacklist).filter_by(user_id=user_id, chat_id=chat_id)
                )
                local_ban = local_ban_res.scalars().first()
                if local_ban:
                    return True

            # Затем проверяем глобальный бан (для всех чатов)
            global_ban_res = await session.execute(
                select(Blacklist).filter_by(user_id=user_id, chat_id=None)
            )
            global_ban = global_ban_res.scalars().first()

            return global_ban is not None