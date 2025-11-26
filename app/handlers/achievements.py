import logging
from aiogram import Router
from aiogram.types import Message
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from app.database.session import get_session
from app.database.models import User, UserAchievement, Achievement

logger = logging.getLogger(__name__)

router = Router()


@router.message(commands="my_achievements")
async def cmd_my_achievements(msg: Message):
    """
    Handles the /my_achievements command, displaying a user's unlocked achievements.
    """
    async_session = get_session()
    async with async_session() as session:
        user_id = msg.from_user.id
        
        # Load the user and their achievements
        user = await session.execute(
            select(User)
            .filter_by(tg_user_id=user_id)
            .options(joinedload(User.user_achievements).joinedload(UserAchievement.achievement))
        )
        user = user.scalars().first()

        if not user or not user.user_achievements:
            return await msg.reply("У вас пока нет достижений.")

        achievements_list = []
        for ua in user.user_achievements:
            achievements_list.append(f"- {ua.achievement.name} ({ua.achievement.description})")
        
        await msg.reply("Ваши достижения:\n" + "\n".join(achievements_list))


@router.message(commands="achievements_leaderboard")
async def cmd_achievements_leaderboard(msg: Message):
    """
    Displays a leaderboard of users with the most achievements.
    """
    async_session = get_session()
    async with async_session() as session:
        leaderboard_res = await session.execute(
            select(User, func.count(UserAchievement.user_id).label("achievement_count"))
            .join(UserAchievement)
            .group_by(User.id)
            .order_by(func.count(UserAchievement.user_id).desc())
            .limit(10)
        )
        leaderboard = leaderboard_res.all()

        if not leaderboard:
            return await msg.reply("Пока нет достижений для отображения в таблице лидеров.")

        leaderboard_list = ["Топ-10 по достижениям:"]
        for i, (user, count) in enumerate(leaderboard, start=1):
            name = user.username or user.first_name or str(user.tg_user_id)
            leaderboard_list.append(f"{i}. {name}: {count} достижений")
        
        await msg.reply("\n".join(leaderboard_list))