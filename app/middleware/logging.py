import re
from typing import Any
from aiogram import BaseMiddleware
from aiogram.types import Message
from aiogram import types
from datetime import datetime

from app.database.session import get_session
from app.database.models import MessageLog, User
from sqlalchemy import select, update
from app.utils import utc_now


LINK_RE = re.compile(r"https?:\/\/\S+", re.IGNORECASE)


class MessageLoggerMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data: dict[str, Any]):
        if isinstance(event, types.Message) and event.chat:
            text = event.text or event.caption or ""
            links = LINK_RE.findall(text) if text else []
            async_session = get_session()
            async with async_session() as session:
                # upsert user by tg_user_id
                res = await session.execute(select(User).where(User.tg_user_id == event.from_user.id))
                user = res.scalars().first()
                if not user:
                    user = User(
                        tg_user_id=event.from_user.id,
                        username=event.from_user.username,
                        first_name=event.from_user.first_name,
                        last_name=event.from_user.last_name,
                    )
                    session.add(user)
                else:
                    # best-effort update username
                    await session.execute(
                        update(User)
                        .where(User.tg_user_id == event.from_user.id)
                        .values(username=event.from_user.username)
                    )

                ml = MessageLog(
                    chat_id=event.chat.id,
                    message_id=event.message_id,
                    user_id=event.from_user.id,
                    username=event.from_user.username,
                    text=text,
                    has_link=bool(links),
                    links="\n".join(links) if links else None,
                    created_at=utc_now(),
                )
                session.add(ml)
                try:
                    await session.commit()
                except Exception:
                    await session.rollback()
        return await handler(event, data)
