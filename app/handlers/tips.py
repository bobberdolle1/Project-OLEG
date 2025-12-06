"""Tips command handler for chat owners.

Provides actionable recommendations for improving chat management.

**Feature: fortress-update**
**Validates: Requirements 15.7**
"""

import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.services.notifications import notification_service

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("советы", "tips"))
async def cmd_tips(msg: Message):
    """
    Handle /советы and /tips commands.
    
    Analyzes recent chat activity and provides 3-5 actionable
    recommendations for the chat owner.
    
    **Validates: Requirements 15.7**
    WHEN a chat owner requests advice with "/советы" or "/tips"
    THEN the Notification System SHALL analyze recent chat activity
    and provide 3-5 actionable recommendations.
    
    Args:
        msg: Incoming message
    """
    # Only work in group chats
    if msg.chat.type == "private":
        await msg.reply(
            "💡 Эта команда работает только в групповых чатах.\n"
            "Используйте её в чате, которым вы управляете."
        )
        return
    
    chat_id = msg.chat.id
    user_id = msg.from_user.id
    
    # Check if user is admin/owner
    try:
        member = await msg.chat.get_member(user_id)
        if member.status not in ("creator", "administrator"):
            await msg.reply(
                "⛔ Эта команда доступна только администраторам чата."
            )
            return
    except Exception as e:
        logger.warning(f"Failed to check admin status: {e}")
        await msg.reply(
            "❌ Не удалось проверить права доступа. Попробуйте позже."
        )
        return
    
    # Send "analyzing" message
    status_msg = await msg.reply("🔍 Анализирую чат...")
    
    try:
        # Generate tips
        tips = await notification_service.generate_tips(chat_id)
        
        # Format tips for display
        formatted_tips = notification_service.format_tips(tips)
        
        # Edit status message with results
        await status_msg.edit_text(formatted_tips)
        
        logger.info(
            f"Generated {len(tips)} tips for chat {chat_id} "
            f"requested by user {user_id}"
        )
        
    except Exception as e:
        logger.error(f"Failed to generate tips for chat {chat_id}: {e}")
        await status_msg.edit_text(
            "❌ Не удалось проанализировать чат. Попробуйте позже."
        )
