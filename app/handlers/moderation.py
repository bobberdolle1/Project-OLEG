"""Обработчик команд модерации для администраторов."""

import logging
import re
from datetime import datetime, timedelta
from aiogram import Router
from aiogram.types import Message
from aiogram import F
from aiogram.types import ChatPermissions

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
        await msg.reply(f"Не смог кикнуть: {e}")

