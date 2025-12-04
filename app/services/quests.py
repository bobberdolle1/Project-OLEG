from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime

from app.database.models import User, Quest, UserQuest, Wallet, GameStat
from app.utils import utc_now

async def check_and_update_quests(
    session: AsyncSession, user: User, event_type: str, **kwargs
):
    """
    Checks if a user has made progress on any active quests based on the event.
    Updates quest progress and awards rewards if quests are completed.
    """
    updated_quests = []

    # Find active quests for the user that match the event type
    user_quests_res = await session.execute(
        select(UserQuest)
        .filter(
            UserQuest.user_id == user.id,
            UserQuest.completed_at == None
        )
        .options(joinedload(UserQuest.quest))
    )
    user_quests = user_quests_res.scalars().all()

    for user_quest in user_quests:
        quest = user_quest.quest
        if quest.event_type == event_type:
            user_quest.progress += 1
            if user_quest.progress >= quest.target_value:
                user_quest.completed_at = utc_now()
                updated_quests.append(quest)

                # Award reward
                if quest.reward_type == "balance":
                    wallet_res = await session.execute(select(Wallet).filter_by(user_id=user.id))
                    wallet = wallet_res.scalars().first()
                    if wallet:
                        wallet.balance += quest.reward_amount
                elif quest.reward_type == "size_cm":
                    game_stat_res = await session.execute(select(GameStat).filter_by(user_id=user.id))
                    game_stat = game_stat_res.scalars().first()
                    if game_stat:
                        game_stat.size_cm += quest.reward_amount
                # Add more reward types as needed
            session.add(user_quest) # Mark as modified
    
    await session.commit()
    return updated_quests