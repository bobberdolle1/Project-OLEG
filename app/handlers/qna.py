"""Обработчик Q&A с личностью Олега."""

import logging
from aiogram import Router, F
from aiogram.types import Message

from app.services.ollama_client import generate_reply

logger = logging.getLogger(__name__)

router = Router()


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

