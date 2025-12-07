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

        quests_list = ["📜 <b>Ваши текущие квесты:</b>\n"]
        for uq in user_quests:
            status = "✅ Выполнено" if uq.completed_at else f"➡️ {uq.progress}/{uq.quest.target_value}"
            quests_list.append(
                f"• <b>{uq.quest.name}</b> — {uq.quest.description}\n  {status}"
            )
        
        await msg.reply("\n".join(quests_list), parse_mode="HTML")


@router.message(Command("quest_progress"))
async def cmd_quest_progress(msg: Message):
    """
    Handles the /quest_progress command, displaying detailed progress on quests.
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

        progress_list = ["📊 <b>Прогресс по квестам:</b>\n"]
        for uq in user_quests:
            if uq.completed_at:
                status = "✅ Выполнено!"
                progress_bar = "██████████"
            else:
                progress_pct = min(100, int((uq.progress / uq.quest.target_value) * 100))
                filled = progress_pct // 10
                progress_bar = "█" * filled + "░" * (10 - filled)
                status = f"{uq.progress}/{uq.quest.target_value} ({progress_pct}%)"
            
            reward_text = f"🎁 {uq.quest.reward_amount} {uq.quest.reward_type}"
            progress_list.append(
                f"• <b>{uq.quest.name}</b>\n"
                f"  [{progress_bar}] {status}\n"
                f"  {reward_text}"
            )
        
        await msg.reply("\n".join(progress_list), parse_mode="HTML")