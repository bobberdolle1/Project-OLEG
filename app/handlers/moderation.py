"""Обработчик команд модерации для администраторов."""

import logging
import re
from datetime import datetime, timedelta
from aiogram import Router
from aiogram.types import Message
from aiogram import F
from aiogram.types import ChatPermissions
from sqlalchemy import select, delete

from app.database.session import get_session
from app.database.models import User, Warning

logger = logging.getLogger(__name__)

router = Router()

DUR_RE = re.compile(r"(\d+)([мчд])", re.IGNORECASE)


async def is_admin(msg: Message) -> bool:
    """
    Проверить, является ли пользователь администратором чата.

    Args:
        msg: Сообщение Telegram

    Returns:
        True, если пользователь админ или создатель чата
    """
    if not msg.chat:
        return False
    member = await msg.bot.get_chat_member(
        msg.chat.id, msg.from_user.id
    )
    status = getattr(member, "status", None)
    return status in {"administrator", "creator"}


def parse_duration(text: str) -> timedelta | None:
    """
    Парсить строку с длительностью.

    Форматы:
    - "10м" -> 10 минут
    - "1ч" -> 1 час
    - "1д" -> 1 день
    - "навсегда" -> None (постоянный бан)

    Args:
        text: Строка с длительностью

    Returns:
        timedelta объект или None для постоянного запрета
    """
    if text.strip().lower() == "навсегда":
        return None
    m = DUR_RE.fullmatch(text.strip())
    if not m:
        return None
    num = int(m.group(1))
    unit = m.group(2).lower()
    if unit == "м":
        return timedelta(minutes=num)
    if unit == "ч":
        return timedelta(hours=num)
    if unit == "д":
        return timedelta(days=num)
    return None


@router.message(F.text.startswith("олег бан"))
async def cmd_ban(msg: Message):
    """
    Команда: олег бан @[ник/reply] [время] [причина]

    Примеры:
    - олег бан @username 1д спам
    - олег бан 1ч оскорбления (ответ на сообщение)
    - олег бан навсегда (ответ на сообщение)
    """
    if not await is_admin(msg):
        await msg.reply("Только для админов, брат.")
        return

    # Получить ID пользователя
    target_id = None
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target_id = msg.reply_to_message.from_user.id
    else:
        await msg.reply("Укажи пользователя реплаем.")
        return

    parts = msg.text.split()
    duration = None
    reason = None

    if len(parts) >= 3:
        duration = parse_duration(parts[2])
    if len(parts) >= 4:
        reason = " ".join(parts[3:])

    until_date = None
    if duration is not None:
        until_date = datetime.utcnow() + duration

    try:
        await msg.bot.ban_chat_member(
            chat_id=msg.chat.id,
            user_id=target_id,
            until_date=until_date
        )
        duration_text = (
            ("до " + until_date.strftime("%d.%m %H:%M"))
            if until_date
            else "навсегда"
        )
        await msg.reply(
            f"Пользователь забанен {duration_text}. "
            f"Причина: {reason or '—'}"
        )
        logger.info(
            f"Ban: user {target_id} "
            f"until {until_date or 'forever'}, reason: {reason}"
        )
    except Exception as e:
        logger.error(f"Ban failed: {e}")
        await msg.reply(f"Не смог забанить: {e}")


@router.message(F.text.startswith("олег мут"))
async def cmd_mute(msg: Message):
    """
    Команда: олег мут @[ник/reply] [время] [причина]

    Запрещает пользователю отправлять сообщения на время.
    """
    if not await is_admin(msg):
        await msg.reply("Только для админов, брат.")
        return

    target_id = None
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target_id = msg.reply_to_message.from_user.id
    else:
        await msg.reply("Укажи пользователя реплаем.")
        return

    parts = msg.text.split()
    duration = None
    reason = None

    if len(parts) >= 3:
        duration = parse_duration(parts[2])
    if len(parts) >= 4:
        reason = " ".join(parts[3:])

    until_date = datetime.utcnow() + (duration or timedelta(hours=1))

    try:
        perms = ChatPermissions(
            can_send_messages=False,
            can_send_audios=False,
            can_send_documents=False,
            can_send_photos=False,
            can_send_videos=False,
            can_send_video_notes=False,
            can_send_voice_notes=False,
            can_send_polls=False,
            can_add_web_page_previews=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False,
        )
        await msg.bot.restrict_chat_member(
            chat_id=msg.chat.id,
            user_id=target_id,
            permissions=perms,
            until_date=until_date,
        )
        await msg.reply(
            f"Пользователь замьючен "
            f"до {until_date.strftime('%d.%m %H:%M')}. "
            f"Причина: {reason or '—'}"
        )
        logger.info(
            f"Mute: user {target_id} "
            f"until {until_date}, reason: {reason}"
        )
    except Exception as e:
        logger.error(f"Mute failed: {e}")
        await msg.reply(f"Не смог замьютить: {e}")


@router.message(F.text.startswith("олег кик"))
async def cmd_kick(msg: Message):
    """
    Команда: олег кик @[ник/reply] [причина]

    Исключает пользователя из чата (временный бан).
    """
    if not await is_admin(msg):
        await msg.reply("Только для админов, брат.")
        return

    target_id = None
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target_id = msg.reply_to_message.from_user.id
    else:
        await msg.reply("Укажи пользователя реплаем.")
        return

    reason = None
    parts = msg.text.split()
    if len(parts) >= 3:
        reason = " ".join(parts[2:])

    try:
        await msg.bot.ban_chat_member(
            chat_id=msg.chat.id, user_id=target_id
        )
        await msg.bot.unban_chat_member(
            chat_id=msg.chat.id,
            user_id=target_id,
            only_if_banned=True
        )
        await msg.reply(
            f"Пользователь кикнут. Причина: {reason or '—'}"
        )
        logger.info(
            f"Kick: user {target_id}, reason: {reason}"
        )
    except Exception as e:
        logger.error(f"Kick failed: {e}")
@router.message(F.text.startswith("/warn"))
async def cmd_warn(msg: Message):
    """
    Issues a warning to a user.
    Usage: /warn [reply] [reason]
    """
    if not await is_admin(msg):
        await msg.reply("Только для админов, брат.")
        return

    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        return await msg.reply("Укажи пользователя реплаем.")
    
    target_user = msg.reply_to_message.from_user
    reason = " ".join(msg.text.split()[1:]) if len(msg.text.split()) > 1 else "Без причины"
    
    async_session = get_session()
    async with async_session() as session:
        # Ensure target user exists
        user_res = await session.execute(select(User).filter_by(tg_user_id=target_user.id))
        user = user_res.scalars().first()
        if not user:
            user = User(tg_user_id=target_user.id, username=target_user.username, first_name=target_user.first_name, last_name=target_user.last_name)
            session.add(user)
            await session.flush()
        
        # Add a strike
        user.strikes += 1
        
        # Log the warning
        warning = Warning(
            user_id=user.id,
            moderator_id=msg.from_user.id,
            reason=reason
        )
        session.add(warning)
        await session.commit()
        
        await msg.reply(f"Пользователю @{target_user.username or target_user.id} выдано предупреждение. Всего предупреждений: {user.strikes}. Причина: {reason}")
        
        # Take action if strikes threshold is met
        if user.strikes >= 3:
            await msg.bot.ban_chat_member(
                chat_id=msg.chat.id,
                user_id=target_user.id,
                until_date=datetime.utcnow() + timedelta(days=1)
            )
            await msg.answer(f"Пользователь @{target_user.username or target_user.id} забанен на 24 часа за 3 предупреждения.")


@router.message(F.text.startswith("/unwarn"))
async def cmd_unwarn(msg: Message):
    """
    Removes the last warning from a user.
    Usage: /unwarn [reply]
    """
    if not await is_admin(msg):
        await msg.reply("Только для админов, брат.")
        return

    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        return await msg.reply("Укажи пользователя реплаем.")
    
    target_user = msg.reply_to_message.from_user
    
    async_session = get_session()
    async with async_session() as session:
        user_res = await session.execute(select(User).filter_by(tg_user_id=target_user.id))
        user = user_res.scalars().first()
        if not user or user.strikes == 0:
            return await msg.reply("У пользователя нет предупреждений.")
        
        # Remove a strike
        user.strikes -= 1
        
        # Remove the last warning from history
        last_warning_res = await session.execute(
            select(Warning)
            .filter_by(user_id=user.id)
            .order_by(Warning.created_at.desc())
        )
        last_warning = last_warning_res.scalars().first()
        if last_warning:
            await session.delete(last_warning)
        
        await session.commit()
        await msg.reply(f"Снято одно предупреждение с пользователя @{target_user.username or target_user.id}. Осталось: {user.strikes}.")


@router.message(commands="strikes")
async def cmd_strikes(msg: Message):
    """
    Displays the number of strikes for a user.
    Usage: /strikes [reply]
    """
    if not await is_admin(msg):
        await msg.reply("Только для админов, брат.")
        return

    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        return await msg.reply("Укажи пользователя реплаем.")
    
    target_user = msg.reply_to_message.from_user
    
    async_session = get_session()
    async with async_session() as session:
        user_res = await session.execute(select(User).filter_by(tg_user_id=target_user.id))
        user = user_res.scalars().first()
        
        if not user or user.strikes == 0:
            return await msg.reply("У пользователя нет предупреждений.")
        
        warnings_res = await session.execute(
            select(Warning)
            .filter_by(user_id=user.id)
            .order_by(Warning.created_at.desc())
        )
        warnings = warnings_res.scalars().all()
        
        response = f"Предупреждения пользователя @{target_user.username or target_user.id} ({user.strikes} всего):\n"
        for w in warnings:
            moderator = await msg.bot.get_chat_member(msg.chat.id, w.moderator_id)
            response += f"- {w.created_at.strftime('%Y-%m-%d')}: {w.reason} (выдал: @{moderator.user.username or w.moderator_id})\n"
        
        await msg.reply(response)