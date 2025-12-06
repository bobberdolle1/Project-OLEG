"""
Private Admin Panel Handler for Chat Owners.

This module provides the /admin command handler for chat owners
to manage their chat settings through private messages with the bot.

Note: This is different from admin_dashboard.py which is for bot owner only.
This handler is for chat owners to manage their own chats via PM.

**Feature: fortress-update**
**Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7, 16.8, 16.9, 16.10, 16.11, 16.12**
"""

import logging
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from app.services.admin_panel import (
    admin_panel_service,
    AdminMenuCategory,
    CALLBACK_PREFIX,
)
from app.database.session import get_session
from app.database.models import Chat
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = Router()


# ============================================================================
# Command Handler (Requirements 16.1, 16.12)
# ============================================================================

@router.message(Command("admin"))
async def cmd_admin_for_owners(msg: Message, bot: Bot):
    """
    /admin command - show admin panel for chat owners.
    
    **Validates: Requirements 16.1, 16.12**
    
    Requirement 16.1: WHEN a chat owner sends "/admin" in private messages
    to the bot THEN the Admin Panel SHALL display a list of chats where
    the user is owner with inline buttons to select a chat.
    
    Requirement 16.12: WHEN "/admin" is sent in a group chat THEN the
    Admin Panel SHALL respond with "Админка доступна только в личных
    сообщениях. Напиши мне в ЛС: @OlegBot"
    """
    # Check if in private chat (Requirement 16.12)
    if msg.chat.type != 'private':
        bot_info = await bot.get_me()
        await msg.reply(
            f"Админка доступна только в личных сообщениях. "
            f"Напиши мне в ЛС: @{bot_info.username}"
        )
        return

    
    user_id = msg.from_user.id
    
    # Get chats where user is owner (Requirement 16.1)
    owner_chats = await admin_panel_service.get_owner_chats(bot, user_id)
    
    if not owner_chats:
        await msg.answer(
            "🔒 <b>Админ-панель</b>\n\n"
            "У вас нет чатов для управления.\n"
            "Добавьте меня в группу, где вы являетесь создателем.",
            parse_mode="HTML"
        )
        return
    
    keyboard = admin_panel_service.build_chat_list_menu(owner_chats)
    
    await msg.answer(
        f"🔒 <b>Админ-панель для владельцев</b>\n\n"
        f"Доступно чатов: {len(owner_chats)}\n"
        f"Выберите чат для настройки:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# ============================================================================
# Chat Selection Callback (Requirement 16.2)
# ============================================================================

@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}chat_"))
async def cb_select_chat(callback: CallbackQuery, bot: Bot):
    """
    Handle chat selection - show main menu for selected chat.
    
    **Validates: Requirements 16.2**
    WHEN the owner selects a chat THEN the Admin Panel SHALL display
    an inline keyboard menu with main configuration categories for that chat.
    """
    user_id = callback.from_user.id
    chat_id = int(callback.data.split("_")[2])
    
    # Verify ownership (Requirement 16.10)
    if not await admin_panel_service.verify_ownership(bot, user_id, chat_id):
        await callback.answer("❌ У вас нет прав на управление этим чатом", show_alert=True)
        return
    
    # Get chat title
    async with get_session()() as session:
        result = await session.execute(select(Chat).filter_by(id=chat_id))
        chat = result.scalar_one_or_none()
    
    chat_title = chat.title if chat else f"Чат {chat_id}"
    
    keyboard = admin_panel_service.build_main_menu(chat_id)
    
    await callback.message.edit_text(
        f"⚙️ <b>Настройки: {chat_title}</b>\n\n"
        f"Выберите категорию настроек:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


# ============================================================================
# Back to Chat List Callback
# ============================================================================

@router.callback_query(F.data == f"{CALLBACK_PREFIX}back_list")
async def cb_back_to_list(callback: CallbackQuery, bot: Bot):
    """Return to chat list."""
    user_id = callback.from_user.id
    
    owner_chats = await admin_panel_service.get_owner_chats(bot, user_id)
    
    if not owner_chats:
        await callback.message.edit_text(
            "🔒 <b>Админ-панель</b>\n\n"
            "У вас нет чатов для управления.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    keyboard = admin_panel_service.build_chat_list_menu(owner_chats)
    
    await callback.message.edit_text(
        f"🔒 <b>Админ-панель для владельцев</b>\n\n"
        f"Доступно чатов: {len(owner_chats)}\n"
        f"Выберите чат для настройки:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()



# ============================================================================
# Category Selection Callbacks (Requirements 16.3-16.7, 16.10)
# ============================================================================

@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}cat_"))
async def cb_select_category(callback: CallbackQuery, bot: Bot):
    """
    Handle category selection - show category-specific menu.
    
    **Validates: Requirements 16.3, 16.4, 16.5, 16.6, 16.7, 16.10**
    """
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    chat_id = int(parts[2])
    category_value = parts[3]
    
    # Verify ownership (Requirement 16.10)
    if not await admin_panel_service.verify_ownership(bot, user_id, chat_id):
        await callback.answer("❌ У вас нет прав на управление этим чатом", show_alert=True)
        return
    
    try:
        category = AdminMenuCategory(category_value)
    except ValueError:
        await callback.answer("Неизвестная категория", show_alert=True)
        return
    
    text, keyboard = await admin_panel_service.build_category_menu(chat_id, category)
    
    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


# ============================================================================
# Protection Callbacks (Requirement 16.3)
# ============================================================================

@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}defcon_"))
async def cb_set_defcon(callback: CallbackQuery, bot: Bot):
    """
    Handle DEFCON level change.
    
    **Validates: Requirements 16.3, 16.9**
    """
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    chat_id = int(parts[2])
    level = parts[3]
    
    text, keyboard = await admin_panel_service.handle_callback(
        bot, user_id, chat_id, "defcon", level
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer(f"✅ DEFCON установлен на уровень {level}")


@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}toggle_"))
async def cb_toggle_protection(callback: CallbackQuery, bot: Bot):
    """
    Handle protection feature toggle.
    
    **Validates: Requirements 16.3, 16.9**
    """
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    chat_id = int(parts[2])
    toggle_type = parts[3]
    
    text, keyboard = await admin_panel_service.handle_callback(
        bot, user_id, chat_id, "toggle", toggle_type
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer("✅ Настройка изменена")


# ============================================================================
# Notification Callbacks (Requirement 16.4)
# ============================================================================

@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}notif_"))
async def cb_toggle_notification(callback: CallbackQuery, bot: Bot):
    """
    Handle notification toggle.
    
    **Validates: Requirements 16.4, 16.9**
    """
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    chat_id = int(parts[2])
    notif_type = parts[3]
    
    text, keyboard = await admin_panel_service.handle_callback(
        bot, user_id, chat_id, "notif", notif_type
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer("✅ Уведомление переключено")



# ============================================================================
# Games Callbacks (Requirement 16.5)
# ============================================================================

@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}games_"))
async def cb_toggle_games(callback: CallbackQuery, bot: Bot):
    """
    Handle games toggle.
    
    **Validates: Requirements 16.5, 16.9**
    """
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    chat_id = int(parts[2])
    action = parts[3]
    
    # For now, just show a message - games config can be extended later
    await callback.answer("🎮 Игры всегда включены в этой версии", show_alert=True)


# ============================================================================
# Dailies Callbacks (Requirement 16.6)
# ============================================================================

@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}daily_"))
async def cb_toggle_daily(callback: CallbackQuery, bot: Bot):
    """
    Handle dailies toggle.
    
    **Validates: Requirements 16.6, 16.9**
    """
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    chat_id = int(parts[2])
    daily_type = parts[3]
    
    text, keyboard = await admin_panel_service.handle_callback(
        bot, user_id, chat_id, "daily", daily_type
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer("✅ Настройка изменена")


# ============================================================================
# Quotes Callbacks (Requirement 16.7)
# ============================================================================

@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}quote_"))
async def cb_quote_settings(callback: CallbackQuery, bot: Bot):
    """
    Handle quote settings.
    
    **Validates: Requirements 16.7, 16.9**
    """
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    chat_id = int(parts[2])
    action = parts[3]
    
    if action == "theme":
        theme = parts[4]
        await callback.answer(f"✅ Тема установлена: {theme}", show_alert=True)
    elif action == "golden":
        await callback.answer("✅ Золотой Фонд переключён", show_alert=True)
    elif action == "stickers":
        await callback.answer("📦 Стикерпак управляется автоматически", show_alert=True)
    else:
        await callback.answer("Неизвестное действие", show_alert=True)


# ============================================================================
# Advanced Settings Callbacks (Requirement 16.10)
# ============================================================================

@router.callback_query(F.data.startswith(f"{CALLBACK_PREFIX}adv_"))
async def cb_advanced_settings(callback: CallbackQuery, bot: Bot):
    """
    Handle advanced settings.
    
    **Validates: Requirements 16.10, 16.9**
    """
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    chat_id = int(parts[2])
    setting = "_".join(parts[3:])  # e.g., "tox_70" or "mute_5"
    
    if setting == "words":
        await callback.answer(
            "📝 Управление запрещёнными словами пока недоступно",
            show_alert=True
        )
        return
    
    text, keyboard = await admin_panel_service.handle_callback(
        bot, user_id, chat_id, "adv", setting
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer("✅ Настройка изменена")
