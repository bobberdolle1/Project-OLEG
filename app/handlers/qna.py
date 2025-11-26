"""Обработчик Q&A с личностью Олега."""

import logging
import random
from aiogram import Router, F
from aiogram.types import Message

from app.services.ollama_client import generate_reply

logger = logging.getLogger(__name__)

router = Router()

# Счетчик голосовых/видео сообщений
VOICE_VIDEO_COUNTER = {"count": 0, "tolerance": 3}


@router.message(F.text.startswith("/start"))
async def cmd_start(msg: Message):
    """Команда /start — приветствие."""
    await msg.reply("Я Олег. Чё надо? Пиши по делу.")


def _should_reply(msg: Message) -> bool:
    """
    Проверить, должен ли бот ответить на сообщение.

    Бот отвечает в следующих случаях:
    - Это ответ на сообщение бота (reply)
    - Бот упомянут в сообщении (@botname)

    Args:
        msg: Сообщение Telegram

    Returns:
        True, если нужно ответить
    """
    # Проверка: это ответ на сообщение бота?
    if msg.reply_to_message:
        if (
            msg.reply_to_message.from_user
            and msg.reply_to_message.from_user.id == msg.bot.id
        ):
            return True

    # Проверка: бот упомянут в тексте?
    if msg.entities and msg.text and msg.bot._me:
        bot_username = msg.bot._me.username
        if bot_username and ("@" + bot_username) in msg.text:
            return True

    return False


@router.message(F.text)
async def general_qna(msg: Message):
    """
    Общий обработчик Q&A.

    Отвечает на вопросы пользователей, если бот упомянут
    или это ответ на сообщение бота.
    """
    if not _should_reply(msg):
        return

    text = msg.text or ""
    try:
        logger.info(
            f"Q&A от @{msg.from_user.username or msg.from_user.id}: "
            f"{text[:50]}..."
        )
        reply = await generate_reply(
            user_text=text,
            username=msg.from_user.username
        )
        await msg.reply(reply, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Ошибка при генерации ответа: {e}")
        await msg.reply(
            "Сервер сломался. Но только ненадолго, обещаю."
        )


@router.message(F.voice)
@router.message(F.video_note)
async def handle_voice_video(msg: Message):
    """
    Обработчик голосовых и видеосообщений.
    
    Олегу не нравятся голосовые и видео, он их считает
    и ругается, если их становится слишком много.
    """
    VOICE_VIDEO_COUNTER["count"] += 1
    count = VOICE_VIDEO_COUNTER["count"]
    tolerance = VOICE_VIDEO_COUNTER["tolerance"]
    
    logger.info(
        f"Голос/видео от @{msg.from_user.username or msg.from_user.id} "
        f"(всего: {count})"
    )
    
    # Ругаться с увеличением интенсивности
    if count == 1:
        await msg.react("😒")
        await msg.reply("Пиши текстом, а не голосом. Лень слушать.")
    elif count == 2:
        await msg.react("🤬")
        await msg.reply(
            "Блин, как много этого голоса! Текст же есть? "
            "Или я плохо вижу?"
        )
    elif count >= tolerance:
        await msg.react("🔥")
        reactions = [
            "Ёбаны голосовухи! Хватит уже! "
            "Пиши как нормальный человек!",
            "Ты издеваешься? Голос 3-й раз подряд?! "
            "Текстом типа нельзя?",
            "Король голосовых сообщений? "
            "Хватит этого бреда!",
            "Опять эти ебаные видео! У меня уши болят! "
            "Пиши буквами, боже!",
        ]
        await msg.reply(random.choice(reactions))
        logger.warning(
            f"Превышен лимит голос/видео: {count} "
            f"(лимит: {tolerance})"
        )

