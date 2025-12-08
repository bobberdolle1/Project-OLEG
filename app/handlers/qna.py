"""Обработчик Q&A с личностью Олега."""

import logging
import random
import re
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime
from sqlalchemy import select

from app.database.session import get_session
from app.database.models import User, UserQuestionHistory
from app.handlers.games import ensure_user # For getting user object
from app.services.ollama_client import generate_text_reply as generate_reply, generate_reply_with_context
from app.services.recommendations import generate_recommendation
from app.services.tts import tts_service
from app.services.golden_fund import golden_fund_service
from app.services.reply_context import reply_context_injector
from app.utils import utc_now

logger = logging.getLogger(__name__)

router = Router()




@router.message(Command("start"))
async def cmd_start(msg: Message):
    """Команда /start — приветствие."""
    await msg.reply("Я Олег. Чё надо? Пиши по делу.")


import random as _random
from sqlalchemy import select as _select
from app.database.models import Chat as _Chat
from app.services.auto_reply import auto_reply_system, ChatSettings as AutoReplySettings


async def _should_reply(msg: Message) -> bool:
    """
    Проверить, должен ли бот ответить на сообщение.

    Бот отвечает в следующих случаях:
    - Это личное сообщение (private chat)
    - Это ответ на сообщение бота (reply)
    - Бот упомянут в сообщении (@botname)
    - Упоминание "олег" в тексте
    - Сообщение содержит вопрос (?)
    - Авто-ответ сработал по вероятности (15-40%)

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

    # Проверка: упоминание "олег" в тексте (без @)
    if msg.text:
        text_lower = msg.text.lower()
        # Проверяем слово "олег" как отдельное слово или в начале/конце
        oleg_triggers = ["олег", "олега", "олегу", "олегом", "олеге", "oleg"]
        for trigger in oleg_triggers:
            # Проверяем что это отдельное слово, а не часть другого
            if re.search(rf'\b{trigger}\b', text_lower):
                return True
        
        # Проверка: сообщение содержит вопрос — бот отвечает на вопросы!
        if "?" in msg.text:
            # Отвечаем на вопросы с высокой вероятностью (70%)
            if _random.random() < 0.70:
                logger.debug(f"Replying to question in chat {msg.chat.id}")
                return True

    # Проверка: авто-ответ через AutoReplySystem
    # Бот активно участвует в чате как настоящий участник
    try:
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(_select(_Chat).filter_by(id=msg.chat.id))
            chat = result.scalars().first()
            
            # Получаем ID топика сообщения
            msg_topic_id = getattr(msg, 'message_thread_id', None)
            
            # Проверяем active_topic_id — если установлен, бот отвечает только в этом топике
            # Если не установлен (None) — бот отвечает во всех топиках
            if chat and chat.active_topic_id is not None:
                if msg_topic_id != chat.active_topic_id:
                    logger.debug(
                        f"Skipping message in topic {msg_topic_id}, "
                        f"bot active only in topic {chat.active_topic_id}"
                    )
                    return False
            
            if msg.text:
                # Получаем настройки чата или используем дефолтные
                auto_reply_chance = 1.0  # По умолчанию авто-ответ включен
                if chat:
                    auto_reply_chance = chat.auto_reply_chance
                
                # Если авто-ответ не отключен (chance > 0)
                if auto_reply_chance > 0:
                    chat_settings = AutoReplySettings(auto_reply_chance=auto_reply_chance)
                    
                    if auto_reply_system.should_reply(msg.text, chat_settings):
                        logger.debug(
                            f"Auto-reply triggered for chat {msg.chat.id}, "
                            f"topic {msg_topic_id}, chance={auto_reply_chance}"
                        )
                        return True
    except Exception as e:
        logger.debug(f"Ошибка при проверке авто-ответа: {e}")
        # При ошибке всё равно пробуем авто-ответ с базовым шансом
        if msg.text:
            chat_settings = AutoReplySettings(auto_reply_chance=1.0)
            if auto_reply_system.should_reply(msg.text, chat_settings):
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


def _is_games_help_request(text: str) -> bool:
    """Проверяет, спрашивает ли пользователь про игры."""
    text_lower = text.lower()
    game_keywords = [
        "помоги с игр", "как играть", "что за игр", "какие игр",
        "как работает grow", "как работает pvp", "как работает casino",
        "что такое grow", "что такое pvp", "что такое casino",
        "как выращивать", "как дуэль", "как казино", "как слоты",
        "объясни игр", "расскажи про игр", "помощь по игр",
        "не понимаю игр", "как начать играть", "с чего начать",
        "/grow", "/pvp", "/casino", "/top", "/profile"
    ]
    return any(kw in text_lower for kw in game_keywords)


GAMES_AI_CONTEXT = """
Ты помогаешь новичку разобраться в мини-играх бота. Вот команды:

/games — полная справка по играм
/grow — увеличить размер (кулдаун 12-24ч, +1-20 см)
/top — топ-10 по размеру
/top_rep — топ-10 по репутации  
/profile — твой профиль и статистика
/pvp @ник — дуэль (победитель забирает 10-30% размера)
/casino [ставка] — слоты (3 одинаковых = x5, 2 = x2)

Новичкам: начни с /grow, потом /profile. Монеты копи, в казино не сливай всё.
"""


@router.message(F.text)
async def general_qna(msg: Message):
    """
    Общий обработчик Q&A.

    Отвечает на вопросы пользователей, если бот упомянут
    или это ответ на сообщение бота.
    """
    # Логируем информацию о топике для отладки
    topic_id = getattr(msg, 'message_thread_id', None)
    if topic_id:
        logger.debug(f"Сообщение из топика {topic_id} в чате {msg.chat.id}: {msg.text[:50] if msg.text else 'empty'}...")
    
    if not await _should_reply(msg):
        return

    text = msg.text or ""
    async_session = get_session()
    user = await ensure_user(msg.from_user) # Ensure user exists and get the User object

    try:
        logger.info(
            f"Q&A от @{msg.from_user.username or msg.from_user.id}: "
            f"{text[:50]}..."
        )

        # Проверяем, спрашивает ли про игры — даём контекст ИИ
        games_context = GAMES_AI_CONTEXT if _is_games_help_request(text) else None

        # Inject reply context if this message is a reply to another message
        # **Validates: Requirements 14.1, 14.2, 14.3, 14.4**
        text_with_context = reply_context_injector.inject(msg, text)

        # Получаем уровень токсичности в чате
        chat_toxicity = await get_current_chat_toxicity(msg.chat.id)

        # Fortress Update: Golden Fund integration (Requirement 9.2, 9.3)
        # 5% chance to respond with a contextually relevant Golden Fund quote
        # **Validates: Requirements 9.2, 9.3**
        golden_quote_sent = False
        if golden_fund_service.should_respond_with_quote():
            try:
                golden_quote = await golden_fund_service.search_relevant_quote(
                    context=text,
                    chat_id=msg.chat.id
                )
                if golden_quote:
                    # If the quote has a sticker, send it
                    if golden_quote.sticker_file_id:
                        try:
                            await msg.reply_sticker(sticker=golden_quote.sticker_file_id)
                            golden_quote_sent = True
                            logger.info(
                                f"Golden Fund sticker sent for context: {text[:50]}... "
                                f"(quote_id={golden_quote.id})"
                            )
                        except Exception as sticker_err:
                            logger.warning(f"Failed to send Golden Fund sticker: {sticker_err}")
                    
                    # If no sticker or sticker failed, send as text quote
                    if not golden_quote_sent:
                        quote_text = f"💬 *{golden_quote.username}*: _{golden_quote.text}_"
                        await msg.reply(quote_text, parse_mode="Markdown")
                        golden_quote_sent = True
                        logger.info(
                            f"Golden Fund quote sent for context: {text[:50]}... "
                            f"(quote_id={golden_quote.id})"
                        )
            except Exception as gf_err:
                logger.warning(f"Golden Fund search failed: {gf_err}")
        
        # If Golden Fund quote was sent, skip normal response generation
        if golden_quote_sent:
            return

        # Если в личных сообщениях, учитываем поведение пользователя
        if msg.chat.type == "private":
            # Здесь в реальной реализации нужно анализировать поведение пользователя
            # и адаптировать стиль ответа соответственно
            # Use text_with_context to include reply context for AI
            # **Validates: Requirements 14.4**
            reply = await generate_reply(
                user_text=text_with_context,
                username=msg.from_user.username,
                chat_context=games_context
            )
        else:
            # Для групповых чатов используем функцию с контекстом из памяти
            # Use text_with_context to include reply context for AI
            # **Validates: Requirements 14.4**
            reply = await generate_reply_with_context(
                user_text=text_with_context,
                username=msg.from_user.username,
                chat_id=msg.chat.id,
                chat_context=games_context
            )

        # Check if we should auto-voice this response (0.1% chance)
        # **Validates: Requirements 5.2**
        voice_sent = False
        if tts_service.should_auto_voice():
            try:
                result = await tts_service.generate_voice(reply)
                if result is not None:
                    await msg.reply_voice(
                        voice=result.audio_data,
                        caption="🎤 Олег решил ответить голосом",
                        duration=int(result.duration_seconds)
                    )
                    voice_sent = True
                    logger.info(f"Auto-voice triggered for response to @{msg.from_user.username or msg.from_user.id}")
            except Exception as e:
                logger.warning(f"Auto-voice failed, falling back to text: {e}")
        
        # Send text response if voice wasn't sent
        if not voice_sent:
            try:
                await msg.reply(reply, disable_web_page_preview=True)
            except TelegramBadRequest as e:
                if "thread not found" in str(e).lower() or "message to reply not found" in str(e).lower():
                    logger.warning(f"Cannot reply - topic/message deleted: {e}")
                    return
                raise

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

