"""
Quest Service - ежедневные квесты.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Quest, UserQuest, User, UserBalance
from app.database.session import get_session
from app.utils import utc_now

logger = logging.getLogger(__name__)

# Определения квестов
QUESTS = [
    # Сообщения
    {"code": "send_messages_5", "name": "📝 Общительный", "description": "Написать 5 сообщений", 
     "reward_type": "coins", "reward_amount": 50, "event_type": "message", "target_value": 5},
    {"code": "send_messages_20", "name": "💬 Болтун дня", "description": "Написать 20 сообщений",
     "reward_type": "coins", "reward_amount": 150, "event_type": "message", "target_value": 20},
    
    # Игры
    {"code": "play_games_3", "name": "🎮 Игрок", "description": "Сыграть 3 игры",
     "reward_type": "coins", "reward_amount": 100, "event_type": "game", "target_value": 3},
    {"code": "win_pvp_1", "name": "⚔️ Победитель", "description": "Выиграть PvP",
     "reward_type": "coins", "reward_amount": 200, "event_type": "pvp_win", "target_value": 1},
    {"code": "win_pvp_3", "name": "🏆 Доминатор", "description": "Выиграть 3 PvP",
     "reward_type": "coins", "reward_amount": 500, "event_type": "pvp_win", "target_value": 3},
    
    # Рыбалка
    {"code": "catch_fish_3", "name": "🎣 Рыбак дня", "description": "Поймать 3 рыбы",
     "reward_type": "coins", "reward_amount": 100, "event_type": "fish", "target_value": 3},
    {"code": "catch_fish_10", "name": "🐟 Мастер удочки", "description": "Поймать 10 рыб",
     "reward_type": "coins", "reward_amount": 300, "event_type": "fish", "target_value": 10},
    
    # Казино
    {"code": "casino_plays_5", "name": "🎰 Азартный", "description": "Сыграть 5 раз в казино",
     "reward_type": "coins", "reward_amount": 100, "event_type": "casino", "target_value": 5},
    
    # Цитаты
    {"code": "create_quote", "name": "💬 Цитатник", "description": "Создать цитату",
     "reward_type": "coins", "reward_amount": 50, "event_type": "quote", "target_value": 1},
    
    # Grow
    {"code": "grow_3", "name": "🌱 Садовод", "description": "Использовать /grow 3 раза",
     "reward_type": "coins", "reward_amount": 75, "event_type": "grow", "target_value": 3},
]


async def init_quests():
    """Инициализировать квесты в БД при старте."""
    async_session = get_session()
    async with async_session() as session:
        for quest_data in QUESTS:
            existing = await session.scalar(
                select(Quest).where(Quest.code == quest_data["code"])
            )
            if not existing:
                quest = Quest(**quest_data)
                session.add(quest)
                logger.info(f"Added quest: {quest_data['code']}")
        await session.commit()


async def assign_daily_quests(user_id: int, count: int = 3) -> list[Quest]:
    """
    Назначить ежедневные квесты пользователю.
    Удаляет старые незавершённые квесты и назначает новые.
    """
    async_session = get_session()
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.tg_user_id == user_id)
        )
        if not user:
            return []
        
        # Удаляем старые незавершённые квесты (старше 24 часов)
        yesterday = utc_now() - timedelta(hours=24)
        await session.execute(
            delete(UserQuest)
            .where(
                UserQuest.user_id == user.id,
                UserQuest.completed_at.is_(None),
                UserQuest.assigned_at < yesterday
            )
        )
        
        # Проверяем текущие активные квесты
        active = await session.execute(
            select(UserQuest)
            .where(
                UserQuest.user_id == user.id,
                UserQuest.completed_at.is_(None)
            )
        )
        active_quest_ids = {uq.quest_id for uq in active.scalars()}
        
        # Если уже есть активные квесты, не назначаем новые
        if len(active_quest_ids) >= count:
            return []
        
        # Получаем все квесты
        all_quests = await session.execute(select(Quest))
        available = [q for q in all_quests.scalars() if q.id not in active_quest_ids]
        
        # Выбираем случайные
        to_assign = random.sample(available, min(count - len(active_quest_ids), len(available)))
        
        assigned = []
        for quest in to_assign:
            uq = UserQuest(
                user_id=user.id,
                quest_id=quest.id,
                assigned_at=utc_now(),
                progress=0
            )
            session.add(uq)
            assigned.append(quest)
        
        await session.commit()
        return assigned


async def update_quest_progress(
    user_id: int,
    event_type: str,
    amount: int = 1
) -> list[tuple[str, int]]:
    """
    Обновить прогресс квестов по событию.
    
    Returns:
        Список (название квеста, награда) для завершённых квестов
    """
    async_session = get_session()
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.tg_user_id == user_id)
        )
        if not user:
            return []
        
        # Получаем активные квесты с нужным event_type
        result = await session.execute(
            select(UserQuest, Quest)
            .join(Quest)
            .where(
                UserQuest.user_id == user.id,
                UserQuest.completed_at.is_(None),
                Quest.event_type == event_type
            )
        )
        
        completed = []
        for uq, quest in result.fetchall():
            uq.progress += amount
            
            if uq.progress >= quest.target_value:
                uq.completed_at = utc_now()
                
                # Выдаём награду
                if quest.reward_type == "coins":
                    balance = await session.scalar(
                        select(UserBalance)
                        .where(
                            UserBalance.user_id == user_id,
                            UserBalance.chat_id == 0
                        )
                    )
                    if not balance:
                        balance = UserBalance(user_id=user_id, chat_id=0, balance=0)
                        session.add(balance)
                    balance.balance += quest.reward_amount
                
                completed.append((quest.name, quest.reward_amount))
                logger.info(f"User {user_id} completed quest {quest.code}")
        
        await session.commit()
        return completed


async def get_user_quests(user_id: int) -> list[tuple[Quest, UserQuest]]:
    """Получить активные квесты пользователя."""
    async_session = get_session()
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.tg_user_id == user_id)
        )
        if not user:
            return []
        
        result = await session.execute(
            select(Quest, UserQuest)
            .join(UserQuest)
            .where(
                UserQuest.user_id == user.id,
                UserQuest.completed_at.is_(None)
            )
        )
        return [(q, uq) for q, uq in result.fetchall()]


# Алиас для совместимости со старым кодом
async def check_and_update_quests(session, user, event_type: str):
    """
    Алиас для update_quest_progress для совместимости.
    
    Returns:
        Список завершённых квестов как объекты с name и reward_amount
    """
    from dataclasses import dataclass
    
    @dataclass
    class QuestResult:
        name: str
        reward_amount: int
        reward_type: str = "coins"
    
    completed = await update_quest_progress(user.tg_user_id, event_type)
    return [QuestResult(name=name, reward_amount=amount) for name, amount in completed]
