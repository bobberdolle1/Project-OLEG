"""Voice command handlers for TTS functionality.

This module provides handlers for:
- /say command for text-to-speech conversion
- Auto-voice integration for responses

Uses Silero TTS for Russian voice synthesis (offline, works in Russia).

**Feature: fortress-update, grand-casino-dictator**
**Validates: Requirements 5.1, 5.2, 5.4, 15.1, 15.2, 15.3, 15.4**
"""

import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.services.tts import tts_service
from app.services.tts_silero import silero_tts_service
from app.services.alive_ui import alive_ui_service, status_context

logger = logging.getLogger(__name__)

router = Router()


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
    # **Validates: Requirements 12.1, 12.2, 12.3**
    status = None
    # Get thread_id for forum chats
    thread_id = getattr(msg, 'message_thread_id', None)
    try:
        # Start status message for TTS generation (shows after 2 seconds)
        # **Property 29: Status message timing**
        status = await alive_ui_service.start_status(
            msg.chat.id, "tts", msg.bot, message_thread_id=thread_id
        )
        
        # Use Silero TTS (offline, works in Russia without restrictions)
        # **Validates: Requirements 15.1, 15.2, 15.3, 15.4**
        result = await silero_tts_service.send_voice(
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
            logger.warning(f"Silero TTS failed: {result.error}")
            # Send text fallback
            await msg.reply(
                f"🔊 <b>Голосовой движок временно недоступен</b>\n\n<i>{text}</i>",
                parse_mode="HTML"
            )
        else:
            logger.info(f"Voice sent successfully, file lifecycle: created={result.created}, sent={result.sent}, deleted={result.deleted}")
            
            if result.was_truncated:
                logger.info(f"Text was truncated for TTS: {len(text)} -> {len(result.original_text)} chars")
            
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        
        # Show error on status message if it exists
        # **Validates: Requirements 12.6**
        if status:
            await alive_ui_service.show_error(status, "Не удалось сгенерировать голос", msg.bot)
        
        # Fallback to text on any error
        # **Validates: Requirements 5.4, 15.4**
        await msg.reply(
            f"🔊 <i>(голосом Олега)</i>\n\n{text}",
            parse_mode="HTML"
        )


async def maybe_voice_response(text: str, msg: Message) -> bool:
    """
    Check if response should be auto-voiced and send voice if so.
    
    This function implements the 0.1% auto-voice probability.
    Call this before sending a text response to potentially
    convert it to voice. Uses Silero TTS (offline, works in Russia).
    
    **Validates: Requirements 5.2, 15.1, 15.2, 15.3**
    
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
        # Use Silero TTS (offline, works in Russia)
        result = await silero_tts_service.send_voice(
            bot=msg.bot,
            chat_id=msg.chat.id,
            text=text,
            reply_to_message_id=msg.message_id
        )
        
        if result.error:
            logger.warning(f"Auto-voice Silero failed: {result.error}")
            return False
        
        return result.sent
        
    except Exception as e:
        logger.error(f"Auto-voice generation failed: {e}")
        return False
