"""Модуль обработки изображений (Vision Module) для бота Олег.

Использует 2-step Vision Pipeline для анализа изображений:
Step 1: Vision model описывает изображение (скрыто от пользователя)
Step 2: Oleg LLM комментирует описание в своём стиле
"""

import logging
import random
import re
from typing import Optional
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from app.services.vision_pipeline import vision_pipeline
from app.services.ollama_client import is_ollama_available

logger = logging.getLogger(__name__)


# Триггеры для упоминания Олега
OLEG_TRIGGERS = ["олег", "олега", "олегу", "олегом", "олеге", "oleg"]

# Вероятность авто-ответа на изображения (2-5%)
AUTO_IMAGE_REPLY_PROBABILITY = 0.035  # 3.5% базовая вероятность


def _contains_bot_mention(text: str, bot) -> bool:
    """
    Проверяет, содержит ли текст упоминание бота.
    
    Args:
        text: Текст для проверки (caption или message text)
        bot: Объект бота для получения username
        
    Returns:
        True если текст содержит упоминание бота
    """
    if not text:
        return False
    
    text_lower = text.lower()
    
    # Проверяем @username бота
    if bot and bot._me and bot._me.username:
        bot_username = bot._me.username.lower()
        if f"@{bot_username}" in text_lower:
            return True
    
    # Проверяем слово "олег" и его формы как отдельное слово
    for trigger in OLEG_TRIGGERS:
        if re.search(rf'\b{trigger}\b', text_lower):
            return True
    
    return False


async def should_process_image(msg: Message) -> tuple[bool, bool]:
    """
    Проверяет, нужно ли обрабатывать изображение.
    
    Бот обрабатывает изображение если:
    - В caption есть упоминание бота (@username или "олег")
    - Это ответ на сообщение бота
    - Авто-ответ сработал по вероятности (2-5%)
    
    Args:
        msg: Сообщение с изображением
        
    Returns:
        Tuple (should_process, is_auto_reply)
        
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
    """
    # Проверяем доступность Ollama перед обработкой
    if not await is_ollama_available():
        logger.debug(f"Image processing: skipping - Ollama not available")
        return False, False
    
    # Проверяем caption на упоминание бота
    caption = msg.caption or ""
    if _contains_bot_mention(caption, msg.bot):
        logger.debug(f"Image processing: bot mentioned in caption for message {msg.message_id}")
        return True, False
    
    # Проверяем, является ли это ответом на сообщение бота
    if msg.reply_to_message and msg.reply_to_message.from_user:
        if msg.reply_to_message.from_user.id == msg.bot.id:
            logger.debug(f"Image processing: reply to bot message for message {msg.message_id}")
            return True, False
    
    # Авто-ответ на изображения с вероятностью 2-5%
    # Только в групповых чатах, не в личных сообщениях
    if msg.chat.type != "private":
        if random.random() < AUTO_IMAGE_REPLY_PROBABILITY:
            logger.debug(f"Image processing: auto-reply triggered for message {msg.message_id}")
            return True, True
    
    logger.debug(f"Image processing: skipping message {msg.message_id} - no explicit mention")
    return False, False

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
    
    Обрабатывает изображение если:
    - Упоминание в caption (@username или "олег")
    - Ответ на сообщение бота
    - Авто-ответ сработал (2-5% вероятность)
    
    **Validates: Requirements 1.1, 1.4**
    """
    # Проверяем, нужно ли обрабатывать изображение
    should_process, is_auto_reply = await should_process_image(msg)
    if not should_process:
        return
    
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
    # Для авто-ответов не используем caption как запрос
    user_query = None
    if not is_auto_reply and text and text.strip():
        user_query = text.strip()

    from aiogram.exceptions import TelegramBadRequest

    processing_msg = None
    try:
        # Для авто-ответов не показываем индикатор процесса
        if not is_auto_reply:
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
            if not is_auto_reply:
                await msg.reply("Хм, модель молчит. Попробуй другую картинку или спроси текстом.")
            return

        # Обрезаем результат если слишком длинный (лимит Telegram - 4096 символов)
        max_length = 4000  # Оставляем запас
        if len(analysis_result) > max_length:
            analysis_result = analysis_result[:max_length] + "...\n\n[обрезано, слишком много текста]"

        # Для авто-ответов добавляем префикс
        if is_auto_reply:
            prefixes = ["👀 ", "🤔 ", "Хм, ", "О, ", ""]
            analysis_result = random.choice(prefixes) + analysis_result

        # Отправляем результат
        await msg.reply(analysis_result)
        
        if is_auto_reply:
            logger.info(f"Auto-reply to image in chat {msg.chat.id}")

    except TelegramBadRequest as e:
        # Игнорируем ошибки типа "thread not found" - топик был удалён
        if "thread not found" in str(e).lower() or "message to reply not found" in str(e).lower():
            logger.warning(f"Не удалось ответить - топик/сообщение удалено: {e}")
        else:
            logger.error(f"Telegram ошибка при обработке изображения: {e}")
    except Exception as e:
        logger.error(f"Ошибка при обработке изображения: {e}")
        if not is_auto_reply:
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