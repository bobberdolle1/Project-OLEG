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
from app.database.models import User, UserQuestionHistory, MessageLog, Chat
from app.handlers.games import ensure_user # For getting user object
from app.services.ollama_client import generate_text_reply as generate_reply, generate_reply_with_context, generate_private_reply, is_ollama_available
from app.services.recommendations import generate_recommendation
from app.services.tts import tts_service
from app.services.golden_fund import golden_fund_service
from app.services.reply_context import reply_context_injector
from app.utils import utc_now

logger = logging.getLogger(__name__)

router = Router()


async def _log_bot_response(chat_id: int, message_id: int, text: str, bot_username: str | None = "oleg_bot"):
    """
    Логирует ответ бота в базу данных для сохранения истории диалога.
    
    Args:
        chat_id: ID чата
        message_id: ID сообщения
        text: Текст ответа
        bot_username: Username бота
    """
    async_session = get_session()
    try:
        async with async_session() as session:
            ml = MessageLog(
                chat_id=chat_id,
                message_id=message_id,
                user_id=0,  # 0 для бота
                username=bot_username,
                text=text,
                has_link=False,
                links=None,
                created_at=utc_now(),
            )
            session.add(ml)
            await session.commit()
            logger.debug(f"Logged bot response to chat {chat_id}")
    except Exception as e:
        logger.warning(f"Failed to log bot response: {e}")




@router.message(Command("start"))
async def cmd_start(msg: Message):
    """Команда /start — приветствие."""
    await msg.reply("Я Олег. Чё надо? Пиши по делу.")


import random as _random
from app.services.auto_reply import auto_reply_system, ChatSettings as AutoReplySettings


async def _should_reply(msg: Message) -> bool:
    """
    Проверить, должен ли бот ответить на сообщение.
    """
    msg_topic_id = getattr(msg, 'message_thread_id', None)
    is_forum = getattr(msg.chat, 'is_forum', False)
    
    # Проверяем доступность Ollama
    if not await is_ollama_available():
        logger.warning(f"[SHOULD_REPLY] NO - Ollama недоступен | chat={msg.chat.id}")
        return False
    
    # В личных сообщениях всегда отвечаем
    if msg.chat.type == "private":
        logger.debug(f"[SHOULD_REPLY] YES - private chat")
        return True

    # Получаем настройки чата
    auto_reply_chance = 1.0
    
    try:
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(select(Chat).filter_by(id=msg.chat.id))
            chat = result.scalars().first()
            
            if chat:
                auto_reply_chance = chat.auto_reply_chance
                logger.debug(
                    f"[SHOULD_REPLY CHECK] chat={msg.chat.id} | topic={msg_topic_id} | "
                    f"forum={is_forum} | auto_chance={auto_reply_chance}"
                )
    except Exception as e:
        logger.warning(f"[SHOULD_REPLY] Ошибка настроек чата: {e}")

    # Проверка: это ответ на сообщение бота?
    if msg.reply_to_message:
        if (
            msg.reply_to_message.from_user
            and msg.reply_to_message.from_user.id == msg.bot.id
        ):
            logger.debug(f"[SHOULD_REPLY] YES - reply to bot")
            return True

    # Проверка: бот упомянут в тексте?
    if msg.entities and msg.text and msg.bot._me:
        bot_username = msg.bot._me.username
        if bot_username and ("@" + bot_username) in msg.text:
            logger.debug(f"[SHOULD_REPLY] YES - bot mentioned @{bot_username}")
            return True

    # Проверка: упоминание "олег" в тексте
    if msg.text:
        text_lower = msg.text.lower()
        oleg_triggers = ["олег", "олега", "олегу", "олегом", "олеге", "oleg"]
        for trigger in oleg_triggers:
            if re.search(rf'\b{trigger}\b', text_lower):
                logger.debug(f"[SHOULD_REPLY] YES - trigger '{trigger}'")
                return True
        
        # Проверка: реальный вопрос
        if "?" in msg.text:
            if _is_real_question(msg.text):
                if _random.random() < 0.40:
                    logger.debug(f"[SHOULD_REPLY] YES - real question (40%)")
                    return True
            else:
                logger.debug(f"[SHOULD_REPLY] SKIP - not real question: {msg.text[:30]}...")

    # Авто-ответ
    if msg.text and auto_reply_chance > 0:
        chat_settings = AutoReplySettings(auto_reply_chance=auto_reply_chance)
        if auto_reply_system.should_reply(msg.text, chat_settings):
            logger.debug(f"[SHOULD_REPLY] YES - auto-reply (chance={auto_reply_chance})")
            return True

    logger.debug(f"[SHOULD_REPLY] NO - no conditions matched")
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


def _is_real_question(text: str) -> bool:
    """
    Проверяет, является ли вопрос реальным/осмысленным.
    
    Реальный вопрос — это вопрос, на который можно дать полезный ответ:
    - Технические вопросы (как настроить, почему не работает, что выбрать)
    - Вопросы с просьбой о помощи
    - Вопросы с конкретным контекстом
    
    НЕ реальные вопросы:
    - Слишком короткие ("как?", "чё?", "а?")
    - Бессмысленные ("как с помидором?", "а ты кто?")
    - Риторические без контекста
    
    Args:
        text: Текст сообщения
        
    Returns:
        True если вопрос реальный и заслуживает ответа
    """
    if not text:
        return False
    
    text_lower = text.lower().strip()
    
    # Слишком короткий вопрос — скорее всего мусор
    # "как?" = 4 символа, "почему лагает?" = 14 символов
    if len(text_lower) < 10:
        return False
    
    # Признаки реального вопроса (технического/полезного)
    real_question_markers = [
        # Просьбы о помощи
        "помоги", "помогите", "подскажи", "подскажите", "посоветуй",
        "как сделать", "как настроить", "как исправить", "как починить",
        "как установить", "как запустить", "как включить", "как выключить",
        "как убрать", "как добавить", "как удалить", "как обновить",
        # Проблемы
        "не работает", "не запускается", "не включается", "не открывается",
        "вылетает", "крашится", "лагает", "тормозит", "фризит", "глючит",
        "ошибка", "проблема", "баг", "issue", "error",
        # Выбор/сравнение
        "что лучше", "что выбрать", "какой лучше", "какую выбрать",
        "стоит ли", "имеет смысл", "есть смысл",
        # Технические вопросы
        "почему", "зачем", "для чего", "в чём разница", "чем отличается",
        "какие характеристики", "какие параметры", "какие настройки",
        "сколько стоит", "где купить", "где скачать", "где найти",
        # Конкретные темы
        "видеокарт", "процессор", "оператив", "ssd", "hdd", "монитор",
        "драйвер", "windows", "linux", "steam", "deck", "игр",
        "fps", "разгон", "температур", "охлаждени", "питани",
        # Явные вопросы
        "кто знает", "кто-нибудь", "может кто", "есть у кого",
        "у кого было", "сталкивался кто", "решил кто",
    ]
    
    # Если есть маркер реального вопроса — это реальный вопрос
    for marker in real_question_markers:
        if marker in text_lower:
            return True
    
    # Проверяем длину и структуру
    # Длинный вопрос (>30 символов) с вопросительным знаком — скорее всего реальный
    if len(text_lower) > 30 and "?" in text:
        # Но фильтруем явный флуд/мусор
        garbage_patterns = [
            "как дела", "как сам", "как ты", "как оно", "как жизнь",
            "чё как", "что как", "ну как", "а как", "и как",
            "кто ты", "ты кто", "ты чё", "ты что",
            "с помидор", "с огурц", "с картош",  # мемные вопросы
        ]
        for garbage in garbage_patterns:
            if garbage in text_lower:
                return False
        return True
    
    # Короткий вопрос без маркеров — скорее всего не стоит отвечать
    return False


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
    """
    if msg.text and msg.text.startswith('/'):
        return
    
    # Собираем информацию для логирования
    topic_id = getattr(msg, 'message_thread_id', None)
    is_forum = getattr(msg.chat, 'is_forum', False)
    user_tag = f"@{msg.from_user.username}" if msg.from_user.username else f"id:{msg.from_user.id}"
    
    # Логируем входящее сообщение
    logger.info(
        f"[QNA IN] chat={msg.chat.id} | type={msg.chat.type} | forum={is_forum} | "
        f"topic={topic_id} | user={user_tag} | msg_id={msg.message_id} | "
        f"text=\"{msg.text[:40] if msg.text else ''}...\""
    )
    
    if not await _should_reply(msg):
        return

    text = msg.text or ""
    async_session = get_session()
    user = await ensure_user(msg.from_user)

    logger.info(f"[QNA PROCESS] Обрабатываем от {user_tag}: \"{text[:50]}...\"")

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

        # Если в личных сообщениях, используем историю диалога для контекста
        if msg.chat.type == "private":
            # Генерируем ответ с учётом истории диалога в ЛС
            # **Validates: Requirements 14.4**
            reply = await generate_private_reply(
                user_text=text_with_context,
                username=msg.from_user.username,
                user_id=msg.from_user.id,
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
                chat_context=games_context,
                topic_id=topic_id  # Передаём ID топика для корректной работы памяти
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
        sent_message = None
        if not voice_sent:
            logger.info(
                f"[QNA SEND] chat={msg.chat.id} | topic={topic_id} | "
                f"forum={is_forum} | reply_to={msg.message_id} | len={len(reply)}"
            )
            try:
                sent_message = await msg.reply(reply, disable_web_page_preview=True)
                logger.info(f"[QNA OK] Ответ отправлен в chat={msg.chat.id}, topic={topic_id}")
            except TelegramBadRequest as e:
                error_msg = str(e).lower()
                logger.error(
                    f"[QNA ERROR] TelegramBadRequest: {e} | chat={msg.chat.id} | "
                    f"topic={topic_id} | forum={is_forum}"
                )
                if "thread not found" in error_msg or "message to reply not found" in error_msg:
                    # Пробуем отправить без reply_to
                    logger.info(f"[QNA FALLBACK] Пробуем send_message: chat={msg.chat.id}, topic={topic_id}")
                    try:
                        sent_message = await msg.bot.send_message(
                            chat_id=msg.chat.id,
                            text=reply,
                            message_thread_id=topic_id,
                            disable_web_page_preview=True
                        )
                        logger.info(f"[QNA FALLBACK OK] send_message успешен")
                    except TelegramBadRequest as fallback_err:
                        logger.error(f"[QNA FALLBACK FAIL] {fallback_err}")
                        return
                else:
                    raise
        
        # Логируем ответ бота в ЛС для сохранения истории диалога
        if msg.chat.type == "private" and sent_message:
            bot_username = msg.bot._me.username if msg.bot._me else "oleg_bot"
            await _log_bot_response(
                chat_id=msg.chat.id,
                message_id=sent_message.message_id,
                text=reply,
                bot_username=bot_username
            )

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
    Удаляет историю диалога для текущего пользователя.
    """
    if msg.chat.type != 'private':
        await msg.reply("Эту команду можно использовать только в личных сообщениях.")
        return

    async_session = get_session()
    try:
        async with async_session() as session:
            from sqlalchemy import delete
            # Удаляем историю сообщений в ЛС (chat_id == user_id для личных чатов)
            result = await session.execute(
                delete(MessageLog).where(MessageLog.chat_id == msg.from_user.id)
            )
            deleted_count = result.rowcount
            await session.commit()
            logger.info(f"Reset context for user {msg.from_user.id}: deleted {deleted_count} messages")
        
        await msg.reply("Контекст диалога сброшен. Олег теперь не помнит, что ты тролль.")
    except Exception as e:
        logger.error(f"Failed to reset context for user {msg.from_user.id}: {e}")
        await msg.reply("Не удалось сбросить контекст. Попробуй позже.")


# Обработчик голосовых перенесён в app/handlers/voice.py

