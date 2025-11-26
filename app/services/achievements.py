from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from aiogram import Bot

from app.database.models import User, Achievement, UserAchievement, GameStat, DuoTeam

async def check_and_award_achievements(
    session: AsyncSession, bot: Bot, user: User, game_stat: GameStat, event_type: str, **kwargs
):
    """
    Checks if a user has earned any new achievements based on their actions and game stats.
    Awards achievements if criteria are met.
    """
    newly_awarded_achievements = []

    # Example achievement: First Grow
    if event_type == "grow" and game_stat.grow_count == 1:
        await award_achievement_by_code(session, bot, user, "first_grow", newly_awarded_achievements)

    # Example achievement: 5 PvP Wins
    if event_type == "pvp_win" and game_stat.pvp_wins == 5:
        await award_achievement_by_code(session, bot, user, "pvp_winner_5", newly_awarded_achievements)
    
    # Example achievement: 1st Casino Jackpot
    if event_type == "casino_jackpot" and game_stat.casino_jackpots == 1:
        await award_achievement_by_code(session, bot, user, "casino_jackpot_1", newly_awarded_achievements)

    return newly_awarded_achievements


async def award_achievement_by_code(
    session: AsyncSession, bot: Bot, user: User, achievement_code: str, newly_awarded_achievements: list
):
    """
    Awards an achievement to a user by its code, if not already awarded.
    """
    achievement = await session.execute(
        select(Achievement).filter_by(code=achievement_code)
    )
    achievement = achievement.scalar_one_or_none()

    if not achievement:
        # Log or handle missing achievement definition
        print(f"Achievement with code {achievement_code} not found.")
        return

    user_achievement = await session.execute(
        select(UserAchievement)
        .filter_by(user_id=user.id, achievement_id=achievement.id)
    )
    user_achievement = user_achievement.scalar_one_or_none()

    if not user_achievement:
        new_user_achievement = UserAchievement(
            user_id=user.id, achievement_id=achievement.id
        )
        session.add(new_user_achievement)
        await session.commit()
        newly_awarded_achievements.append(achievement)
        print(f"Achievement '{achievement.name}' awarded to user {user.tg_user_id}")

        # Notify duo partner
        duo_res = await session.execute(
            select(DuoTeam)
            .filter(or_(DuoTeam.user1_id == user.id, DuoTeam.user2_id == user.id))
            .options(joinedload(DuoTeam.user1), joinedload(DuoTeam.user2))
        )
        duo_team = duo_res.scalars().first()

        if duo_team:
            partner = duo_team.user1 if duo_team.user2.id == user.id else duo_team.user2
            try:
                await bot.send_message(
                    chat_id=partner.tg_user_id,
                    text=f"🤝 Ваш партнер {user.username or user.first_name} получил новое достижение: {achievement.name}!"
                )
            except Exception as e:
                logger.error(f"Failed to notify duo partner {partner.tg_user_id}: {e}")
    else:
        print(f"Achievement '{achievement.name}' already awarded to user {user.tg_user_id}")

