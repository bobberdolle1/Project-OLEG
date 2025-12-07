"""
GIF Patrol Handler - обработчик GIF-анимаций для модерации.

Перехватывает GIF/анимации и анализирует их на запрещённый контент
через GIFPatrolService.

**Feature: fortress-update**
**Validates: Requirements 3.3, 3.4, 3.5**
"""

import logging
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

from app.services.gif_patrol import gif_patrol_service, GIFAnalysisResult
from app.services.alive_ui import alive_ui_service

logger = logging.getLogger(__name__)

router = Router()

# Максимальный размер файла для анализа (20MB)
MAX_FILE_SIZE = 20 * 1024 * 1024

# Таймаут для анализа GIF (секунды)
ANALYSIS_TIMEOUT = 5.0


async def extract_animation_bytes(message: Message, bot: Bot) -> Optional[bytes]:
    """
    Извлекает байты анимации из сообщения.
    
    Args:
        message: Сообщение с анимацией
        bot: Экземпляр бота
        
    Returns:
        Байты анимации или None
    """
    try:
        animation = message.animation
        if not animation:
            return None
        
        # Проверяем размер файла
        if animation.file_size and animation.file_size > MAX_FILE_SIZE:
            logger.warning(f"Animation too large: {animation.file_size} bytes")
            return None
        
        # Получаем file_info для загрузки
        file_info = await bot.get_file(animation.file_id)
        
        # Загружаем файл
        file_bytes_io = await bot.download_file(file_info.file_path)
        return file_bytes_io.read()
        
    except Exception as e:
        logger.error(f"Error extracting animation: {e}")
        return None


async def handle_unsafe_content(
    message: Message, 
    result: GIFAnalysisResult,
    bot: Bot
) -> None:
    """
    Обрабатывает обнаружение небезопасного контента.
    
    Args:
        message: Сообщение с GIF
        result: Результат анализа
        bot: Экземпляр бота
    """
    try:
        # Удаляем сообщение
        await message.delete()
        
        # Формируем причину
        categories = ", ".join(result.detected_categories)
        
        # Баним пользователя
        try:
            await bot.ban_chat_member(
                chat_id=message.chat.id,
                user_id=message.from_user.id
            )
            logger.info(
                f"Banned user {message.from_user.id} in chat {message.chat.id} "
                f"for inappropriate GIF content: {categories}"
            )
        except TelegramBadRequest as e:
            # Возможно, нет прав на бан
            logger.warning(f"Could not ban user: {e}")
        
        # Отправляем уведомление в чат
        notification = (
            f"🚫 GIF-патруль обнаружил запрещённый контент ({categories}) "
            f"от пользователя {message.from_user.full_name}. "
            f"Сообщение удалено, пользователь заблокирован."
        )
        
        try:
            await bot.send_message(
                chat_id=message.chat.id,
                text=notification,
                message_thread_id=thread_id
            )
        except TelegramBadRequest:
            pass  # Игнорируем ошибки отправки уведомления
            
    except Exception as e:
        logger.error(f"Error handling unsafe content: {e}")


async def queue_for_later_analysis(
    message: Message,
    file_id: str
) -> None:
    """
    Ставит GIF в очередь для отложенного анализа.
    
    Используется когда Vision модель недоступна.
    
    Args:
        message: Сообщение с GIF
        file_id: Telegram file_id
    """
    try:
        task_id = await gif_patrol_service.queue_analysis(
            message_id=message.message_id,
            chat_id=message.chat.id,
            file_id=file_id
        )
        logger.info(f"Queued GIF for later analysis: {task_id}")
    except Exception as e:
        logger.error(f"Error queuing GIF for analysis: {e}")


@router.message(F.animation)
async def handle_animation_message(message: Message, bot: Bot):
    """
    Обработчик сообщений с GIF/анимациями.
    
    Анализирует GIF на запрещённый контент и принимает меры
    при обнаружении нарушений.
    
    **Validates: Requirements 3.3, 3.4, 3.5**
    """
    # Пропускаем сообщения без отправителя (системные)
    if not message.from_user:
        return
    
    # Пропускаем сообщения от ботов
    if message.from_user.is_bot:
        return
    
    animation = message.animation
    if not animation:
        return
    
    logger.info(
        f"Processing animation from user {message.from_user.id} "
        f"in chat {message.chat.id}"
    )
    
    # Извлекаем байты анимации
    animation_bytes = await extract_animation_bytes(message, bot)
    
    if not animation_bytes:
        # Не удалось загрузить - ставим в очередь на потом
        await queue_for_later_analysis(message, animation.file_id)
        return
    
    # Start Alive UI status for GIF analysis
    # **Validates: Requirements 12.1, 12.2, 12.3**
    status = None
    thread_id = getattr(message, 'message_thread_id', None)
    try:
        # Only show status for potentially long analysis
        status = await alive_ui_service.start_status(
            message.chat.id, "gif", bot, message_thread_id=thread_id
        )
        
        # Анализируем GIF
        result = await gif_patrol_service.analyze_gif(animation_bytes)
        
        # Clean up status message
        # **Property 32: Status cleanup**
        if status:
            await alive_ui_service.finish_status(status, bot)
            status = None
        
        # Проверяем на ошибку анализа (Vision недоступен)
        if result.error:
            logger.warning(f"GIF analysis error: {result.error}")
            # Ставим в очередь для повторного анализа
            await queue_for_later_analysis(message, animation.file_id)
            return
        
        # Если контент небезопасен - принимаем меры
        if not result.is_safe:
            logger.warning(
                f"Unsafe GIF detected from user {message.from_user.id}: "
                f"{result.detected_categories}"
            )
            await handle_unsafe_content(message, result, bot)
        else:
            logger.debug(
                f"GIF from user {message.from_user.id} passed analysis"
            )
            
    except Exception as e:
        logger.error(f"Error analyzing GIF: {e}")
        
        # Show error on status message if it exists
        # **Validates: Requirements 12.6**
        if status:
            await alive_ui_service.show_error(status, "Ошибка анализа GIF", bot)
        
        # При ошибке - ставим в очередь (fail-open)
        await queue_for_later_analysis(message, animation.file_id)
