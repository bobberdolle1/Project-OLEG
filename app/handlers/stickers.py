"""
Обработчик стикеров для Олега.

Олег реагирует на стикеры:
- Если его упомянули в ответе на стикер
- Рандомно с небольшой вероятностью (2%)
- Может ответить стикером или текстом
"""

import logging
import random
import re
from aiogram import Router, F
from aiogram.types import Message

from app.services.ollama_client import is_ollama_available

logger = logging.getLogger(__name__)

router = Router()

# Вероятность авто-ответа на стикер
AUTO_STICKER_REPLY_PROBABILITY = 0.02  # 2%

# Триггеры для упоминания Олега
OLEG_TRIGGERS = ["олег", "олега", "олегу", "олегом", "олеге", "oleg"]

# Реакции на стикеры по эмодзи
EMOJI_REACTIONS = {
    # Позитивные
    "😂": ["ору", "кек", "жиза", "база", "классика"],
    "🤣": ["ахахах", "ору в голос", "база"],
    "😁": ["норм", "👍", "база"],
    "😊": ["мило", "👍"],
    "🥰": ["мимими", "ня"],
    "😍": ["вау", "красиво"],
    "🔥": ["огонь", "база", "топ"],
    "💪": ["сила", "база", "красава"],
    "👍": ["👍", "норм", "согласен"],
    "❤️": ["❤️", "взаимно"],
    "💯": ["база", "факт", "согласен"],
    
    # Негативные/саркастичные
    "😢": ["не плачь", "бывает", "F"],
    "😭": ["F", "соболезную", "бывает"],
    "😤": ["остынь", "не кипятись"],
    "😡": ["воу воу", "полегче"],
    "🤡": ["🤡", "клоун детектед", "ну ты и клоун"],
    "💀": ["💀", "мёртв", "F"],
    "☠️": ["F", "RIP"],
    "🗿": ["🗿", "база", "моаи момент"],
    
    # Нейтральные
    "🤔": ["хм", "думаю...", "интересно"],
    "😐": ["ну такое", "..."],
    "😑": ["...", "ок"],
    "🙄": ["ага", "конечно"],
    "🤷": ["хз", "без понятия", "¯\\_(ツ)_/¯"],
    
    # Мемные
    "🐸": ["пепе", "редкий пепе"],
    "🦆": ["кря", "утка"],
    "🐱": ["мяу", "котик"],
    "🐶": ["гав", "пёсик"],
    "💩": ["говнокод?", "фу"],
    "🎮": ["геймер момент", "база"],
    "🖥️": ["пк мастер рейс", "база"],
    "🎧": ["вайб", "музыка"],
}

# Дефолтные реакции если эмодзи не распознан
DEFAULT_REACTIONS = [
    "👀",
    "🗿",
    "норм стикер",
    "ок",
    "видел и лучше",
    "классика",
    "база",
    "...",
    "хм",
]

# Реакции на стикерпаки (по названию)
STICKERPACK_REACTIONS = {
    "pepe": ["пепе база", "редкий пепе", "классика"],
    "doge": ["вау", "такой дож", "мем из 2013"],
    "cat": ["мяу", "котик", "ня"],
    "anime": ["анимешник детектед", "вижу культурного человека"],
    "meme": ["мем", "классика", "база"],
}


def _contains_bot_mention(text: str, bot) -> bool:
    """Проверяет упоминание бота в тексте."""
    if not text:
        return False
    
    text_lower = text.lower()
    
    if bot and bot._me and bot._me.username:
        bot_username = bot._me.username.lower()
        if f"@{bot_username}" in text_lower:
            return True
    
    for trigger in OLEG_TRIGGERS:
        if re.search(rf'\b{trigger}\b', text_lower):
            return True
    
    return False


async def should_react_to_sticker(msg: Message) -> tuple[bool, bool]:
    """
    Проверяет, нужно ли реагировать на стикер.
    
    Returns:
        (should_react, is_auto_reply)
    """
    # Проверяем доступность Ollama
    if not await is_ollama_available():
        return False, False
    
    # В личке всегда отвечаем
    if msg.chat.type == "private":
        return True, False
    
    # Проверяем ответ на сообщение бота
    if msg.reply_to_message and msg.reply_to_message.from_user:
        if msg.reply_to_message.from_user.id == msg.bot.id:
            return True, False
    
    # Авто-ответ с вероятностью 2%
    if random.random() < AUTO_STICKER_REPLY_PROBABILITY:
        return True, True
    
    return False, False


def get_reaction_for_sticker(sticker) -> str:
    """
    Генерирует реакцию на стикер.
    
    Args:
        sticker: Объект стикера
        
    Returns:
        Текст реакции
    """
    # Пробуем по эмодзи
    emoji = sticker.emoji
    if emoji and emoji in EMOJI_REACTIONS:
        return random.choice(EMOJI_REACTIONS[emoji])
    
    # Пробуем по названию стикерпака
    if sticker.set_name:
        set_name_lower = sticker.set_name.lower()
        for keyword, reactions in STICKERPACK_REACTIONS.items():
            if keyword in set_name_lower:
                return random.choice(reactions)
    
    # Дефолтная реакция
    return random.choice(DEFAULT_REACTIONS)


@router.message(F.sticker)
async def handle_sticker(msg: Message):
    """
    Обработчик стикеров.
    """
    if not msg.from_user or msg.from_user.is_bot:
        return
    
    sticker = msg.sticker
    if not sticker:
        return
    
    should_react, is_auto = await should_react_to_sticker(msg)
    if not should_react:
        return
    
    # Генерируем реакцию
    reaction = get_reaction_for_sticker(sticker)
    
    # Логируем
    emoji_info = sticker.emoji or "no_emoji"
    set_info = sticker.set_name or "no_set"
    logger.info(
        f"[STICKER] chat={msg.chat.id} | user={msg.from_user.id} | "
        f"emoji={emoji_info} | set={set_info} | auto={is_auto} | reaction={reaction}"
    )
    
    try:
        await msg.reply(reaction)
    except Exception as e:
        logger.warning(f"Failed to reply to sticker: {e}")
