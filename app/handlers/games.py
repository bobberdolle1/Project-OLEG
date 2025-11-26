"""Игровые механики и команды."""

import logging
import random
from datetime import datetime, timedelta
from aiogram import Router
from aiogram.types import Message
from aiogram import F
from sqlalchemy import select

from app.database.session import get_session
from app.database.models import User, GameStat, Wallet

logger = logging.getLogger(__name__)

router = Router()

# Константы для баланса игр
GROW_MIN = 1
GROW_MAX = 20
GROW_COOLDOWN_MIN_HOURS = 12
GROW_COOLDOWN_MAX_HOURS = 24

CASINO_MIN_BET = 1
CASINO_MAX_BET = 1000
CASINO_DEFAULT_BET = 10

PVP_STEAL_MIN_PCT = 10
PVP_STEAL_MAX_PCT = 30


async def ensure_user(tg_user) -> User:
    """
    Убедиться, что пользователь существует в БД.

    Если пользователь не существует, создает записи:
    - User (базовая информация)
    - GameStat (статистика игр, "размер")
    - Wallet (виртуальная валюта, начальный баланс 100)

    Args:
        tg_user: Объект пользователя Telegram

    Returns:
        User объект
    """
    async_session = get_session()
    async with async_session() as session:
        # Поиск существующего пользователя
        res = await session.execute(
            select(User).where(User.tg_user_id == tg_user.id)
        )
        user = res.scalars().first()
        if not user:
            user = User(
                tg_user_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
            )
            session.add(user)
            await session.flush()

        # Убедиться в наличии GameStat
        res2 = await session.execute(
            select(GameStat).where(
                GameStat.tg_user_id == tg_user.id
            )
        )
        gs = res2.scalars().first()
        if not gs:
            gs = GameStat(
                user_id=user.id,
                tg_user_id=tg_user.id,
                username=tg_user.username,
                size_cm=0
            )
            session.add(gs)
        else:
            # Обновить никнейм если изменился
            gs.username = tg_user.username

        # Убедиться в наличии Wallet
        res3 = await session.execute(
            select(Wallet).where(Wallet.user_id == user.id)
        )
        w = res3.scalars().first()
        if not w:
            w = Wallet(user_id=user.id, balance=100)
            session.add(w)

        await session.commit()
        return user


@router.message(F.text.startswith("/grow"))
async def cmd_grow(msg: Message):
    """
    Команда /grow — увеличить "пиписю".

    Случайное увеличение размера (1-20 см) с кулдауном.
    """
    async_session = get_session()
    await ensure_user(msg.from_user)
    async with async_session() as session:
        res = await session.execute(
            select(GameStat).where(
                GameStat.tg_user_id == msg.from_user.id
            )
        )
        gs = res.scalars().first()
        now = datetime.utcnow()
        if gs.next_grow_at and gs.next_grow_at > now:
            delta = gs.next_grow_at - now
            hours, remainder = divmod(
                int(delta.total_seconds()), 3600
            )
            minutes = remainder // 60
            return await msg.reply(
                f"Подожди ещё {hours}ч {minutes}м, "
                f"не спеши, чемпион."
            )
        gain = random.randint(GROW_MIN, GROW_MAX)
        cooldown_hours = random.randint(
            GROW_COOLDOWN_MIN_HOURS, GROW_COOLDOWN_MAX_HOURS
        )
        gs.size_cm += gain
        gs.next_grow_at = now + timedelta(hours=cooldown_hours)
        await session.commit()

        # Получить рейтинг
        res2 = await session.execute(
            select(GameStat).order_by(GameStat.size_cm.desc())
        )
        all_stats = res2.scalars().all()
        rank = next(
            (i + 1 for i, s in enumerate(all_stats)
             if s.tg_user_id == msg.from_user.id),
            1
        )
        await msg.reply(
            f"+{gain} см 📈\n"
            f"Текущий: {gs.size_cm} см\n"
            f"Место: #{rank}/{len(all_stats)}\n"
            f"Кулдаун: {cooldown_hours}ч"
        )
        logger.info(
            f"Grow: @{msg.from_user.username} "
            f"+{gain} cm (total: {gs.size_cm})"
        )


@router.message(F.text.startswith("/top"))
async def cmd_top(msg: Message):
    async_session = get_session()
    async with async_session() as session:
        res = await session.execute(select(GameStat).order_by(GameStat.size_cm.desc()).limit(10))
        top10 = res.scalars().all()
        if not top10:
            return await msg.reply("Пусто. Никто не растил свою гордость.")
        lines = []
        for i, s in enumerate(top10, start=1):
            name = s.username or str(s.tg_user_id)
            lines.append(f"{i}. {name}: {s.size_cm} см")
        await msg.reply("Топ-10:\n" + "\n".join(lines))


@router.message(F.text.startswith("/pvp"))
async def cmd_pvp(msg: Message):
    async_session = get_session()
    await ensure_user(msg.from_user)
    # Identify opponent: reply user preferred
    opponent_id = None
    opponent_name = None
    if msg.reply_to_message and msg.reply_to_message.from_user:
        opponent_id = msg.reply_to_message.from_user.id
        opponent_name = msg.reply_to_message.from_user.username or str(opponent_id)
    else:
        parts = (msg.text or "").split()
        if len(parts) >= 2 and parts[1].startswith("@"):
            opponent_name = parts[1][1:]
    if not opponent_id and not opponent_name:
        return await msg.reply("Кого бить-то? Ответь реплаем на сообщение соперника или укажи @ник.")
    async with async_session() as session:
        # load attacker and opponent stats
        res_att = await session.execute(select(GameStat).where(GameStat.tg_user_id == msg.from_user.id))
        att = res_att.scalars().first()
        if not att:
            return await msg.reply("Ты пустой. Сначала /grow, потом разборки.")
        if not opponent_id and opponent_name:
            # find by username in GameStat
            res_op_user = await session.execute(select(GameStat).where(GameStat.username == opponent_name))
            opp = res_op_user.scalars().first()
        else:
            res_op = await session.execute(select(GameStat).where(GameStat.tg_user_id == opponent_id))
            opp = res_op.scalars().first()
        if not opp:
            return await msg.reply("Соперник не найден или ещё не играл. Позови его в /grow.")
        # compute duel
        a_score = att.size_cm + random.randint(-5, 5)
        o_score = opp.size_cm + random.randint(-5, 5)
        if a_score == o_score:
            # tie breaker
            a_score += random.randint(0, 1)
        if a_score > o_score:
            winner, loser = att, opp
            winner_name = msg.from_user.username or str(att.tg_user_id)
            loser_name = opp.username or str(opp.tg_user_id)
        else:
            winner, loser = opp, att
            winner_name = opp.username or str(opp.tg_user_id)
            loser_name = msg.from_user.username or str(att.tg_user_id)
        steal_pct = random.randint(10, 30)
        steal_amt = max(1, (loser.size_cm * steal_pct) // 100)
        loser.size_cm = max(0, loser.size_cm - steal_amt)
        winner.size_cm += steal_amt
        await session.commit()
        await msg.reply(
            f"Дуэль: {winner_name} vs {loser_name}. Победил {winner_name} и забрал {steal_amt} см ({steal_pct}%)."
        )


SLOTS = ["🍒", "🍋", "🔧", "🧰", "🎮", "🔥"]


def roll_slots():
    return [random.choice(SLOTS) for _ in range(3)]


def slots_payout(reel: list[str]) -> int:
    # 3 same -> x5; 2 same -> x2; else 0
    if reel[0] == reel[1] == reel[2]:
        return 5
    if reel[0] == reel[1] or reel[1] == reel[2] or reel[0] == reel[2]:
        return 2
    return 0


@router.message(F.text.startswith("/casino"))
async def cmd_casino(msg: Message):
    async_session = get_session()
    user = await ensure_user(msg.from_user)
    parts = (msg.text or "").split()
    bet = 10
    if len(parts) >= 2:
        try:
            bet = int(parts[1])
        except Exception:
            pass
    bet = max(1, min(1000, bet))
    async with async_session() as session:
        # load wallet
        resw = await session.execute(select(Wallet).where(Wallet.user_id == user.id))
        w = resw.scalars().first()
        if not w:
            w = Wallet(user_id=user.id, balance=100)
            session.add(w)
            await session.flush()
        if w.balance < bet:
            return await msg.reply(f"У тебя {w.balance}, а ставка {bet}. Бедно живёшь. Пополнись победами в /pvp.")
        w.balance -= bet
        reel = roll_slots()
        mult = slots_payout(reel)
        win = bet * mult
        w.balance += win
        await session.commit()
        board = " ".join(reel)
        if mult == 5:
            text = f"{board} — Джекпот! Выигрыш {win}. Баланс: {w.balance}"
        elif mult == 2:
            text = f"{board} — Норм, удвоил. Выигрыш {win}. Баланс: {w.balance}"
        else:
            text = f"{board} — Мимо, дружище. Баланс: {w.balance}"
        await msg.reply(text)
