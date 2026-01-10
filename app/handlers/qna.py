"""Обработчик Q&A с личностью Олега."""

import logging
import random
import re
import asyncio
import time
from aiogram import Router, F, Bot
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
from app.utils import utc_now, safe_reply

logger = logging.getLogger(__name__)

router = Router()


async def keep_typing(bot: Bot, chat_id: int, stop_event: asyncio.Event, thread_id: int = None):
    """
    Периодически отправляет статус 'typing' пока не установлен stop_event.
    Telegram сбрасывает статус через 5 секунд, поэтому обновляем каждые 4 секунды.
    
    Args:
        bot: Bot instance
        chat_id: ID чата
        stop_event: Event для остановки typing
        thread_id: ID топика для супергрупп с форумами (message_thread_id)
    """
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id, "typing", message_thread_id=thread_id)
        except Exception:
            pass  # Игнорируем ошибки
        await asyncio.sleep(4)


# Дебаунс для сообщений — если юзер шлёт несколько сообщений подряд, отвечаем только на последнее
# Ключ: (chat_id, user_id), значение: (message_id, timestamp, asyncio.Task)
_pending_messages: dict[tuple[int, int], tuple[int, float, asyncio.Task | None]] = {}
_DEBOUNCE_DELAY = 2.0  # Ждём 2 секунды перед ответом

# Глобальный троттлинг на уровне чата — не больше 1 ответа в N секунд
# Ключ: chat_id, значение: timestamp последнего ответа
_chat_last_response: dict[int, float] = {}
_CHAT_THROTTLE_DELAY = 3.0  # Минимум 3 секунды между ответами в одном чате

# Очередь сообщений на обработку для каждого чата
# Ключ: chat_id, значение: (message, timestamp)
_chat_pending_queue: dict[int, tuple[Message, float]] = {}
_chat_processing_lock: dict[int, asyncio.Lock] = {}


async def _get_chat_context(msg: Message) -> str | None:
    """
    Получает контекст чата для передачи в LLM.
    
    Включает: название чата, описание (если есть), тип чата, текущий топик.
    Это помогает боту понимать где он находится и адаптировать ответы.
    
    Args:
        msg: Сообщение из чата
        
    Returns:
        Строка с контекстом чата или None для личных сообщений
    """
    if msg.chat.type == "private":
        return None
    
    context_parts = []
    
    # Название чата
    if msg.chat.title:
        context_parts.append(f"Название чата: «{msg.chat.title}»")
    
    # Тип чата
    chat_type_map = {
        "group": "обычная группа",
        "supergroup": "супергруппа",
    }
    chat_type = chat_type_map.get(msg.chat.type, msg.chat.type)
    if msg.chat.is_forum:
        chat_type = "форум с топиками"
    context_parts.append(f"Тип: {chat_type}")
    
    # Информация о текущем топике (для форумов)
    topic_id = getattr(msg, 'message_thread_id', None)
    if msg.chat.is_forum and topic_id:
        from app.services.sdoc_service import SDOC_TOPICS
        topic_info = SDOC_TOPICS.get(topic_id)
        if topic_info:
            context_parts.append(f"ТЕКУЩИЙ ТОПИК: «{topic_info['name']}» (id: {topic_id})")
        else:
            context_parts.append(f"Текущий топик ID: {topic_id}")
    elif msg.chat.is_forum and not topic_id:
        context_parts.append("Текущий топик: General (основной)")
    
    # Пробуем получить описание чата
    try:
        full_chat = await msg.bot.get_chat(msg.chat.id)
        if full_chat.description:
            # Обрезаем если слишком длинное
            desc = full_chat.description[:200]
            if len(full_chat.description) > 200:
                desc += "..."
            context_parts.append(f"Описание: {desc}")
    except Exception:
        pass  # Не критично если не получилось
    
    if not context_parts:
        return None
    
    return "ИНФОРМАЦИЯ О ЧАТЕ: " + " | ".join(context_parts)


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
    # В группах игнорируем /start без @username бота
    if msg.chat.type != "private":
        # Проверяем, адресована ли команда именно этому боту
        if msg.text and msg.bot._me:
            bot_username = msg.bot._me.username
            # /start@OlegBot — обрабатываем, /start — игнорируем
            if bot_username and f"@{bot_username.lower()}" not in msg.text.lower():
                return  # Не наша команда, игнорируем
        # В группе — короткое представление
        await msg.reply("Я Олег. Чё надо? Пиши по делу.")
    else:
        # В ЛС — дружелюбное приветствие без лишней инфы
        welcome_text = (
            "Здарова! Я Олег — твой персональный кибер-кентуха.\n\n"
            "Пиши что хочешь — отвечу, помогу, поясню за железо. "
            "Можешь скинуть фото — проанализирую, голосовое — распознаю.\n\n"
            "Если нужна админка для твоих чатов — жми /admin\n"
            "Справка по командам — /help"
        )
        await msg.reply(welcome_text)


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


@router.message(F.text, ~F.text.startswith("/"))
async def general_qna(msg: Message):
    """
    Общий обработчик Q&A.
    Не обрабатывает команды (начинающиеся с /).
    """
    
    # Проверяем, не замучена ли группа владельцем
    from app.handlers.owner_panel import is_group_muted
    if is_group_muted(msg.chat.id):
        return
    
    # Собираем информацию для логирования
    topic_id = getattr(msg, 'message_thread_id', None)
    is_forum = getattr(msg.chat, 'is_forum', False)
    user_tag = f"@{msg.from_user.username}" if msg.from_user.username else f"id:{msg.from_user.id}"
    
    # Детальная диагностика топика
    logger.debug(
        f"[QNA DEBUG] raw message_thread_id={msg.message_thread_id if hasattr(msg, 'message_thread_id') else 'NO_ATTR'}, "
        f"is_topic_message={getattr(msg, 'is_topic_message', 'NO_ATTR')}, "
        f"reply_to={msg.reply_to_message.message_id if msg.reply_to_message else None}"
    )
    
    # Логируем входящее сообщение
    logger.info(
        f"[QNA IN] chat={msg.chat.id} | type={msg.chat.type} | forum={is_forum} | "
        f"topic={topic_id} | user={user_tag} | msg_id={msg.message_id} | "
        f"text=\"{msg.text[:40] if msg.text else ''}...\""
    )
    
    if not await _should_reply(msg):
        return
    
    chat_id = msg.chat.id
    current_time = time.time()
    
    # Троттлинг на уровне чата — не спамим ответами
    # Если недавно отвечали в этом чате, пропускаем (кроме прямых обращений)
    is_direct_mention = False
    if msg.text:
        text_lower = msg.text.lower()
        bot_username = msg.bot._me.username if msg.bot._me else None
        is_direct_mention = (
            (bot_username and f"@{bot_username.lower()}" in text_lower) or
            any(re.search(rf'\b{t}\b', text_lower) for t in ["олег", "олега", "олегу"])
        )
    
    # Для прямых обращений — отвечаем всегда
    # Для остальных — троттлинг
    if not is_direct_mention:
        last_response_time = _chat_last_response.get(chat_id, 0)
        time_since_last = current_time - last_response_time
        
        if time_since_last < _CHAT_THROTTLE_DELAY:
            # Сохраняем в очередь — может ответим позже
            _chat_pending_queue[chat_id] = (msg, current_time)
            logger.debug(f"[THROTTLE] Пропускаем msg_id={msg.message_id}, недавно отвечали ({time_since_last:.1f}s ago)")
            return
    
    # Получаем или создаём лок для этого чата
    if chat_id not in _chat_processing_lock:
        _chat_processing_lock[chat_id] = asyncio.Lock()
    
    # Пробуем захватить лок (без ожидания)
    lock = _chat_processing_lock[chat_id]
    if lock.locked():
        # Уже обрабатываем сообщение в этом чате — сохраняем в очередь
        _chat_pending_queue[chat_id] = (msg, current_time)
        logger.debug(f"[THROTTLE] Чат занят, msg_id={msg.message_id} в очереди")
        return
    
    async with lock:
        await _process_qna_message(msg)
        _chat_last_response[chat_id] = time.time()


async def _process_qna_message(msg: Message):
    """Обработка сообщения после дебаунса."""
    user_tag = f"@{msg.from_user.username}" if msg.from_user.username else f"id:{msg.from_user.id}"
    text = msg.text or ""
    topic_id = getattr(msg, 'message_thread_id', None)
    is_forum = getattr(msg.chat, 'is_forum', False)
    async_session = get_session()
    user = await ensure_user(msg.from_user)

    logger.info(f"[QNA PROCESS] Обрабатываем от {user_tag}: \"{text[:50]}...\"")
    
    # Запускаем фоновую задачу для поддержания статуса "печатает..."
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(msg.bot, msg.chat.id, stop_typing, topic_id))

    try:
        # Получаем контекст чата (название, описание, тип)
        chat_info_context = await _get_chat_context(msg)
        
        # Проверяем, спрашивает ли про игры — даём контекст ИИ
        games_context = GAMES_AI_CONTEXT if _is_games_help_request(text) else None
        
        # Объединяем контексты
        full_chat_context = None
        if chat_info_context or games_context:
            parts = [p for p in [chat_info_context, games_context] if p]
            full_chat_context = "\n".join(parts)

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
                chat_context=full_chat_context
            )
        else:
            # Для групповых чатов используем функцию с контекстом из памяти
            # Use text_with_context to include reply context for AI
            # **Validates: Requirements 14.4**
            reply = await generate_reply_with_context(
                user_text=text_with_context,
                username=msg.from_user.username,
                chat_id=msg.chat.id,
                chat_context=full_chat_context,
                topic_id=topic_id,  # Передаём ID топика для корректной работы памяти
                user_id=msg.from_user.id  # ID пользователя для профиля
            )

        # Если reply None - ошибка уже была показана недавно, не спамим
        if reply is None:
            logger.debug(f"Suppressed duplicate error response for chat {msg.chat.id}")
            return

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
            # Детальная диагностика перед отправкой
            logger.info(
                f"[QNA SEND] chat={msg.chat.id} | topic={topic_id} | "
                f"forum={is_forum} | reply_to={msg.message_id} | len={len(reply)} | "
                f"chat_type={msg.chat.type}"
            )
            
            # Для форумов проверяем что topic_id корректный
            if is_forum and topic_id is None:
                logger.warning(
                    f"[QNA WARN] Форум без topic_id! chat={msg.chat.id}, "
                    f"возможно General топик скрыт"
                )
            
            try:
                # Конвертируем Markdown в HTML
                from app.utils import markdown_to_html
                formatted_reply = markdown_to_html(reply)
                
                if is_forum:
                    # Используем reply_parameters — работает для всех топиков включая старые
                    logger.info(f"[QNA] Форум: отправка через reply_parameters (topic={topic_id})")
                    import httpx
                    bot_token = msg.bot.token
                    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    payload = {
                        "chat_id": msg.chat.id,
                        "text": formatted_reply,
                        "parse_mode": "HTML",
                        "reply_parameters": {
                            "message_id": msg.message_id,
                            "chat_id": msg.chat.id
                        },
                        "disable_web_page_preview": True
                    }
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(api_url, json=payload)
                        result = resp.json()
                        if result.get("ok"):
                            logger.info(f"[QNA OK] Ответ отправлен через reply_parameters")
                            sent_message = None
                        else:
                            error_desc = result.get("description", "Unknown error")
                            logger.error(f"[QNA ERROR] API error: {error_desc}")
                            # Если ошибка парсинга — пробуем без форматирования
                            if "can't parse" in error_desc.lower():
                                payload["text"] = reply
                                del payload["parse_mode"]
                                resp = await client.post(api_url, json=payload)
                                if resp.json().get("ok"):
                                    logger.info(f"[QNA OK] Ответ отправлен без форматирования")
                                    sent_message = None
                                else:
                                    raise TelegramBadRequest(
                                        method="sendMessage",
                                        message=error_desc
                                    )
                            else:
                                raise TelegramBadRequest(
                                    method="sendMessage",
                                    message=error_desc
                                )
                else:
                    try:
                        sent_message = await msg.reply(formatted_reply, parse_mode="HTML", disable_web_page_preview=True)
                    except TelegramBadRequest as parse_err:
                        if "can't parse" in str(parse_err).lower():
                            # Ошибка парсинга — отправляем без форматирования
                            logger.warning(f"[QNA] Parse error, sending without formatting")
                            sent_message = await msg.reply(reply, disable_web_page_preview=True)
                        else:
                            raise
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
                        # Если topic_id есть — отправляем в этот топик
                        # Если topic_id None и это форум — пробуем без thread_id (General)
                        thread_id_to_use = topic_id if topic_id else None
                        sent_message = await msg.bot.send_message(
                            chat_id=msg.chat.id,
                            text=formatted_reply,
                            parse_mode="HTML",
                            message_thread_id=thread_id_to_use,
                            disable_web_page_preview=True
                        )
                        logger.info(f"[QNA FALLBACK OK] send_message успешен (thread={thread_id_to_use})")
                    except TelegramBadRequest as fallback_err:
                        logger.error(f"[QNA FALLBACK FAIL] {fallback_err}")
                        # Последняя попытка — отправить в чат без указания топика
                        if is_forum and topic_id:
                            try:
                                logger.info(f"[QNA FALLBACK2] Пробуем без thread_id")
                                sent_message = await msg.bot.send_message(
                                    chat_id=msg.chat.id,
                                    text=reply,  # Без форматирования на последней попытке
                                    disable_web_page_preview=True
                                )
                                logger.info(f"[QNA FALLBACK2 OK] Отправлено без thread_id")
                            except TelegramBadRequest as final_err:
                                logger.error(f"[QNA FALLBACK2 FAIL] {final_err}")
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
            try:
                await safe_reply(msg, f"💡 Рекомендация: {recommendation}")
            except Exception:
                pass  # Игнорируем ошибки отправки рекомендации

    except Exception as e:
        logger.error(f"Ошибка при генерации ответа: {e}")
        try:
            await safe_reply(msg, "Сервер сломался. Но только ненадолго, обещаю.")
        except Exception:
            pass  # Игнорируем если не можем ответить
    finally:
        # Останавливаем статус "печатает..."
        stop_typing.set()
        typing_task.cancel()
        try:
            await typing_task
        except asyncio.CancelledError:
            pass


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


def format_whois_profile(profile, username: str) -> list[str]:
    """
    Форматирует профиль пользователя для вывода в /whois.
    
    Args:
        profile: UserProfile объект или None
        username: Имя пользователя для отображения
        
    Returns:
        Список строк для вывода
    """
    lines = []
    
    if not profile:
        return lines
    
    # Личная информация
    personal = []
    if profile.name:
        personal.append(f"Имя: {profile.name}")
    if profile.age:
        personal.append(f"{profile.age} лет")
    if profile.birthday:
        personal.append(f"🎂 {profile.birthday}")
    if profile.city:
        personal.append(f"📍 {profile.city}")
    if profile.job:
        personal.append(f"💼 {profile.job}")
    if personal:
        lines.append("\n👤 " + " • ".join(personal))
    
    # Железо
    hardware = []
    if profile.gpu:
        hardware.append(f"GPU: {profile.gpu}")
    if profile.cpu:
        hardware.append(f"CPU: {profile.cpu}")
    if profile.ram:
        hardware.append(f"RAM: {profile.ram}")
    if hardware:
        lines.append("\n🖥 <b>Сетап:</b> " + " | ".join(hardware))
    
    # Устройства
    devices = []
    if profile.steam_deck:
        deck_str = "Steam Deck"
        if profile.steam_deck_mods:
            deck_str += f" ({', '.join(profile.steam_deck_mods[:3])})"
        devices.append(deck_str)
    if profile.laptop:
        devices.append(f"💻 {profile.laptop}")
    if profile.console:
        devices.append(f"🎮 {profile.console}")
    if devices:
        lines.append("📱 " + " | ".join(devices))
    
    # ОС
    if profile.os or profile.distro:
        os_str = profile.distro or profile.os
        if profile.de:
            os_str += f" + {profile.de}"
        lines.append(f"💿 {os_str}")
    
    # Предпочтения
    if profile.brand_preference:
        lines.append(f"❤️ Фанат {profile.brand_preference.upper()}")
    
    # Экспертиза
    if profile.expertise:
        lines.append(f"🧠 Шарит в: {', '.join(profile.expertise[:4])}")
    
    # Игры
    if profile.games:
        lines.append(f"🎮 Играет: {', '.join(profile.games[:5])}")
    
    # Хобби
    if profile.hobbies:
        lines.append(f"🎯 Хобби: {', '.join(profile.hobbies[:4])}")
    
    # Языки программирования
    if profile.languages:
        lines.append(f"💻 Кодит на: {', '.join(profile.languages[:4])}")
    
    # Питомцы
    if profile.pets:
        lines.append(f"🐾 Питомцы: {', '.join(profile.pets)}")
    
    # Текущие проблемы
    if profile.current_problems:
        lines.append(f"\n⚠️ <b>Последняя проблема:</b> {profile.current_problems[-1][:80]}...")
    
    return lines


@router.message(Command("whois"))
async def cmd_whois(msg: Message):
    """
    Показывает досье на пользователя — информацию которую Олег собрал из сообщений.
    Использование: /whois (реплай) или /whois @username или /whois (свой профиль)
    """
    from app.services.user_memory import user_memory
    from app.database.session import get_session
    from app.database.models import MessageLog, User
    from sqlalchemy import select, func
    
    # Определяем целевого пользователя
    target_user_id = None
    target_username = None
    
    if msg.reply_to_message and msg.reply_to_message.from_user:
        # Реплай на сообщение
        target_user_id = msg.reply_to_message.from_user.id
        target_username = msg.reply_to_message.from_user.username or msg.reply_to_message.from_user.first_name
    else:
        # Парсим аргументы команды
        args = msg.text.split(maxsplit=1)
        if len(args) > 1:
            username_arg = args[1].strip().lstrip('@')
            if username_arg:
                # Ищем по username в БД
                async with get_session()() as session:
                    result = await session.execute(
                        select(User).where(User.username == username_arg)
                    )
                    found_user = result.scalars().first()
                    if found_user:
                        target_user_id = found_user.tg_user_id
                        target_username = found_user.username or found_user.first_name
                    else:
                        await msg.reply(f"Не нашёл @{username_arg} в базе.")
                        return
        else:
            # Свой профиль
            target_user_id = msg.from_user.id
            target_username = msg.from_user.username or msg.from_user.first_name
    
    if not target_user_id:
        await msg.reply("Ответь на сообщение или укажи @username")
        return
    
    # Получаем профиль из памяти Олега
    profile = await user_memory.get_profile(msg.chat.id, target_user_id)
    
    # Получаем базовую статистику из БД
    async with get_session()() as session:
        db_user_result = await session.execute(
            select(User).where(User.tg_user_id == target_user_id)
        )
        db_user = db_user_result.scalars().first()
        
        # Получаем игровую статистику
        from app.database.models import GameStat
        game_stat_result = await session.execute(
            select(GameStat).where(GameStat.user_id == target_user_id)
        )
        game_stat = game_stat_result.scalars().first()
        
        msg_count = await session.scalar(
            select(func.count(MessageLog.id)).where(
                MessageLog.chat_id == msg.chat.id,
                MessageLog.user_id == target_user_id
            )
        )
        
        first_msg_date = await session.scalar(
            select(func.min(MessageLog.created_at)).where(
                MessageLog.chat_id == msg.chat.id,
                MessageLog.user_id == target_user_id
            )
        )
    
    # Формируем досье
    name = target_username or f"ID:{target_user_id}"
    lines = [f"📋 <b>Досье Олега: @{name}</b>"]
    
    if not profile and msg_count == 0:
        lines.append("\n<i>🔍 Олег ещё не собрал информацию об этом человеке. Чем больше общаешься — тем полнее досье.</i>")
        await msg.reply("\n".join(lines), parse_mode="HTML")
        return
    
    # Добавляем информацию из профиля
    profile_lines = format_whois_profile(profile, name)
    lines.extend(profile_lines)
    
    # Статистика
    lines.append("\n📊 <b>Статистика (по данным Олега):</b>")
    if msg_count:
        lines.append(f"   💬 {msg_count} сообщений в этом чате")
    if first_msg_date:
        lines.append(f"   📅 Олег видит с {first_msg_date.strftime('%d.%m.%Y')}")
    
    # Игровая статистика
    if game_stat:
        game_stats = []
        if game_stat.pp_size and game_stat.pp_size > 0:
            game_stats.append(f"📏 {game_stat.pp_size} см")
        if game_stat.coins and game_stat.coins > 0:
            game_stats.append(f"🪙 {game_stat.coins}")
        if db_user and db_user.reputation and db_user.reputation != 0:
            rep_emoji = "⭐" if db_user.reputation > 0 else "💩"
            game_stats.append(f"{rep_emoji} {db_user.reputation}")
        if game_stats:
            lines.append(f"   🎰 {' | '.join(game_stats)}")
    
    # Статус брака (Requirements 9.6)
    from app.handlers.marriages import get_spouse_id
    spouse_id = await get_spouse_id(target_user_id, msg.chat.id)
    if spouse_id:
        # Получаем имя супруга
        async with get_session()() as session:
            spouse_result = await session.execute(
                select(User).where(User.tg_user_id == spouse_id)
            )
            spouse_user = spouse_result.scalars().first()
            spouse_name = spouse_user.username or spouse_user.first_name if spouse_user else f"ID:{spouse_id}"
        lines.append(f"   💍 В браке с @{spouse_name}")
    
    # Подсказка - показываем только если профиль реально пустой
    def has_profile_data(p) -> bool:
        if not p:
            return False
        # Проверяем все значимые поля профиля
        return any([
            p.name, p.gpu, p.cpu, p.ram, p.os, p.distro,
            p.games, p.expertise, p.hobbies, p.languages,
            p.city, p.job, p.steam_deck, p.laptop, p.console,
            p.brand_preference, p.age, p.birthday, p.pets,
            p.current_problems
        ])
    
    if not has_profile_data(profile):
        lines.append("\n<i>🔍 Олег ещё собирает информацию. Чем больше общаешься — тем полнее досье.</i>")
    
    # Кнопка очистки для своего профиля
    if target_user_id == msg.from_user.id and profile:
        lines.append("\n<i>Хочешь стереть? /clearprofile</i>")
    
    await msg.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("mood"))
async def cmd_mood(msg: Message):
    """
    Показывает текущее настроение Олега.
    """
    logger.info(f"[CMD] /mood handler called by {msg.from_user.id}")
    from app.services.mood import mood_service
    
    mood, trigger = mood_service.get_current_mood()
    energy = mood_service.get_energy_level()
    
    # Эмодзи для энергии
    if energy >= 0.8:
        energy_emoji = "⚡"
        energy_text = "на максимуме"
    elif energy >= 0.5:
        energy_emoji = "🔋"
        energy_text = "норм"
    else:
        energy_emoji = "🪫"
        energy_text = "на нуле"
    
    # Эмодзи для настроения
    mood_emojis = {
        "сонный": "😴",
        "бодрый": "😊",
        "нормальный": "😐",
        "расслабленный": "😌",
        "раздражённый": "😤",
        "весёлый": "😄",
        "задумчивый": "🤔",
        "лаконичный": "🤐",
        "экспертный": "🧐",
        "дерзкий": "😏",
    }
    
    # Ищем подходящий эмодзи
    mood_emoji = "🤖"
    for key, emoji in mood_emojis.items():
        if key in mood.lower():
            mood_emoji = emoji
            break
    
    lines = [
        f"{mood_emoji} <b>Настроение Олега:</b> {mood}",
        f"{energy_emoji} <b>Энергия:</b> {energy_text} ({int(energy * 100)}%)",
    ]
    
    if trigger:
        lines.append(f"\n💬 {trigger}")
    
    await msg.reply("\n".join(lines), parse_mode="HTML")


@router.message(Command("clearprofile"))
async def cmd_clearprofile(msg: Message):
    """
    Очищает профиль пользователя из памяти Олега.
    Использование: /clearprofile — очистить свой профиль
    """
    logger.info(f"[CMD] /clearprofile handler called by {msg.from_user.id}")
    from app.services.user_memory import user_memory
    from app.services.vector_db import vector_db
    
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    
    try:
        # Удаляем профиль из кэша
        cache_key = user_memory._get_cache_key(chat_id, user_id)
        if cache_key in user_memory._cache:
            del user_memory._cache[cache_key]
        if cache_key in user_memory._cache_timestamps:
            del user_memory._cache_timestamps[cache_key]
        
        # Удаляем из ChromaDB
        collection_name = user_memory._get_collection_name(chat_id)
        try:
            vector_db.delete_facts(
                collection_name=collection_name,
                where={"user_id": user_id, "type": "profile"}
            )
        except Exception as e:
            logger.debug(f"Profile deletion from ChromaDB: {e}")
        
        username = msg.from_user.username or msg.from_user.first_name
        await msg.reply(
            f"🗑 Профиль @{username} очищен.\n\n"
            "Олег забыл всё что знал о тебе. "
            "Новые факты будут собираться заново из твоих сообщений."
        )
        logger.info(f"Profile cleared for user {user_id} in chat {chat_id}")
    except Exception as e:
        logger.error(f"Error clearing profile: {e}")
        await msg.reply("❌ Не удалось очистить профиль. Попробуй позже.")


# Доступные поля для редактирования профиля
EDITABLE_PROFILE_FIELDS = {
    "имя": "name",
    "name": "name",
    "город": "city",
    "city": "city",
    "работа": "job",
    "job": "job",
    "возраст": "age",
    "age": "age",
    "gpu": "gpu",
    "видеокарта": "gpu",
    "cpu": "cpu",
    "процессор": "cpu",
    "ram": "ram",
    "память": "ram",
    "os": "os",
    "ос": "os",
    "distro": "distro",
    "дистрибутив": "distro",
    "ноутбук": "laptop",
    "laptop": "laptop",
}


@router.message(Command("editprofile"))
async def cmd_editprofile(msg: Message):
    """
    Редактирует поле профиля пользователя.
    
    Использование:
    /editprofile — показать доступные поля
    /editprofile gpu RTX 4090 — установить GPU
    /editprofile город Москва — установить город
    /editprofile gpu — удалить значение GPU
    """
    from app.services.user_memory import user_memory, UserProfile
    
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    username = msg.from_user.username or msg.from_user.first_name
    
    # Парсим аргументы
    args = msg.text.split(maxsplit=2)
    
    if len(args) < 2:
        # Показываем справку
        fields_list = ", ".join(sorted(set(EDITABLE_PROFILE_FIELDS.keys())))
        await msg.reply(
            "✏️ <b>Редактирование профиля</b>\n\n"
            "<b>Использование:</b>\n"
            "<code>/editprofile поле значение</code> — установить\n"
            "<code>/editprofile поле</code> — удалить значение\n\n"
            f"<b>Доступные поля:</b>\n{fields_list}\n\n"
            "<b>Примеры:</b>\n"
            "<code>/editprofile gpu RTX 4090</code>\n"
            "<code>/editprofile город Питер</code>\n"
            "<code>/editprofile имя Вася</code>\n"
            "<code>/editprofile gpu</code> — удалить GPU",
            parse_mode="HTML"
        )
        return
    
    field_name = args[1].lower()
    value = args[2].strip() if len(args) > 2 else None
    
    # Проверяем поле
    if field_name not in EDITABLE_PROFILE_FIELDS:
        await msg.reply(
            f"❌ Неизвестное поле: {field_name}\n\n"
            f"Доступные: {', '.join(sorted(set(EDITABLE_PROFILE_FIELDS.keys())))}"
        )
        return
    
    profile_field = EDITABLE_PROFILE_FIELDS[field_name]
    
    try:
        # Получаем или создаём профиль
        profile = await user_memory.get_profile(chat_id, user_id)
        if not profile:
            profile = UserProfile(user_id=user_id, username=username)
        
        # Обновляем поле
        old_value = getattr(profile, profile_field, None)
        
        if profile_field == "age" and value:
            # Возраст — число
            try:
                value = int(value)
                if not (10 <= value <= 100):
                    await msg.reply("❌ Возраст должен быть от 10 до 100")
                    return
            except ValueError:
                await msg.reply("❌ Возраст должен быть числом")
                return
        
        setattr(profile, profile_field, value)
        
        # Сохраняем
        await user_memory.save_profile(chat_id, user_id, profile)
        
        # Формируем ответ
        field_display = field_name.capitalize()
        if value:
            if old_value:
                await msg.reply(f"✅ {field_display}: {old_value} → {value}")
            else:
                await msg.reply(f"✅ {field_display}: {value}")
        else:
            if old_value:
                await msg.reply(f"🗑 {field_display} удалено (было: {old_value})")
            else:
                await msg.reply(f"ℹ️ {field_display} и так пустое")
        
        logger.info(f"Profile field {profile_field} updated for user {user_id}: {old_value} -> {value}")
        
    except Exception as e:
        logger.error(f"Error editing profile: {e}")
        await msg.reply("❌ Не удалось обновить профиль. Попробуй позже.")


@router.message(Command("birthday"))
async def cmd_birthday(msg: Message):
    """
    Устанавливает день рождения для поздравлений.
    
    Использование:
    /birthday DD.MM — установить дату (например: /birthday 15.03)
    /birthday — показать текущую дату
    /birthday удалить — удалить дату
    """
    from app.services.user_memory import user_memory, UserProfile
    
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    username = msg.from_user.username or msg.from_user.first_name
    
    args = msg.text.split(maxsplit=1)
    
    # Получаем текущий профиль
    profile = await user_memory.get_profile(chat_id, user_id)
    
    if len(args) < 2:
        # Показываем текущую дату
        if profile and profile.birthday:
            chat_info = ""
            if profile.birthday_chat_id:
                chat_info = f"\n📍 Чат для поздравлений: {profile.birthday_chat_id}"
            await msg.reply(
                f"🎂 Твой день рождения: <b>{profile.birthday}</b>{chat_info}\n\n"
                "Олег поздравит тебя в 10:00 по Москве.\n"
                "Удалить: <code>/birthday удалить</code>",
                parse_mode="HTML"
            )
        else:
            await msg.reply(
                "🎂 <b>Установка дня рождения</b>\n\n"
                "Использование: <code>/birthday DD.MM</code>\n"
                "Пример: <code>/birthday 15.03</code>\n\n"
                "Олег поздравит тебя в этом чате в 10:00 по Москве.",
                parse_mode="HTML"
            )
        return
    
    arg = args[1].strip().lower()
    
    # Удаление
    if arg in ("удалить", "delete", "remove", "clear"):
        if profile:
            profile.birthday = None
            profile.birthday_chat_id = None
            await user_memory.save_profile(chat_id, user_id, profile)
        await msg.reply("🗑 День рождения удалён. Олег больше не будет поздравлять.")
        return
    
    # Парсим дату DD.MM
    import re
    match = re.match(r'^(\d{1,2})[./](\d{1,2})$', arg)
    if not match:
        await msg.reply(
            "❌ Неверный формат. Используй: <code>/birthday DD.MM</code>\n"
            "Пример: <code>/birthday 15.03</code>",
            parse_mode="HTML"
        )
        return
    
    day, month = int(match.group(1)), int(match.group(2))
    
    # Валидация
    if not (1 <= month <= 12):
        await msg.reply("❌ Месяц должен быть от 1 до 12")
        return
    
    days_in_month = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if not (1 <= day <= days_in_month[month - 1]):
        await msg.reply(f"❌ В {month}-м месяце нет {day}-го дня")
        return
    
    # Форматируем с ведущими нулями
    birthday_str = f"{day:02d}.{month:02d}"
    
    # Сохраняем
    success = await user_memory.set_birthday(
        chat_id=chat_id,
        user_id=user_id,
        username=username,
        birthday=birthday_str,
        birthday_chat_id=chat_id  # Поздравлять в этом чате
    )
    
    if success:
        await msg.reply(
            f"🎂 День рождения установлен: <b>{birthday_str}</b>\n\n"
            f"Олег поздравит тебя в этом чате в 10:00 по Москве.",
            parse_mode="HTML"
        )
        logger.info(f"Birthday set for user {user_id}: {birthday_str}")
    else:
        await msg.reply("❌ Не удалось сохранить. Попробуй позже.")


@router.message(Command("limit"))
async def cmd_limit(msg: Message):
    """
    Показывает лимит запросов.
    """
    from app.services.token_limiter import token_limiter
    from app.config import settings
    
    if not settings.antispam_enabled:
        await msg.reply("Лимиты отключены.")
        return
    
    user_id = msg.from_user.id
    stats = token_limiter.get_user_stats(user_id)
    
    if stats['is_whitelisted']:
        await msg.reply("✨ У тебя безлимит!")
        return
    
    await msg.reply(
        f"📊 <b>Лимиты</b>\n"
        f"В минуту: {stats['minute_requests']}/{stats['burst_limit']} (сброс {stats['minute_reset_secs']}с)\n"
        f"В час: {stats['hour_requests']}/{stats['hourly_limit']} (сброс {stats['hour_reset_mins']}м)",
        parse_mode="HTML"
    )
