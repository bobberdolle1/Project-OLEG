"""Citadel Command Handlers for DEFCON Protection System.

This module provides command handlers for managing the Citadel DEFCON
protection system, including setting protection levels and viewing status.

**Feature: fortress-update**
**Validates: Requirements 1.7**
"""

import logging
import re
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from app.services.citadel import citadel_service, DEFCONLevel

logger = logging.getLogger(__name__)

router = Router()

# DEFCON level descriptions
DEFCON_DESCRIPTIONS = {
    DEFCONLevel.PEACEFUL: (
        "🟢 DEFCON 1 (Мирный режим)\n"
        "• Базовая защита от спам-ссылок\n"
        "• Простая капча для новичков"
    ),
    DEFCONLevel.STRICT: (
        "🟡 DEFCON 2 (Строгий режим)\n"
        "• Фильтр нецензурной лексики\n"
        "• Лимит стикеров (3 подряд)\n"
        "• Блокировка пересылок из каналов"
    ),
    DEFCONLevel.MARTIAL_LAW: (
        "🔴 DEFCON 3 (Военное положение)\n"
        "• Полные ограничения для новичков\n"
        "• Сложная капча (ИИ-загадки)\n"
        "• Запрет медиа и ссылок для новых"
    ),
}


async def is_admin(message: Message) -> bool:
    """
    Check if the user is an admin in the chat.
    
    Args:
        message: Incoming message
        
    Returns:
        True if user is admin or creator
    """
    if message.chat.type == 'private':
        return True
    
    try:
        member = await message.bot.get_chat_member(
            message.chat.id,
            message.from_user.id
        )
        return member.status in ('administrator', 'creator')
    except Exception as e:
        logger.error(f"Failed to check admin status: {e}")
        return False


@router.message(Command("defcon"))
async def cmd_defcon(message: Message):
    """
    Handle /defcon command.
    
    Usage:
        /defcon - Show current DEFCON level
        /defcon 1|2|3 - Set DEFCON level (admin only)
    """
    await handle_defcon_command(message)


@router.message(F.text.lower().startswith("олег defcon"))
async def oleg_defcon(message: Message):
    """
    Handle "олег defcon" command.
    
    Usage:
        олег defcon - Show current DEFCON level
        олег defcon 1|2|3 - Set DEFCON level (admin only)
    """
    await handle_defcon_command(message)


async def handle_defcon_command(message: Message):
    """
    Process DEFCON command.
    
    Args:
        message: Incoming message with DEFCON command
    """
    chat_id = message.chat.id
    text = message.text or ""
    
    # Extract level from command
    level_match = re.search(r'\b([123])\b', text)
    
    if level_match:
        # Setting DEFCON level - requires admin
        if not await is_admin(message):
            await message.reply(
                "⛔ Только администраторы могут менять уровень DEFCON."
            )
            return
        
        new_level = int(level_match.group(1))
        
        try:
            config = await citadel_service.set_defcon(chat_id, DEFCONLevel(new_level))
            
            level_desc = DEFCON_DESCRIPTIONS.get(config.defcon_level, "")
            
            await message.reply(
                f"✅ Уровень защиты изменён!\n\n{level_desc}"
            )
            
            logger.info(
                f"DEFCON level changed to {new_level} in chat {chat_id} "
                f"by user {message.from_user.id}"
            )
            
        except ValueError as e:
            await message.reply(f"❌ Ошибка: {e}")
        except Exception as e:
            logger.error(f"Failed to set DEFCON level: {e}")
            await message.reply("❌ Не удалось изменить уровень защиты.")
    
    else:
        # Show current DEFCON level
        try:
            config = await citadel_service.get_config(chat_id)
            
            level_desc = DEFCON_DESCRIPTIONS.get(config.defcon_level, "")
            
            # Build status message
            status_parts = [
                "🏰 **Статус Цитадели**\n",
                level_desc,
                "\n**Активные функции:**"
            ]
            
            # List active features
            features = []
            if config.anti_spam_enabled:
                features.append("• Антиспам ✅")
            if config.profanity_filter_enabled:
                features.append("• Фильтр мата ✅")
            if config.sticker_limit > 0:
                features.append(f"• Лимит стикеров: {config.sticker_limit}")
            if config.forward_block_enabled:
                features.append("• Блок пересылок ✅")
            if config.hard_captcha_enabled:
                features.append("• Сложная капча ✅")
            
            if not features:
                features.append("• Базовая защита")
            
            status_parts.extend(features)
            
            # Add raid mode status if active
            if config.is_raid_mode_active:
                status_parts.append("\n⚠️ **РЕЖИМ РЕЙДА АКТИВЕН**")
            
            # Add usage hint
            status_parts.append("\n\n💡 Используй `олег defcon 1/2/3` для смены уровня")
            
            await message.reply(
                "\n".join(status_parts),
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Failed to get DEFCON status: {e}")
            await message.reply("❌ Не удалось получить статус защиты.")


@router.message(Command("raid"))
async def cmd_raid(message: Message):
    """
    Handle /raid command to manually activate/deactivate raid mode.
    
    Usage:
        /raid on - Activate raid mode (admin only)
        /raid off - Deactivate raid mode (admin only)
        /raid - Show raid mode status
    """
    if not await is_admin(message):
        await message.reply("⛔ Только администраторы могут управлять режимом рейда.")
        return
    
    chat_id = message.chat.id
    text = (message.text or "").lower()
    
    try:
        if "on" in text or "вкл" in text:
            config = await citadel_service.activate_raid_mode(chat_id)
            await message.reply(
                "🚨 **РЕЖИМ РЕЙДА АКТИВИРОВАН**\n\n"
                "• Все новые участники будут ограничены\n"
                "• DEFCON установлен на уровень 3\n"
                "• Режим автоматически отключится через 15 минут",
                parse_mode="Markdown"
            )
            
        elif "off" in text or "выкл" in text:
            config = await citadel_service.deactivate_raid_mode(chat_id)
            await message.reply(
                "✅ Режим рейда отключён.\n"
                "Уровень DEFCON сохранён."
            )
            
        else:
            config = await citadel_service.get_config(chat_id)
            if config.is_raid_mode_active:
                await message.reply(
                    "🚨 Режим рейда **АКТИВЕН**\n"
                    "Используй `/raid off` для отключения",
                    parse_mode="Markdown"
                )
            else:
                await message.reply(
                    "✅ Режим рейда не активен\n"
                    "Используй `/raid on` для активации",
                    parse_mode="Markdown"
                )
                
    except Exception as e:
        logger.error(f"Failed to manage raid mode: {e}")
        await message.reply("❌ Ошибка при управлении режимом рейда.")


@router.message(F.text.lower().startswith("олег рейд"))
async def oleg_raid(message: Message):
    """Handle 'олег рейд' command."""
    # Reuse the /raid handler
    await cmd_raid(message)
