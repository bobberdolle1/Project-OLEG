"""Utility functions for the bot."""

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """
    Get current UTC time (Python 3.12+ compatible).
    
    Replaces deprecated utc_now().
    
    Returns:
        Current UTC datetime with timezone info
    """
    return datetime.now(timezone.utc)


async def safe_reply(
    msg: Message,
    text: str,
    parse_mode: Optional[str] = None,
    disable_web_page_preview: bool = True
) -> bool:
    """
    Безопасная отправка ответа с поддержкой старых топиков форума.
    
    Для форумов использует reply_parameters через прямой API вызов,
    что работает для всех топиков включая старые (id < 1000).
    
    Args:
        msg: Исходное сообщение для ответа
        text: Текст ответа
        parse_mode: Режим парсинга (HTML, Markdown, None)
        disable_web_page_preview: Отключить превью ссылок
        
    Returns:
        True если сообщение отправлено успешно
    """
    is_forum = getattr(msg.chat, 'is_forum', False)
    topic_id = getattr(msg, 'message_thread_id', None)
    
    try:
        if is_forum:
            # Для форумов используем reply_parameters — работает для всех топиков
            logger.debug(f"[SAFE_REPLY] Форум: отправка через reply_parameters (topic={topic_id})")
            bot_token = msg.bot.token
            api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": msg.chat.id,
                "text": text,
                "reply_parameters": {
                    "message_id": msg.message_id,
                    "chat_id": msg.chat.id
                },
                "disable_web_page_preview": disable_web_page_preview
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            
            async with httpx.AsyncClient() as client:
                resp = await client.post(api_url, json=payload)
                result = resp.json()
                if result.get("ok"):
                    logger.debug(f"[SAFE_REPLY] OK через reply_parameters")
                    return True
                else:
                    error_desc = result.get("description", "Unknown error")
                    logger.error(f"[SAFE_REPLY] API error: {error_desc}")
                    # Пробуем fallback через msg.answer()
                    await msg.answer(text, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)
                    return True
        else:
            # Для обычных чатов используем стандартный reply
            await msg.reply(text, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)
            return True
            
    except TelegramBadRequest as e:
        error_msg = str(e).lower()
        if "thread not found" in error_msg or "message to reply not found" in error_msg:
            logger.warning(f"[SAFE_REPLY] Топик/сообщение удалено, пробуем answer(): {e}")
            try:
                await msg.answer(text, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)
                return True
            except Exception as fallback_err:
                logger.error(f"[SAFE_REPLY] Fallback answer() тоже не сработал: {fallback_err}")
                return False
        logger.error(f"[SAFE_REPLY] TelegramBadRequest: {e}")
        return False
    except Exception as e:
        logger.error(f"[SAFE_REPLY] Unexpected error: {e}")
        return False
