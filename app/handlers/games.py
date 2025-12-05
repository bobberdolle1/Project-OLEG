"""Игровые механики и команды."""

import logging
import random
from datetime import datetime, timedelta
from aiogram import Router
from aiogram.types import Message
from aiogram import F
from aiogram.filters import Command
from sqlalchemy import select

from app.database.session import get_session
from app.database.models import User, GameStat, Wallet
from app.services.achievements import check_and_award_achievements
from app.services.quests import check_and_update_quests
from app.services.profile import get_full_user_profile
from app.services.game_engine import game_engine
from app.utils import utc_now

logger = logging.getLogger(__name__)

router = Router()

# Справка по играм
GAMES_HELP = """
🎮 <b>Мини-игры Олега — Полный гайд</b>

<b>📏 /grow — Выращивание</b>
Увеличь свой "размер" на 1-20 см.
• Кулдаун: 12-24 часа (рандом)
• Чем больше размер — тем выше ранг
• Пример: <code>/grow</code>

<b>🔫 /roulette — Русская рулетка</b>
Крути барабан, испытай удачу!
• 1/6 шанс "выстрела" — теряешь 50 очков
• 5/6 шанс выжить — получаешь 10 очков
• Пример: <code>/roulette</code>

<b>🪙 /coinflip — Монетка</b>
Ставь на орла или решку!
• 50/50 вероятность
• Выигрыш: удвоение ставки
• Примеры:
  <code>/coinflip 50 heads</code> — ставка 50 на орла
  <code>/coinflip 100 tails</code> — ставка 100 на решку

<b>⚔️ /challenge — PvP с согласием</b>
Вызови другого игрока на дуэль!
• Соперник должен принять вызов
• Ставки списываются только при согласии
• Таймаут: 5 минут
• Пример: <code>/challenge @username 100</code>

<b>⚔️ /pvp — Быстрая дуэль</b>
Сразись с другим игроком!
• Победитель забирает 10-30% размера проигравшего
• Победа: +5 репутации, поражение: -2
• Примеры:
  <code>/pvp @username</code> — по нику
  Или ответь на сообщение соперника и напиши <code>/pvp</code>

<b>🎰 /casino — Слоты</b>
Крути барабаны, выигрывай монеты!
• Ставка: 1-1000 монет (по умолчанию 10)
• 3 одинаковых = x5 (джекпот!)
• 2 одинаковых = x2
• Примеры:
  <code>/casino</code> — ставка 10
  <code>/casino 100</code> — ставка 100

<b>🏆 /top — Топ игроков</b>
Показывает топ-10 по размеру.

<b>⭐ /top_rep — Топ по репутации</b>
Топ-10 по репутации (растёт от побед).

<b>👤 /profile — Твой профиль</b>
Вся статистика: размер, ранг, монеты, победы.

<b>💡 Советы новичкам:</b>
1. Начни с /grow — получи первые сантиметры
2. /roulette — быстрый способ заработать (или потерять)
3. /coinflip — классика азарта
4. /challenge — честный PvP со ставками
5. Выполняй квесты (/quests) для бонусов

<i>Вопросы? Напиши "помоги с играми" — я объясню!</i>
"""

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

# Словарь рангов для игры /grow
RANKS = [
    (10, "Микрочелик"),
    (20, "Кнопочный воин"),
    (30, "Среднячок"),
    (40, "Тянет к проводочкам"),
    (50, "Почти нормальный"),
    (60, "Нормальный размер"),
    (70, "Хороший экземпляр"),
    (80, "Завидная длина"),
    (90, "Амбал"),
    (100, "Гигачад"),
    (120, "Легенда"),
    (150, "Миф"),
    (200, "Мегамиф"),
    (300, "Титан"),
    (500, "Космический бур"),
    (1000, "Божественный размер"),
    (float('inf'), "Легендарный гигант")
]


def get_rank_by_size(size_cm: int) -> str:
    """
    Возвращает ранг по размеру "пиписи".

    Args:
        size_cm: Размер в сантиметрах

    Returns:
        Название ранга
    """
    for threshold, rank_name in RANKS:
        if size_cm <= threshold:
            return rank_name
    return RANKS[-1][1]  # Возвращаем последний ранг, если размер больше всех порогов


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


@router.message(Command("games"))
async def cmd_games(msg: Message):
    """Команда /games — справка по всем мини-играм."""
    await msg.reply(GAMES_HELP, parse_mode="HTML")
    logger.info(f"Games help requested by @{msg.from_user.username or msg.from_user.id}")


@router.message(F.text.startswith("/grow"))
async def cmd_grow(msg: Message):
    """
    Команда /grow — увеличить "пиписю".

    Случайное увеличение размера (1-20 см) с кулдауном.
    """
    async_session = get_session()
    user = await ensure_user(msg.from_user) # Get the User object here
    async with async_session() as session:
        res = await session.execute(
            select(GameStat).where(
                GameStat.tg_user_id == msg.from_user.id
            )
        )
        gs = res.scalars().first()
        now = utc_now()
        # Ensure both datetimes are comparable (handle naive vs aware)
        next_grow = gs.next_grow_at
        if next_grow and next_grow.tzinfo is None:
            from datetime import timezone
            next_grow = next_grow.replace(tzinfo=timezone.utc)
        if next_grow and next_grow > now:
            delta = next_grow - now
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
        gs.grow_count += 1
        gs.next_grow_at = now + timedelta(hours=cooldown_hours)
        await session.commit()

        new_achievements = await check_and_award_achievements(session, msg.bot, user, gs, "grow")
        for achievement in new_achievements:
            await msg.answer(f"🎉 Новое достижение: {achievement.name}!")
        
        updated_quests = await check_and_update_quests(session, user, "grow")
        for quest in updated_quests:
            await msg.answer(f"✅ Выполнили квест: {quest.name}! Награда: {quest.reward_amount} {quest.reward_type}!")

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
        # Получить ранг по размеру
        size_rank = get_rank_by_size(gs.size_cm)
        await msg.reply(
            f"+{gain} см 📈\n"
            f"Текущий: {gs.size_cm} см\n"
            f"Ранг: {size_rank}\n"
            f"Место: #{rank}/{len(all_stats)}\n"
            f"Кулдаун: {cooldown_hours}ч\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📋 /top · /pvp · /casino · /profile"
        )
        logger.info(
            f"Grow: @{msg.from_user.username} "
            f"+{gain} cm (total: {gs.size_cm}, rank: {size_rank})"
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
            size_rank = get_rank_by_size(s.size_cm)
            lines.append(f"{i}. {name}: {s.size_cm} см ({size_rank})")
        await msg.reply(
            "🏆 Топ-10:\n" + "\n".join(lines) +
            "\n━━━━━━━━━━━━━━━\n"
            "📋 /grow · /pvp · /casino · /profile"
        )


@router.message(F.text.startswith("/top_rep"))
async def cmd_top_rep(msg: Message):
    async_session = get_session()
    async with async_session() as session:
        res = await session.execute(select(GameStat).order_by(GameStat.reputation.desc()).limit(10))
        top10 = res.scalars().all()
        if not top10:
            return await msg.reply("Пусто. Ни у кого нет репутации.")
        lines = []
        for i, s in enumerate(top10, start=1):
            name = s.username or str(s.tg_user_id)
            lines.append(f"{i}. {name}: {s.reputation} репутации")
        await msg.reply(
            "⭐ Топ-10 по репутации:\n" + "\n".join(lines) +
            "\n━━━━━━━━━━━━━━━\n"
            "📋 /grow · /pvp · /casino · /profile"
        )


@router.message(F.text.startswith("/profile"))
async def cmd_profile(msg: Message):
    """
    Displays the user's comprehensive profile data.
    """
    async_session = get_session()
    user = await ensure_user(msg.from_user)

    async with async_session() as session:
        user, game_stat, wallet, user_achievements, user_quests, guild_memberships, duo_team = \
            await get_full_user_profile(session, user.tg_user_id)

        if not user:
            return await msg.reply("Ваш профиль не найден. Пожалуйста, начните играть (например, /grow).")

        # Получить ранг по размеру
        size_rank = get_rank_by_size(game_stat.size_cm)
        profile_text = (
            f"📈 Ваш профиль, {user.username or user.first_name}:\n"
            f"📏 Размер: {game_stat.size_cm} см\n"
            f"🏆 Ранг: {size_rank}\n"
            f"🏅 Репутация: {game_stat.reputation}\n"
            f"💰 Баланс: {wallet.balance} монет\n"
            f"⚔️ Побед в PvP: {game_stat.pvp_wins}\n"
            f"🌱 Выращиваний: {game_stat.grow_count}\n"
            f"🎰 Джекпотов в казино: {game_stat.casino_jackpots}\n"
        )

        if guild_memberships:
            guild_name = guild_memberships[0].guild.name
            guild_role = guild_memberships[0].role
            profile_text += f"🛡️ Гильдия: {guild_name} ({guild_role})\n"
        
        if duo_team:
            partner = duo_team.user1 if duo_team.user2.id == user.id else duo_team.user2
            profile_text += f"🤝 Дуэт: @{partner.username or str(partner.tg_user_id)} (Рейтинг: {duo_team.stats.rating})\n"

        if user_achievements:
            profile_text += "\n🏆 Достижения:\n"
            for ua in user_achievements:
                profile_text += f"  - {ua.achievement.name}\n"
        
        if user_quests:
            profile_text += "\n📜 Активные квесты:\n"
            for uq in user_quests:
                status = "Выполнено" if uq.completed_at else f"Прогресс: {uq.progress}/{uq.quest.target_value}"
                profile_text += f"  - {uq.quest.name} ({status})\n"

        profile_text += "\n━━━━━━━━━━━━━━━\n📋 /grow · /pvp · /casino · /top"
        await msg.reply(profile_text)


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
        # Increment pvp_wins for the winner
        winner.pvp_wins += 1
        winner.reputation += 5
        loser.reputation -= 2
        await session.commit()
        
        # Get the User object for the winner
        winner_user_res = await session.execute(select(User).where(User.id == winner.user_id))
        winner_user = winner_user_res.scalars().first()

        new_achievements = await check_and_award_achievements(session, msg.bot, winner_user, winner, "pvp_win")
        for achievement in new_achievements:
            await msg.answer(f"🎉 Новое достижение для {winner_user.username or str(winner_user.tg_user_id)}: {achievement.name}!")
        
        updated_quests = await check_and_update_quests(session, winner_user, "pvp_win")
        for quest in updated_quests:
            await msg.answer(f"✅ {winner_user.username or str(winner_user.tg_user_id)} выполнил квест: {quest.name}! Награда: {quest.reward_amount} {quest.reward_type}!")


        
        await msg.reply(
            f"⚔️ Дуэль: {winner_name} vs {loser_name}\n"
            f"🏆 Победил {winner_name} и забрал {steal_amt} см ({steal_pct}%)\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📋 /grow · /top · /casino · /profile"
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

        gs_res = await session.execute(select(GameStat).where(GameStat.user_id == user.id))
        gs = gs_res.scalars().first()

        board = " ".join(reel)
        if mult == 5:
            gs.casino_jackpots += 1
            text = (
                f"🎰 {board}\n"
                f"🎉 Джекпот! Выигрыш: {win} монет\n"
                f"💰 Баланс: {w.balance}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📋 /grow · /pvp · /top · /profile"
            )
        elif mult == 2:
            text = (
                f"🎰 {board}\n"
                f"✨ Норм, удвоил! Выигрыш: {win} монет\n"
                f"💰 Баланс: {w.balance}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📋 /grow · /pvp · /top · /profile"
            )
        else:
            text = (
                f"🎰 {board}\n"
                f"😢 Мимо, дружище\n"
                f"💰 Баланс: {w.balance}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📋 /grow · /pvp · /top · /profile"
            )
        
        await session.commit()

        if mult == 5: # Only check for achievements if a jackpot occurred
            new_achievements = await check_and_award_achievements(session, msg.bot, user, gs, "casino_jackpot")
            for achievement in new_achievements:
                await msg.answer(f"🎉 Новое достижение: {achievement.name}!")
            
            updated_quests = await check_and_update_quests(session, user, "casino_jackpot")
            for quest in updated_quests:
                await msg.answer(f"✅ Выполнили квест: {quest.name}! Награда: {quest.reward_amount} {quest.reward_type}!")

        
        await msg.reply(text)


@router.message(Command("roulette"))
async def cmd_roulette(msg: Message):
    """
    Команда /roulette — Русская рулетка.
    
    Игрок крутит барабан с 1 пулей в 6 камерах.
    - Выстрел (1/6): теряет очки
    - Выживание (5/6): получает очки
    
    Requirements: 9.1, 9.2, 9.3, 9.4
    """
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    
    # Ensure user exists in DB
    await ensure_user(msg.from_user)
    
    # Play roulette using the game engine
    result = game_engine.play_roulette(user_id, chat_id)
    
    # Log the result
    logger.info(
        f"Roulette: @{msg.from_user.username or user_id} - "
        f"{'SHOT' if result.shot else 'SURVIVED'}, "
        f"change: {result.points_change}, balance: {result.new_balance}"
    )
    
    # Send the dramatic Oleg-style message
    await msg.reply(
        f"🔫 <b>Русская рулетка</b>\n\n"
        f"{result.message}\n\n"
        f"💰 Баланс: {result.new_balance} очков\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📋 /grow · /pvp · /casino · /profile",
        parse_mode="HTML"
    )


@router.message(Command("coinflip"))
async def cmd_coinflip(msg: Message):
    """
    Команда /coinflip — Подбрасывание монетки.
    
    Использование: /coinflip <ставка> <heads|tails>
    Примеры:
      /coinflip 50 heads
      /coinflip 100 tails
    
    - 50/50 вероятность
    - Выигрыш: удвоение ставки
    - Проигрыш: потеря ставки
    
    Requirements: 10.1, 10.2, 10.3, 10.4, 10.5
    """
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    
    # Ensure user exists in DB
    await ensure_user(msg.from_user)
    
    # Parse command arguments
    parts = (msg.text or "").split()
    
    # Default values
    bet_amount = 10
    choice = None
    
    # Parse bet amount and choice
    if len(parts) >= 2:
        try:
            bet_amount = int(parts[1])
        except ValueError:
            # Maybe they put choice first?
            choice = parts[1].lower()
    
    if len(parts) >= 3:
        choice = parts[2].lower()
    elif len(parts) == 2 and choice is None:
        # Only bet amount provided, no choice
        return await msg.reply(
            "🪙 <b>Монетка</b>\n\n"
            "Использование: <code>/coinflip &lt;ставка&gt; &lt;heads|tails&gt;</code>\n"
            "Пример: <code>/coinflip 50 heads</code>\n\n"
            "Выбери сторону: heads (орёл) или tails (решка)",
            parse_mode="HTML"
        )
    
    # Validate choice
    if choice not in ("heads", "tails"):
        return await msg.reply(
            "🪙 <b>Монетка</b>\n\n"
            "Использование: <code>/coinflip &lt;ставка&gt; &lt;heads|tails&gt;</code>\n"
            "Пример: <code>/coinflip 50 heads</code>\n\n"
            "Выбери сторону: heads (орёл) или tails (решка)",
            parse_mode="HTML"
        )
    
    # Validate bet amount
    if bet_amount <= 0:
        return await msg.reply(
            "🪙 Ставка должна быть положительной, гений.",
            parse_mode="HTML"
        )
    
    # Play coin flip using the game engine
    result = game_engine.flip_coin(user_id, chat_id, bet_amount, choice)
    
    # Log the result
    logger.info(
        f"CoinFlip: @{msg.from_user.username or user_id} - "
        f"choice={result.choice}, result={result.result}, won={result.won}, "
        f"bet={result.bet_amount}, change={result.balance_change}, balance={result.new_balance}"
    )
    
    # Handle errors
    if not result.success:
        await msg.reply(
            f"🪙 <b>Монетка</b>\n\n"
            f"{result.message}",
            parse_mode="HTML"
        )
        return
    
    # Format choice display
    choice_display = "орёл" if result.choice == "heads" else "решка"
    result_display = "орёл" if result.result == "heads" else "решка"
    
    # Send the result message
    if result.won:
        emoji = "🎉"
        outcome = f"Выпало: {result_display.upper()}! Ты угадал!"
    else:
        emoji = "😢"
        outcome = f"Выпало: {result_display.upper()}! Мимо..."
    
    await msg.reply(
        f"🪙 <b>Монетка</b>\n\n"
        f"Твой выбор: {choice_display}\n"
        f"{emoji} {outcome}\n\n"
        f"{result.message}\n\n"
        f"💰 Баланс: {result.new_balance} очков\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📋 /grow · /pvp · /casino · /roulette",
        parse_mode="HTML"
    )
