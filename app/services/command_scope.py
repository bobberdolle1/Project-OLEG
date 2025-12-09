"""Command scope manager for registering different commands in group and private chats."""

import logging
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats

logger = logging.getLogger(__name__)


# Commands visible in group chats - games, moderation, group features
GROUP_COMMANDS = [
    BotCommand(command="help", description="Справка по командам"),
    BotCommand(command="games", description="Гайд по играм для новичков"),
    BotCommand(command="grow", description="Увеличить размер"),
    BotCommand(command="top", description="Топ-10 игроков по размеру"),
    BotCommand(command="top_rep", description="Топ-10 по репутации"),
    BotCommand(command="profile", description="Твой профиль со статистикой"),
    BotCommand(command="pvp", description="Дуэль с другим игроком"),
    BotCommand(command="casino", description="Слоты (по умолчанию 10 монет)"),
    BotCommand(command="achievements", description="Список всех достижений"),
    BotCommand(command="my_achievements", description="Твои достижения"),
    BotCommand(command="quests", description="Активные квесты"),
    BotCommand(command="quest_progress", description="Прогресс по квестам"),
    BotCommand(command="create_guild", description="Создать гильдию"),
    BotCommand(command="guild_info", description="Информация о гильдии"),
    BotCommand(command="create_duo", description="Создать дуэт"),
    BotCommand(command="duo_stats", description="Статистика дуэта"),
    BotCommand(command="say", description="Голосовое сообщение от Олега"),
    BotCommand(command="tips", description="Советы по управлению чатом"),
]


# Commands visible in private chats - admin panel, personal commands
# Note: /owner is intentionally hidden (anonymous command for bot owner only)
PRIVATE_COMMANDS = [
    BotCommand(command="help", description="Справка по командам"),
    BotCommand(command="start", description="Приветствие"),
    BotCommand(command="admin", description="Админ-панель для управления чатами"),
    BotCommand(command="reset", description="Сбросить контекст диалога"),
    BotCommand(command="myhistory", description="История твоих вопросов"),
    BotCommand(command="say", description="Голосовое сообщение от Олега"),
]


async def setup_commands(bot: Bot) -> bool:
    """
    Register command scopes for different chat types.
    
    Sets up separate command menus for:
    - Private chats: admin, reset, help, say, start
    - Group chats: games, moderation, quotes, etc.
    
    Args:
        bot: The Bot instance to register commands for
        
    Returns:
        True if registration was successful, False otherwise
    """
    try:
        # Register commands for private chats
        await bot.set_my_commands(
            commands=PRIVATE_COMMANDS,
            scope=BotCommandScopeAllPrivateChats()
        )
        logger.info(f"Registered {len(PRIVATE_COMMANDS)} commands for private chats")
        
        # Register commands for group chats
        await bot.set_my_commands(
            commands=GROUP_COMMANDS,
            scope=BotCommandScopeAllGroupChats()
        )
        logger.info(f"Registered {len(GROUP_COMMANDS)} commands for group chats")
        
        return True
        
    except Exception as e:
        logger.warning(f"Failed to register command scopes: {e}")
        return False
