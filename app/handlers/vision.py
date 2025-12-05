"""Модуль обработки изображений (Vision Module) для бота Олег.

Использует 2-step Vision Pipeline для анализа изображений:
Step 1: Vision model описывает изображение (скрыто от пользователя)
Step 2: Oleg LLM комментирует описание в своём стиле
"""

import logging
from typing import Optional
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from app.services.vision_pipeline import vision_pipeline

logger = logging.getLogger(__name__)

router = Router()


# Legacy function kept for backward compatibility - now uses VisionPipeline
async def analyze_image_with_vlm(image_data: bytes, prompt: str) -> str:
    """
    Анализирует изображение с помощью 2-step Vision Pipeline.
    
    DEPRECATED: Используйте vision_pipeline.analyze() напрямую.

    Args:
        image_data: Байты изображения
        prompt: Текст запроса к модели (используется как user_query)

    Returns:
        Результат анализа изображения в стиле Олега
    """
    logger.info(f"analyze_image_with_vlm called (legacy), delegating to VisionPipeline")
    return await vision_pipeline.analyze(image_data, user_query=prompt if prompt else None)


async def extract_image_bytes(message: Message) -> Optional[bytes]:
    """
    Извлекает байты изображения из сообщения.

    Args:
        message: Сообщение с изображением

    Returns:
        Байты изображения или None
    """
    try:
        # Получаем самое большое фото из списка
        if message.photo:
            # Берем самое большое изображение (последнее в списке)
            photo = message.photo[-1]

            # Получаем file_info для загрузки
            file_info = await message.bot.get_file(photo.file_id)

            # Загружаем изображение
            file_bytes_io = await message.bot.download_file(file_info.file_path)
            image_bytes = file_bytes_io.read()
            return image_bytes
        elif message.document and message.document.mime_type and message.document.mime_type.startswith('image/'):
            # Если это документ изображения
            file_info = await message.bot.get_file(message.document.file_id)
            file_bytes_io = await message.bot.download_file(file_info.file_path)
            image_bytes = file_bytes_io.read()
            return image_bytes
        else:
            return None
    except Exception as e:
        logger.error(f"Ошибка при извлечении изображения: {e}")
        return None


@router.message(F.photo | F.document)
async def handle_image_message(msg: Message):
    """
    Обработчик сообщений с изображениями.
    """
    # Проверяем, есть ли текст рядом с изображением (для запроса)
    text = msg.caption if msg.caption else ""

    # Проверяем, не является ли это командой
    if text and text.startswith('/'):
        return

    # Проверяем, есть ли изображение
    image_bytes = await extract_image_bytes(msg)
    if not image_bytes:
        logger.warning(f"Не удалось извлечь изображение из сообщения {msg.message_id}")
        return

    # Используем текст как user_query для VisionPipeline
    user_query = text.strip() if text and text.strip() else None

    from aiogram.exceptions import TelegramBadRequest

    processing_msg = None
    try:
        # Отправляем индикатор процесса
        processing_msg = await msg.reply("👀 Разглядываю...")

        # Анализируем изображение через 2-step Vision Pipeline
        # Step 1: Vision model описывает изображение (скрыто от пользователя)
        # Step 2: Oleg LLM комментирует описание в своём стиле
        analysis_result = await vision_pipeline.analyze(image_bytes, user_query=user_query)

        # Удаляем сообщение о процессе
        if processing_msg:
            try:
                await processing_msg.delete()
            except:
                pass  # Игнорируем ошибку при удалении

        # Проверяем на пустой результат
        if not analysis_result or not analysis_result.strip():
            await msg.reply("Хм, модель молчит. Попробуй другую картинку или спроси текстом.")
            return

        # Обрезаем результат если слишком длинный (лимит Telegram - 4096 символов)
        max_length = 4000  # Оставляем запас
        if len(analysis_result) > max_length:
            analysis_result = analysis_result[:max_length] + "...\n\n[обрезано, слишком много текста]"

        # Отправляем результат
        await msg.reply(analysis_result)

    except TelegramBadRequest as e:
        # Игнорируем ошибки типа "thread not found" - топик был удалён
        if "thread not found" in str(e).lower() or "message to reply not found" in str(e).lower():
            logger.warning(f"Не удалось ответить - топик/сообщение удалено: {e}")
        else:
            logger.error(f"Telegram ошибка при обработке изображения: {e}")
    except Exception as e:
        logger.error(f"Ошибка при обработке изображения: {e}")
        try:
            await msg.reply("Глаза мои разлюбили. Не могу разглядеть, что там на скрине.")
        except:
            pass  # Если не можем ответить - просто игнорируем


# Команда для проверки работы модуля зрения
@router.message(Command("vision_test"))
async def cmd_vision_test(msg: Message):
    """
    Команда для тестирования модуля зрения.
    """
    await msg.reply(
        "📸 Модуль зрения активирован!\n"
        "Пришли фото со своим вопросом в описании, и я всё рассмотрю и отвечу по существу."
    )