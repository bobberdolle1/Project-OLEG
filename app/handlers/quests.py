import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select, and_
from sqlalchemy.orm import joinedload
from datetime import datetime

from app.database.session import get_session
from app.database.models import User, Quest, UserQuest
from app.handlers.games import ensure_user

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("quests"))
async def cmd_quests(msg: Message):
    """
    Handles the /quests command, displaying a user's assigned daily quests.
    """
    async_session = get_session()
    user = await ensure_user(msg.from_user)

    async with async_session() as session:
        user_quests_res = await session.execute(
            select(UserQuest)
            .filter_by(user_id=user.id)
            .options(joinedload(UserQuest.quest))
        )
        user_quests = user_quests_res.scalars().all()

        if not user_quests:
            return await msg.reply("У вас пока нет активных квестов.")

        quests_list = ["Ваши текущие квесты:"]
        for uq in user_quests:
            status = "✅ Выполнено" if uq.completed_at else f"➡️ Прогресс: {uq.progress}/{uq.quest.target_value}"
            quests_list.append(
                f"- {uq.quest.name} ({uq.quest.description}) - {status}"
            )
        
        await msg.reply("\n".join(quests_list))