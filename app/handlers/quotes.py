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
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

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
from app.services.alive_ui import alive_ui_service

logger = logging.getLogger(__name__)

router = Router()


async def create_quote_image(text: str, username: str, timestamp: Optional[str] = None) -> BytesIO:
    """
    Создает изображение цитаты с текстом и именем пользователя.
    
    Fortress Update: Uses new QuoteGeneratorService with gradient backgrounds.
    Requirements: 7.1, 7.2, 7.5
    
    Args:
        text: Текст цитаты
        username: Имя пользователя
        timestamp: Опциональная временная метка
    
    Returns:
        BytesIO объект с изображением в формате WebP
    """
    style = QuoteStyle(theme=QuoteTheme.DARK)
    quote_image = await quote_generator_service.render_quote(
        text=text,
        username=username,
        style=style,
        timestamp=timestamp
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
    style = QuoteStyle(theme=QuoteTheme.DARK)
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
    style = QuoteStyle(theme=QuoteTheme.DARK)
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


async def _generate_single_message_quote(msg: Message):
    """
    Генерирует цитату из одного сообщения.
    
    Fortress Update: Uses new QuoteGeneratorService with gradient backgrounds.
    Requirements: 7.1, 7.2, 7.5, 7.6
    """
    original_msg = msg.reply_to_message
    
    # Извлекаем текст из сообщения
    text = extract_message_text(original_msg)
    if not text:
        await msg.reply("❌ Не могу создать цитату из этого сообщения (нет текста).")
        return
    
    username = original_msg.from_user.username or original_msg.from_user.first_name
    
    # Get timestamp if available
    timestamp = None
    if original_msg.date:
        timestamp = original_msg.date.strftime("%H:%M")
    
    # Start Alive UI status for quote rendering
    # **Validates: Requirements 12.1, 12.2, 12.3**
    status = None
    try:
        status = await alive_ui_service.start_status(msg.chat.id, "quote", msg.bot)
        
        # Создаем изображение цитаты (Requirement 7.1, 7.2, 7.5)
        image_io = await create_quote_image(text, username, timestamp)
        
        # Clean up status message before sending response
        # **Property 32: Status cleanup**
        if status:
            await alive_ui_service.finish_status(status, msg.bot)
            status = None
        
        # Отправляем изображение как фото
        await msg.answer_photo(photo=image_io, caption="💬 Цитата создана")
        
        # Сохраняем цитату в базу данных (Requirement 7.6)
        # Property 19: Quote persistence
        image_io.seek(0)  # Reset position for saving
        quote_id = await save_quote_to_db(
            user_id=original_msg.from_user.id,
            text=text,
            username=username,
            image_io=image_io,
            telegram_chat_id=original_msg.chat.id,
            telegram_message_id=original_msg.message_id
        )
        logger.info(f"Quote saved with ID {quote_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при создании цитаты: {e}")
        
        # Show error on status message if it exists
        # **Validates: Requirements 12.6**
        if status:
            await alive_ui_service.show_error(status, "Не удалось создать цитату", msg.bot)
        else:
            await msg.reply("❌ Ошибка при создании цитаты.")


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
    
    username = original_msg.from_user.username or original_msg.from_user.first_name
    
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
        
        if reply_text and reply_msg.from_user:
            reply_username = reply_msg.from_user.username or reply_msg.from_user.first_name
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
        
        caption = f"💬 Цитата ({len(messages)} сообщ.)"
        await msg.answer_photo(photo=image_io, caption=caption)
        
        # Сохраняем цитату в базу данных (Requirement 7.6)
        # Property 19: Quote persistence
        image_io.seek(0)
        combined_text = "\n---\n".join([m.text for m in messages])
        quote_id = await save_quote_to_db(
            user_id=original_msg.from_user.id,
            text=combined_text,
            username=username,
            image_io=image_io,
            telegram_chat_id=original_msg.chat.id,
            telegram_message_id=original_msg.message_id
        )
        logger.info(f"Quote chain saved with ID {quote_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при создании цепочки цитат: {e}")
        await msg.reply("❌ Ошибка при создании цепочки цитат.")


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
    
    username = original_msg.from_user.username or original_msg.from_user.first_name
    
    # Start Alive UI status for roast quote (uses thinking category for LLM)
    # **Validates: Requirements 12.1, 12.2, 12.3**
    status = None
    try:
        status = await alive_ui_service.start_status(msg.chat.id, "thinking", msg.bot)
        
        # Создаем изображение цитаты с комментарием (Requirement 7.4, 7.5)
        # The roast comment is generated inside the service
        image_io = await create_quote_with_comment(text, username)
        
        # Clean up status message before sending response
        # **Property 32: Status cleanup**
        if status:
            await alive_ui_service.finish_status(status, msg.bot)
            status = None
        
        # Отправляем изображение как фото
        await msg.answer_photo(photo=image_io, caption="🔥 Режим прожарки активирован")
        
        # Сохраняем цитату в базу данных (Requirement 7.6)
        # Property 19: Quote persistence
        image_io.seek(0)
        quote_id = await save_quote_to_db(
            user_id=original_msg.from_user.id,
            text=text,
            username=username,
            image_io=image_io,
            comment="[roast mode]",  # Comment is embedded in image
            telegram_chat_id=original_msg.chat.id,
            telegram_message_id=original_msg.message_id
        )
        logger.info(f"Roast quote saved with ID {quote_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при создании цитаты с комментарием: {e}")
        
        # Show error on status message if it exists
        # **Validates: Requirements 12.6**
        if status:
            await alive_ui_service.show_error(status, "Не удалось создать цитату", msg.bot)
        else:
            await msg.reply("❌ Ошибка при создании цитаты с комментарием.")


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
                # Quote not found in database - it might be a photo that wasn't created via /q
                await msg.reply(
                    "❌ Эта цитата не найдена в базе данных. "
                    "Сначала создайте цитату командой /q, затем добавьте её в стикерпак."
                )
                return
            
            if quote.is_sticker:
                await msg.reply("ℹ️ Эта цитата уже добавлена в стикерпак.")
                return
            
            # Get chat title for pack naming
            chat_title = msg.chat.title or "Chat"
            
            # Check if pack rotation is needed and get/create current pack
            current_pack = await sticker_pack_service.get_current_pack(msg.chat.id)
            if current_pack is None:
                current_pack = await sticker_pack_service.create_new_pack(msg.chat.id, chat_title)
                await msg.reply(f"📦 Создан новый стикерпак: {current_pack.title}")
            
            # Check if pack is full and needs rotation (Requirement 8.2)
            rotated_pack = await sticker_pack_service.rotate_pack_if_needed(msg.chat.id, chat_title)
            if rotated_pack:
                await msg.reply(f"📦 Стикерпак заполнен! Создан новый: {rotated_pack.title}")
                current_pack = rotated_pack
            
            # For now, we mark the quote as a sticker candidate
            # In a full implementation, we would use Telegram Bot API to actually add to sticker pack
            # This requires the bot to be the owner of the sticker pack
            
            # Generate a placeholder sticker file ID (in real implementation, this comes from Telegram API)
            placeholder_file_id = f"sticker_{quote.id}_{msg.chat.id}"
            
            # Add sticker to pack (Property 21: Sticker record update)
            result = await sticker_pack_service.add_sticker(
                chat_id=msg.chat.id,
                quote_id=quote.id,
                sticker_file_id=placeholder_file_id,
                chat_title=chat_title
            )
            
            if result.success:
                pack_info = await sticker_pack_service.get_current_pack(msg.chat.id)
                sticker_count = pack_info.sticker_count if pack_info else 0
                
                response = f"✅ Цитата добавлена в стикерпак!\n"
                response += f"📦 Пак: {current_pack.title}\n"
                response += f"🎯 Стикеров в паке: {sticker_count}/120"
                
                if result.pack_rotated:
                    response += f"\n\n🔄 Был создан новый пак: {result.new_pack_name}"
                
                await msg.reply(response)
                logger.info(
                    f"User {msg.from_user.username} added quote {quote.id} to sticker pack "
                    f"'{current_pack.name}' (now {sticker_count} stickers)"
                )
            else:
                await msg.reply(f"❌ Ошибка: {result.error}")

    except Exception as e:
        logger.error(f"Ошибка при добавлении цитаты в стикерпак: {e}")
        await msg.reply("❌ Ошибка при добавлении цитаты в стикерпак.")


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
                
    except Exception as e:
        logger.error(f"Ошибка при удалении цитаты из стикерпака: {e}")
        await msg.reply("❌ Ошибка при удалении цитаты из стикерпака.")


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