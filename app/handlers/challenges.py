"""
PvP Challenge handlers with consent system.

Implements /challenge command and Accept/Decline callback buttons.
Requirements: 8.1, 8.2
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select

from app.database.session import get_session
from app.database.models import User, GameChallenge, UserBalance
from app.services.game_engine import game_engine, ChallengeStatus, GameType
from app.utils import utc_now

logger = logging.getLogger(__name__)

router = Router()

# Callback data prefixes
ACCEPT_PREFIX = "challenge_accept:"
DECLINE_PREFIX = "challenge_decline:"


async def ensure_user_balance(user_id: int, chat_id: int) -> int:
    """
    Ensure user has a balance record, create if not exists.
    
    Args:
        user_id: Telegram user ID
        chat_id: Telegram chat ID
        
    Returns:
        Current balance
    """
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
                balance=100,  # Default starting balance
                total_won=0,
                total_lost=0
            )
            session.add(balance)
            await session.commit()
            return 100
        
        return balance.balance


async def sync_balance_to_db(user_id: int, chat_id: int, new_balance: int, won: int = 0, lost: int = 0):
    """
    Sync in-memory balance to database.
    
    Args:
        user_id: Telegram user ID
        chat_id: Telegram chat ID
        new_balance: New balance value
        won: Amount won (to add to total_won)
        lost: Amount lost (to add to total_lost)
    """
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
    """
    Save challenge to database.
    
    Args:
        challenge: Challenge object from game engine
    """
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
    """
    Update challenge status in database.
    
    Args:
        challenge_id: Challenge UUID
        status: New status
    """
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
    """
    Create inline keyboard for challenge accept/decline.
    
    Args:
        challenge_id: Challenge UUID
        
    Returns:
        InlineKeyboardMarkup with Accept and Decline buttons
    """
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


@router.message(Command("challenge"))
async def cmd_challenge(msg: Message):
    """
    Command /challenge @user [bet] - Challenge another user to a game.
    
    Requirements:
    - 8.1: Send challenge with Accept button
    - 8.4: Prevent multiple pending challenges
    
    Usage:
        /challenge @username - Challenge with no bet
        /challenge @username 50 - Challenge with 50 point bet
        Reply to a message with /challenge - Challenge that user
    """
    if not msg.from_user:
        return
    
    challenger_id = msg.from_user.id
    chat_id = msg.chat.id
    
    # Parse target user and bet amount
    target_id = None
    target_name = None
    bet_amount = 0
    
    # Check if replying to a message
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target_id = msg.reply_to_message.from_user.id
        target_name = msg.reply_to_message.from_user.username or msg.reply_to_message.from_user.first_name
    
    # Parse command arguments
    parts = (msg.text or "").split()
    for part in parts[1:]:  # Skip /challenge
        if part.startswith("@"):
            target_name = part[1:]  # Remove @
        else:
            try:
                bet_amount = int(part)
            except ValueError:
                pass
    
    # If we have a username but no ID, we need to find the user
    if not target_id and target_name:
        # Try to find user in database by username
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.username == target_name)
            )
            user = result.scalars().first()
            if user:
                target_id = user.tg_user_id
    
    if not target_id:
        await msg.reply(
            "❌ Кого вызываешь? Укажи @username или ответь на сообщение.\n"
            "Пример: /challenge @username 50"
        )
        return
    
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
        f"⚔️ <b>Вызов на бой!</b>\n\n"
        f"@{challenger_name} вызывает тебя на дуэль{bet_text}!\n\n"
        f"У тебя 5 минут, чтобы принять или отклонить."
    )
    
    # Send challenge with buttons
    await msg.reply(
        challenge_text,
        reply_markup=create_challenge_keyboard(challenge.id),
        parse_mode="HTML"
    )
    
    logger.info(
        f"Challenge created: {challenge.id} - "
        f"{challenger_id} vs {target_id} for {bet_amount}"
    )


@router.callback_query(F.data.startswith(ACCEPT_PREFIX))
async def callback_accept_challenge(callback: CallbackQuery):
    """
    Handle Accept button click.
    
    Requirements:
    - 8.2: Start game and deduct resources from both players
    """
    if not callback.data or not callback.from_user:
        return
    
    challenge_id = callback.data[len(ACCEPT_PREFIX):]
    acceptor_id = callback.from_user.id
    
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
    
    # Update message
    acceptor_name = callback.from_user.username or callback.from_user.first_name
    bet_text = f" Ставка: {challenge.bet_amount} очков с каждого." if challenge.bet_amount > 0 else ""
    
    await callback.message.edit_text(
        f"⚔️ <b>Бой начался!</b>\n\n"
        f"@{acceptor_name} принял вызов!{bet_text}\n\n"
        f"🎲 Да начнётся битва!",
        parse_mode="HTML"
    )
    
    await callback.answer("Вызов принят! Готовься к бою!")
    
    logger.info(f"Challenge accepted: {challenge_id} by {acceptor_id}")


@router.callback_query(F.data.startswith(DECLINE_PREFIX))
async def callback_decline_challenge(callback: CallbackQuery):
    """
    Handle Decline button click.
    
    No resources are deducted when declining.
    """
    if not callback.data or not callback.from_user:
        return
    
    challenge_id = callback.data[len(DECLINE_PREFIX):]
    decliner_id = callback.from_user.id
    
    # Decline challenge
    result = game_engine.decline_challenge(challenge_id, decliner_id)
    
    if not result.success:
        await callback.answer(result.message, show_alert=True)
        return
    
    # Update database
    await update_challenge_status_in_db(challenge_id, ChallengeStatus.DECLINED)
    
    # Update message
    decliner_name = callback.from_user.username or callback.from_user.first_name
    
    await callback.message.edit_text(
        f"🏃 <b>Вызов отклонён</b>\n\n"
        f"@{decliner_name} струсил и убежал!",
        parse_mode="HTML"
    )
    
    await callback.answer("Вызов отклонён. Трус!")
    
    logger.info(f"Challenge declined: {challenge_id} by {decliner_id}")


@router.message(Command("balance"))
async def cmd_balance(msg: Message):
    """
    Command /balance - Show current balance.
    """
    if not msg.from_user:
        return
    
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    
    balance = await ensure_user_balance(user_id, chat_id)
    
    await msg.reply(
        f"💰 Твой баланс: {balance} очков\n\n"
        f"Используй /challenge @user [ставка] для вызова на дуэль."
    )


@router.message(Command("cancel_challenge"))
async def cmd_cancel_challenge(msg: Message):
    """
    Command /cancel_challenge - Cancel your pending challenge.
    """
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
