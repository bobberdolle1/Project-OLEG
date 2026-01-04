"""
Обработчик команд цитатника (OlegQuotes).

Fortress Update v6.0: Enhanced quote generation with gradient backgrounds,
quote chains, and roast mode.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
"""

import logging
from io import BytesIO
from typing import List, Optional

from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputSticker
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.session import get_session
from app.database.models import User
from app.handlers.games import ensure_user
from app.services.quote_generator import (
    quote_generator_service,
    QuoteStyle,
    QuoteTheme,
    MessageData,
    MAX_CHAIN_MESSAGES,
)
from PIL import Image
from app.services.alive_ui import alive_ui_service

logger = logging.getLogger(__name__)

router = Router()


def build_quote_keyboard(quote_id: int, likes: int = 0, dislikes: int = 0) -> InlineKeyboardMarkup:
    """Создаёт клавиатуру с кнопками лайк/дизлайк для цитаты."""
    kb = InlineKeyboardBuilder()
    like_text = f"👍 {likes}" if likes > 0 else "👍"
    dislike_text = f"👎 {dislikes}" if dislikes > 0 else "👎"
    kb.button(text=like_text, callback_data=f"quote_like:{quote_id}")
    kb.button(text=dislike_text, callback_data=f"quote_dislike:{quote_id}")
    kb.button(text="📦 В стикерпак", callback_data=f"quote_sticker:{quote_id}")
    kb.adjust(2, 1)
    return kb.as_markup()


def resize_for_sticker(image_data: bytes) -> bytes:
    """
    Ресайзит изображение для отправки как стикер.
    Telegram требует максимум 512px по одной стороне.
    
    Args:
        image_data: Исходные байты изображения
        
    Returns:
        Байты изображения в формате WebP с размером до 512px
    """
    img = Image.open(BytesIO(image_data))
    
    # Определяем новый размер (максимум 512px по большей стороне)
    max_size = 512
    width, height = img.size
    
    if width > max_size or height > max_size:
        if width > height:
            new_width = max_size
            new_height = int(height * (max_size / width))
        else:
            new_height = max_size
            new_width = int(width * (max_size / height))
        
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Сохраняем в WebP
    output = BytesIO()
    img.save(output, format='WEBP', quality=95)
    output.seek(0)
    return output.read()


async def get_user_avatar(bot, user_id: int, max_retries: int = 3) -> Optional[bytes]:
    """
    Загружает аватарку пользователя из Telegram с retry логикой.
    
    RC8: Added retry logic and improved error handling.
    Requirements: 3.1
    
    Args:
        bot: Telegram bot instance
        user_id: ID пользователя
        max_retries: Максимальное количество попыток загрузки
        
    Returns:
        Байты аватарки или None если загрузка не удалась
    """
    import asyncio
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            photos = await bot.get_user_profile_photos(user_id, limit=1)
            if photos.total_count > 0:
                photo = photos.photos[0][-1]  # Берём самое большое фото
                file = await bot.get_file(photo.file_id)
                file_bytes = await bot.download_file(file.file_path)
                avatar_data = file_bytes.read()
                
                # Validate that we got actual image data
                if avatar_data and len(avatar_data) > 0:
                    logger.debug(f"Successfully loaded avatar for user {user_id} on attempt {attempt + 1}")
                    return avatar_data
                else:
                    logger.warning(f"Empty avatar data for user {user_id} on attempt {attempt + 1}")
                    
            else:
                # User has no profile photos - this is not an error
                logger.debug(f"User {user_id} has no profile photos")
                return None
                
        except Exception as e:
            last_error = e
            logger.debug(f"Failed to get avatar for user {user_id} (attempt {attempt + 1}/{max_retries}): {e}")
            
            # Wait before retry (exponential backoff)
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
    
    # All retries failed
    if last_error:
        logger.warning(f"Failed to get avatar for user {user_id} after {max_retries} attempts: {last_error}")
    
    return None  # Placeholder will be rendered automatically by _draw_avatar


async def get_user_info(bot, chat_id: int, user) -> dict:
    """Получает расширенную информацию о пользователе."""
    info = {
        "username": user.username or user.first_name,
        "full_name": user.full_name,
        "premium_emoji": None,
        "custom_title": None,
    }
    
    # Получаем премиум эмодзи статус
    if hasattr(user, 'emoji_status') and user.emoji_status:
        info["premium_emoji"] = user.emoji_status.custom_emoji_id
    
    # Получаем кастомный титул в группе
    try:
        member = await bot.get_chat_member(chat_id, user.id)
        if hasattr(member, 'custom_title') and member.custom_title:
            info["custom_title"] = member.custom_title
    except Exception as e:
        logger.debug(f"Failed to get custom title for user {user.id}: {e}")
    
    return info


async def create_quote_image(
    text: str,
    username: str,
    timestamp: Optional[str] = None,
    avatar_data: Optional[bytes] = None,
    custom_title: Optional[str] = None,
    full_name: Optional[str] = None,
) -> BytesIO:
    """
    Создает изображение цитаты с текстом и именем пользователя.
    
    Args:
        text: Текст цитаты
        username: Имя пользователя (@username)
        timestamp: Опциональная временная метка
        avatar_data: Байты аватарки пользователя
        custom_title: Кастомный титул в группе
        full_name: Полное имя пользователя
    
    Returns:
        BytesIO объект с изображением в формате WebP
    """
    # RC8: Use default QuoteStyle which now defaults to LIGHT theme
    style = QuoteStyle()
    quote_image = await quote_generator_service.render_quote(
        text=text,
        username=username,
        style=style,
        timestamp=timestamp,
        avatar_data=avatar_data,
        custom_title=custom_title,
        full_name=full_name,
    )
    
    return BytesIO(quote_image.image_data)


async def create_quote_chain_image(messages: List[MessageData]) -> BytesIO:
    """
    Создает изображение цепочки цитат из нескольких сообщений.
    
    Fortress Update: Supports up to 10 messages in a chain.
    Requirements: 7.3, 7.5
    Property 17: Quote chain limit - max 10 messages
    
    Args:
        messages: Список сообщений для цитаты
    
    Returns:
        BytesIO объект с изображением в формате WebP
    """
    # RC8: Use default QuoteStyle which now defaults to LIGHT theme
    style = QuoteStyle()
    quote_image = await quote_generator_service.render_quote_chain(
        messages=messages,
        style=style
    )
    
    return BytesIO(quote_image.image_data)


async def create_quote_with_comment(text: str, username: str, comment: str = None) -> BytesIO:
    """
    Создает изображение цитаты с текстом, именем пользователя и комментарием Олега.
    
    Fortress Update: Uses new QuoteGeneratorService with roast mode.
    Requirements: 7.4, 7.5
    
    Args:
        text: Текст цитаты
        username: Имя пользователя
        comment: Комментарий Олега (если None, будет сгенерирован)
    
    Returns:
        BytesIO объект с изображением в формате WebP
    """
    # RC8: Use default QuoteStyle which now defaults to LIGHT theme
    style = QuoteStyle()
    quote_image = await quote_generator_service.render_roast_quote(
        text=text,
        username=username,
        style=style
    )
    
    return BytesIO(quote_image.image_data)


@router.message(Command("q"))
async def cmd_quote(msg: Message):
    """
    Команда /q - генерирует цитату из одного сообщения.
    
    Fortress Update v6.0: Enhanced with gradient backgrounds, quote chains, and roast mode.
    Requirements: 7.1, 7.3, 7.4, 7.6
    
    Использование:
    - /q (в ответ на сообщение) - создает цитату из одного сообщения
    - /q [число] (в ответ на сообщение) - создает цитату из нескольких сообщений (макс 10)
    - /q * (в ответ на сообщение) - режим прожарки с комментарием Олега
    
    Property 17: Quote chain limit - max 10 messages
    """
    logger.info(f"[QUOTE] /q command received from {msg.from_user.id} in chat {msg.chat.id}")
    
    # Проверяем включена ли функция
    from app.services.bot_config import is_feature_enabled
    if not await is_feature_enabled(msg.chat.id, "quotes"):
        return  # Молча игнорируем
    
    if not msg.reply_to_message:
        await msg.reply("❌ Нужно ответить на сообщение, чтобы сделать из него цитату.")
        return

    # Получаем текст команды
    command_text = msg.text.split(maxsplit=1)
    param = command_text[1].strip() if len(command_text) > 1 else None

    # Определяем режим работы
    if param == "*":
        # Режим прожарки (Requirement 7.4)
        await _generate_roast_quote(msg)
    elif param and param.isdigit():
        # Режим нескольких сообщений (Requirement 7.3)
        count = int(param)
        # Property 17: Enforce max 10 messages
        if count > MAX_CHAIN_MESSAGES:
            await msg.reply(f"❌ Слишком много сообщений для цитаты (максимум {MAX_CHAIN_MESSAGES}).")
            return
        if count < 1:
            count = 1
        await _generate_multi_message_quote(msg, count)
    else:
        # Режим одного сообщения (Requirement 7.1)
        await _generate_single_message_quote(msg)


def get_quote_author(original_msg: Message) -> tuple:
    """
    Определяет автора сообщения для цитаты.
    Учитывает пересланные сообщения — берёт оригинального автора.
    
    Returns:
        (user_id, username, full_name, user_for_avatar)
        user_for_avatar может быть None если это forward_sender_name
    """
    # Проверяем, пересланное ли это сообщение
    if original_msg.forward_from:
        # Пересланное от пользователя (не скрыт)
        fwd_user = original_msg.forward_from
        return (
            fwd_user.id,
            fwd_user.username or fwd_user.first_name,
            fwd_user.full_name,
            fwd_user
        )
    elif original_msg.forward_sender_name:
        # Пересланное от пользователя со скрытым аккаунтом
        return (
            None,  # ID недоступен
            original_msg.forward_sender_name,
            original_msg.forward_sender_name,
            None  # Аватарка недоступна
        )
    elif original_msg.forward_from_chat:
        # Пересланное из канала/группы
        chat = original_msg.forward_from_chat
        return (
            chat.id,
            chat.username or chat.title,
            chat.title,
            None  # Для каналов аватарку не грузим
        )
    else:
        # Обычное сообщение — берём from_user
        user = original_msg.from_user
        return (
            user.id,
            user.username or user.first_name,
            user.full_name,
            user
        )


async def _generate_single_message_quote(msg: Message):
    """
    Генерирует цитату из одного сообщения.
    
    Fortress Update: Uses new QuoteGeneratorService with gradient backgrounds.
    Requirements: 7.1, 7.2, 7.5, 7.6
    """
    logger.info(f"[QUOTE] _generate_single_message_quote called for chat {msg.chat.id}")
    original_msg = msg.reply_to_message
    
    # Определяем автора (учитываем пересланные сообщения)
    user_id, username, full_name, user_for_avatar = get_quote_author(original_msg)
    
    # Извлекаем текст из сообщения
    text = extract_message_text(original_msg)
    logger.info(f"[QUOTE] Extracted text: {text[:50] if text else 'None'}...")
    if not text:
        await msg.reply("❌ Не могу создать цитату из этого сообщения (нет текста).")
        return
    
    logger.info(f"[QUOTE] Username: {username}, Full name: {full_name}")
    
    # Get timestamp if available
    timestamp = None
    if original_msg.date:
        timestamp = original_msg.date.strftime("%H:%M")
    
    # Start Alive UI status for quote rendering
    status = None
    thread_id = getattr(msg, 'message_thread_id', None)
    try:
        status = await alive_ui_service.start_status(
            msg.chat.id, "quote", msg.bot, message_thread_id=thread_id
        )
        
        # Загружаем аватарку пользователя (если доступен user)
        avatar_data = None
        custom_title = None
        if user_for_avatar and user_id:
            avatar_data = await get_user_avatar(msg.bot, user_id)
            # Получаем кастомный титул в группе (только для участников чата)
            user_info = await get_user_info(msg.bot, msg.chat.id, user_for_avatar)
            custom_title = user_info.get("custom_title")
        
        # Создаем изображение цитаты
        image_io = await create_quote_image(
            text=text,
            username=username,
            timestamp=timestamp,
            avatar_data=avatar_data,
            custom_title=custom_title,
            full_name=full_name,
        )
        
        # Clean up status message before sending response
        if status:
            await alive_ui_service.finish_status(status, msg.bot)
            status = None
        
        # Подготавливаем изображение для отправки как стикер (размер до 512px)
        image_io.seek(0)
        image_data = image_io.read()
        sticker_data = resize_for_sticker(image_data)
        sticker_file = BufferedInputFile(sticker_data, filename="quote.webp")
        
        # Сначала сохраняем в БД чтобы получить ID для кнопок
        # Для пересланных сообщений со скрытым аккаунтом используем ID того, кто переслал
        save_user_id = user_id if user_id else msg.from_user.id
        image_io.seek(0)
        quote_id = await save_quote_to_db(
            user_id=save_user_id,
            text=text,
            username=username,
            image_io=image_io,
            telegram_chat_id=msg.chat.id,
            telegram_message_id=0  # Обновим после отправки
        )
        
        # Создаём клавиатуру с кнопками
        keyboard = build_quote_keyboard(quote_id)
        
        # Отправляем как стикер с кнопками
        sent_msg = await msg.answer_sticker(
            sticker=sticker_file,
            reply_markup=keyboard,
        )
        
        # Обновляем message_id в БД
        await update_quote_message_id(quote_id, sent_msg.message_id)
        logger.info(f"Quote saved with ID {quote_id}")
        
    except TelegramBadRequest as e:
        if "thread not found" in str(e).lower() or "message to reply not found" in str(e).lower():
            logger.warning(f"Cannot create quote - topic/message deleted: {e}")
            return
        logger.error(f"Telegram ошибка при создании цитаты: {e}")
        if status:
            await alive_ui_service.show_error(status, "Не удалось создать цитату", msg.bot)
    except Exception as e:
        logger.error(f"Ошибка при создании цитаты: {e}")
        
        # Show error on status message if it exists
        # **Validates: Requirements 12.6**
        if status:
            await alive_ui_service.show_error(status, "Не удалось создать цитату", msg.bot)
        else:
            try:
                await msg.reply("❌ Ошибка при создании цитаты.")
            except TelegramBadRequest:
                pass


def get_message_author_for_chain(message: Message) -> tuple:
    """
    Получает автора сообщения для цепочки цитат.
    Учитывает пересланные сообщения.
    
    Returns:
        (username, user_id)
    """
    if message.forward_from:
        fwd = message.forward_from
        return (fwd.username or fwd.first_name, fwd.id)
    elif message.forward_sender_name:
        return (message.forward_sender_name, None)
    elif message.forward_from_chat:
        chat = message.forward_from_chat
        return (chat.username or chat.title, chat.id)
    elif message.from_user:
        return (message.from_user.username or message.from_user.first_name, message.from_user.id)
    return ("Unknown", None)


async def _generate_multi_message_quote(msg: Message, count: int):
    """
    Генерирует цитату из нескольких сообщений.
    
    Fortress Update: Supports quote chains up to 10 messages.
    Requirements: 7.3, 7.5, 7.6
    Property 17: Quote chain limit - max 10 messages
    
    Note: Due to Telegram API limitations, we can only reliably get the replied-to message.
    For a full chain, we would need message history access which requires admin rights.
    This implementation creates a chain starting from the replied message.
    """
    original_msg = msg.reply_to_message
    
    # Извлекаем текст из сообщения
    text = extract_message_text(original_msg)
    if not text:
        await msg.reply("❌ Не могу создать цитату из этого сообщения (нет текста).")
        return
    
    # Определяем автора (учитываем пересланные сообщения)
    username, first_user_id = get_message_author_for_chain(original_msg)
    
    # Build message chain
    # For now, we create a chain with the single message repeated conceptually
    # In a full implementation, we would fetch message history
    messages = [
        MessageData(
            text=text,
            username=username,
            timestamp=original_msg.date.strftime("%H:%M") if original_msg.date else None
        )
    ]
    
    # Try to get reply chain if the original message is also a reply
    current_msg = original_msg
    chain_count = 1
    
    while chain_count < count and current_msg.reply_to_message:
        reply_msg = current_msg.reply_to_message
        reply_text = extract_message_text(reply_msg)
        
        if reply_text:
            reply_username, _ = get_message_author_for_chain(reply_msg)
            messages.insert(0, MessageData(
                text=reply_text,
                username=reply_username,
                timestamp=reply_msg.date.strftime("%H:%M") if reply_msg.date else None
            ))
            chain_count += 1
            current_msg = reply_msg
        else:
            break
    
    # Enforce max chain limit (Property 17)
    if len(messages) > MAX_CHAIN_MESSAGES:
        messages = messages[:MAX_CHAIN_MESSAGES]
    
    try:
        # Создаем изображение цепочки цитат (Requirement 7.3, 7.5)
        image_io = await create_quote_chain_image(messages)
        
        # Подготавливаем изображение для отправки как стикер
        image_io.seek(0)
        image_data = image_io.read()
        sticker_data = resize_for_sticker(image_data)
        sticker_file = BufferedInputFile(sticker_data, filename="quote_chain.webp")
        
        # Сначала сохраняем в БД чтобы получить ID для кнопок
        save_user_id = first_user_id if first_user_id else msg.from_user.id
        image_io.seek(0)
        combined_text = "\n---\n".join([m.text for m in messages])
        quote_id = await save_quote_to_db(
            user_id=save_user_id,
            text=combined_text,
            username=username,
            image_io=image_io,
            telegram_chat_id=msg.chat.id,
            telegram_message_id=0  # Обновим после отправки
        )
        
        # Создаём клавиатуру с кнопками
        keyboard = build_quote_keyboard(quote_id)
        
        # Отправляем как стикер (caption не поддерживается для стикеров)
        sent_msg = await msg.answer_sticker(sticker=sticker_file, reply_markup=keyboard)
        
        # Обновляем message_id в БД
        await update_quote_message_id(quote_id, sent_msg.message_id)
        logger.info(f"Quote chain saved with ID {quote_id}")
        
    except TelegramBadRequest as e:
        if "thread not found" in str(e).lower() or "message to reply not found" in str(e).lower():
            logger.warning(f"Cannot create quote chain - topic/message deleted: {e}")
            return
        logger.error(f"Telegram ошибка при создании цепочки цитат: {e}")
    except Exception as e:
        logger.error(f"Ошибка при создании цепочки цитат: {e}")
        try:
            await msg.reply("❌ Ошибка при создании цепочки цитат.")
        except TelegramBadRequest:
            pass


async def _generate_roast_quote(msg: Message):
    """
    Генерирует цитату с комментарием Олега (режим прожарки).
    
    Fortress Update: Uses new QuoteGeneratorService with LLM-generated roast.
    Requirements: 7.4, 7.5, 7.6
    """
    original_msg = msg.reply_to_message
    
    # Извлекаем текст из сообщения
    text = extract_message_text(original_msg)
    if not text:
        await msg.reply("❌ Не могу создать цитату из этого сообщения (нет текста).")
        return
    
    # Определяем автора (учитываем пересланные сообщения)
    user_id, username, full_name, _ = get_quote_author(original_msg)
    
    # Start Alive UI status for roast quote (uses thinking category for LLM)
    # **Validates: Requirements 12.1, 12.2, 12.3**
    status = None
    thread_id = getattr(msg, 'message_thread_id', None)
    try:
        status = await alive_ui_service.start_status(
            msg.chat.id, "thinking", msg.bot, message_thread_id=thread_id
        )
        
        # Создаем изображение цитаты с комментарием (Requirement 7.4, 7.5)
        # The roast comment is generated inside the service
        image_io = await create_quote_with_comment(text, username)
        
        # Clean up status message before sending response
        # **Property 32: Status cleanup**
        if status:
            await alive_ui_service.finish_status(status, msg.bot)
            status = None
        
        # Подготавливаем изображение для отправки как стикер
        image_io.seek(0)
        image_data = image_io.read()
        sticker_data = resize_for_sticker(image_data)
        sticker_file = BufferedInputFile(sticker_data, filename="quote_roast.webp")
        
        # Сначала сохраняем в БД чтобы получить ID для кнопок
        save_user_id = user_id if user_id else msg.from_user.id
        image_io.seek(0)
        quote_id = await save_quote_to_db(
            user_id=save_user_id,
            text=text,
            username=username,
            image_io=image_io,
            comment="[roast mode]",  # Comment is embedded in image
            telegram_chat_id=msg.chat.id,
            telegram_message_id=0  # Обновим после отправки
        )
        
        # Создаём клавиатуру с кнопками
        keyboard = build_quote_keyboard(quote_id)
        
        # Отправляем как стикер (caption не поддерживается для стикеров)
        sent_msg = await msg.answer_sticker(
            sticker=sticker_file,
            reply_markup=keyboard
        )
        
        # Обновляем message_id в БД
        await update_quote_message_id(quote_id, sent_msg.message_id)
        logger.info(f"Roast quote saved with ID {quote_id}")
        
    except TelegramBadRequest as e:
        if "thread not found" in str(e).lower() or "message to reply not found" in str(e).lower():
            logger.warning(f"Cannot create roast quote - topic/message deleted: {e}")
            return
        logger.error(f"Telegram ошибка при создании цитаты с комментарием: {e}")
        if status:
            await alive_ui_service.show_error(status, "Не удалось создать цитату", msg.bot)
    except Exception as e:
        logger.error(f"Ошибка при создании цитаты с комментарием: {e}")
        
        # Show error on status message if it exists
        # **Validates: Requirements 12.6**
        if status:
            await alive_ui_service.show_error(status, "Не удалось создать цитату", msg.bot)
        else:
            try:
                await msg.reply("❌ Ошибка при создании цитаты с комментарием.")
            except TelegramBadRequest:
                pass


def extract_message_text(message: Message) -> str:
    """
    Извлекает текст из сообщения, учитывая различные типы контента.
    
    Args:
        message: Сообщение Telegram
    
    Returns:
        Текст сообщения или пустую строку
    """
    if message.text:
        return message.text
    elif message.caption:
        return message.caption
    elif message.sticker:
        return f"стикер '{message.sticker.emoji or 'эмодзи'}'"
    elif message.photo:
        return f"фото: {message.caption or 'без описания'}"
    elif message.video:
        return f"видео: {message.caption or 'без описания'}"
    elif message.document:
        return f"документ: {message.document.file_name or 'без названия'}"
    elif message.audio:
        return f"аудио: {message.audio.title or message.caption or 'без названия'}"
    elif message.voice:
        return "голосовое сообщение"
    else:
        return ""


async def save_quote_to_db(user_id: int, text: str, username: str, image_io: BytesIO, comment: str = None, telegram_chat_id: int = None, telegram_message_id: int = None):
    """
    Сохраняет цитату в базу данных для возможного использования в стикерпаке.

    Args:
        user_id: ID пользователя, чье сообщение цитируется
        text: Текст цитаты
        username: Имя пользователя
        image_io: Изображение цитаты
        comment: Комментарий Олега (опционально)
        telegram_chat_id: ID чата в Telegram (для связи с сообщением)
        telegram_message_id: ID сообщения в Telegram (для отслеживания реакций)

    Returns:
        ID созданной цитаты
    """
    from app.handlers.games import ensure_user
    from aiogram.types import User as TgUser

    # Создаем временного пользователя Telegram для передачи в ensure_user
    temp_tg_user = TgUser(id=user_id, is_bot=False, first_name=username or "Unknown")
    user = await ensure_user(temp_tg_user)  # Получаем объект пользователя

    async_session = get_session()
    async with async_session() as session:
        from app.database.models import Quote

        # Сохраняем изображение
        image_data = image_io.getvalue()

        new_quote = Quote(
            user_id=user.id,
            text=text,
            username=username,
            image_data=image_data,
            comment=comment,
            likes_count=0,
            is_golden_fund=False,
            telegram_chat_id=telegram_chat_id,
            telegram_message_id=telegram_message_id
        )
        session.add(new_quote)
        await session.commit()

        # Обновляем объект, чтобы получить ID
        await session.refresh(new_quote)
        return new_quote.id


async def update_quote_message_id(quote_id: int, message_id: int):
    """Обновляет telegram_message_id для цитаты."""
    async_session = get_session()
    async with async_session() as session:
        from sqlalchemy import update
        from app.database.models import Quote
        await session.execute(
            update(Quote).where(Quote.id == quote_id).values(telegram_message_id=message_id)
        )
        await session.commit()


@router.callback_query(F.data.startswith("quote_like:"))
async def cb_quote_like(callback: CallbackQuery):
    """Обработчик лайка цитаты."""
    quote_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    async_session = get_session()
    async with async_session() as session:
        from sqlalchemy import select
        from app.database.models import Quote, QuoteVote
        
        # Проверяем, голосовал ли уже
        existing_vote = await session.execute(
            select(QuoteVote).filter_by(quote_id=quote_id, user_id=user_id)
        )
        vote = existing_vote.scalars().first()
        
        quote_res = await session.execute(select(Quote).filter_by(id=quote_id))
        quote = quote_res.scalars().first()
        
        if not quote:
            await callback.answer("Цитата не найдена", show_alert=True)
            return
        
        if vote:
            if vote.vote_type == "like":
                await callback.answer("Ты уже лайкнул эту цитату")
                return
            else:
                # Меняем дизлайк на лайк
                vote.vote_type = "like"
                quote.likes_count += 1
                quote.dislikes_count = max(0, (quote.dislikes_count or 0) - 1)
        else:
            # Новый лайк
            new_vote = QuoteVote(quote_id=quote_id, user_id=user_id, vote_type="like")
            session.add(new_vote)
            quote.likes_count += 1
        
        await session.commit()
        
        # Обновляем клавиатуру
        keyboard = build_quote_keyboard(quote_id, quote.likes_count, quote.dislikes_count or 0)
        try:
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        except TelegramBadRequest:
            pass
        
        await callback.answer("👍 Лайк!")


@router.callback_query(F.data.startswith("quote_dislike:"))
async def cb_quote_dislike(callback: CallbackQuery):
    """Обработчик дизлайка цитаты."""
    quote_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    async_session = get_session()
    async with async_session() as session:
        from sqlalchemy import select
        from app.database.models import Quote, QuoteVote
        
        # Проверяем, голосовал ли уже
        existing_vote = await session.execute(
            select(QuoteVote).filter_by(quote_id=quote_id, user_id=user_id)
        )
        vote = existing_vote.scalars().first()
        
        quote_res = await session.execute(select(Quote).filter_by(id=quote_id))
        quote = quote_res.scalars().first()
        
        if not quote:
            await callback.answer("Цитата не найдена", show_alert=True)
            return
        
        if vote:
            if vote.vote_type == "dislike":
                await callback.answer("Ты уже дизлайкнул эту цитату")
                return
            else:
                # Меняем лайк на дизлайк
                vote.vote_type = "dislike"
                quote.likes_count = max(0, quote.likes_count - 1)
                quote.dislikes_count = (quote.dislikes_count or 0) + 1
        else:
            # Новый дизлайк
            new_vote = QuoteVote(quote_id=quote_id, user_id=user_id, vote_type="dislike")
            session.add(new_vote)
            quote.dislikes_count = (quote.dislikes_count or 0) + 1
        
        await session.commit()
        
        # Обновляем клавиатуру
        keyboard = build_quote_keyboard(quote_id, quote.likes_count, quote.dislikes_count or 0)
        try:
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        except TelegramBadRequest:
            pass
        
        await callback.answer("👎 Дизлайк!")


@router.callback_query(F.data.startswith("quote_sticker:"))
async def cb_quote_sticker(callback: CallbackQuery):
    """Обработчик добавления цитаты в стикерпак через Telegram API."""
    from app.services.sticker_pack import sticker_pack_service
    
    quote_id = int(callback.data.split(":")[1])
    
    # Проверяем права админа
    try:
        chat_member = await callback.bot.get_chat_member(
            chat_id=callback.message.chat.id,
            user_id=callback.from_user.id
        )
        if chat_member.status not in ["administrator", "creator"]:
            await callback.answer("Только админы могут добавлять в стикерпак", show_alert=True)
            return
    except Exception:
        await callback.answer("Ошибка проверки прав", show_alert=True)
        return
    
    try:
        # Получаем цитату из БД
        async_session = get_session()
        async with async_session() as session:
            from sqlalchemy import select
            from app.database.models import Quote
            
            quote_result = await session.execute(select(Quote).filter_by(id=quote_id))
            quote = quote_result.scalars().first()
            
            if not quote:
                await callback.answer("❌ Цитата не найдена", show_alert=True)
                return
            
            if quote.is_sticker:
                await callback.answer("ℹ️ Эта цитата уже в стикерпаке", show_alert=True)
                return
            
            if not quote.image_data:
                await callback.answer("❌ Изображение цитаты не найдено", show_alert=True)
                return
            
            # Получаем информацию о боте
            bot_info = await callback.bot.get_me()
            bot_username = bot_info.username
            
            # Получаем название чата
            chat_title = callback.message.chat.title or "Chat"
            chat_id = callback.message.chat.id
            
            # Проверяем/создаём стикерпак
            current_pack = await sticker_pack_service.get_current_pack(chat_id)
            
            # Ресайзим изображение для стикера
            sticker_data = resize_for_sticker(quote.image_data)
            sticker_file = BufferedInputFile(sticker_data, filename="sticker.webp")
            
            if current_pack is None:
                # Создаём новый стикерпак — текущий пользователь становится владельцем
                pack_name = f"oleg_quotes_{abs(chat_id)}_v1_by_{bot_username}"
                pack_title = f"Цитаты Олега - {chat_title}"[:64]
                owner_user_id = callback.from_user.id
                
                try:
                    # Создаём стикерпак через Telegram API
                    input_sticker = InputSticker(
                        sticker=sticker_file,
                        format="static",
                        emoji_list=["💬"]
                    )
                    
                    await callback.bot.create_new_sticker_set(
                        user_id=owner_user_id,
                        name=pack_name,
                        title=pack_title,
                        stickers=[input_sticker],
                        sticker_type="regular"
                    )
                    
                    # Сохраняем в БД с owner_user_id
                    current_pack = await sticker_pack_service.create_new_pack(
                        chat_id, chat_title, owner_user_id=owner_user_id
                    )
                    
                    # Получаем file_id созданного стикера
                    sticker_set = await callback.bot.get_sticker_set(pack_name)
                    sticker_file_id = sticker_set.stickers[0].file_id if sticker_set.stickers else None
                    
                    # Обновляем цитату
                    quote.is_sticker = True
                    quote.sticker_file_id = sticker_file_id
                    quote.sticker_pack_id = current_pack.id
                    await session.commit()
                    
                    await callback.answer(f"✅ Создан стикерпак! Ты его владелец.", show_alert=True)
                    logger.info(f"Created sticker pack {pack_name} with owner {owner_user_id}")
                    return
                    
                except TelegramBadRequest as e:
                    if "PEER_ID_INVALID" in str(e):
                        await callback.answer("❌ Сначала напиши боту в ЛС", show_alert=True)
                    elif "STICKERSET_INVALID" in str(e):
                        await callback.answer("❌ Ошибка создания стикерпака", show_alert=True)
                    else:
                        logger.error(f"Error creating sticker pack: {e}")
                        await callback.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)
                    return
            else:
                # Добавляем в существующий стикерпак
                # Используем owner_user_id из БД
                owner_user_id = current_pack.owner_user_id
                
                if not owner_user_id:
                    await callback.answer("❌ Владелец стикерпака не найден", show_alert=True)
                    return
                
                try:
                    # Проверяем, не заполнен ли пак
                    if current_pack.sticker_count >= 120:
                        # Создаём новый том с тем же владельцем
                        rotated = await sticker_pack_service.rotate_pack_if_needed(chat_id, chat_title)
                        if rotated:
                            current_pack = rotated
                            pack_name = current_pack.name
                            pack_title = current_pack.title
                            
                            input_sticker = InputSticker(
                                sticker=sticker_file,
                                format="static",
                                emoji_list=["💬"]
                            )
                            
                            await callback.bot.create_new_sticker_set(
                                user_id=owner_user_id,
                                name=pack_name,
                                title=pack_title,
                                stickers=[input_sticker],
                                sticker_type="regular"
                            )
                            
                            sticker_set = await callback.bot.get_sticker_set(pack_name)
                            sticker_file_id = sticker_set.stickers[0].file_id if sticker_set.stickers else None
                            
                            quote.is_sticker = True
                            quote.sticker_file_id = sticker_file_id
                            quote.sticker_pack_id = current_pack.id
                            await session.commit()
                            
                            await callback.answer(f"✅ Создан новый том стикерпака!", show_alert=True)
                            return
                    
                    # Добавляем стикер в существующий пак от имени владельца
                    input_sticker = InputSticker(
                        sticker=sticker_file,
                        format="static",
                        emoji_list=["💬"]
                    )
                    
                    await callback.bot.add_sticker_to_set(
                        user_id=owner_user_id,
                        name=current_pack.name,
                        sticker=input_sticker
                    )
                    
                    # Получаем file_id добавленного стикера
                    sticker_set = await callback.bot.get_sticker_set(current_pack.name)
                    sticker_file_id = sticker_set.stickers[-1].file_id if sticker_set.stickers else None
                    
                    # Обновляем БД
                    await sticker_pack_service.add_sticker(
                        chat_id=chat_id,
                        quote_id=quote_id,
                        sticker_file_id=sticker_file_id,
                        chat_title=chat_title
                    )
                    
                    sticker_count = current_pack.sticker_count + 1
                    await callback.answer(f"✅ Добавлено в стикерпак ({sticker_count}/120)", show_alert=True)
                    logger.info(f"Added sticker for quote {quote_id} to pack {current_pack.name}")
                    
                except TelegramBadRequest as e:
                    if "PEER_ID_INVALID" in str(e):
                        await callback.answer("❌ Владелец пака должен написать боту в ЛС", show_alert=True)
                    elif "STICKERSET_INVALID" in str(e) or "STICKER_SET_INVALID" in str(e):
                        await callback.answer("❌ Стикерпак не найден в Telegram", show_alert=True)
                    else:
                        logger.error(f"Error adding sticker: {e}")
                        await callback.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)
                    return
                    
    except Exception as e:
        logger.error(f"Error in cb_quote_sticker: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.message(Command("qs"))
async def cmd_quote_save(msg: Message):
    """
    Команда /qs - добавляет цитату в стикерпак бота.
    Работает в ответ на сообщение с цитатой.
    
    Fortress Update v6.0: Uses StickerPackService for pack management.
    Requirements: 8.1, 8.2, 8.3, 8.4
    """
    from app.services.sticker_pack import sticker_pack_service
    
    if not msg.reply_to_message:
        await msg.reply("❌ Нужно ответить на сообщение с цитатой, чтобы добавить её в стикерпак.")
        return

    # Проверяем, что это сообщение с изображением (цитатой)
    if not (msg.reply_to_message.photo or msg.reply_to_message.sticker):
        await msg.reply("❌ Можно добавлять в стикерпак только изображения цитат.")
        return
    
    # Проверяем права админа
    try:
        chat_member = await msg.bot.get_chat_member(
            chat_id=msg.chat.id,
            user_id=msg.from_user.id
        )
        if chat_member.status not in ["administrator", "creator"]:
            await msg.reply("❌ Только админы могут добавлять в стикерпак")
            return
    except Exception:
        await msg.reply("❌ Ошибка проверки прав")
        return

    try:
        # Find the quote in the database by message ID
        async_session = get_session()
        async with async_session() as session:
            from sqlalchemy import select
            from app.database.models import Quote
            
            # Try to find quote by telegram message ID
            quote_result = await session.execute(
                select(Quote).filter_by(
                    telegram_message_id=msg.reply_to_message.message_id,
                    telegram_chat_id=msg.chat.id
                )
            )
            quote = quote_result.scalars().first()
            
            if not quote:
                await msg.reply(
                    "❌ Эта цитата не найдена в базе данных. "
                    "Сначала создайте цитату командой /q, затем добавьте её в стикерпак."
                )
                return
            
            if quote.is_sticker:
                await msg.reply("ℹ️ Эта цитата уже добавлена в стикерпак.")
                return
            
            if not quote.image_data:
                await msg.reply("❌ Изображение цитаты не найдено")
                return
            
            # Получаем информацию о боте
            bot_info = await msg.bot.get_me()
            bot_username = bot_info.username
            
            # Get chat title for pack naming
            chat_title = msg.chat.title or "Chat"
            chat_id = msg.chat.id
            
            # Проверяем/создаём стикерпак
            current_pack = await sticker_pack_service.get_current_pack(chat_id)
            
            # Ресайзим изображение для стикера
            sticker_data = resize_for_sticker(quote.image_data)
            sticker_file = BufferedInputFile(sticker_data, filename="sticker.webp")
            
            if current_pack is None:
                # Создаём новый стикерпак — текущий пользователь становится владельцем
                pack_name = f"oleg_quotes_{abs(chat_id)}_v1_by_{bot_username}"
                pack_title = f"Цитаты Олега - {chat_title}"[:64]
                owner_user_id = msg.from_user.id
                
                try:
                    input_sticker = InputSticker(
                        sticker=sticker_file,
                        format="static",
                        emoji_list=["💬"]
                    )
                    
                    await msg.bot.create_new_sticker_set(
                        user_id=owner_user_id,
                        name=pack_name,
                        title=pack_title,
                        stickers=[input_sticker],
                        sticker_type="regular"
                    )
                    
                    current_pack = await sticker_pack_service.create_new_pack(
                        chat_id, chat_title, owner_user_id=owner_user_id
                    )
                    
                    sticker_set = await msg.bot.get_sticker_set(pack_name)
                    sticker_file_id = sticker_set.stickers[0].file_id if sticker_set.stickers else None
                    
                    quote.is_sticker = True
                    quote.sticker_file_id = sticker_file_id
                    quote.sticker_pack_id = current_pack.id
                    await session.commit()
                    
                    await msg.reply(f"✅ Создан стикерпак! Ты его владелец.\n📦 Пак: {pack_title}")
                    logger.info(f"Created sticker pack {pack_name} with owner {owner_user_id}")
                    return
                    
                except TelegramBadRequest as e:
                    if "PEER_ID_INVALID" in str(e):
                        await msg.reply("❌ Сначала напиши боту в ЛС, потом попробуй снова")
                    elif "STICKERSET_INVALID" in str(e):
                        await msg.reply("❌ Ошибка создания стикерпака")
                    else:
                        logger.error(f"Error creating sticker pack: {e}")
                        await msg.reply(f"❌ Ошибка: {str(e)[:100]}")
                    return
            else:
                # Добавляем в существующий стикерпак
                owner_user_id = current_pack.owner_user_id
                
                if not owner_user_id:
                    await msg.reply("❌ Владелец стикерпака не найден")
                    return
                
                try:
                    if current_pack.sticker_count >= 120:
                        rotated = await sticker_pack_service.rotate_pack_if_needed(chat_id, chat_title)
                        if rotated:
                            current_pack = rotated
                            pack_name = current_pack.name
                            
                            input_sticker = InputSticker(
                                sticker=sticker_file,
                                format="static",
                                emoji_list=["💬"]
                            )
                            
                            await msg.bot.create_new_sticker_set(
                                user_id=owner_user_id,
                                name=pack_name,
                                title=current_pack.title,
                                stickers=[input_sticker],
                                sticker_type="regular"
                            )
                            
                            sticker_set = await msg.bot.get_sticker_set(pack_name)
                            sticker_file_id = sticker_set.stickers[0].file_id if sticker_set.stickers else None
                            
                            quote.is_sticker = True
                            quote.sticker_file_id = sticker_file_id
                            quote.sticker_pack_id = current_pack.id
                            await session.commit()
                            
                            await msg.reply(f"✅ Стикерпак заполнен! Создан новый: {current_pack.title}")
                            return
                    
                    input_sticker = InputSticker(
                        sticker=sticker_file,
                        format="static",
                        emoji_list=["💬"]
                    )
                    
                    await msg.bot.add_sticker_to_set(
                        user_id=owner_user_id,
                        name=current_pack.name,
                        sticker=input_sticker
                    )
                    
                    sticker_set = await msg.bot.get_sticker_set(current_pack.name)
                    sticker_file_id = sticker_set.stickers[-1].file_id if sticker_set.stickers else None
                    
                    await sticker_pack_service.add_sticker(
                        chat_id=chat_id,
                        quote_id=quote.id,
                        sticker_file_id=sticker_file_id,
                        chat_title=chat_title
                    )
                    
                    quote.is_sticker = True
                    quote.sticker_file_id = sticker_file_id
                    quote.sticker_pack_id = current_pack.id
                    await session.commit()
                    
                    sticker_count = current_pack.sticker_count + 1
                    await msg.reply(f"✅ Добавлено в стикерпак ({sticker_count}/120)\n📦 Пак: {current_pack.title}")
                    logger.info(f"Added sticker for quote {quote.id} to pack {current_pack.name}")
                    
                except TelegramBadRequest as e:
                    if "PEER_ID_INVALID" in str(e):
                        await msg.reply("❌ Владелец пака должен написать боту в ЛС")
                    elif "STICKERSET_INVALID" in str(e) or "STICKER_SET_INVALID" in str(e):
                        await msg.reply("❌ Стикерпак не найден в Telegram")
                    else:
                        logger.error(f"Error adding sticker: {e}")
                        await msg.reply(f"❌ Ошибка: {str(e)[:100]}")
                    return

    except TelegramBadRequest as e:
        if "thread not found" in str(e).lower() or "message to reply not found" in str(e).lower():
            logger.warning(f"Cannot add to sticker pack - topic/message deleted: {e}")
            return
        logger.error(f"Telegram ошибка при добавлении цитаты в стикерпак: {e}")
    except Exception as e:
        logger.error(f"Ошибка при добавлении цитаты в стикерпак: {e}")
        try:
            await msg.reply("❌ Ошибка при добавлении цитаты в стикерпак.")
        except TelegramBadRequest:
            pass


@router.message(Command("qd"))
async def cmd_quote_delete(msg: Message):
    """
    Команда /qd - удаляет цитату из стикерпака (только для админов).
    Работает в ответ на сообщение с цитатой.
    
    Fortress Update v6.0: Uses StickerPackService for pack management.
    Requirements: 8.5
    """
    from app.services.sticker_pack import sticker_pack_service
    
    if not msg.reply_to_message:
        await msg.reply("❌ Нужно ответить на сообщение с цитатой, чтобы удалить её.")
        return

    # Проверяем, является ли пользователь админом
    try:
        chat_member = await msg.bot.get_chat_member(
            chat_id=msg.chat.id,
            user_id=msg.from_user.id
        )
        if chat_member.status not in ["administrator", "creator"]:
            await msg.reply("❌ Удаление цитат могут выполнять только администраторы.")
            return
    except Exception:
        await msg.reply("❌ Не удалось проверить статус администратора.")
        return

    try:
        # Find the quote in the database by message ID
        async_session = get_session()
        async with async_session() as session:
            from sqlalchemy import select
            from app.database.models import Quote
            
            # Try to find quote by telegram message ID
            quote_result = await session.execute(
                select(Quote).filter_by(
                    telegram_message_id=msg.reply_to_message.message_id,
                    telegram_chat_id=msg.chat.id
                )
            )
            quote = quote_result.scalars().first()
            
            if not quote:
                await msg.reply("❌ Эта цитата не найдена в базе данных.")
                return
            
            if not quote.is_sticker:
                await msg.reply("ℹ️ Эта цитата не является стикером.")
                return
            
            # Remove sticker from pack
            success = await sticker_pack_service.remove_sticker(quote.id)
            
            if success:
                await msg.reply("✅ Цитата удалена из стикерпака.")
                logger.info(
                    f"Admin {msg.from_user.username} removed quote {quote.id} from sticker pack"
                )
            else:
                await msg.reply("❌ Не удалось удалить цитату из стикерпака.")
                
    except TelegramBadRequest as e:
        if "thread not found" in str(e).lower() or "message to reply not found" in str(e).lower():
            logger.warning(f"Cannot delete from sticker pack - topic/message deleted: {e}")
            return
        logger.error(f"Telegram ошибка при удалении цитаты из стикерпака: {e}")
    except Exception as e:
        logger.error(f"Ошибка при удалении цитаты из стикерпака: {e}")
        try:
            await msg.reply("❌ Ошибка при удалении цитаты из стикерпака.")
        except TelegramBadRequest:
            pass


# Обработчик реакций на сообщения (включая цитаты) для "живых цитат"
# Fortress Update: Integrated with ReputationService for "thank you" reactions
# **Validates: Requirements 4.5**
from aiogram import Router
from aiogram.types import MessageReactionUpdated
from app.services.reputation import reputation_service

# Создаем отдельный роутер для реакций
reactions_router = Router()

# Emoji that count as "thank you" reactions for reputation bonus
THANK_YOU_EMOJIS = ['👍', '❤️', '🔥', '🙏', '👏', '💯']

@reactions_router.message_reaction()
async def handle_message_reaction(update: MessageReactionUpdated):
    """
    Обрабатывает реакции на сообщения, включая цитаты.
    Используется для "живых цитат" - если цитата набирает N лайков,
    она попадает в "золотой фонд".
    
    Fortress Update: Also awards reputation bonus for "thank you" reactions.
    **Validates: Requirements 4.5**
    """
    # Проверяем, есть ли добавленные реакции
    if update.new_reaction:
        for reaction in update.new_reaction:
            # Проверяем, является ли реакция лайком (emoji или other_type)
            if hasattr(reaction, 'emoji') and reaction.emoji in THANK_YOU_EMOJIS:
                # Это лайк, увеличиваем счётчик для соответствующей цитаты
                await handle_like_reaction(update)
                return


async def handle_like_reaction(update: MessageReactionUpdated):
    """
    Обрабатывает лайк-реакции на сообщения.
    
    Fortress Update: Awards reputation bonus for "thank you" reactions.
    **Validates: Requirements 4.5**

    Args:
        update: Обновление реакции
    """
    # Fortress Update: Award reputation bonus to the message author
    # We need to find who authored the message that received the reaction
    # The reactor (update.user) is giving thanks to the message author
    
    # Get the message author from the replied message
    # Note: MessageReactionUpdated doesn't directly contain the original message author
    # We need to look it up from our database or the quote record
    
    # Находим цитату по chat_id и message_id
    async_session = get_session()
    async with async_session() as session:
        from sqlalchemy import select
        from app.database.models import Quote

        # Ищем цитату по ID сообщения и ID чата
        quote_res = await session.execute(
            select(Quote)
            .filter_by(telegram_message_id=update.message_id, telegram_chat_id=update.chat.id)
        )
        quote = quote_res.scalars().first()

        if quote:
            # Увеличиваем счётчик лайков
            quote.likes_count += 1
            logger.info(f"Цитата ID {quote.id} получила лайк, всего лайков: {quote.likes_count}")
            
            # Fortress Update: Award reputation bonus to the quote author (Requirement 4.5)
            # Only award if the reactor is not the same as the author
            if update.user and update.user.id != quote.user_id:
                try:
                    # Get the quote author's telegram user ID
                    from app.database.models import User
                    user_res = await session.execute(
                        select(User).filter_by(id=quote.user_id)
                    )
                    author = user_res.scalars().first()
                    
                    if author:
                        await reputation_service.apply_thank_you(
                            author.tg_user_id, 
                            update.chat.id
                        )
                        logger.info(
                            f"Awarded thank you reputation to user {author.tg_user_id} "
                            f"for quote {quote.id}"
                        )
                except Exception as rep_error:
                    logger.warning(f"Failed to award thank you reputation: {rep_error}")

            # Если цитата набрала 5 и более лайков, добавляем в "золотой фонд"
            # Fortress Update: Use GoldenFundService for promotion check
            # **Validates: Requirements 9.1, 9.5**
            from app.services.golden_fund import golden_fund_service
            
            if golden_fund_service.check_and_promote(quote.likes_count) and not quote.is_golden_fund:
                # Promote quote to Golden Fund
                await golden_fund_service.promote_quote(session, quote.id)
                logger.info(f"Цитата ID {quote.id} добавлена в 'золотой фонд'")

                # Fortress Update: Notify chat when quote enters Golden Fund (Requirement 9.5)
                # **Validates: Requirements 9.5**
                try:
                    from aiogram import Bot
                    from app.config import settings
                    
                    # Get bot instance to send notification
                    bot = Bot(token=settings.telegram_bot_token)
                    
                    notification_text = (
                        f"🏆 *Цитата вошла в Золотой Фонд!*\n\n"
                        f"💬 _{quote.text[:100]}{'...' if len(quote.text) > 100 else ''}_\n\n"
                        f"— @{quote.username}\n\n"
                        f"🔥 Набрала {quote.likes_count} реакций!"
                    )
                    
                    await bot.send_message(
                        chat_id=update.chat.id,
                        text=notification_text,
                        parse_mode="Markdown"
                    )
                    
                    await bot.session.close()
                    logger.info(f"Golden Fund notification sent for quote {quote.id} in chat {update.chat.id}")
                except Exception as e:
                    logger.warning(f"Ошибка при отправке уведомления о 'золотом фонде': {e}")

            await session.commit()
        else:
            logger.info(f"Цитата для сообщения {update.message_id} в чате {update.chat.id} не найдена")


async def mark_quote_as_sticker(quote_id: int, sticker_file_id: str = None):
    """
    Помечает цитату как стикер для включения в стикерпак.

    Args:
        quote_id: ID цитаты в базе данных
        sticker_file_id: ID файла стикера в Telegram (опционально)
    """
    async_session = get_session()
    async with async_session() as session:
        from sqlalchemy import select
        from app.database.models import Quote

        # Находим цитату по ID
        quote_res = await session.execute(select(Quote).filter_by(id=quote_id))
        quote = quote_res.scalars().first()

        if quote:
            # Помечаем как стикер
            quote.is_sticker = True
            if sticker_file_id:
                quote.sticker_file_id = sticker_file_id

            await session.commit()
            logger.info(f"Цитата ID {quote_id} помечена как стикер")
        else:
            logger.warning(f"Цитата с ID {quote_id} не найдена для пометки как стикер")


async def unmark_quote_as_sticker(quote_id: int):
    """
    Убирает пометку стикера с цитаты.

    Args:
        quote_id: ID цитаты в базе данных
    """
    async_session = get_session()
    async with async_session() as session:
        from sqlalchemy import select
        from app.database.models import Quote

        # Находим цитату по ID
        quote_res = await session.execute(select(Quote).filter_by(id=quote_id))
        quote = quote_res.scalars().first()

        if quote:
            # Убираем пометку стикера
            quote.is_sticker = False
            quote.sticker_file_id = None

            await session.commit()
            logger.info(f"С цитаты ID {quote_id} убрана пометка стикера")
        else:
            logger.warning(f"Цитата с ID {quote_id} не найдена для снятия пометки стикера")


async def update_quote_likes(quote_id: int, reaction_type: str = "like"):
    """
    Обновляет количество лайков у цитаты.

    Args:
        quote_id: ID цитаты
        reaction_type: Тип реакции (like, dislike и т.д.)
    """
    async_session = get_session()
    async with async_session() as session:
        from sqlalchemy import select
        from app.database.models import Quote

        # Получаем цитату
        quote_res = await session.execute(select(Quote).filter_by(id=quote_id))
        quote = quote_res.scalars().first()

        if quote:
            # Увеличиваем количество лайков
            if reaction_type == "like":
                quote.likes_count += 1

            # Если цитата набрала 5 и более лайков, добавляем в "золотой фонд"
            if quote.likes_count >= 5:
                quote.is_golden_fund = True

            await session.commit()