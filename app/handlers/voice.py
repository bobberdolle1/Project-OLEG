"""Voice command handlers for TTS and STT functionality.

This module provides handlers for:
- /say command for text-to-speech conversion
- Incoming voice message recognition (STT)
- Auto-voice integration for responses

Uses Edge TTS for Russian voice synthesis (Microsoft API).
Uses faster-whisper for speech recognition (STT).

**Feature: fortress-update, grand-casino-dictator**
**Validates: Requirements 5.1, 5.2, 5.4, 15.1, 15.2, 15.3, 15.4**
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from app.services.tts import tts_service
from app.services.tts_edge import edge_tts_service
from app.services.alive_ui import alive_ui_service
from app.services.voice_recognition import transcribe_voice_message, transcribe_video_note, is_available as stt_available
from app.services.ollama_client import generate_reply_with_context, is_ollama_available

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.voice)
async def handle_voice_message(msg: Message):
    """
    Handle incoming voice messages - transcribe and respond.
    
    Uses faster-whisper for speech recognition.
    """
    if not stt_available():
        logger.warning("STT not available, skipping voice message")
        return
    
    # Проверяем доступность Ollama перед обработкой
    if not await is_ollama_available():
        logger.debug("Skipping voice message - Ollama not available")
        return
    
    logger.info(f"Voice message from @{msg.from_user.username or msg.from_user.id}")
    
    # Show typing indicator
    await msg.bot.send_chat_action(msg.chat.id, "typing")
    
    try:
        # Transcribe voice message
        text = await transcribe_voice_message(msg.bot, msg.voice.file_id)
        
        if not text:
            await msg.reply("🎤 Не удалось распознать голосовое сообщение")
            return
        
        logger.info(f"Transcribed: {text[:100]}...")
        
        # Get Oleg's response
        response = await generate_reply_with_context(
            text,
            username=msg.from_user.username or msg.from_user.first_name,
            chat_id=msg.chat.id
        )
        
        if response:
            # Reply with transcription and response
            reply_text = f"🎤 <i>{text}</i>\n\n{response}"
            await msg.reply(reply_text, parse_mode="HTML")
        else:
            # Just show transcription if no response
            await msg.reply(f"🎤 <i>{text}</i>", parse_mode="HTML")
            
    except Exception as e:
        logger.error(f"Voice message handling failed: {e}")
        await msg.reply("🎤 Ошибка при обработке голосового сообщения")


@router.message(F.video_note)
async def handle_video_note(msg: Message):
    """
    Handle incoming video notes (circles) - extract audio, transcribe and respond.
    """
    if not stt_available():
        logger.warning("STT not available, skipping video note")
        return
    
    # Проверяем доступность Ollama перед обработкой
    if not await is_ollama_available():
        logger.debug("Skipping video note - Ollama not available")
        return
    
    logger.info(f"Video note from @{msg.from_user.username or msg.from_user.id}")
    
    # Show typing indicator
    await msg.bot.send_chat_action(msg.chat.id, "typing")
    
    try:
        # Transcribe video note
        text = await transcribe_video_note(msg.bot, msg.video_note.file_id)
        
        if not text:
            await msg.reply("🎥 Не удалось распознать речь в кружочке")
            return
        
        logger.info(f"Transcribed video note: {text[:100]}...")
        
        # Get Oleg's response
        response = await generate_reply_with_context(
            text,
            username=msg.from_user.username or msg.from_user.first_name,
            chat_id=msg.chat.id
        )
        
        if response:
            reply_text = f"🎥 <i>{text}</i>\n\n{response}"
            await msg.reply(reply_text, parse_mode="HTML")
        else:
            await msg.reply(f"🎥 <i>{text}</i>", parse_mode="HTML")
            
    except Exception as e:
        logger.error(f"Video note handling failed: {e}")
        await msg.reply("🎥 Ошибка при обработке кружочка")


@router.message(Command("say"))
async def cmd_say(msg: Message):
    """
    Command /say <text> — convert text to voice message.
    
    Generates a voice message with Oleg's characteristic voice
    and sends it as a voice note. Uses EdgeTTSService with proper
    temp file lifecycle management (Create → Send → Delete).
    
    **Validates: Requirements 5.1, 15.1, 15.2, 15.3**
    
    Args:
        msg: Incoming message with /say command
    """
    # Extract text after /say command
    text = msg.text
    if text:
        # Remove the /say command prefix
        text = text.replace("/say", "", 1).strip()
    
    if not text:
        await msg.reply(
            "Напиши текст после команды, например: /say Привет, я Олег!",
            parse_mode="HTML"
        )
        return
    
    logger.info(f"TTS requested by @{msg.from_user.username or msg.from_user.id}: {text[:50]}...")
    
    # Try to generate voice with Alive UI status
    status = None
    thread_id = getattr(msg, 'message_thread_id', None)
    try:
        # Start status message for TTS generation
        status = await alive_ui_service.start_status(
            msg.chat.id, "tts", msg.bot, message_thread_id=thread_id
        )
        
        # Use Edge TTS (Microsoft API)
        result = await edge_tts_service.send_voice_with_notification(
            bot=msg.bot,
            chat_id=msg.chat.id,
            text=text,
            reply_to_message_id=msg.message_id
        )
        
        # Clean up status message
        if status:
            await alive_ui_service.finish_status(status, msg.bot)
            status = None
        
        if result.error:
            logger.warning(f"Edge TTS failed: {result.error}")
        else:
            logger.info(f"Voice sent successfully, file lifecycle: created={result.created}, sent={result.sent}, deleted={result.deleted}")
            
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        
        if status:
            await alive_ui_service.show_error(status, "Не удалось сгенерировать голос", msg.bot)
        
        # Fallback to text on any error
        await msg.reply(
            f"🔊 <i>(голосом Олега)</i>\n\n{text}",
            parse_mode="HTML"
        )


async def maybe_voice_response(text: str, msg: Message) -> bool:
    """
    Check if response should be auto-voiced and send voice if so.
    
    This function implements the 0.1% auto-voice probability.
    
    Args:
        text: Response text to potentially voice
        msg: Original message to reply to
        
    Returns:
        True if voice was sent, False if text should be sent instead
    """
    if not tts_service.should_auto_voice():
        return False
    
    logger.info(f"Auto-voice triggered for response to @{msg.from_user.username or msg.from_user.id}")
    
    try:
        # Use Edge TTS
        result = await edge_tts_service.send_voice(
            bot=msg.bot,
            chat_id=msg.chat.id,
            text=text,
            reply_to_message_id=msg.message_id
        )
        
        if result.error:
            logger.warning(f"Auto-voice Edge TTS failed: {result.error}")
            return False
        
        return result.sent
        
    except Exception as e:
        logger.error(f"Auto-voice generation failed: {e}")
        return False
