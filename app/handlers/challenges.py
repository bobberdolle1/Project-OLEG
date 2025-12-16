"""
Duel handlers with PvP and PvE modes.

Implements /challenge and /fight commands with RPG-style zone combat.
Requirements: 4.1, 4.2, 4.3, 4.4, 6.1, 6.2
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select

from app.database.session import get_session
from app.database.models import User, GameChallenge, UserBalance
from app.services.game_engine import game_engine, ChallengeStatus, GameType
from app.services.state_manager import state_manager
from app.services.duel_engine import DuelEngine, DuelState, DuelStatus, Zone, OLEG_USER_ID
from app.handlers.games import ensure_user
from app.utils import utc_now

logger = logging.getLogger(__name__)

router = Router()

# Callback data prefixes
ACCEPT_PREFIX = "challenge_accept:"
DECLINE_PREFIX = "challenge_decline:"
DUEL_ATTACK_PREFIX = "duel:"  # duel:{owner_id}:attack:{zone}
DUEL_DEFEND_PREFIX = "duel:"  # duel:{owner_id}:defend:{zone}

# Global duel engine instance
duel_engine = DuelEngine()

# Zone display names
ZONE_NAMES = {
    Zone.HEAD: "🎯 Голова",
    Zone.BODY: "💪 Тело",
    Zone.LEGS: "🦵 Ноги"
}

ZONE_EMOJI = {
    Zone.HEAD: "🎯",
    Zone.BODY: "💪",
    Zone.LEGS: "🦵"
}


async def ensure_user_balance(user_id: int, chat_id: int) -> int:
    """Ensure user has a balance record, create if not exists."""
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(UserBalance).where(
                UserBalance.user_id == user_id,
                UserBalance.chat_id == chat_id
            )
        )
        balance = result.scalars().first()
        
        if not balance:
            balance = UserBalance(
                user_id=user_id,
                chat_id=chat_id,
                balance=100,
                total_won=0,
                total_lost=0
            )
            session.add(balance)
            await session.commit()
            return 100
        
        return balance.balance


async def sync_balance_to_db(user_id: int, chat_id: int, new_balance: int, won: int = 0, lost: int = 0):
    """Sync in-memory balance to database."""
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(UserBalance).where(
                UserBalance.user_id == user_id,
                UserBalance.chat_id == chat_id
            )
        )
        balance = result.scalars().first()
        
        if balance:
            balance.balance = new_balance
            balance.total_won += won
            balance.total_lost += lost
        else:
            balance = UserBalance(
                user_id=user_id,
                chat_id=chat_id,
                balance=new_balance,
                total_won=won,
                total_lost=lost
            )
            session.add(balance)
        
        await session.commit()


async def save_challenge_to_db(challenge):
    """Save challenge to database."""
    async_session = get_session()
    async with async_session() as session:
        db_challenge = GameChallenge(
            id=challenge.id,
            chat_id=challenge.chat_id,
            challenger_id=challenge.challenger_id,
            target_id=challenge.target_id,
            game_type=challenge.game_type,
            bet_amount=challenge.bet_amount,
            status=challenge.status,
            created_at=challenge.created_at,
            expires_at=challenge.expires_at
        )
        session.add(db_challenge)
        await session.commit()


async def update_challenge_status_in_db(challenge_id: str, status: str):
    """Update challenge status in database."""
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(GameChallenge).where(GameChallenge.id == challenge_id)
        )
        challenge = result.scalars().first()
        if challenge:
            challenge.status = status
            await session.commit()


def create_challenge_keyboard(challenge_id: str) -> InlineKeyboardMarkup:
    """Create inline keyboard for challenge accept/decline."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="⚔️ Принять бой",
                callback_data=f"{ACCEPT_PREFIX}{challenge_id}"
            ),
            InlineKeyboardButton(
                text="🏃 Отклонить",
                callback_data=f"{DECLINE_PREFIX}{challenge_id}"
            )
        ]
    ])


def create_attack_keyboard(owner_id: int) -> InlineKeyboardMarkup:
    """Create inline keyboard for attack zone selection.
    
    Requirements: 6.1 - Attack zones: [Голова] [Тело] [Ноги]
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🎯 Голова",
                callback_data=f"duel:{owner_id}:attack:head"
            ),
            InlineKeyboardButton(
                text="💪 Тело",
                callback_data=f"duel:{owner_id}:attack:body"
            ),
            InlineKeyboardButton(
                text="🦵 Ноги",
                callback_data=f"duel:{owner_id}:attack:legs"
            )
        ]
    ])


def create_defend_keyboard(owner_id: int, attack_zone: str) -> InlineKeyboardMarkup:
    """Create inline keyboard for defense zone selection.
    
    Requirements: 6.1 - Defend zones: [Голова] [Тело] [Ноги]
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🎯 Голова",
                callback_data=f"duel:{owner_id}:defend:{attack_zone}:head"
            ),
            InlineKeyboardButton(
                text="💪 Тело",
                callback_data=f"duel:{owner_id}:defend:{attack_zone}:body"
            ),
            InlineKeyboardButton(
                text="🦵 Ноги",
                callback_data=f"duel:{owner_id}:defend:{attack_zone}:legs"
            )
        ]
    ])


def render_duel_status(
    duel_state: DuelState,
    player1_name: str,
    player2_name: str,
    last_round_info: str = ""
) -> str:
    """Render duel status message with HP bars.
    
    Requirements: 6.2 - Show health bars in format: "Олег: [████░░░] 60%"
    """
    p1_hp_bar = duel_engine.render_hp_bar(duel_state.player1_hp)
    p2_hp_bar = duel_engine.render_hp_bar(duel_state.player2_hp)
    
    status_text = (
        f"⚔️ <b>Дуэль</b>\n\n"
        f"👤 {player1_name}: {p1_hp_bar}\n"
        f"👤 {player2_name}: {p2_hp_bar}\n"
    )
    
    if last_round_info:
        status_text += f"\n{last_round_info}\n"
    
    if duel_state.bet > 0:
        status_text += f"\n💰 Ставка: {duel_state.bet} очков"
    
    return status_text


def render_round_result(
    player_attack: Zone,
    player_defend: Zone,
    opp_attack: Zone,
    opp_defend: Zone,
    player_hit: bool,
    opp_hit: bool,
    player_name: str,
    opp_name: str
) -> str:
    """Render the result of a combat round."""
    lines = []
    
    if player_hit:
        lines.append(f"✅ {player_name} попал в {ZONE_NAMES[player_attack]}!")
    else:
        lines.append(f"❌ {player_name} промахнулся ({ZONE_NAMES[player_attack]} заблокирована)")
    
    if opp_hit:
        lines.append(f"✅ {opp_name} попал в {ZONE_NAMES[opp_attack]}!")
    else:
        lines.append(f"❌ {opp_name} промахнулся ({ZONE_NAMES[opp_attack]} заблокирована)")
    
    return "\n".join(lines)


@router.message(Command("challenge", "fight", "duel"))
async def cmd_challenge(msg: Message):
    """
    Command /challenge [@user] [bet] - Challenge to a duel.
    
    Requirements:
    - 4.1: PvP mode with @username argument (wait for confirmation)
    - 4.2: PvE mode without arguments (instant Oleg accept)
    - 4.4: Instant Oleg acceptance in PvE
    - 2.2, 2.3: Block if user already playing
    """
    if not msg.from_user:
        return
    
    challenger_id = msg.from_user.id
    chat_id = msg.chat.id
    challenger_name = msg.from_user.username or msg.from_user.first_name
    
    # Save challenger to DB for future PvP lookups
    await ensure_user(msg.from_user)
    
    # Check if user is already playing (Requirements 2.2, 2.3)
    if await state_manager.is_playing(challenger_id, chat_id):
        session = await state_manager.get_session(challenger_id, chat_id)
        game_name = session.game_type if session else "игру"
        return await msg.reply(
            f"⚠️ Ты уже играешь в {game_name}! Заверши текущую игру."
        )
    
    # Parse target user and bet amount
    target_id = None
    target_name = None
    bet_amount = 0
    
    # Check if replying to a message
    if msg.reply_to_message and msg.reply_to_message.from_user:
        reply_user = msg.reply_to_message.from_user
        # Skip if replying to bot or self
        if not reply_user.is_bot and reply_user.id != challenger_id:
            target_id = reply_user.id
            target_name = reply_user.username or reply_user.first_name
            # Save target user to DB for future PvP lookups
            await ensure_user(reply_user)
    
    # Parse command arguments
    parts = (msg.text or "").split()
    for part in parts[1:]:  # Skip command
        if part.startswith("@"):
            target_name = part[1:]  # Remove @
            target_id = None  # Will need to look up
        else:
            try:
                bet_amount = int(part)
            except ValueError:
                pass
    
    # If we have a username but no ID, try to find the user
    username_was_specified = False
    if target_name and not target_id:
        username_was_specified = True
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.username == target_name)
            )
            user = result.scalars().first()
            if user:
                target_id = user.tg_user_id
    
    # PvE mode: no target specified (Requirements 4.2, 4.4)
    if not target_id:
        # If username was specified but not found, show error instead of PvE
        if username_was_specified:
            await msg.reply(
                f"❌ Пользователь @{target_name} не найден.\n\n"
                "💡 <b>Совет:</b> Ответь на сообщение соперника командой /challenge\n"
                "Или просто /challenge для боя с Олегом.",
                parse_mode="HTML"
            )
            return
        await start_pve_duel(msg, challenger_id, chat_id, challenger_name, bet_amount)
        return
    
    # PvP mode: target specified (Requirement 4.1)
    await start_pvp_challenge(msg, challenger_id, target_id, target_name, chat_id, bet_amount)


async def start_pve_duel(
    msg: Message,
    challenger_id: int,
    chat_id: int,
    challenger_name: str,
    bet_amount: int
):
    """Start a PvE duel against Oleg.
    
    Requirements:
    - 4.2: PvE mode without arguments
    - 4.4: Instant Oleg acceptance
    - 4.3: Oleg makes moves using random selection
    """
    # Ensure balance exists
    balance = await ensure_user_balance(challenger_id, chat_id)
    
    # Check if user has enough balance for bet
    if bet_amount > 0 and balance < bet_amount:
        await msg.reply(
            f"❌ Недостаточно очков! У тебя {balance}, нужно {bet_amount}."
        )
        return
    
    # Create duel state
    duel_state = duel_engine.create_duel(
        challenger_id=challenger_id,
        target_id=OLEG_USER_ID,  # Oleg's ID for PvE
        bet=bet_amount
    )
    
    # Send initial duel message
    status_text = render_duel_status(
        duel_state,
        challenger_name,
        "🤖 Олег"
    )
    status_text += "\n\n🎯 <b>Выбери зону атаки:</b>"
    
    sent_msg = await msg.reply(
        status_text,
        reply_markup=create_attack_keyboard(challenger_id),
        parse_mode="HTML"
    )
    
    # Register game session
    await state_manager.register_game(
        user_id=challenger_id,
        chat_id=chat_id,
        game_type="duel",
        message_id=sent_msg.message_id,
        initial_state={
            "duel_state": {
                "player1_id": duel_state.player1_id,
                "player2_id": duel_state.player2_id,
                "player1_hp": duel_state.player1_hp,
                "player2_hp": duel_state.player2_hp,
                "current_turn": duel_state.current_turn,
                "bet": duel_state.bet,
                "status": duel_state.status.value
            },
            "player1_name": challenger_name,
            "player2_name": "🤖 Олег",
            "phase": "attack",  # attack or defend
            "attack_zone": None
        }
    )
    
    logger.info(f"PvE duel started: {challenger_id} vs Oleg, bet={bet_amount}")


async def start_pvp_challenge(
    msg: Message,
    challenger_id: int,
    target_id: int,
    target_name: str,
    chat_id: int,
    bet_amount: int
):
    """Start a PvP challenge (wait for opponent confirmation).
    
    Requirement 4.1: PvP mode with @username argument
    """
    # Ensure balances exist
    await ensure_user_balance(challenger_id, chat_id)
    await ensure_user_balance(target_id, chat_id)
    
    # Sync balances from DB to game engine
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(UserBalance).where(
                UserBalance.user_id == challenger_id,
                UserBalance.chat_id == chat_id
            )
        )
        challenger_balance = result.scalars().first()
        if challenger_balance:
            game_engine.set_balance(challenger_id, chat_id, challenger_balance.balance)
        
        result = await session.execute(
            select(UserBalance).where(
                UserBalance.user_id == target_id,
                UserBalance.chat_id == chat_id
            )
        )
        target_balance = result.scalars().first()
        if target_balance:
            game_engine.set_balance(target_id, chat_id, target_balance.balance)
    
    # Create challenge
    result = game_engine.create_challenge(
        chat_id=chat_id,
        challenger_id=challenger_id,
        target_id=target_id,
        game_type=GameType.PVP,
        bet_amount=bet_amount
    )
    
    if not result.success:
        await msg.reply(f"❌ {result.message}")
        return
    
    challenge = result.challenge
    
    # Save to database
    await save_challenge_to_db(challenge)
    
    # Build challenge message
    challenger_name = msg.from_user.username or msg.from_user.first_name
    bet_text = f" на {bet_amount} очков" if bet_amount > 0 else ""
    
    challenge_text = (
        f"⚔️ <b>Вызов на дуэль!</b>\n\n"
        f"@{challenger_name} вызывает @{target_name} на бой{bet_text}!\n\n"
        f"У тебя 5 минут, чтобы принять или отклонить."
    )
    
    await msg.reply(
        challenge_text,
        reply_markup=create_challenge_keyboard(challenge.id),
        parse_mode="HTML"
    )
    
    logger.info(f"PvP challenge created: {challenger_id} vs {target_id}, bet={bet_amount}")


@router.callback_query(F.data.startswith(ACCEPT_PREFIX))
async def callback_accept_challenge(callback: CallbackQuery):
    """Handle Accept button click for PvP challenge."""
    if not callback.data or not callback.from_user:
        return
    
    challenge_id = callback.data[len(ACCEPT_PREFIX):]
    acceptor_id = callback.from_user.id
    acceptor_name = callback.from_user.username or callback.from_user.first_name
    chat_id = callback.message.chat.id if callback.message else 0
    
    # Accept challenge
    result = game_engine.accept_challenge(challenge_id, acceptor_id)
    
    if not result.success:
        await callback.answer(result.message, show_alert=True)
        return
    
    challenge = result.challenge
    
    # Update database
    await update_challenge_status_in_db(challenge_id, ChallengeStatus.ACCEPTED)
    
    # Sync balances to database
    challenger_balance = game_engine.get_balance(challenge.challenger_id, challenge.chat_id)
    target_balance = game_engine.get_balance(challenge.target_id, challenge.chat_id)
    
    await sync_balance_to_db(
        challenge.challenger_id, 
        challenge.chat_id, 
        challenger_balance.balance,
        lost=challenge.bet_amount
    )
    await sync_balance_to_db(
        challenge.target_id, 
        challenge.chat_id, 
        target_balance.balance,
        lost=challenge.bet_amount
    )
    
    # Create duel state for PvP
    duel_state = duel_engine.create_duel(
        challenger_id=challenge.challenger_id,
        target_id=challenge.target_id,
        bet=challenge.bet_amount
    )
    
    # Get challenger name
    async_session = get_session()
    async with async_session() as session:
        result_db = await session.execute(
            select(User).where(User.tg_user_id == challenge.challenger_id)
        )
        challenger_user = result_db.scalars().first()
        challenger_name = challenger_user.username if challenger_user else "Игрок"
    
    # Register game session for challenger
    await state_manager.register_game(
        user_id=challenge.challenger_id,
        chat_id=chat_id,
        game_type="duel",
        message_id=callback.message.message_id,
        initial_state={
            "duel_state": {
                "player1_id": duel_state.player1_id,
                "player2_id": duel_state.player2_id,
                "player1_hp": duel_state.player1_hp,
                "player2_hp": duel_state.player2_hp,
                "current_turn": duel_state.current_turn,
                "bet": duel_state.bet,
                "status": duel_state.status.value
            },
            "player1_name": challenger_name,
            "player2_name": acceptor_name,
            "phase": "attack",
            "attack_zone": None,
            "pvp_mode": True,
            "challenge_id": challenge_id
        }
    )
    
    # Update message with duel UI
    status_text = render_duel_status(duel_state, challenger_name, acceptor_name)
    status_text += f"\n\n🎯 <b>{challenger_name}, выбери зону атаки:</b>"
    
    await callback.message.edit_text(
        status_text,
        reply_markup=create_attack_keyboard(challenge.challenger_id),
        parse_mode="HTML"
    )
    
    await callback.answer("Вызов принят! Да начнётся бой!")
    logger.info(f"PvP challenge accepted: {challenge_id}")


@router.callback_query(F.data.startswith(DECLINE_PREFIX))
async def callback_decline_challenge(callback: CallbackQuery):
    """Handle Decline button click."""
    if not callback.data or not callback.from_user:
        return
    
    challenge_id = callback.data[len(DECLINE_PREFIX):]
    decliner_id = callback.from_user.id
    
    result = game_engine.decline_challenge(challenge_id, decliner_id)
    
    if not result.success:
        await callback.answer(result.message, show_alert=True)
        return
    
    await update_challenge_status_in_db(challenge_id, ChallengeStatus.DECLINED)
    
    decliner_name = callback.from_user.username or callback.from_user.first_name
    
    await callback.message.edit_text(
        f"🏃 <b>Вызов отклонён</b>\n\n"
        f"@{decliner_name} струсил и убежал!",
        parse_mode="HTML"
    )
    
    await callback.answer("Вызов отклонён. Трус!")
    logger.info(f"Challenge declined: {challenge_id}")


@router.callback_query(F.data.regexp(r"^duel:\d+:attack:(head|body|legs)$"))
async def callback_duel_attack(callback: CallbackQuery):
    """Handle attack zone selection.
    
    Requirements: 6.1 - Attack zones selection
    """
    if not callback.data or not callback.from_user:
        return
    
    # Parse callback data: duel:{owner_id}:attack:{zone}
    parts = callback.data.split(":")
    owner_id = int(parts[1])
    zone_str = parts[3]
    
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id if callback.message else 0
    
    # Verify owner (anti-click protection is also in middleware)
    if user_id != owner_id:
        await callback.answer("⚠️ Это не твоя кнопка, сталкер!", show_alert=True)
        return
    
    # Get session
    session = await state_manager.get_session(user_id, chat_id)
    if not session or session.game_type != "duel":
        await callback.answer("❌ Игра не найдена", show_alert=True)
        return
    
    # Store attack zone and show defend selection
    attack_zone = zone_str
    session.state["attack_zone"] = attack_zone
    session.state["phase"] = "defend"
    await state_manager.update_state(user_id, chat_id, session.state)
    
    # Get duel state for display
    duel_data = session.state["duel_state"]
    duel_state = DuelState(
        player1_id=duel_data["player1_id"],
        player2_id=duel_data["player2_id"],
        player1_hp=duel_data["player1_hp"],
        player2_hp=duel_data["player2_hp"],
        current_turn=duel_data["current_turn"],
        bet=duel_data["bet"],
        status=DuelStatus(duel_data["status"])
    )
    
    player1_name = session.state["player1_name"]
    player2_name = session.state["player2_name"]
    
    zone_display = ZONE_NAMES[Zone(attack_zone)]
    status_text = render_duel_status(duel_state, player1_name, player2_name)
    status_text += f"\n\n⚔️ Атакуешь: {zone_display}\n🛡️ <b>Выбери зону защиты:</b>"
    
    await callback.message.edit_text(
        status_text,
        reply_markup=create_defend_keyboard(owner_id, attack_zone),
        parse_mode="HTML"
    )
    
    await callback.answer(f"Атака: {zone_display}")


@router.callback_query(F.data.regexp(r"^duel:\d+:defend:(head|body|legs):(head|body|legs)$"))
async def callback_duel_defend(callback: CallbackQuery):
    """Handle defense zone selection and execute combat round.
    
    Requirements: 6.1 - Defense zones and RPS mechanics
    """
    if not callback.data or not callback.from_user:
        return
    
    # Parse callback data: duel:{owner_id}:defend:{attack_zone}:{defend_zone}
    parts = callback.data.split(":")
    owner_id = int(parts[1])
    attack_zone_str = parts[3]
    defend_zone_str = parts[4]
    
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id if callback.message else 0
    
    # Verify owner
    if user_id != owner_id:
        await callback.answer("⚠️ Это не твоя кнопка, сталкер!", show_alert=True)
        return
    
    # Get session
    session = await state_manager.get_session(user_id, chat_id)
    if not session or session.game_type != "duel":
        await callback.answer("❌ Игра не найдена", show_alert=True)
        return
    
    # Get duel state
    duel_data = session.state["duel_state"]
    duel_state = DuelState(
        player1_id=duel_data["player1_id"],
        player2_id=duel_data["player2_id"],
        player1_hp=duel_data["player1_hp"],
        player2_hp=duel_data["player2_hp"],
        current_turn=duel_data["current_turn"],
        bet=duel_data["bet"],
        status=DuelStatus(duel_data["status"])
    )
    
    player1_name = session.state["player1_name"]
    player2_name = session.state["player2_name"]
    
    # Convert zones
    player_attack = Zone(attack_zone_str)
    player_defend = Zone(defend_zone_str)
    
    # Get opponent's move (Oleg for PvE, or stored for PvP)
    if duel_state.is_pve:
        # PvE: Oleg makes random move (Requirement 4.3)
        opp_attack, opp_defend = duel_engine.oleg_move()
    else:
        # PvP: For now, simplified - opponent also makes random move
        # Full PvP would need turn-based system
        opp_attack, opp_defend = duel_engine.oleg_move()
    
    # Execute combat round
    new_duel_state = duel_engine.make_move(
        state=duel_state,
        player_id=user_id,
        attack=player_attack,
        defend=player_defend,
        opponent_attack=opp_attack,
        opponent_defend=opp_defend
    )
    
    # Calculate what happened
    player_hit = player_attack != opp_defend
    opp_hit = opp_attack != player_defend
    
    round_result = render_round_result(
        player_attack, player_defend,
        opp_attack, opp_defend,
        player_hit, opp_hit,
        player1_name, player2_name
    )
    
    # Check if game ended
    if new_duel_state.is_finished:
        await handle_duel_end(callback, new_duel_state, session, round_result)
        return
    
    # Update session state
    session.state["duel_state"] = {
        "player1_id": new_duel_state.player1_id,
        "player2_id": new_duel_state.player2_id,
        "player1_hp": new_duel_state.player1_hp,
        "player2_hp": new_duel_state.player2_hp,
        "current_turn": new_duel_state.current_turn,
        "bet": new_duel_state.bet,
        "status": new_duel_state.status.value
    }
    session.state["phase"] = "attack"
    session.state["attack_zone"] = None
    await state_manager.update_state(user_id, chat_id, session.state)
    
    # Show next round
    status_text = render_duel_status(new_duel_state, player1_name, player2_name, round_result)
    status_text += "\n\n🎯 <b>Выбери зону атаки:</b>"
    
    await callback.message.edit_text(
        status_text,
        reply_markup=create_attack_keyboard(owner_id),
        parse_mode="HTML"
    )
    
    await callback.answer("Раунд завершён!")


async def handle_duel_end(
    callback: CallbackQuery,
    duel_state: DuelState,
    session,
    round_result: str
):
    """Handle duel end - determine winner, update balances and ELO.
    
    Requirements: 10.1 - Update ELO after PvP games
    """
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id if callback.message else 0
    
    player1_name = session.state["player1_name"]
    player2_name = session.state["player2_name"]
    
    # Determine winner and loser
    winner_id = duel_state.winner_id
    loser_id = duel_state.player2_id if winner_id == duel_state.player1_id else duel_state.player1_id
    winner_name = player1_name if winner_id == duel_state.player1_id else player2_name
    loser_name = player2_name if winner_id == duel_state.player1_id else player1_name
    
    # Build final message
    final_text = render_duel_status(duel_state, player1_name, player2_name, round_result)
    
    if winner_id == duel_state.player1_id:
        final_text += f"\n\n🏆 <b>{winner_name} победил!</b>"
        if duel_state.is_pve:
            final_text += "\n💪 Олег повержен!"
    else:
        final_text += f"\n\n🏆 <b>{winner_name} победил!</b>"
        if duel_state.is_pve:
            final_text += "\n😈 Олег торжествует!"
    
    # Handle bet payouts
    if duel_state.bet > 0:
        winnings = duel_state.bet * 2
        if winner_id == duel_state.player1_id:
            # Player won
            balance = await ensure_user_balance(duel_state.player1_id, chat_id)
            new_balance = balance + winnings
            await sync_balance_to_db(
                duel_state.player1_id, chat_id, new_balance, won=winnings
            )
            final_text += f"\n💰 Выигрыш: {winnings} очков!"
        else:
            # Player lost (to Oleg or opponent)
            if not duel_state.is_pve:
                # PvP: winner gets the pot
                balance = await ensure_user_balance(winner_id, chat_id)
                new_balance = balance + winnings
                await sync_balance_to_db(winner_id, chat_id, new_balance, won=winnings)
            final_text += f"\n💸 Проигрыш: {duel_state.bet} очков"
    
    # Update ELO ratings for PvP duels (Requirement 10.1)
    elo_info = ""
    if not duel_state.is_pve:
        try:
            from app.services.leagues import league_service
            from app.database.models import GameStat
            
            async_session = get_session()
            async with async_session() as db_session:
                # Update ELO ratings
                winner_status, loser_status = await league_service.update_elo(
                    winner_id=winner_id,
                    loser_id=loser_id,
                    session=db_session
                )
                
                # Also update GameStat ELO fields for consistency
                winner_stat_result = await db_session.execute(
                    select(GameStat).where(GameStat.tg_user_id == winner_id)
                )
                winner_stat = winner_stat_result.scalar_one_or_none()
                if winner_stat:
                    winner_stat.elo_rating = winner_status.elo
                    winner_stat.league = winner_status.league.code
                
                loser_stat_result = await db_session.execute(
                    select(GameStat).where(GameStat.tg_user_id == loser_id)
                )
                loser_stat = loser_stat_result.scalar_one_or_none()
                if loser_stat:
                    loser_stat.elo_rating = loser_status.elo
                    loser_stat.league = loser_status.league.code
                
                await db_session.commit()
                
                # Format ELO change info
                elo_info = (
                    f"\n\n📊 <b>ELO:</b>\n"
                    f"  {winner_name}: +{winner_status.elo - (winner_status.elo - 16)} → {winner_status.elo} ({winner_status.league.display_name})\n"
                    f"  {loser_name}: {loser_status.elo - (loser_status.elo + 16)} → {loser_status.elo} ({loser_status.league.display_name})"
                )
                
                logger.info(
                    f"ELO updated after duel: winner={winner_id} ({winner_status.elo}), "
                    f"loser={loser_id} ({loser_status.elo})"
                )
        except Exception as e:
            logger.warning(f"Failed to update ELO after duel: {e}")
    
    final_text += elo_info
    
    # End game session
    await state_manager.end_game(user_id, chat_id)
    
    await callback.message.edit_text(final_text, parse_mode="HTML")
    await callback.answer("Дуэль завершена!")
    
    logger.info(f"Duel ended: winner={winner_id}, bet={duel_state.bet}")


@router.message(Command("cancel_challenge"))
async def cmd_cancel_challenge(msg: Message):
    """Command /cancel_challenge - Cancel your pending challenge."""
    if not msg.from_user:
        return
    
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    
    # Find pending challenges
    pending = game_engine.get_user_pending_challenges(user_id, chat_id)
    
    if not pending:
        await msg.reply("У тебя нет активных вызовов.")
        return
    
    # Cancel the first pending challenge where user is challenger
    for challenge in pending:
        if challenge.challenger_id == user_id:
            result = game_engine.cancel_challenge(challenge.id, user_id)
            if result.success:
                await update_challenge_status_in_db(challenge.id, ChallengeStatus.CANCELLED)
                await msg.reply("✅ Вызов отменён.")
                return
    
    await msg.reply("У тебя нет вызовов, которые можно отменить.")


@router.message(Command("surrender", "ff"))
async def cmd_surrender(msg: Message):
    """Command /surrender - Surrender current duel."""
    if not msg.from_user:
        return
    
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    
    session = await state_manager.get_session(user_id, chat_id)
    if not session or session.game_type != "duel":
        await msg.reply("❌ Ты не в дуэли.")
        return
    
    # End the game
    await state_manager.end_game(user_id, chat_id)
    
    await msg.reply("🏳️ Ты сдался! Позор на твою голову, сталкер.")
    logger.info(f"User {user_id} surrendered duel")
