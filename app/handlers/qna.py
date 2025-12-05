"""Обработчик Q&A с личностью Олега."""

import logging
import random
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from datetime import datetime
from sqlalchemy import select

from app.database.session import get_session
from app.database.models import User, UserQuestionHistory
from app.handlers.games import ensure_user # For getting user object
from app.services.ollama_client import generate_text_reply as generate_reply, generate_reply_with_context
from app.services.recommendations import generate_recommendation
from app.utils import utc_now

logger = logging.getLogger(__name__)

router = Router()




@router.message(Command("start"))
async def cmd_start(msg: Message):
    """Команда /start — приветствие."""
    await msg.reply("Я Олег. Чё надо? Пиши по делу.")


def _should_reply(msg: Message) -> bool:
    """
    Проверить, должен ли бот ответить на сообщение.

    Бот отвечает в следующих случаях:
    - Это личное сообщение (private chat)
    - Это ответ на сообщение бота (reply)
    - Бот упомянут в сообщении (@botname)

    Args:
        msg: Сообщение Telegram

    Returns:
        True, если нужно ответить
    """
    # В личных сообщениях всегда отвечаем
    if msg.chat.type == "private":
        return True

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


async def get_current_chat_toxicity(chat_id: int) -> float:
    """
    Получает текущий уровень токсичности в чате.

    Args:
        chat_id: ID чата

    Returns:
        Уровень токсичности от 0 до 100
    """
    # Временно возвращаем фиксированное значение
    # В реальной реализации будет вызов функции анализа токсичности
    from app.services.ollama_client import analyze_chat_toxicity

    try:
        toxicity_percentage, _ = await analyze_chat_toxicity(24)
        return toxicity_percentage
    except Exception as e:
        logger.error(f"Ошибка при анализе токсичности: {e}")
        return 0.0  # Возвращаем 0 при ошибке


async def adjust_toxicity_for_private_chat(user_id: int, text: str) -> float:
    """
    Адаптирует уровень токсичности для ответа в личных сообщениях
    в зависимости от поведения пользователя.

    Args:
        user_id: ID пользователя
        text: Текст сообщения от пользователя

    Returns:
        Уровень токсичности для генерации ответа (0-100)
    """
    # В реальной реализации можно анализировать:
    # 1. Историю сообщений с пользователем
    # 2. Слова и тон в сообщении
    # 3. Частоту сообщений (возможный спам)
    # 4. Использование ненормативной лексики

    # Простая эвристика для демонстрации
    toxicity = 30  # базовый уровень

    # Повышаем токсичность на основании некоторых признаков
    if any(word in text.lower() for word in ["идиот", "дурак", "тупой", "нах", "еба", "сука", "бля"]):
        toxicity += 20

    if text.isupper() and len(text) > 10:
        toxicity += 15  # Капс часто указывает на агрессию

    if "?" in text and "???" in text:
        # Тройной вопрос может быть саркастическим
        toxicity += 10

    # Понижаем токсичность для вежливого общения
    if any(phrase in text.lower() for phrase in ["пожалуйста", "спасибо", "привет", "здраствуй"]):
        toxicity = max(0, toxicity - 10)

    return min(100, toxicity)  # Ограничиваем максимальный уровень 100


async def potentially_roast_toxic_user(msg: Message):
    """
    Потенциально "наезжает" на токсичного пользователя, если уровень токсичности высок.

    Args:
        msg: Сообщение, триггернувшее "наезд"
    """
    # С вероятностью 30% "наезжаем" на пользователя
    if random.random() < 0.3:
        try:
            target_user = msg.from_user
            username = f"@{target_user.username}" if target_user.username else f"{target_user.first_name}"

            # Создаем саркастический комментарий
            roasts = [
                f"{username}, а ты сегодня золотой, да? Слишком токсично для меня!",
                f"{username}, остынь немного, а то уже всех задел!",
                f"Токсичность на максимуме, {username}! Может, не будешь?",
                f"{username}, ты как чайник, только не кипяток, а токсикоз!",
                f"Эй, {username}, агрессия - это не сила, это слабость, братишка."
            ]

            roast_message = random.choice(roasts)
            await msg.reply(roast_message)
        except Exception as e:
            logger.warning(f"Ошибка при 'наезде' на токсичного пользователя: {e}")


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
    async_session = get_session()
    user = await ensure_user(msg.from_user) # Ensure user exists and get the User object

    try:
        logger.info(
            f"Q&A от @{msg.from_user.username or msg.from_user.id}: "
            f"{text[:50]}..."
        )

        # Получаем уровень токсичности в чате
        chat_toxicity = await get_current_chat_toxicity(msg.chat.id)

        # Если в личных сообщениях, учитываем поведение пользователя
        if msg.chat.type == "private":
            # Здесь в реальной реализации нужно анализировать поведение пользователя
            # и адаптировать стиль ответа соответственно
            reply = await generate_reply(
                user_text=text,
                username=msg.from_user.username,
                chat_context=None
            )
        else:
            # Для групповых чатов используем функцию с контекстом из памяти
            reply = await generate_reply_with_context(
                user_text=text,
                username=msg.from_user.username,
                chat_id=msg.chat.id,
                chat_context=None
            )

        await msg.reply(reply, disable_web_page_preview=True)

        # В случае высокой токсичности, бот может "наехать" на самых токсичных пользователей
        if chat_toxicity > 70 and msg.chat.type != "private":
            await potentially_roast_toxic_user(msg)
        elif msg.chat.type == "private" and "спам" in text.lower():
            # В личных сообщениях реагируем на спам
            try:
                await msg.reply("Хватит спамить, чувак. Я тебе не робот для рекламы.")
            except:
                pass

        # Save to history
        async with async_session() as session:
            history_entry = UserQuestionHistory(
                user_id=user.id,
                question=text,
                answer=reply,
                asked_at=utc_now()
            )
            session.add(history_entry)
            await session.commit()

        # Get and send recommendation
        recommendation = await generate_recommendation(session, user, text)
        if recommendation:
            await msg.answer(f"💡 Рекомендация: {recommendation}")

    except Exception as e:
        logger.error(f"Ошибка при генерации ответа: {e}")
        await msg.reply(
            "Сервер сломался. Но только ненадолго, обещаю."
        )


@router.message(Command("myhistory"))
async def cmd_myhistory(msg: Message):
    """
    Handles the /myhistory command, displaying a user's question history.
    """
    async_session = get_session()
    user = await ensure_user(msg.from_user)

    async with async_session() as session:
        history_res = await session.execute(
            select(UserQuestionHistory)
            .filter_by(user_id=user.id)
            .order_by(UserQuestionHistory.asked_at.desc())
            .limit(10) # Display last 10 questions
        )
        history_entries = history_res.scalars().all()

        if not history_entries:
            return await msg.reply("У вас пока нет истории вопросов.")

        history_list = ["Ваша история вопросов:"]
        for entry in history_entries:
            history_list.append(
                f"--- От {entry.asked_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"В: {entry.question}\n"
                f"О: {entry.answer[:100]}..." # Truncate long answers
            )

        await msg.reply("\n\n".join(history_list), disable_web_page_preview=True)


@router.message(Command("reset"))
async def cmd_reset_context(msg: Message):
    """
    Сброс контекста в личных сообщениях.
    """
    if msg.chat.type != 'private':
        await msg.reply("Эту команду можно использовать только в личных сообщениях.")
        return

    # В реальной реализации нужно очистить историю сообщений для этого пользователя
    # В текущем виде система не хранит контекст в нужном формате, поэтому
    # просто сообщим пользователю о сбросе
    await msg.reply("Контекст диалога сброшен. Олег теперь не помнит, что ты тролль.")


# Обработчик голосовых перенесён в app/handlers/voice.py

