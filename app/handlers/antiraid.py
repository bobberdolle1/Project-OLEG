"""Anti-raid handler for detecting and responding to mass join attacks.

**Feature: fortress-update**
**Validates: Requirements 1.5, 1.6, 15.1**
"""

import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Deque, Dict

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import ChatPermissions
from app.utils import utc_now

logger = logging.getLogger(__name__)

# Simple in-memory join tracking per chat
join_events: Dict[int, Deque[datetime]] = {}
raid_mode_until: Dict[int, datetime] = {}

router = Router()


def _is_raid(chat_id: int, now: datetime, window_sec: int = 60, threshold: int = 5) -> bool:
    dq = join_events.setdefault(chat_id, deque())
    # purge old
    while dq and (now - dq[0]).total_seconds() > window_sec:
        dq.popleft()
    return len(dq) >= threshold


def _start_raid(chat_id: int, now: datetime, duration_min: int = 15):
    raid_mode_until[chat_id] = now + timedelta(minutes=duration_min)


def _is_raid_active(chat_id: int, now: datetime) -> bool:
    until = raid_mode_until.get(chat_id)
    return bool(until and until > now)


def approve_keyboard(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="Размьютить", callback_data=f"approve:{user_id}"))
    return kb.as_markup()


@router.message(F.new_chat_members)
async def on_new_members(msg: Message):
    """
    Handle new chat members and detect raid conditions.
    
    **Validates: Requirements 1.5, 1.6, 15.1**
    """
    now = utc_now()
    chat_id = msg.chat.id

    # track
    dq = join_events.setdefault(chat_id, deque())
    dq.append(now)

    # detect raid
    if _is_raid(chat_id, now):
        if not _is_raid_active(chat_id, now):
            _start_raid(chat_id, now)
            await msg.answer("🚨 Замечен налёт новичков. Включаю ограничения на 15 минут.")
            
            # Fortress Update: Send raid notification to owner (Requirement 15.1)
            await _notify_owner_raid(msg, len(dq))

    # if raid active -> auto restrict every newcomer, send approve button
    if _is_raid_active(chat_id, now):
        for user in msg.new_chat_members:
            try:
                perms = ChatPermissions(can_send_messages=False)
                await msg.bot.restrict_chat_member(chat_id=chat_id, user_id=user.id, permissions=perms, until_date=now + timedelta(hours=1))
                await msg.answer(
                    f"@{user.username or user.id} временно замьючен. Админы, нажмите кнопку для одобрения.",
                    reply_markup=approve_keyboard(user.id)
                )
            except Exception:
                pass


@router.callback_query(F.data.startswith("approve:"))
async def on_approve(cb: CallbackQuery):
    # Only admins can approve
    member = await cb.bot.get_chat_member(cb.message.chat.id, cb.from_user.id)
    if getattr(member, "status", None) not in {"administrator", "creator"}:
        return await cb.answer("Только для админов", show_alert=True)
    try:
        parts = cb.data.split(":", 1)
        target_id = int(parts[1])
        await cb.bot.restrict_chat_member(
            chat_id=cb.message.chat.id,
            user_id=target_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_add_web_page_previews=True,
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=False,
            ),
        )
        await cb.message.edit_text("Пользователь одобрен и размьючен.")
        await cb.answer("Готово")
    except Exception as e:
        await cb.answer(f"Ошибка: {e}", show_alert=True)



async def _notify_owner_raid(msg: Message, join_count: int):
    """
    Send raid notification to chat owner.
    
    **Validates: Requirements 15.1**
    WHEN Raid Mode is automatically activated THEN the Notification System
    SHALL automatically send a private message to the chat owner with
    details about the raid attempt.
    """
    try:
        from app.services.notifications import notification_service
        
        chat_id = msg.chat.id
        chat_title = msg.chat.title or f"Chat {chat_id}"
        
        # Create notification
        notification = await notification_service.notify_raid(
            chat_id=chat_id,
            chat_title=chat_title,
            join_count=join_count,
            time_window=60,
            duration=15
        )
        
        if notification:
            # Get owner ID from notification config
            config = await notification_service.get_config(chat_id)
            
            if config.owner_id:
                try:
                    await msg.bot.send_message(
                        chat_id=config.owner_id,
                        text=f"{notification.title}\n\n{notification.message}"
                    )
                    logger.info(f"Sent raid notification to owner {config.owner_id} for chat {chat_id}")
                except Exception as send_error:
                    logger.warning(f"Failed to send raid notification to owner: {send_error}")
                    
    except Exception as e:
        logger.error(f"Failed to create raid notification: {e}")
