"""Обработчик голосовых сообщений с распознаванием речи."""

import logging
from aiogram import Router, F
from aiogram.types import Message

from app.config import settings
from app.services.voice_recognition import transcribe_voice_message, is_available
from app.services.ollama_client import generate_reply_with_context, extract_facts_from_message, store_fact_to_memory

logger = logging.getLogger(__name__)

router = Router()


def _is_meaningful_text(text: str) -> bool:
    """
    Проверяет, содержит ли текст что-то осмысленное.
    Фильтрует короткие междометия типа "ага", "угу", "лол".
    """
    if not text:
        return False
    
    # Минимальная длина для осмысленного сообщения
    if len(text) < 10:
        return False
    
    # Список бессмысленных фраз
    meaningless = [
        "ага", "угу", "ну", "да", "нет", "ок", "окей", "лол", "хах", "ахах",
        "эм", "ээ", "ммм", "хм", "ну да", "ну нет", "типа", "короче"
    ]
    
    text_lower = text.lower().strip()
    return text_lower not in meaningless


@router.message(F.voice)
async def handle_voice_message(msg: Message):
    """
    Обработчик голосовых сообщений.
    Распознаёт речь и обрабатывает как текстовое сообщение.
    """
    # Проверяем, включена ли функция
    if not settings.voice_recognition_enabled:
        # Если выключено — просто ругаемся как раньше
        await msg.reply("Голосовые? Серьёзно? Пиши текстом, я не твоя мамка.")
        return
    
    # Проверяем доступность Whisper
    if not is_available():
        await msg.reply(
            "Распознавание голоса временно недоступно. "
            "Пиши текстом, пока админы чинят."
        )
        return
    
    # Отправляем индикатор обработки
    processing_msg = await msg.reply("🎤 Слушаю твою голосовуху...")
    
    try:
        # Распознаём голосовое
        text = await transcribe_voice_message(msg.bot, msg.voice.file_id)
        
        if not text:
            await processing_msg.edit_text(
                "Не разобрал, что ты там бормочешь. "
                "Говори чётче или пиши текстом."
            )
            return
        
        # Показываем распознанный текст
        await processing_msg.edit_text(f"🎤 Распознано: «{text}»\n\n⏳ Думаю над ответом...")
        
        # Проверяем, стоит ли сохранять в RAG
        if _is_meaningful_text(text):
            user_info = {"username": msg.from_user.username} if msg.from_user.username else {}
            facts = await extract_facts_from_message(text, msg.chat.id, user_info)
            for fact in facts:
                await store_fact_to_memory(fact['text'], msg.chat.id, fact['metadata'])
        
        # Генерируем ответ как на обычное текстовое сообщение
        reply = await generate_reply_with_context(
            user_text=text,
            username=msg.from_user.username,
            chat_id=msg.chat.id,
            chat_context=None
        )
        
        # Отправляем ответ
        await processing_msg.edit_text(f"🎤 «{text}»\n\n{reply}")
        
        logger.info(f"Голосовое от @{msg.from_user.username}: {text[:50]}...")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке голосового: {e}")
        await processing_msg.edit_text(
            "Что-то пошло не так с твоей голосовухой. "
            "Попробуй ещё раз или пиши текстом."
        )


@router.message(F.video_note)
async def handle_video_note(msg: Message):
    """
    Обработчик видеосообщений (кружочков).
    Пока просто ругаемся — распознавание видео сложнее.
    """
    await msg.reply(
        "Кружочки? Ты думаешь я буду смотреть твоё лицо? "
        "Пиши текстом или голосом, если лень печатать."
    )
