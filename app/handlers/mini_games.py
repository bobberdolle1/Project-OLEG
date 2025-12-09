"""Mini Games Handlers - All new games for v7.5 with inline buttons.

Includes: Fishing, Crash, Dice, Guess, War, Wheel, Lootbox, Cockfight.
Updated in v7.5.1 with full inventory, fishing shop, and statistics.
"""

import logging
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select

from app.database.session import get_session
from app.database.models import User, UserBalance
from app.services.mini_games import (
    fishing_game, crash_engine, dice_game, guess_engine,
    war_game, wheel_game, lootbox_engine, cockfight_game,
    RoosterTier, FishRarity
)
from app.services.state_manager import state_manager
from app.services.economy import economy_service
from app.services.inventory import inventory_service, ITEM_CATALOG, ItemType
from app.services.fishing_stats import fishing_stats_service

logger = logging.getLogger(__name__)
router = Router()

# Callback prefixes
FISH_PREFIX = "fish:"
CRASH_PREFIX = "crash:"
DICE_PREFIX = "dice:"
GUESS_PREFIX = "guess:"
WAR_PREFIX = "war:"
WHEEL_PREFIX = "wheel:"
LOOT_PREFIX = "loot:"
COCK_PREFIX = "cock:"


async def get_user_balance(user_id: int, chat_id: int) -> int:
    """Get user balance, create if not exists."""
    async_session = get_session()
    async with async_session() as session:
        res = await session.execute(
            select(UserBalance).where(
                UserBalance.user_id == user_id,
                UserBalance.chat_id == chat_id
            )
        )
        balance = res.scalars().first()
        if not balance:
            balance = UserBalance(user_id=user_id, chat_id=chat_id, balance=100)
            session.add(balance)
            await session.commit()
        return balance.balance


async def update_user_balance(user_id: int, chat_id: int, change: int) -> int:
    """Update user balance and return new value."""
    async_session = get_session()
    async with async_session() as session:
        res = await session.execute(
            select(UserBalance).where(
                UserBalance.user_id == user_id,
                UserBalance.chat_id == chat_id
            )
        )
        balance = res.scalars().first()
        if not balance:
            balance = UserBalance(user_id=user_id, chat_id=chat_id, balance=100)
            session.add(balance)
        
        balance.balance += change
        if change > 0:
            balance.total_won += change
        else:
            balance.total_lost += abs(change)
        
        await session.commit()
        return balance.balance


# ============================================================================
# FISHING GAME
# ============================================================================

def get_fishing_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Create fishing game keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎣 Забросить", callback_data=f"{FISH_PREFIX}{user_id}:cast"),
            InlineKeyboardButton(text="📊 Статистика", callback_data=f"{FISH_PREFIX}{user_id}:stats"),
        ],
        [
            InlineKeyboardButton(text="🏪 Магазин удочек", callback_data=f"{FISH_PREFIX}{user_id}:shop"),
            InlineKeyboardButton(text="🎒 Инвентарь", callback_data=f"{FISH_PREFIX}{user_id}:inventory"),
        ]
    ])


def get_rod_shop_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Create fishing rod shop keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥈 Серебряная (500)", callback_data=f"{FISH_PREFIX}{user_id}:buy:silver_rod")],
        [InlineKeyboardButton(text="🥇 Золотая (2000)", callback_data=f"{FISH_PREFIX}{user_id}:buy:golden_rod")],
        [InlineKeyboardButton(text="👑 Легендарная (10000)", callback_data=f"{FISH_PREFIX}{user_id}:buy:legendary_rod")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{FISH_PREFIX}{user_id}:back")],
    ])


def get_inventory_keyboard(user_id: int, items: list) -> InlineKeyboardMarkup:
    """Create inventory keyboard with equip buttons for rods."""
    buttons = []
    
    rod_types = [ItemType.SILVER_ROD, ItemType.GOLDEN_ROD, ItemType.LEGENDARY_ROD]
    for item in items:
        if item.item_type in [r.value for r in rod_types]:
            equipped = "✅ " if item.equipped else ""
            item_info = ITEM_CATALOG.get(item.item_type)
            if item_info:
                buttons.append([
                    InlineKeyboardButton(
                        text=f"{equipped}{item_info.emoji} {item_info.name}",
                        callback_data=f"{FISH_PREFIX}{user_id}:equip:{item.item_type}"
                    )
                ])
    
    # Show consumables count
    consumable_types = [ItemType.LUCKY_CHARM, ItemType.ENERGY_DRINK, ItemType.SHIELD]
    consumable_row = []
    for item in items:
        if item.item_type in [c.value for c in consumable_types]:
            item_info = ITEM_CATALOG.get(item.item_type)
            if item_info:
                consumable_row.append(f"{item_info.emoji}x{item.quantity}")
    
    if consumable_row:
        buttons.append([InlineKeyboardButton(text=" | ".join(consumable_row), callback_data=f"{FISH_PREFIX}{user_id}:noop")])
    
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{FISH_PREFIX}{user_id}:back")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("fish"))
async def cmd_fish(message: Message):
    """Start fishing game."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    balance = await get_user_balance(user_id, chat_id)
    
    # Get equipped rod
    equipped_rod = await inventory_service.get_equipped_rod(user_id, chat_id)
    rod_bonus = int(equipped_rod.effect.get("rod_bonus", 0) * 100)
    
    text = (
        "🎣 <b>РЫБАЛКА</b>\n\n"
        "Лови рыбу и продавай за монеты!\n"
        f"🎣 Удочка: {equipped_rod.emoji} {equipped_rod.name}\n"
        f"📈 Бонус: +{rod_bonus}% к редким рыбам\n\n"
        f"💰 Баланс: {balance} монет\n\n"
        "Нажми «Забросить» чтобы начать!"
    )
    
    await message.reply(text, reply_markup=get_fishing_keyboard(user_id), parse_mode="HTML")


@router.callback_query(F.data.startswith(FISH_PREFIX))
async def callback_fishing(callback: CallbackQuery):
    """Handle fishing callbacks."""
    parts = callback.data.split(":")
    if len(parts) < 3:
        return await callback.answer("Ошибка")
    
    _, owner_id, action = parts[:3]
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if int(owner_id) != user_id:
        return await callback.answer("Это не твоя удочка!", show_alert=True)
    
    if action == "noop":
        return await callback.answer()
    
    if action == "cast":
        # Get equipped rod bonus
        equipped_rod = await inventory_service.get_equipped_rod(user_id, chat_id)
        rod_bonus = equipped_rod.effect.get("rod_bonus", 0.0)
        
        result = fishing_game.cast(user_id, rod_bonus)
        
        if not result.success:
            return await callback.answer(result.message, show_alert=True)
        
        # Record catch in stats
        if result.fish:
            await fishing_stats_service.record_catch(
                user_id, chat_id, 
                result.fish.rarity.value, 
                result.fish.name,
                result.coins_earned
            )
        
        # Add coins
        if result.coins_earned > 0:
            new_balance = await update_user_balance(user_id, chat_id, result.coins_earned)
        else:
            new_balance = await get_user_balance(user_id, chat_id)
        
        text = f"{result.message}\n\n💰 Баланс: {new_balance} монет"
        await callback.message.edit_text(text, reply_markup=get_fishing_keyboard(user_id), parse_mode="HTML")
        await callback.answer()
    
    elif action == "stats":
        stats = await fishing_stats_service.get_stats(user_id, chat_id)
        balance = await get_user_balance(user_id, chat_id)
        
        stats_text = fishing_stats_service.format_stats(stats)
        stats_text += f"\n\n💰 Баланс: {balance} монет"
        
        await callback.message.edit_text(
            stats_text, 
            reply_markup=get_fishing_keyboard(user_id), 
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif action == "shop":
        balance = await get_user_balance(user_id, chat_id)
        
        text = (
            "🏪 <b>МАГАЗИН УДОЧЕК</b>\n\n"
            "🥈 <b>Серебряная</b> — 500 монет\n"
            "   +10% к редким рыбам\n\n"
            "🥇 <b>Золотая</b> — 2000 монет\n"
            "   +25% к редким рыбам\n\n"
            "👑 <b>Легендарная</b> — 10000 монет\n"
            "   +50% к редким рыбам!\n\n"
            f"💰 Твой баланс: {balance} монет"
        )
        
        await callback.message.edit_text(
            text, 
            reply_markup=get_rod_shop_keyboard(user_id), 
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif action == "buy":
        item_type = parts[3] if len(parts) > 3 else None
        if not item_type or item_type not in ITEM_CATALOG:
            return await callback.answer("Неизвестный предмет", show_alert=True)
        
        item_info = ITEM_CATALOG[item_type]
        balance = await get_user_balance(user_id, chat_id)
        
        if balance < item_info.price:
            return await callback.answer(
                f"Недостаточно монет! Нужно {item_info.price}, у тебя {balance}", 
                show_alert=True
            )
        
        # Check if already owned
        if await inventory_service.has_item(user_id, chat_id, item_type):
            return await callback.answer(
                f"У тебя уже есть {item_info.emoji} {item_info.name}!", 
                show_alert=True
            )
        
        # Deduct money and add item
        await update_user_balance(user_id, chat_id, -item_info.price)
        result = await inventory_service.add_item(user_id, chat_id, item_type)
        
        # Auto-equip if it's a rod
        if item_type.endswith("_rod"):
            await inventory_service.equip_item(user_id, chat_id, item_type)
            await fishing_stats_service.update_equipped_rod(user_id, chat_id, item_type)
        
        new_balance = await get_user_balance(user_id, chat_id)
        
        await callback.message.edit_text(
            f"✅ Куплено {item_info.emoji} {item_info.name}!\n\n"
            f"💰 Баланс: {new_balance} монет\n\n"
            f"<i>Удочка автоматически экипирована.</i>",
            reply_markup=get_fishing_keyboard(user_id),
            parse_mode="HTML"
        )
        await callback.answer(f"🎉 {item_info.name} куплена!")
    
    elif action == "inventory":
        items = await inventory_service.get_inventory(user_id, chat_id)
        balance = await get_user_balance(user_id, chat_id)
        
        if not items:
            text = (
                "🎒 <b>ИНВЕНТАРЬ</b>\n\n"
                "Пусто! Покупай предметы в магазине.\n\n"
                f"💰 Баланс: {balance} монет"
            )
        else:
            text = "🎒 <b>ИНВЕНТАРЬ</b>\n\n"
            
            # Group items
            rods = []
            consumables = []
            for item in items:
                item_info = ITEM_CATALOG.get(item.item_type)
                if item_info:
                    if item.item_type.endswith("_rod"):
                        equipped = " ✅" if item.equipped else ""
                        rods.append(f"{item_info.emoji} {item_info.name}{equipped}")
                    else:
                        consumables.append(f"{item_info.emoji} {item_info.name} x{item.quantity}")
            
            if rods:
                text += "<b>Удочки:</b>\n" + "\n".join(f"  {r}" for r in rods) + "\n\n"
            if consumables:
                text += "<b>Расходники:</b>\n" + "\n".join(f"  {c}" for c in consumables) + "\n\n"
            
            text += f"💰 Баланс: {balance} монет"
        
        await callback.message.edit_text(
            text, 
            reply_markup=get_inventory_keyboard(user_id, items), 
            parse_mode="HTML"
        )
        await callback.answer()
    
    elif action == "equip":
        item_type = parts[3] if len(parts) > 3 else None
        if not item_type:
            return await callback.answer("Ошибка", show_alert=True)
        
        result = await inventory_service.equip_item(user_id, chat_id, item_type)
        
        if result.success:
            await fishing_stats_service.update_equipped_rod(user_id, chat_id, item_type)
            await callback.answer(f"✅ {result.message}")
            
            # Refresh inventory view
            items = await inventory_service.get_inventory(user_id, chat_id)
            balance = await get_user_balance(user_id, chat_id)
            
            text = "🎒 <b>ИНВЕНТАРЬ</b>\n\n"
            rods = []
            for item in items:
                item_info = ITEM_CATALOG.get(item.item_type)
                if item_info and item.item_type.endswith("_rod"):
                    equipped = " ✅" if item.equipped else ""
                    rods.append(f"{item_info.emoji} {item_info.name}{equipped}")
            
            if rods:
                text += "<b>Удочки:</b>\n" + "\n".join(f"  {r}" for r in rods) + "\n\n"
            text += f"💰 Баланс: {balance} монет"
            
            await callback.message.edit_text(
                text, 
                reply_markup=get_inventory_keyboard(user_id, items), 
                parse_mode="HTML"
            )
        else:
            await callback.answer(result.message, show_alert=True)
    
    elif action == "back":
        balance = await get_user_balance(user_id, chat_id)
        equipped_rod = await inventory_service.get_equipped_rod(user_id, chat_id)
        
        text = (
            "🎣 <b>РЫБАЛКА</b>\n\n"
            "Лови рыбу и продавай за монеты!\n"
            f"🎣 Удочка: {equipped_rod.emoji} {equipped_rod.name}\n"
            f"📈 Бонус: +{int(equipped_rod.effect.get('rod_bonus', 0) * 100)}% к редким\n\n"
            f"💰 Баланс: {balance} монет\n\n"
            "Нажми «Забросить» чтобы начать!"
        )
        
        await callback.message.edit_text(text, reply_markup=get_fishing_keyboard(user_id), parse_mode="HTML")
        await callback.answer()


# ============================================================================
# CRASH GAME
# ============================================================================

def get_crash_keyboard(user_id: int, playing: bool = False) -> InlineKeyboardMarkup:
    """Create crash game keyboard."""
    if playing:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 ЗАБРАТЬ", callback_data=f"{CRASH_PREFIX}{user_id}:cashout")],
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 10", callback_data=f"{CRASH_PREFIX}{user_id}:start:10"),
                InlineKeyboardButton(text="🚀 50", callback_data=f"{CRASH_PREFIX}{user_id}:start:50"),
                InlineKeyboardButton(text="🚀 100", callback_data=f"{CRASH_PREFIX}{user_id}:start:100"),
            ],
            [
                InlineKeyboardButton(text="🚀 250", callback_data=f"{CRASH_PREFIX}{user_id}:start:250"),
                InlineKeyboardButton(text="🚀 500", callback_data=f"{CRASH_PREFIX}{user_id}:start:500"),
            ],
        ])


@router.message(Command("crash"))
async def cmd_crash(message: Message):
    """Start crash game."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    balance = await get_user_balance(user_id, chat_id)
    
    text = (
        "🚀 <b>CRASH</b>\n\n"
        "Множитель растёт — успей забрать до краша!\n"
        "Чем дольше ждёшь — тем больше выигрыш, но рискуешь всё потерять.\n\n"
        f"💰 Баланс: {balance} монет\n\n"
        "Выбери ставку:"
    )
    
    await message.reply(text, reply_markup=get_crash_keyboard(user_id), parse_mode="HTML")


@router.callback_query(F.data.startswith(CRASH_PREFIX))
async def callback_crash(callback: CallbackQuery):
    """Handle crash game callbacks."""
    parts = callback.data.split(":")
    if len(parts) < 3:
        return await callback.answer("Ошибка")
    
    _, owner_id, action = parts[:3]
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if int(owner_id) != user_id:
        return await callback.answer("Это не твоя игра!", show_alert=True)
    
    if action == "start":
        bet = int(parts[3]) if len(parts) > 3 else 10
        balance = await get_user_balance(user_id, chat_id)
        
        if balance < bet:
            return await callback.answer(f"Недостаточно монет! У тебя {balance}", show_alert=True)
        
        # Check if already playing
        if await state_manager.is_playing(user_id, chat_id):
            return await callback.answer("У тебя уже есть активная игра!", show_alert=True)
        
        # Deduct bet
        await update_user_balance(user_id, chat_id, -bet)
        
        # Start game
        result = crash_engine.start_game(user_id, bet)
        if not result.success:
            await update_user_balance(user_id, chat_id, bet)  # Refund
            return await callback.answer(result.message, show_alert=True)
        
        # Register session
        await state_manager.register_game(user_id, chat_id, "crash", callback.message.message_id, {"bet": bet})
        
        # Start multiplier animation
        await callback.message.edit_text(
            f"🚀 <b>CRASH</b>\n\n"
            f"Ставка: {bet} монет\n"
            f"Множитель: x{result.multiplier}\n\n"
            f"Жми ЗАБРАТЬ пока не поздно!",
            reply_markup=get_crash_keyboard(user_id, playing=True),
            parse_mode="HTML"
        )
        
        # Auto-tick the game
        asyncio.create_task(crash_auto_tick(callback.message, user_id, chat_id, bet))
        await callback.answer("🚀 Поехали!")
    
    elif action == "cashout":
        result = crash_engine.cash_out(user_id)
        if not result.success:
            return await callback.answer(result.message, show_alert=True)
        
        # Add winnings
        game = crash_engine.get_game(user_id)
        if game:
            total = game.bet + result.winnings
            new_balance = await update_user_balance(user_id, chat_id, total)
            crash_engine.end_game(user_id)
            await state_manager.end_game(user_id, chat_id)
            
            await callback.message.edit_text(
                f"🚀 <b>CRASH</b>\n\n"
                f"💰 Забрал на x{result.multiplier}!\n"
                f"Выигрыш: +{result.winnings} монет\n\n"
                f"💰 Баланс: {new_balance} монет",
                reply_markup=get_crash_keyboard(user_id, playing=False),
                parse_mode="HTML"
            )
        await callback.answer(f"💰 +{result.winnings} монет!")


async def crash_auto_tick(message: Message, user_id: int, chat_id: int, bet: int):
    """Auto-tick crash game."""
    while True:
        await asyncio.sleep(0.8)
        
        game = crash_engine.get_game(user_id)
        if not game or game.status != "playing":
            break
        
        result = crash_engine.tick(user_id)
        
        if result.crashed:
            crash_engine.end_game(user_id)
            await state_manager.end_game(user_id, chat_id)
            balance = await get_user_balance(user_id, chat_id)
            
            try:
                await message.edit_text(
                    f"🚀 <b>CRASH</b>\n\n"
                    f"💥 КРАШ на x{result.multiplier}!\n"
                    f"Потерял: -{bet} монет\n\n"
                    f"💰 Баланс: {balance} монет",
                    reply_markup=get_crash_keyboard(user_id, playing=False),
                    parse_mode="HTML"
                )
            except:
                pass
            break
        
        try:
            await message.edit_text(
                f"🚀 <b>CRASH</b>\n\n"
                f"Ставка: {bet} монет\n"
                f"Множитель: x{result.multiplier}\n"
                f"Потенциальный выигрыш: {int(bet * result.multiplier)} монет\n\n"
                f"Жми ЗАБРАТЬ пока не поздно!",
                reply_markup=get_crash_keyboard(user_id, playing=True),
                parse_mode="HTML"
            )
        except:
            pass


# ============================================================================
# DICE GAME
# ============================================================================

def get_dice_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Create dice game keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎲 10", callback_data=f"{DICE_PREFIX}{user_id}:10"),
            InlineKeyboardButton(text="🎲 25", callback_data=f"{DICE_PREFIX}{user_id}:25"),
            InlineKeyboardButton(text="🎲 50", callback_data=f"{DICE_PREFIX}{user_id}:50"),
        ],
        [
            InlineKeyboardButton(text="🎲 100", callback_data=f"{DICE_PREFIX}{user_id}:100"),
            InlineKeyboardButton(text="🎲 250", callback_data=f"{DICE_PREFIX}{user_id}:250"),
        ],
    ])


@router.message(Command("dice"))
async def cmd_dice(message: Message):
    """Start dice game."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    balance = await get_user_balance(user_id, chat_id)
    
    text = (
        "🎲 <b>КОСТИ</b>\n\n"
        "Бросаешь 2 кубика против бота.\n"
        "У кого сумма больше — тот победил!\n\n"
        f"💰 Баланс: {balance} монет\n\n"
        "Выбери ставку:"
    )
    
    await message.reply(text, reply_markup=get_dice_keyboard(user_id), parse_mode="HTML")


@router.callback_query(F.data.startswith(DICE_PREFIX))
async def callback_dice(callback: CallbackQuery):
    """Handle dice game callbacks."""
    parts = callback.data.split(":")
    if len(parts) != 3:
        return await callback.answer("Ошибка")
    
    _, owner_id, bet_str = parts
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if int(owner_id) != user_id:
        return await callback.answer("Это не твои кости!", show_alert=True)
    
    bet = int(bet_str)
    balance = await get_user_balance(user_id, chat_id)
    
    if balance < bet:
        return await callback.answer(f"Недостаточно монет! У тебя {balance}", show_alert=True)
    
    # Deduct bet first
    await update_user_balance(user_id, chat_id, -bet)
    
    # Play game
    result = dice_game.play_vs_bot(user_id, bet)
    
    # Add winnings (includes bet back if won/draw)
    new_balance = await update_user_balance(user_id, chat_id, result.winnings)
    
    text = f"🎲 <b>КОСТИ</b>\n\n{result.message}\n\n💰 Баланс: {new_balance} монет"
    await callback.message.edit_text(text, reply_markup=get_dice_keyboard(user_id), parse_mode="HTML")
    await callback.answer()


# ============================================================================
# GUESS NUMBER GAME
# ============================================================================

def get_guess_keyboard(user_id: int, game_active: bool = False, min_val: int = 1, max_val: int = 100) -> InlineKeyboardMarkup:
    """Create guess game keyboard."""
    if not game_active:
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔮 10 монет", callback_data=f"{GUESS_PREFIX}{user_id}:start:10"),
                InlineKeyboardButton(text="🔮 50 монет", callback_data=f"{GUESS_PREFIX}{user_id}:start:50"),
            ],
            [
                InlineKeyboardButton(text="🔮 100 монет", callback_data=f"{GUESS_PREFIX}{user_id}:start:100"),
            ],
        ])
    else:
        # Generate number buttons based on current range
        buttons = []
        step = max(1, (max_val - min_val) // 5)
        row = []
        for i, num in enumerate(range(min_val, max_val + 1, step)):
            if num <= max_val:
                row.append(InlineKeyboardButton(text=str(num), callback_data=f"{GUESS_PREFIX}{user_id}:guess:{num}"))
                if len(row) == 3:
                    buttons.append(row)
                    row = []
        if row:
            buttons.append(row)
        
        buttons.append([InlineKeyboardButton(text="❌ Сдаться", callback_data=f"{GUESS_PREFIX}{user_id}:giveup")])
        return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("guess"))
async def cmd_guess(message: Message):
    """Start guess number game."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    balance = await get_user_balance(user_id, chat_id)
    
    # Check for active game
    game = guess_engine.get_game(user_id)
    if game and game.status.value == "playing":
        text = (
            f"🔮 <b>УГАДАЙ ЧИСЛО</b>\n\n"
            f"Число от {game.min_val} до {game.max_val}\n"
            f"Попыток осталось: {game.max_attempts - game.attempts}\n\n"
            f"Выбери число:"
        )
        await message.reply(text, reply_markup=get_guess_keyboard(user_id, True, game.min_val, game.max_val), parse_mode="HTML")
        return
    
    text = (
        "🔮 <b>УГАДАЙ ЧИСЛО</b>\n\n"
        "Загадываю число от 1 до 100.\n"
        "У тебя 7 попыток угадать!\n"
        "Чем меньше попыток — тем больше награда.\n\n"
        f"💰 Баланс: {balance} монет\n\n"
        "Выбери ставку:"
    )
    
    await message.reply(text, reply_markup=get_guess_keyboard(user_id), parse_mode="HTML")


@router.callback_query(F.data.startswith(GUESS_PREFIX))
async def callback_guess(callback: CallbackQuery):
    """Handle guess game callbacks."""
    parts = callback.data.split(":")
    if len(parts) < 3:
        return await callback.answer("Ошибка")
    
    _, owner_id, action = parts[:3]
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if int(owner_id) != user_id:
        return await callback.answer("Это не твоя игра!", show_alert=True)
    
    if action == "start":
        bet = int(parts[3]) if len(parts) > 3 else 10
        balance = await get_user_balance(user_id, chat_id)
        
        if balance < bet:
            return await callback.answer(f"Недостаточно монет! У тебя {balance}", show_alert=True)
        
        # Deduct bet
        await update_user_balance(user_id, chat_id, -bet)
        
        # Start game
        result = guess_engine.start_game(user_id, bet)
        game = guess_engine.get_game(user_id)
        
        text = f"🔮 <b>УГАДАЙ ЧИСЛО</b>\n\n{result.message}\n\nВыбери число:"
        await callback.message.edit_text(
            text, 
            reply_markup=get_guess_keyboard(user_id, True, game.min_val, game.max_val),
            parse_mode="HTML"
        )
        await callback.answer("Игра началась!")
    
    elif action == "guess":
        number = int(parts[3]) if len(parts) > 3 else 50
        result = guess_engine.guess(user_id, number)
        game = guess_engine.get_game(user_id)
        
        if result.correct or result.attempts_left == 0:
            # Game over
            if result.winnings > 0:
                new_balance = await update_user_balance(user_id, chat_id, result.winnings + game.bet)
            else:
                new_balance = await get_user_balance(user_id, chat_id)
            
            guess_engine.end_game(user_id)
            text = f"🔮 <b>УГАДАЙ ЧИСЛО</b>\n\n{result.message}\n\n💰 Баланс: {new_balance} монет"
            await callback.message.edit_text(text, reply_markup=get_guess_keyboard(user_id), parse_mode="HTML")
        else:
            text = (
                f"🔮 <b>УГАДАЙ ЧИСЛО</b>\n\n"
                f"{result.hint}\n"
                f"Попыток осталось: {result.attempts_left}\n\n"
                f"Выбери число:"
            )
            await callback.message.edit_text(
                text,
                reply_markup=get_guess_keyboard(user_id, True, game.min_val, game.max_val),
                parse_mode="HTML"
            )
        await callback.answer()
    
    elif action == "giveup":
        game = guess_engine.get_game(user_id)
        if game:
            guess_engine.end_game(user_id)
            balance = await get_user_balance(user_id, chat_id)
            text = f"🔮 <b>УГАДАЙ ЧИСЛО</b>\n\n😢 Сдался! Число было {game.target}.\n-{game.bet} монет\n\n💰 Баланс: {balance} монет"
            await callback.message.edit_text(text, reply_markup=get_guess_keyboard(user_id), parse_mode="HTML")
        await callback.answer("Сдался!")


# ============================================================================
# WAR CARD GAME
# ============================================================================

def get_war_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Create war game keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🃏 10", callback_data=f"{WAR_PREFIX}{user_id}:10"),
            InlineKeyboardButton(text="🃏 25", callback_data=f"{WAR_PREFIX}{user_id}:25"),
            InlineKeyboardButton(text="🃏 50", callback_data=f"{WAR_PREFIX}{user_id}:50"),
        ],
        [
            InlineKeyboardButton(text="🃏 100", callback_data=f"{WAR_PREFIX}{user_id}:100"),
            InlineKeyboardButton(text="🃏 250", callback_data=f"{WAR_PREFIX}{user_id}:250"),
        ],
    ])


@router.message(Command("war"))
async def cmd_war(message: Message):
    """Start war card game."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    balance = await get_user_balance(user_id, chat_id)
    
    text = (
        "🃏 <b>ВОЙНА</b>\n\n"
        "Простая карточная игра!\n"
        "Ты и бот тянете по карте — у кого старше, тот победил.\n\n"
        f"💰 Баланс: {balance} монет\n\n"
        "Выбери ставку:"
    )
    
    await message.reply(text, reply_markup=get_war_keyboard(user_id), parse_mode="HTML")


@router.callback_query(F.data.startswith(WAR_PREFIX))
async def callback_war(callback: CallbackQuery):
    """Handle war game callbacks."""
    parts = callback.data.split(":")
    if len(parts) != 3:
        return await callback.answer("Ошибка")
    
    _, owner_id, bet_str = parts
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if int(owner_id) != user_id:
        return await callback.answer("Это не твои карты!", show_alert=True)
    
    bet = int(bet_str)
    balance = await get_user_balance(user_id, chat_id)
    
    if balance < bet:
        return await callback.answer(f"Недостаточно монет! У тебя {balance}", show_alert=True)
    
    # Deduct bet first
    await update_user_balance(user_id, chat_id, -bet)
    
    # Play game
    result = war_game.play(user_id, bet)
    
    # Add winnings (includes bet back if won/draw)
    new_balance = await update_user_balance(user_id, chat_id, result.winnings)
    
    text = f"🃏 <b>ВОЙНА</b>\n\n{result.message}\n\n💰 Баланс: {new_balance} монет"
    await callback.message.edit_text(text, reply_markup=get_war_keyboard(user_id), parse_mode="HTML")
    await callback.answer()


# ============================================================================
# WHEEL OF FORTUNE
# ============================================================================

def get_wheel_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Create wheel game keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎡 10", callback_data=f"{WHEEL_PREFIX}{user_id}:10"),
            InlineKeyboardButton(text="🎡 25", callback_data=f"{WHEEL_PREFIX}{user_id}:25"),
            InlineKeyboardButton(text="🎡 50", callback_data=f"{WHEEL_PREFIX}{user_id}:50"),
        ],
        [
            InlineKeyboardButton(text="🎡 100", callback_data=f"{WHEEL_PREFIX}{user_id}:100"),
            InlineKeyboardButton(text="🎡 250", callback_data=f"{WHEEL_PREFIX}{user_id}:250"),
        ],
    ])


@router.message(Command("wheel"))
async def cmd_wheel(message: Message):
    """Start wheel of fortune game."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    balance = await get_user_balance(user_id, chat_id)
    
    text = (
        "🎡 <b>КОЛЕСО ФОРТУНЫ</b>\n\n"
        "Крути колесо и испытай удачу!\n\n"
        "💀 Банкрот — потеря всего\n"
        "😢 x0.5 — минус половина\n"
        "🔄 x1 — возврат ставки\n"
        "💰 x1.5-x3 — выигрыш\n"
        "🌟 x5 — большой выигрыш\n"
        "👑 x10 — ДЖЕКПОТ!\n\n"
        f"💰 Баланс: {balance} монет\n\n"
        "Выбери ставку:"
    )
    
    await message.reply(text, reply_markup=get_wheel_keyboard(user_id), parse_mode="HTML")


@router.callback_query(F.data.startswith(WHEEL_PREFIX))
async def callback_wheel(callback: CallbackQuery):
    """Handle wheel game callbacks."""
    parts = callback.data.split(":")
    if len(parts) != 3:
        return await callback.answer("Ошибка")
    
    _, owner_id, bet_str = parts
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if int(owner_id) != user_id:
        return await callback.answer("Это не твоё колесо!", show_alert=True)
    
    bet = int(bet_str)
    balance = await get_user_balance(user_id, chat_id)
    
    if balance < bet:
        return await callback.answer(f"Недостаточно монет! У тебя {balance}", show_alert=True)
    
    # Deduct bet first
    await update_user_balance(user_id, chat_id, -bet)
    
    # Play game
    result = wheel_game.spin(user_id, bet)
    
    # Add winnings (includes bet back based on multiplier)
    new_balance = await update_user_balance(user_id, chat_id, result.winnings)
    
    text = f"{result.message}\n\n💰 Баланс: {new_balance} монет"
    await callback.message.edit_text(text, reply_markup=get_wheel_keyboard(user_id), parse_mode="HTML")
    await callback.answer()


# ============================================================================
# LOOTBOX SYSTEM
# ============================================================================

def get_lootbox_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Create lootbox keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📦 Обычный (50)", callback_data=f"{LOOT_PREFIX}{user_id}:common"),
            InlineKeyboardButton(text="📦 Редкий (150)", callback_data=f"{LOOT_PREFIX}{user_id}:rare"),
        ],
        [
            InlineKeyboardButton(text="📦 Эпик (400)", callback_data=f"{LOOT_PREFIX}{user_id}:epic"),
            InlineKeyboardButton(text="📦 Легенда (1000)", callback_data=f"{LOOT_PREFIX}{user_id}:legendary"),
        ],
    ])


LOOTBOX_PRICES = {
    "common": 50,
    "rare": 150,
    "epic": 400,
    "legendary": 1000,
}


@router.message(Command("loot"))
async def cmd_loot(message: Message):
    """Open lootbox menu."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    balance = await get_user_balance(user_id, chat_id)
    
    text = (
        "📦 <b>ЛУТБОКСЫ</b>\n\n"
        "Открывай коробки и получай награды!\n\n"
        "📦 <b>Обычный</b> (50) — базовые награды\n"
        "📦 <b>Редкий</b> (150) — лучше шансы\n"
        "📦 <b>Эпический</b> (400) — гарантированный эпик+\n"
        "📦 <b>Легендарный</b> (1000) — шанс на легендарку!\n\n"
        f"💰 Баланс: {balance} монет\n\n"
        "Выбери лутбокс:"
    )
    
    await message.reply(text, reply_markup=get_lootbox_keyboard(user_id), parse_mode="HTML")


@router.callback_query(F.data.startswith(LOOT_PREFIX))
async def callback_lootbox(callback: CallbackQuery):
    """Handle lootbox callbacks."""
    parts = callback.data.split(":")
    if len(parts) != 3:
        return await callback.answer("Ошибка")
    
    _, owner_id, loot_type = parts
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if int(owner_id) != user_id:
        return await callback.answer("Это не твой лутбокс!", show_alert=True)
    
    price = LOOTBOX_PRICES.get(loot_type, 50)
    balance = await get_user_balance(user_id, chat_id)
    
    if balance < price:
        return await callback.answer(f"Недостаточно монет! У тебя {balance}, нужно {price}", show_alert=True)
    
    # Deduct price
    await update_user_balance(user_id, chat_id, -price)
    
    # Open lootbox
    result = lootbox_engine.open(loot_type)
    
    # Add coins from lootbox
    if result.total_coins > 0:
        await update_user_balance(user_id, chat_id, result.total_coins)
    
    # Add items to inventory
    items_added = []
    for item_type in result.items:
        if item_type:
            add_result = await inventory_service.add_item(user_id, chat_id, item_type)
            if add_result.success and add_result.item:
                items_added.append(f"{add_result.item.emoji} {add_result.item.name}")
    
    new_balance = await get_user_balance(user_id, chat_id)
    
    text = f"{result.message}"
    if items_added:
        text += f"\n\n🎁 Добавлено в инвентарь:\n" + "\n".join(f"  {i}" for i in items_added)
    text += f"\n\n💰 Баланс: {new_balance} монет"
    
    await callback.message.edit_text(text, reply_markup=get_lootbox_keyboard(user_id), parse_mode="HTML")
    await callback.answer("📦 Открыто!")


# ============================================================================
# COCKFIGHT GAME
# ============================================================================

def get_cockfight_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Create cockfight keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐔 Обычный петух", callback_data=f"{COCK_PREFIX}{user_id}:select:common")],
        [InlineKeyboardButton(text="🐓 Редкий петух", callback_data=f"{COCK_PREFIX}{user_id}:select:rare")],
        [InlineKeyboardButton(text="🦃 Эпический петух", callback_data=f"{COCK_PREFIX}{user_id}:select:epic")],
    ])


def get_cockfight_bet_keyboard(user_id: int, tier: str) -> InlineKeyboardMarkup:
    """Create cockfight bet keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💰 25", callback_data=f"{COCK_PREFIX}{user_id}:fight:{tier}:25"),
            InlineKeyboardButton(text="💰 50", callback_data=f"{COCK_PREFIX}{user_id}:fight:{tier}:50"),
            InlineKeyboardButton(text="💰 100", callback_data=f"{COCK_PREFIX}{user_id}:fight:{tier}:100"),
        ],
        [
            InlineKeyboardButton(text="💰 250", callback_data=f"{COCK_PREFIX}{user_id}:fight:{tier}:250"),
            InlineKeyboardButton(text="💰 500", callback_data=f"{COCK_PREFIX}{user_id}:fight:{tier}:500"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{COCK_PREFIX}{user_id}:back")],
    ])


@router.message(Command("cockfight"))
async def cmd_cockfight(message: Message):
    """Start cockfight game."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    balance = await get_user_balance(user_id, chat_id)
    
    text = (
        "🐔 <b>ПЕТУШИНЫЕ БОИ</b> 🐔\n\n"
        "Выбери своего бойца и сделай ставку!\n\n"
        "🐔 <b>Обычный</b> — базовая сила, x1.5 выигрыш\n"
        "🐓 <b>Редкий</b> — сильнее, x2 выигрыш\n"
        "🦃 <b>Эпический</b> — элита, x2.5 выигрыш\n\n"
        f"💰 Баланс: {balance} монет\n\n"
        "Выбери петуха:"
    )
    
    await message.reply(text, reply_markup=get_cockfight_keyboard(user_id), parse_mode="HTML")


@router.callback_query(F.data.startswith(COCK_PREFIX))
async def callback_cockfight(callback: CallbackQuery):
    """Handle cockfight callbacks."""
    parts = callback.data.split(":")
    if len(parts) < 3:
        return await callback.answer("Ошибка")
    
    _, owner_id, action = parts[:3]
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if int(owner_id) != user_id:
        return await callback.answer("Это не твой петух!", show_alert=True)
    
    if action == "select":
        tier = parts[3] if len(parts) > 3 else "common"
        tier_names = {"common": "Обычный 🐔", "rare": "Редкий 🐓", "epic": "Эпический 🦃"}
        
        text = (
            f"🐔 <b>ПЕТУШИНЫЕ БОИ</b>\n\n"
            f"Выбран: {tier_names.get(tier, tier)}\n\n"
            f"Выбери ставку:"
        )
        await callback.message.edit_text(text, reply_markup=get_cockfight_bet_keyboard(user_id, tier), parse_mode="HTML")
        await callback.answer()
    
    elif action == "fight":
        tier = parts[3] if len(parts) > 3 else "common"
        bet = int(parts[4]) if len(parts) > 4 else 25
        
        balance = await get_user_balance(user_id, chat_id)
        if balance < bet:
            return await callback.answer(f"Недостаточно монет! У тебя {balance}", show_alert=True)
        
        # Deduct bet first
        await update_user_balance(user_id, chat_id, -bet)
        
        # Map tier string to enum
        tier_map = {"common": RoosterTier.COMMON, "rare": RoosterTier.RARE, "epic": RoosterTier.EPIC}
        rooster_tier = tier_map.get(tier, RoosterTier.COMMON)
        
        # Play game
        result = cockfight_game.fight(user_id, bet, rooster_tier)
        
        # Update balance with result (winnings already include bet back if won)
        if result.won:
            # Won: add winnings (which is bet * multiplier)
            new_balance = await update_user_balance(user_id, chat_id, result.winnings + bet)
        elif result.winnings == 0:
            # Draw: refund bet
            new_balance = await update_user_balance(user_id, chat_id, bet)
        else:
            # Lost: bet already deducted
            new_balance = await get_user_balance(user_id, chat_id)
        
        text = f"{result.message}\n\n💰 Баланс: {new_balance} монет"
        await callback.message.edit_text(text, reply_markup=get_cockfight_keyboard(user_id), parse_mode="HTML")
        await callback.answer()
    
    elif action == "back":
        balance = await get_user_balance(user_id, chat_id)
        text = (
            "🐔 <b>ПЕТУШИНЫЕ БОИ</b> 🐔\n\n"
            "Выбери своего бойца и сделай ставку!\n\n"
            f"💰 Баланс: {balance} монет\n\n"
            "Выбери петуха:"
        )
        await callback.message.edit_text(text, reply_markup=get_cockfight_keyboard(user_id), parse_mode="HTML")
        await callback.answer()


# ============================================================================
# BALANCE & DAILY BONUS
# ============================================================================

@router.message(Command("balance"))
async def cmd_balance(message: Message):
    """Show user balance."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    balance = await get_user_balance(user_id, chat_id)
    
    await message.reply(
        f"💰 <b>Твой баланс</b>\n\n"
        f"🪙 {balance} монет\n\n"
        f"<i>Зарабатывай в играх: /games</i>",
        parse_mode="HTML"
    )


@router.message(Command("daily"))
async def cmd_daily(message: Message):
    """Claim daily bonus."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # TODO: Add proper daily tracking with cooldown
    # For now, just give a small bonus
    bonus = 25
    new_balance = await update_user_balance(user_id, chat_id, bonus)
    
    await message.reply(
        f"🎁 <b>Ежедневный бонус!</b>\n\n"
        f"+{bonus} монет\n\n"
        f"💰 Баланс: {new_balance} монет\n\n"
        f"<i>Приходи завтра за новым бонусом!</i>",
        parse_mode="HTML"
    )
    
    logger.info(f"Daily bonus claimed by user {user_id}: +{bonus}")


@router.message(Command("transfer"))
async def cmd_transfer(message: Message):
    """Transfer coins to another user."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Parse command: /transfer @user amount
    parts = message.text.split()
    if len(parts) < 3:
        return await message.reply(
            "💸 <b>Перевод монет</b>\n\n"
            "Использование: /transfer @username сумма\n"
            "Пример: /transfer @friend 100",
            parse_mode="HTML"
        )
    
    # Get target user
    target_mention = parts[1]
    if not target_mention.startswith("@"):
        return await message.reply("❌ Укажи пользователя через @username")
    
    try:
        amount = int(parts[2])
    except ValueError:
        return await message.reply("❌ Укажи корректную сумму")
    
    if amount <= 0:
        return await message.reply("❌ Сумма должна быть положительной")
    
    balance = await get_user_balance(user_id, chat_id)
    if balance < amount:
        return await message.reply(f"❌ Недостаточно монет! У тебя {balance}")
    
    # For now, just show the intent (need target user ID for actual transfer)
    await message.reply(
        f"💸 Для перевода {amount} монет пользователю {target_mention}, "
        f"попроси его написать что-нибудь в чат, чтобы я мог его найти.",
        parse_mode="HTML"
    )


# ============================================================================
# INVENTORY & SHOP COMMANDS
# ============================================================================

SHOP_PREFIX = "shop:"


def get_shop_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Create shop keyboard with all purchasable items."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎣 Удочки", callback_data=f"{SHOP_PREFIX}{user_id}:rods")],
        [InlineKeyboardButton(text="🧪 Расходники", callback_data=f"{SHOP_PREFIX}{user_id}:consumables")],
        [InlineKeyboardButton(text="🎒 Мой инвентарь", callback_data=f"{SHOP_PREFIX}{user_id}:inventory")],
    ])


def get_shop_rods_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Create rod shop keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥈 Серебряная удочка (500)", callback_data=f"{SHOP_PREFIX}{user_id}:buy:silver_rod")],
        [InlineKeyboardButton(text="🥇 Золотая удочка (2000)", callback_data=f"{SHOP_PREFIX}{user_id}:buy:golden_rod")],
        [InlineKeyboardButton(text="👑 Легендарная удочка (10000)", callback_data=f"{SHOP_PREFIX}{user_id}:buy:legendary_rod")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{SHOP_PREFIX}{user_id}:back")],
    ])


def get_shop_consumables_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Create consumables shop keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🥤 Энергетик (50)", callback_data=f"{SHOP_PREFIX}{user_id}:buy:energy_drink")],
        [InlineKeyboardButton(text="🍀 Талисман удачи (100)", callback_data=f"{SHOP_PREFIX}{user_id}:buy:lucky_charm")],
        [InlineKeyboardButton(text="🛡️ Щит (200)", callback_data=f"{SHOP_PREFIX}{user_id}:buy:shield")],
        [InlineKeyboardButton(text="👑 VIP статус (1000)", callback_data=f"{SHOP_PREFIX}{user_id}:buy:vip_status")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"{SHOP_PREFIX}{user_id}:back")],
    ])


@router.message(Command("shop"))
async def cmd_shop(message: Message):
    """Open the shop."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    balance = await get_user_balance(user_id, chat_id)
    
    text = (
        "🏪 <b>МАГАЗИН</b>\n\n"
        "Покупай предметы за монеты!\n\n"
        "🎣 <b>Удочки</b> — улучшают шанс редкой рыбы\n"
        "🧪 <b>Расходники</b> — бонусы для игр\n\n"
        f"💰 Баланс: {balance} монет"
    )
    
    await message.reply(text, reply_markup=get_shop_keyboard(user_id), parse_mode="HTML")


@router.message(Command("inventory"))
async def cmd_inventory(message: Message):
    """Show user inventory."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    items = await inventory_service.get_inventory(user_id, chat_id)
    balance = await get_user_balance(user_id, chat_id)
    
    if not items:
        text = (
            "🎒 <b>ИНВЕНТАРЬ</b>\n\n"
            "Пусто! Покупай предметы в /shop\n\n"
            f"💰 Баланс: {balance} монет"
        )
    else:
        text = "🎒 <b>ИНВЕНТАРЬ</b>\n\n"
        
        # Group items by category
        rods = []
        consumables = []
        
        for item in items:
            item_info = ITEM_CATALOG.get(item.item_type)
            if item_info:
                if item.item_type.endswith("_rod"):
                    equipped = " ✅" if item.equipped else ""
                    rods.append(f"  {item_info.emoji} {item_info.name}{equipped}")
                else:
                    consumables.append(f"  {item_info.emoji} {item_info.name} x{item.quantity}")
        
        if rods:
            text += "<b>🎣 Удочки:</b>\n" + "\n".join(rods) + "\n\n"
        if consumables:
            text += "<b>🧪 Расходники:</b>\n" + "\n".join(consumables) + "\n\n"
        
        text += f"💰 Баланс: {balance} монет\n\n"
        text += "<i>Используй /fish для рыбалки</i>"
    
    await message.reply(text, parse_mode="HTML")


@router.callback_query(F.data.startswith(SHOP_PREFIX))
async def callback_shop(callback: CallbackQuery):
    """Handle shop callbacks."""
    parts = callback.data.split(":")
    if len(parts) < 3:
        return await callback.answer("Ошибка")
    
    _, owner_id, action = parts[:3]
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if int(owner_id) != user_id:
        return await callback.answer("Это не твой магазин!", show_alert=True)
    
    balance = await get_user_balance(user_id, chat_id)
    
    if action == "rods":
        text = (
            "🎣 <b>УДОЧКИ</b>\n\n"
            "🥈 <b>Серебряная</b> — 500 монет\n"
            "   +10% к редким рыбам\n\n"
            "🥇 <b>Золотая</b> — 2000 монет\n"
            "   +25% к редким рыбам\n\n"
            "👑 <b>Легендарная</b> — 10000 монет\n"
            "   +50% к редким рыбам!\n\n"
            f"💰 Баланс: {balance} монет"
        )
        await callback.message.edit_text(text, reply_markup=get_shop_rods_keyboard(user_id), parse_mode="HTML")
        await callback.answer()
    
    elif action == "consumables":
        text = (
            "🧪 <b>РАСХОДНИКИ</b>\n\n"
            "🥤 <b>Энергетик</b> — 50 монет\n"
            "   Сбрасывает кулдаун рыбалки\n\n"
            "🍀 <b>Талисман удачи</b> — 100 монет\n"
            "   +10% к выигрышу в следующей игре\n\n"
            "🛡️ <b>Щит</b> — 200 монет\n"
            "   Защита от потери в следующей игре\n\n"
            "👑 <b>VIP статус</b> — 1000 монет\n"
            "   +20% к выигрышам на 24 часа\n\n"
            f"💰 Баланс: {balance} монет"
        )
        await callback.message.edit_text(text, reply_markup=get_shop_consumables_keyboard(user_id), parse_mode="HTML")
        await callback.answer()
    
    elif action == "inventory":
        items = await inventory_service.get_inventory(user_id, chat_id)
        
        if not items:
            text = (
                "🎒 <b>ИНВЕНТАРЬ</b>\n\n"
                "Пусто! Покупай предметы в магазине.\n\n"
                f"💰 Баланс: {balance} монет"
            )
        else:
            text = "🎒 <b>ИНВЕНТАРЬ</b>\n\n"
            
            rods = []
            consumables = []
            for item in items:
                item_info = ITEM_CATALOG.get(item.item_type)
                if item_info:
                    if item.item_type.endswith("_rod"):
                        equipped = " ✅" if item.equipped else ""
                        rods.append(f"  {item_info.emoji} {item_info.name}{equipped}")
                    else:
                        consumables.append(f"  {item_info.emoji} {item_info.name} x{item.quantity}")
            
            if rods:
                text += "<b>🎣 Удочки:</b>\n" + "\n".join(rods) + "\n\n"
            if consumables:
                text += "<b>🧪 Расходники:</b>\n" + "\n".join(consumables) + "\n\n"
            
            text += f"💰 Баланс: {balance} монет"
        
        await callback.message.edit_text(text, reply_markup=get_shop_keyboard(user_id), parse_mode="HTML")
        await callback.answer()
    
    elif action == "buy":
        item_type = parts[3] if len(parts) > 3 else None
        if not item_type or item_type not in ITEM_CATALOG:
            return await callback.answer("Неизвестный предмет", show_alert=True)
        
        item_info = ITEM_CATALOG[item_type]
        
        if balance < item_info.price:
            return await callback.answer(
                f"Недостаточно монет! Нужно {item_info.price}, у тебя {balance}",
                show_alert=True
            )
        
        # Check if already owned (for non-stackable items)
        if not item_info.stackable:
            if await inventory_service.has_item(user_id, chat_id, item_type):
                return await callback.answer(
                    f"У тебя уже есть {item_info.emoji} {item_info.name}!",
                    show_alert=True
                )
        
        # Deduct money and add item
        await update_user_balance(user_id, chat_id, -item_info.price)
        result = await inventory_service.add_item(user_id, chat_id, item_type)
        
        # Auto-equip if it's a rod
        if item_type.endswith("_rod"):
            await inventory_service.equip_item(user_id, chat_id, item_type)
            await fishing_stats_service.update_equipped_rod(user_id, chat_id, item_type)
        
        new_balance = await get_user_balance(user_id, chat_id)
        
        await callback.message.edit_text(
            f"✅ Куплено {item_info.emoji} {item_info.name}!\n\n"
            f"💰 Баланс: {new_balance} монет",
            reply_markup=get_shop_keyboard(user_id),
            parse_mode="HTML"
        )
        await callback.answer(f"🎉 {item_info.name}!")
    
    elif action == "back":
        text = (
            "🏪 <b>МАГАЗИН</b>\n\n"
            "Покупай предметы за монеты!\n\n"
            "🎣 <b>Удочки</b> — улучшают шанс редкой рыбы\n"
            "🧪 <b>Расходники</b> — бонусы для игр\n\n"
            f"💰 Баланс: {balance} монет"
        )
        await callback.message.edit_text(text, reply_markup=get_shop_keyboard(user_id), parse_mode="HTML")
        await callback.answer()


# ============================================================================
# USE CONSUMABLE ITEMS
# ============================================================================

@router.message(Command("use"))
async def cmd_use(message: Message):
    """Use a consumable item."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply(
            "🧪 <b>Использование предметов</b>\n\n"
            "Команда: /use [предмет]\n\n"
            "Доступные предметы:\n"
            "  🥤 энергетик — сброс кулдауна рыбалки\n"
            "  🍀 талисман — +10% к следующей игре\n"
            "  🛡️ щит — защита от проигрыша\n\n"
            "Пример: /use энергетик",
            parse_mode="HTML"
        )
    
    item_name = parts[1].lower().strip()
    
    # Map Russian names to item types
    item_map = {
        "энергетик": ItemType.ENERGY_DRINK,
        "energy": ItemType.ENERGY_DRINK,
        "талисман": ItemType.LUCKY_CHARM,
        "luck": ItemType.LUCKY_CHARM,
        "щит": ItemType.SHIELD,
        "shield": ItemType.SHIELD,
    }
    
    item_type = item_map.get(item_name)
    if not item_type:
        return await message.reply("❌ Неизвестный предмет. Используй /use для списка.")
    
    # Check if user has the item
    if not await inventory_service.has_item(user_id, chat_id, item_type):
        item_info = ITEM_CATALOG[item_type]
        return await message.reply(
            f"❌ У тебя нет {item_info.emoji} {item_info.name}!\n"
            f"Купи в /shop"
        )
    
    # Use the item
    result = await inventory_service.remove_item(user_id, chat_id, item_type, 1)
    item_info = ITEM_CATALOG[item_type]
    
    if item_type == ItemType.ENERGY_DRINK:
        # Reset fishing cooldown
        fishing_game.reset_cooldown(user_id)
        await message.reply(
            f"🥤 Использован {item_info.name}!\n\n"
            f"⚡ Кулдаун рыбалки сброшен!\n"
            f"Используй /fish"
        )
    elif item_type == ItemType.LUCKY_CHARM:
        # TODO: Store luck bonus in user state
        await message.reply(
            f"🍀 Использован {item_info.name}!\n\n"
            f"✨ +10% к выигрышу в следующей игре!"
        )
    elif item_type == ItemType.SHIELD:
        # TODO: Store shield in user state
        await message.reply(
            f"🛡️ Использован {item_info.name}!\n\n"
            f"🛡️ Защита от проигрыша активирована!"
        )
    
    logger.info(f"User {user_id} used item {item_type}")
