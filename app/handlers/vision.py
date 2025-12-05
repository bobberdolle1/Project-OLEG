"""Модуль обработки изображений (Vision Module) для бота Олег."""

import logging
import base64
import asyncio
from io import BytesIO
from typing import Optional
import httpx
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from app.config import settings
from app.services.ollama_client import _ollama_chat

logger = logging.getLogger(__name__)

router = Router()

async def analyze_image_with_vlm(image_data: bytes, prompt: str) -> str:
    """
    Анализирует изображение с помощью мультимодальной модели Ollama.

    Args:
        image_data: Байты изображения
        prompt: Текст запроса к модели

    Returns:
        Результат анализа изображения
    """
    try:
        # Кодируем изображение в base64 для передачи в API
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        # Подготавливаем данные для запроса к Ollama
        payload = {
            "model": settings.ollama_vision_model,  # Используем модель из конфига
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_base64]  # Передаем закодированное изображение
                }
            ],
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_ctx": 4096,
                "num_predict": 1024,
                "repeat_penalty": 1.2,
                "stop": ["Ты — в чате", "Ты —"]
            }
        }

        async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            return data.get("message", {}).get("content", "").strip()

    except httpx.ConnectError:
        logger.error("Не могу подключиться к Ollama серверу")
        return "❌ Не могу связаться с сервером ИИ. Проверь, запущен ли Ollama с мультимодальной моделью."
    except Exception as e:
        logger.error(f"Ошибка при анализе изображения: {e}")
        return "⚠️ Не удалось проанализировать изображение. Попробуйте другое."


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

    # Если есть текст, используем его как запрос для анализа изображения
    if text and text.strip():
        # Подготавливаем промпт для анализа изображения
        vision_prompt = f"""
        Проанализируй это изображение и ответь на следующий вопрос:
        {text}

        Будь кратким и точным в своем ответе. Используй манеру Олега - грубоватую, но по делу.
        """
    else:
        # Если текста нет, просто описываем изображение
        vision_prompt = """
        Дай краткое описание этого изображения. Если видишь ошибки, код или схему - объясни в стиле Олега, коротко и по делу.
        """

    from aiogram.exceptions import TelegramBadRequest

    processing_msg = None
    try:
        # Отправляем индикатор процесса
        processing_msg = await msg.reply("👀 Разглядываю...")

        # Анализируем изображение
        analysis_result = await analyze_image_with_vlm(image_bytes, vision_prompt)

        # Удаляем сообщение о процессе
        if processing_msg:
            try:
                await processing_msg.delete()
            except:
                pass  # Игнорируем ошибку при удалении

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