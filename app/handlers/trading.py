import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.database.models import User, Wallet, GameStat, TradeOffer
from app.handlers.games import ensure_user # Reusing ensure_user from games handler

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("sell"))
async def cmd_sell(msg: Message):
    """
    Handles the /sell command to create a trade offer.
    Usage: /sell <item_type> <quantity> <price>
    Example: /sell size_cm 10 100 (sells 10 cm for 100 coins)
    """
    async_session = get_session()
    seller_user = await ensure_user(msg.from_user)

    parts = (msg.text or "").split()
    if len(parts) != 4:
        return await msg.reply("Использование: /sell <тип_предмета> <количество> <цена>")

    item_type = parts[1]
    try:
        quantity = int(parts[2])
        price = int(parts[3])
    except ValueError:
        return await msg.reply("Количество и цена должны быть числами.")

    if quantity <= 0 or price <= 0:
        return await msg.reply("Количество и цена должны быть положительными числами.")

    async with async_session() as session:
        # Check if seller has the item
        if item_type == "size_cm":
            game_stat_res = await session.execute(select(GameStat).filter_by(user_id=seller_user.id))
            game_stat = game_stat_res.scalars().first()
            if not game_stat or game_stat.size_cm < quantity:
                return await msg.reply(f"У вас недостаточно {item_type}.")
        elif item_type == "balance": # Selling coins is also possible
            wallet_res = await session.execute(select(Wallet).filter_by(user_id=seller_user.id))
            wallet = wallet_res.scalars().first()
            if not wallet or wallet.balance < quantity:
                return await msg.reply(f"У вас недостаточно {item_type}.")
        else:
            return await msg.reply(f"Неизвестный тип предмета: {item_type}.")
        
        # Create trade offer
        trade_offer = TradeOffer(
            seller_user_id=seller_user.id,
            item_type=item_type,
            item_quantity=quantity,
            price=price,
            status="active"
        )
        session.add(trade_offer)
        await session.commit()
        await msg.reply(
            f"Выставили на продажу: {quantity} {item_type} за {price} монет. (ID: {trade_offer.id})"
        )


@router.message(Command("trades"))
async def cmd_trades(msg: Message):
    """
    Handles the /trades command to list all active trade offers.
    """
    async_session = get_session()
    async with async_session() as session:
        active_trades_res = await session.execute(
            select(TradeOffer).filter_by(status="active").limit(10)
        )
        active_trades = active_trades_res.scalars().all()

        if not active_trades:
            return await msg.reply("Активных предложений на продажу нет.")

        trade_list = ["Активные предложения:"]
        for trade in active_trades:
            seller_user_res = await session.execute(select(User).filter_by(id=trade.seller_user_id))
            seller_user = seller_user_res.scalars().first()
            seller_name = seller_user.username or str(seller_user.tg_user_id)
            trade_list.append(
                f"ID: {trade.id} | Продавец: {seller_name} | "
                f"Предмет: {trade.item_quantity} {trade.item_type} | Цена: {trade.price}"
            )
        await msg.reply("\n".join(trade_list))


@router.message(Command("buy"))
async def cmd_buy(msg: Message):
    """
    Handles the /buy command to purchase a trade offer.
    Usage: /buy <trade_id>
    """
    async_session = get_session()
    buyer_user = await ensure_user(msg.from_user)

    parts = (msg.text or "").split()
    if len(parts) != 2:
        return await msg.reply("Использование: /buy <ID_предложения>")
    
    try:
        trade_id = int(parts[1])
    except ValueError:
        return await msg.reply("ID предложения должен быть числом.")

    async with async_session() as session:
        trade_offer_res = await session.execute(select(TradeOffer).filter_by(id=trade_id, status="active"))
        trade_offer = trade_offer_res.scalars().first()

        if not trade_offer:
            return await msg.reply("Предложение не найдено или уже неактивно.")
        
        if trade_offer.seller_user_id == buyer_user.id:
            return await msg.reply("Нельзя купить собственное предложение.")

        # Load buyer's wallet
        buyer_wallet_res = await session.execute(select(Wallet).filter_by(user_id=buyer_user.id))
        buyer_wallet = buyer_wallet_res.scalars().first()
        if not buyer_wallet or buyer_wallet.balance < trade_offer.price:
            return await msg.reply("Недостаточно средств для покупки.")
        
        # Load seller's wallet
        seller_wallet_res = await session.execute(select(Wallet).filter_by(user_id=trade_offer.seller_user_id))
        seller_wallet = seller_wallet_res.scalars().first()
        if not seller_wallet: # This should not happen if ensure_user is used correctly for seller
            return await msg.reply("Ошибка продавца: кошелек не найден.")
        
        # Perform transaction
        buyer_wallet.balance -= trade_offer.price
        seller_wallet.balance += trade_offer.price
        
        # Transfer item
        if trade_offer.item_type == "size_cm":
            buyer_game_stat_res = await session.execute(select(GameStat).filter_by(user_id=buyer_user.id))
            buyer_game_stat = buyer_game_stat_res.scalars().first()
            if not buyer_game_stat:
                return await msg.reply("Ошибка покупателя: GameStat не найден.")
            buyer_game_stat.size_cm += trade_offer.item_quantity

            seller_game_stat_res = await session.execute(select(GameStat).filter_by(user_id=trade_offer.seller_user_id))
            seller_game_stat = seller_game_stat_res.scalars().first()
            if not seller_game_stat or seller_game_stat.size_cm < trade_offer.item_quantity:
                # This should ideally be checked at sell time, but good to re-verify
                return await msg.reply("У продавца недостаточно предмета для завершения сделки.")
            seller_game_stat.size_cm -= trade_offer.item_quantity
        elif trade_offer.item_type == "balance":
            # This is handled by wallet transfer already
            pass
        else:
            return await msg.reply("Неизвестный тип предмета для передачи.")
        
        trade_offer.status = "completed"
        await session.commit()
        await msg.reply(f"Вы успешно купили {trade_offer.item_quantity} {trade_offer.item_type} за {trade_offer.price} монет!")


@router.message(Command("cancel"))
async def cmd_cancel(msg: Message):
    """
    Handles the /cancel command to cancel an active trade offer.
    Usage: /cancel <trade_id>
    """
    async_session = get_session()
    user = await ensure_user(msg.from_user)

    parts = (msg.text or "").split()
    if len(parts) != 2:
        return await msg.reply("Использование: /cancel <ID_предложения>")
    
    try:
        trade_id = int(parts[1])
    except ValueError:
        return await msg.reply("ID предложения должен быть числом.")

    async with async_session() as session:
        trade_offer_res = await session.execute(
            select(TradeOffer)
            .filter_by(id=trade_id, seller_user_id=user.id, status="active")
        )
        trade_offer = trade_offer_res.scalars().first()

        if not trade_offer:
            return await msg.reply("Предложение не найдено или вы не являетесь его продавцом, или оно уже неактивно.")
        
        trade_offer.status = "cancelled"
        await session.commit()
        await msg.reply(f"Предложение {trade_id} отменено.")
