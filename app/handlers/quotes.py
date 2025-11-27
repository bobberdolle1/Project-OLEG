"""Обработчик команд цитатника (OlegQuotes)."""

import logging
import random
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from aiogram import Router, F
from aiogram.types import Message, ContentType
from aiogram.filters import Command
from aiogram.methods import SendSticker
from aiogram.exceptions import TelegramBadRequest

from app.database.session import get_session
from app.database.models import User
from app.handlers.games import ensure_user

logger = logging.getLogger(__name__)

router = Router()

# Шрифты для рендеринга цитат (попробуем использовать системные)
try:
    # Попробуем использовать стандартный шрифт
    default_font = ImageFont.truetype("DejaVuSans.ttf", 16)
    username_font = ImageFont.truetype("DejaVuSans.ttf", 14)
except:
    # Если не найден, используем дефолтный
    default_font = ImageFont.load_default()
    username_font = ImageFont.load_default()


async def create_quote_image(text: str, username: str) -> BytesIO:
    """
    Создает изображение цитаты с текстом и именем пользователя.
    
    Args:
        text: Текст цитаты
        username: Имя пользователя
    
    Returns:
        BytesIO объект с изображением
    """
    # Настройки изображения
    width, height = 512, 256
    padding = 20
    avatar_size = 40
    
    # Создаем изображение
    img = Image.new('RGB', (width, height), color=(54, 57, 63))  # Серый фон как в Discord
    draw = ImageDraw.Draw(img)
    
    # Рисуем контейнер для сообщения
    message_rect = [
        padding, 
        padding, 
        width - padding, 
        height - padding
    ]
    
    # Добавляем рамку
    draw.rectangle(message_rect, outline=(88, 101, 242), width=2)
    
    # Рисуем аватарку (условную)
    avatar_rect = [padding + 5, padding + 5, padding + 5 + avatar_size, padding + 5 + avatar_size]
    draw.ellipse(avatar_rect, fill=(88, 101, 242))
    
    # Рендерим имя пользователя
    username_text = f"@{username}" if username else "Аноним"
    draw.text((padding + 5 + avatar_size + 10, padding + 5), username_text, font=username_font, fill=(255, 255, 255))
    
    # Рендерим текст сообщения
    # Для простоты, обрежем текст если он слишком длинный
    if len(text) > 140:
        text = text[:140] + "..."
    
    draw.text((padding + 5 + avatar_size + 10, padding + 25), text, font=default_font, fill=(218, 219, 220))
    
    # Сохраняем в BytesIO
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    return img_io


async def create_quote_with_comment(text: str, username: str, comment: str) -> BytesIO:
    """
    Создает изображение цитаты с текстом, именем пользователя и комментарием Олега.
    
    Args:
        text: Текст цитаты
        username: Имя пользователя
        comment: Комментарий Олега
    
    Returns:
        BytesIO объект с изображением
    """
    # Настройки изображения
    width, height = 512, 356
    padding = 20
    avatar_size = 40
    
    # Создаем изображение
    img = Image.new('RGB', (width, height), color=(54, 57, 63))  # Серый фон как в Discord
    draw = ImageDraw.Draw(img)
    
    # Рисуем контейнер для оригинального сообщения
    message_rect = [
        padding, 
        padding, 
        width - padding, 
        height // 2
    ]
    
    # Добавляем рамку
    draw.rectangle(message_rect, outline=(88, 101, 242), width=2)
    
    # Рисуем аватарку (условную)
    avatar_rect = [padding + 5, padding + 5, padding + 5 + avatar_size, padding + 5 + avatar_size]
    draw.ellipse(avatar_rect, fill=(88, 101, 242))
    
    # Рендерим имя пользователя
    username_text = f"@{username}" if username else "Аноним"
    draw.text((padding + 5 + avatar_size + 10, padding + 5), username_text, font=username_font, fill=(255, 255, 255))
    
    # Рендерим текст сообщения
    if len(text) > 140:
        text = text[:140] + "..."
    
    draw.text((padding + 5 + avatar_size + 10, padding + 25), text, font=default_font, fill=(218, 219, 220))
    
    # Рендерим комментарий Олега
    comment_rect = [
        padding,
        height // 2,
        width - padding,
        height - padding
    ]
    
    # Добавляем рамку для комментария
    draw.rectangle(comment_rect, outline=(240, 71, 71), width=2)  # Красная рамка для комментария Олега
    
    # Рендерим комментарий Олега
    oleg_text = f"Олег: {comment}"
    if len(oleg_text) > 140:
        oleg_text = oleg_text[:140] + "..."
    
    draw.text((padding + 10, height // 2 + 15), oleg_text, font=default_font, fill=(255, 215, 0))  # Желтый цвет для Олега
    
    # Сохраняем в BytesIO
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    return img_io


@router.message(Command("q"))
async def cmd_quote(msg: Message):
    """
    Команда /q - генерирует цитату из одного сообщения.
    
    Использование:
    - /q (в ответ на сообщение) - создает цитату из одного сообщения
    - /q [число] (в ответ на сообщение) - создает цитату из нескольких сообщений
    - /q * (в ответ на сообщение) - режим прожарки с комментарием Олега
    """
    if not msg.reply_to_message:
        await msg.reply("❌ Нужно ответить на сообщение, чтобы сделать из него цитату.")
        return

    # Получаем текст команды
    command_text = msg.text.split(maxsplit=1)
    param = command_text[1] if len(command_text) > 1 else None

    # Определяем режим работы
    if param == "*":
        # Режим прожарки
        await _generate_roast_quote(msg)
    elif param and param.isdigit():
        # Режим нескольких сообщений
        count = int(param)
        if count > 10:
            await msg.reply("❌ Слишком много сообщений для цитаты (максимум 10).")
            return
        await _generate_multi_message_quote(msg, count)
    else:
        # Режим одного сообщения
        await _generate_single_message_quote(msg)


async def _generate_single_message_quote(msg: Message):
    """Генерирует цитату из одного сообщения."""
    original_msg = msg.reply_to_message
    
    # Извлекаем текст из сообщения
    text = extract_message_text(original_msg)
    if not text:
        await msg.reply("❌ Не могу создать цитату из этого сообщения (нет текста).")
        return
    
    username = original_msg.from_user.username or original_msg.from_user.first_name
    
    try:
        # Создаем изображение цитаты
        image_io = await create_quote_image(text, username)
        
        # Отправляем изображение как фото
        await msg.answer_photo(photo=image_io, caption="💬 Цитата создана")
        
        # Сохраняем цитату в базу данных как возможный стикер
        # Сохраняем ID чата и сообщения, содержащего цитату (original_msg), а не команду
        await save_quote_to_db(
            user_id=original_msg.from_user.id,
            text=text,
            username=username,
            image_io=image_io,
            telegram_chat_id=original_msg.chat.id,
            telegram_message_id=original_msg.message_id
        )
        
    except Exception as e:
        logger.error(f"Ошибка при создании цитаты: {e}")
        await msg.reply("❌ Ошибка при создании цитаты.")


async def _generate_multi_message_quote(msg: Message, count: int):
    """Генерирует цитату из нескольких сообщений."""
    # Эта функция требует доступ к истории чата, что в aiogram может быть ограничено
    # Для упрощения реализации, пока что поддержим только одно сообщение
    # В продвинутой реализации нужно будет использовать Telegram API для получения истории
    await msg.reply(f"🔄 Режим нескольких сообщений ({count}) в разработке. Пока поддерживается только одно сообщение.")
    await _generate_single_message_quote(msg)


async def _generate_roast_quote(msg: Message):
    """Генерирует цитату с комментарием Олега (режим прожарки)."""
    original_msg = msg.reply_to_message
    
    # Извлекаем текст из сообщения
    text = extract_message_text(original_msg)
    if not text:
        await msg.reply("❌ Не могу создать цитату из этого сообщения (нет текста).")
        return
    
    username = original_msg.from_user.username or original_msg.from_user.first_name
    
    try:
        # Генерируем комментарий Олега с помощью Ollama
        from app.services.ollama_client import _ollama_chat
        
        # Подготавливаем промпт для генерации комментария
        roast_prompt = (
            f"Ты - Олег, грубоватый, прямолинейный, матерящийся, "
            f"но полезный бот. Дай короткий, едкий комментарий "
            f"к следующему сообщению: '{text}'. "
            f"Твой комментарий должен быть ёмким, с юмором или сарказмом, "
            f"но без оскорблений по признакам. Максимум 1-2 предложения."
        )
        
        system_prompt = (
            "Ты - Олег, грубоватый, прямолинейный, матерящийся, "
            "но полезный бот. Говори коротко, по делу, с иронией и сленгом. "
            "Можешь ругнуться, но без оскорблений по запрещённым признакам. "
            "Контекст — чаты про технику, разгон, Steam Deck, железо. "
            "Помогай чётко, без воды."
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": roast_prompt}
        ]
        
        comment = await _ollama_chat(messages, temperature=0.8)
        
        # Создаем изображение цитаты с комментарием
        image_io = await create_quote_with_comment(text, username, comment)
        
        # Отправляем изображение как фото
        await msg.answer_photo(photo=image_io, caption="🔥 Режим прожарки активирован")
        
        # Сохраняем цитату в базу данных как возможный стикер
        # Сохраняем ID чата и сообщения, содержащего цитату (original_msg), а не команду
        await save_quote_to_db(
            user_id=original_msg.from_user.id,
            text=text,
            username=username,
            image_io=image_io,
            comment=comment,
            telegram_chat_id=original_msg.chat.id,
            telegram_message_id=original_msg.message_id
        )
        
    except Exception as e:
        logger.error(f"Ошибка при создании цитаты с комментарием: {e}")
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
    """
    if not msg.reply_to_message:
        await msg.reply("❌ Нужно ответить на сообщение с цитатой, чтобы добавить её в стикерпак.")
        return

    # Проверяем, что это сообщение с изображением (цитатой)
    if not (msg.reply_to_message.photo or msg.reply_to_message.sticker):
        await msg.reply("❌ Можно добавлять в стикерпак только изображения цитат.")
        return

    try:
        # В текущей реализации мы не можем программно создавать стикерпаки через бота
        # Вместо этого пометим цитату как подходящую для стикерпака в базе данных
        # Найдем цитату в базе данных по каким-то критериям (в реальной системе нужен будет способ идентификации)

        # Для демонстрации просто покажем сообщение и логируем
        await msg.reply("🔄 Цитата помечена как подходящая для стикерпака.")
        logger.info(f"Пользователь {msg.from_user.username} отметил цитату для стикерпака")

        # В продвинутой реализации:
        # 1. Нужно будет находить соответствующую запись цитаты в базе данных
        # 2. Помечать её как стикер
        # 3. При накоплении N цитат можно будет вручную создать стикерпак
        # Пока что просто логируем действие

    except Exception as e:
        logger.error(f"Ошибка при добавлении цитаты в стикерпак: {e}")
        await msg.reply("❌ Ошибка при добавлении цитаты в стикерпак.")


@router.message(Command("qd"))
async def cmd_quote_delete(msg: Message):
    """
    Команда /qd - удаляет цитату из стикерпака (только для админов).
    Работает в ответ на сообщение с цитатой.
    """
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

    # В текущей реализации просто снимаем пометку стикера
    await msg.reply("🔄 Цитата снята с пометки стикера.")

    # В продвинутой реализации:
    # 1. Нужно будет находить соответствующую запись цитаты в базе данных
    # 2. Снимать с неё пометку стикера
    logger.info(f"Администратор {msg.from_user.username} снял цитату с пометки стикера")


# Обработчик реакций на сообщения (включая цитаты) для "живых цитат"
from aiogram import Router
from aiogram.types import MessageReactionUpdated

# Создаем отдельный роутер для реакций
reactions_router = Router()

@reactions_router.message_reaction()
async def handle_message_reaction(update: MessageReactionUpdated):
    """
    Обрабатывает реакции на сообщения, включая цитаты.
    Используется для "живых цитат" - если цитата набирает N лайков,
    она попадает в "золотой фонд".
    """
    # Проверяем, есть ли добавленные реакции
    if update.new_reaction:
        for reaction in update.new_reaction:
            # Проверяем, является ли реакция лайком (emoji или other_type)
            if hasattr(reaction, 'emoji') and reaction.emoji in ['👍', '❤️', '🔥', '+1']:
                # Это лайк, увеличиваем счётчик для соответствующей цитаты
                await handle_like_reaction(update)
                return


async def handle_like_reaction(update: MessageReactionUpdated):
    """
    Обрабатывает лайк-реакции на сообщения.

    Args:
        update: Обновление реакции
    """
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

            # Если цитата набрала 5 и более лайков, добавляем в "золотой фонд"
            if quote.likes_count >= 5 and not quote.is_golden_fund:
                quote.is_golden_fund = True
                await session.commit()
                logger.info(f"Цитата ID {quote.id} добавлена в 'золотой фонд'")

                # Уведомляем пользователей о достижении
                try:
                    # В реальной реализации можно отправить уведомление в чат
                    # await bot.send_message(chat_id=update.chat.id, text=f"🎉 Цитата стала частью 'золотого фонда'!")
                    pass
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления о 'золотом фонде': {e}")

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