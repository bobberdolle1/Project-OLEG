from datetime import datetime, timedelta
import pytz
import random
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from aiogram import Bot
from sqlalchemy import select, and_, delete, or_, func
from sqlalchemy.orm import joinedload

from app.config import settings
from app.services.ollama_client import summarize_chat, generate_creative
from app.database.session import get_session
from app.database.models import User, Wallet, GameStat, Auction, Bid, Quest, UserQuest, TeamWar, TeamWarParticipant, GlobalStats, GuildMember

_scheduler: AsyncIOScheduler | None = None


async def job_daily_summary(bot: Bot):
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(select(Chat))
        chats = result.scalars().all()

        for chat in chats:
            if chat.summary_topic_id:
                text = await summarize_chat(chat.id)
                await bot.send_message(
                    chat_id=chat.id,
                    message_thread_id=chat.summary_topic_id,
                    text=text,
                    disable_web_page_preview=True
                )
                await asyncio.sleep(1)

async def job_creative(bot: Bot):
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(select(Chat))
        chats = result.scalars().all()

        for chat in chats:
            if chat.creative_topic_id:
                text = await generate_creative(chat.id)
                await bot.send_message(
                    chat_id=chat.id,
                    message_thread_id=chat.creative_topic_id,
                    text=text,
                    disable_web_page_preview=True
                )
                await asyncio.sleep(1)


async def job_close_auctions(bot: Bot):
    """
    Closes expired auctions, transfers items and funds, and notifies participants.
    """
    async_session = get_session()
    async with async_session() as session:
        expired_auctions_res = await session.execute(
            select(Auction)
            .filter(
                Auction.ends_at <= datetime.utcnow(),
                Auction.status == "active"
            )
            .options(
                joinedload(Auction.seller),
                joinedload(Auction.current_highest_bid).joinedload(Bid.bidder)
            )
        )
        expired_auctions = expired_auctions_res.scalars().all()

        for auction in expired_auctions:
            if auction.current_highest_bid:
                # Auction has a winner
                winner_bid = auction.current_highest_bid
                winner_user = winner_bid.bidder
                seller_user = auction.seller

                # Transfer item from seller to winner
                if auction.item_type == "size_cm":
                    seller_game_stat_res = await session.execute(select(GameStat).filter_by(user_id=seller_user.id))
                    seller_game_stat = seller_game_stat_res.scalars().first()
                    seller_game_stat.size_cm -= auction.item_quantity

                    winner_game_stat_res = await session.execute(select(GameStat).filter_by(user_id=winner_user.id))
                    winner_game_stat = winner_game_stat_res.scalars().first()
                    winner_game_stat.size_cm += auction.item_quantity
                elif auction.item_type == "balance":
                    # This case is less likely for auctions but for completeness
                    pass
                
                # Transfer funds from winner to seller
                winner_wallet_res = await session.execute(select(Wallet).filter_by(user_id=winner_user.id))
                winner_wallet = winner_wallet_res.scalars().first()
                # Deduct bid amount from winner (already done when bid was placed)
                # Here we just ensure the seller gets the money
                
                seller_wallet_res = await session.execute(select(Wallet).filter_by(user_id=seller_user.id))
                seller_wallet = seller_wallet_res.scalars().first()
                seller_wallet.balance += winner_bid.amount

                auction.status = "completed"
                await bot.send_message(
                    chat_id=seller_user.tg_user_id,
                    text=f"Ваш аукцион ID:{auction.id} завершен! {winner_user.username} купил {auction.item_quantity} {auction.item_type} за {winner_bid.amount} монет."
                )
                await bot.send_message(
                    chat_id=winner_user.tg_user_id,
                    text=f"Вы выиграли аукцион ID:{auction.id} и получили {auction.item_quantity} {auction.item_type} за {winner_bid.amount} монет!"
                )
            else:
                # No bids, auction expired
                auction.status = "expired"
                await bot.send_message(
                    chat_id=auction.seller.tg_user_id,
                    text=f"Ваш аукцион ID:{auction.id} завершился без ставок и был отменен."
                )
            await session.commit()


async def job_assign_daily_quests(bot: Bot):
    """
    Assigns a random set of daily quests to all active users.
    """
    async_session = get_session()
    async with async_session() as session:
        # Get all available quests
        all_quests_res = await session.execute(select(Quest))
        all_quests = all_quests_res.scalars().all()

        if not all_quests:
            logger.warning("No quests found in the database to assign.")
            return

        # Get all active users
        active_users_res = await session.execute(select(User))
        active_users = active_users_res.scalars().all()

        if not active_users:
            logger.info("No active users to assign quests to.")
            return

        for user in active_users:
            # Clear previous day's quests
            await session.execute(
                delete(UserQuest).where(
                    and_(UserQuest.user_id == user.id, UserQuest.completed_at == None) # Only delete uncompleted quests from previous days
                )
            )

            # Select a random subset of quests to assign (e.g., 3 quests)
            quests_to_assign = random.sample(all_quests, min(3, len(all_quests)))

            for quest in quests_to_assign:
                user_quest = UserQuest(
                    user_id=user.id,
                    quest_id=quest.id,
                    assigned_at=datetime.utcnow(),
                    progress=0,
                    completed_at=None
                )
                session.add(user_quest)
            await session.commit()
            logger.info(f"Assigned {len(quests_to_assign)} quests to user {user.tg_user_id}")


async def job_update_team_wars(bot: Bot):
    """
    Manages the lifecycle of team wars: starting, ending, and determining winners.
    """
    async_session = get_session()
    async with async_session() as session:
        # 1. Activate declared wars
        declared_wars_res = await session.execute(
            select(TeamWar)
            .filter(
                TeamWar.start_time == None, # Not yet started
                TeamWar.status == "declared",
                TeamWar.created_at <= datetime.utcnow() - timedelta(minutes=5) # Allow some time for acceptance
            )
            .options(joinedload(TeamWar.declarer_guild), joinedload(TeamWar.defender_guild))
        )
        declared_wars = declared_wars_res.scalars().all()

        for war in declared_wars:
            # Check if defender accepted (start_time is set)
            if war.start_time: # War was accepted by defender
                war.status = "active"
                await session.commit()
                # Notify declarer guild leader
                declarer_leader_res = await session.execute(
                    select(User)
                    .join(GuildMember)
                    .filter(and_(GuildMember.guild_id == war.declarer_guild.id, GuildMember.role == "leader"))
                )
                declarer_leader = declarer_leader_res.scalars().first()
                if declarer_leader:
                    await bot.send_message(
                        chat_id=declarer_leader.tg_user_id,
                        text=f"Война ID:{war.id} между '{war.declarer_guild.name}' и '{war.defender_guild.name}' началась!"
                    )
                # Notify defender guild leader
                defender_leader_res = await session.execute(
                    select(User)
                    .join(GuildMember)
                    .filter(and_(GuildMember.guild_id == war.defender_guild.id, GuildMember.role == "leader"))
                )
                defender_leader = defender_leader_res.scalars().first()
                if defender_leader:
                    await bot.send_message(
                        chat_id=defender_leader.tg_user_id,
                        text=f"Война ID:{war.id} между '{war.declarer_guild.name}' и '{war.defender_guild.name}' началась!"
                    )
            else: # Defender did not accept within the grace period, cancel the war
                war.status = "cancelled"
                await session.commit()
                # Notify declarer guild leader
                declarer_leader_res = await session.execute(
                    select(User)
                    .join(GuildMember)
                    .filter(and_(GuildMember.guild_id == war.declarer_guild.id, GuildMember.role == "leader"))
                )
                declarer_leader = declarer_leader_res.scalars().first()
                if declarer_leader:
                    await bot.send_message(
                        chat_id=declarer_leader.tg_user_id,
                        text=f"Война ID:{war.id} против '{war.defender_guild.name}' была отменена, так как не была принята вовремя."
                    )
        
        # 2. End active wars
        active_wars_res = await session.execute(
            select(TeamWar)
            .filter(
                TeamWar.end_time <= datetime.utcnow(),
                TeamWar.status == "active"
            )
            .options(joinedload(TeamWar.declarer_guild), joinedload(TeamWar.defender_guild))
        )
        active_wars = active_wars_res.scalars().all()

        for war in active_wars:
            # Determine winner based on participant scores (or other criteria)
            declarer_guild_score = await session.execute(
                select(func.sum(TeamWarParticipant.score))
                .filter(and_(TeamWarParticipant.team_war_id == war.id, TeamWarParticipant.guild_id == war.declarer_guild_id))
            )
            declarer_guild_score = declarer_guild_score.scalar_one_or_none() or 0

            defender_guild_score = await session.execute(
                select(func.sum(TeamWarParticipant.score))
                .filter(and_(TeamWarParticipant.team_war_id == war.id, TeamWarParticipant.guild_id == war.defender_guild_id))
            )
            defender_guild_score = defender_guild_score.scalar_one_or_none() or 0

            if declarer_guild_score > defender_guild_score:
                war.winner_guild_id = war.declarer_guild_id
                winner_message = f"Гильдия '{war.declarer_guild.name}' победила!"
            elif defender_guild_score > declarer_guild_score:
                war.winner_guild_id = war.defender_guild_id
                winner_message = f"Гильдия '{war.defender_guild.name}' победила!"
            else:
                war.winner_guild_id = None
                winner_message = "Война закончилась ничьей!"
            
            war.status = "finished"
            await session.commit()

            # Notify both guilds
            message_text = f"Война ID:{war.id} между '{war.declarer_guild.name}' ({declarer_guild_score}) и '{war.defender_guild.name}' ({defender_guild_score}) завершена. {winner_message}"
            await bot.send_message(
                chat_id=war.declarer_guild.owner.tg_user_id,
                text=message_text
            )
            await bot.send_message(
                chat_id=war.defender_guild.owner.tg_user_id,
                text=message_text
            )


async def job_aggregate_daily_stats(bot: Bot):
    """
    Aggregates daily statistics from GameStat into GlobalStats.
    """
    async_session = get_session()
    async with async_session() as session:
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)

        # Get total stats from GameStat for today
        current_game_stats_res = await session.execute(
            select(
                func.sum(GameStat.pvp_wins).label("total_pvp_wins"),
                func.sum(GameStat.grow_count).label("total_grow_count"),
                func.sum(GameStat.casino_jackpots).label("total_casino_jackpots"),
                func.sum(GameStat.reputation).label("total_reputation")
            )
        )
        current_stats = current_game_stats_res.one()

        # Get yesterday's global stats
        yesterday_global_stats_res = await session.execute(
            select(GlobalStats)
            .filter(GlobalStats.date == yesterday, GlobalStats.period_type == "daily")
        )
        yesterday_global_stats = yesterday_global_stats_res.scalars().first()

        # Calculate deltas
        pvp_wins_delta = current_stats.total_pvp_wins - (yesterday_global_stats.total_pvp_wins if yesterday_global_stats else 0)
        grow_count_delta = current_stats.total_grow_count - (yesterday_global_stats.total_grow_count if yesterday_global_stats else 0)
        casino_jackpots_delta = current_stats.total_casino_jackpots - (yesterday_global_stats.total_casino_jackpots if yesterday_global_stats else 0)
        reputation_delta = current_stats.total_reputation - (yesterday_global_stats.total_reputation if yesterday_global_stats else 0)

        # Create new GlobalStats entry
        new_global_stats = GlobalStats(
            date=today,
            period_type="daily",
            total_pvp_wins=current_stats.total_pvp_wins,
            pvp_wins_delta=pvp_wins_delta,
            total_grow_count=current_stats.total_grow_count,
            grow_count_delta=grow_count_delta,
            total_casino_jackpots=current_stats.total_casino_jackpots,
            casino_jackpots_delta=casino_jackpots_delta,
            total_reputation=current_stats.total_reputation,
            reputation_delta=reputation_delta
        )
        session.add(new_global_stats)
        await session.commit()
        logger.info(f"Daily statistics aggregated for {today}")


async def job_sync_chat_members(bot: Bot):
    """
    Periodically checks chat members and updates their status in the database.
    """
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(select(Chat))
        chats = result.scalars().all()

        for chat in chats:
            active_users_res = await session.execute(
                select(User).filter(User.status == "active")
            )
            active_users = active_users_res.scalars().all()

            for user in active_users:
                try:
                    chat_member = await bot.get_chat_member(
                        chat_id=chat.id,
                        user_id=user.tg_user_id
                    )
                    if chat_member.status in ["left", "kicked"]:
                        user.status = "left"
                        logger.info(f"User {user.tg_user_id} has left the chat {chat.id}. Updating status.")
                except Exception:
                    user.status = "left" # User not found in chat
                    logger.info(f"User {user.tg_user_id} not found in chat {chat.id}. Updating status.")
                
                await asyncio.sleep(0.1) # Rate limit
            
            await session.commit()




async def setup_scheduler(bot: Bot):
    global _scheduler
    if _scheduler:
        return
    tz = pytz.timezone(settings.timezone)
    _scheduler = AsyncIOScheduler(timezone=tz)
    _scheduler.add_job(job_daily_summary, CronTrigger(hour=8, minute=0), args=[bot], id="daily_summary")
    _scheduler.add_job(job_creative, CronTrigger(hour=20, minute=0), args=[bot], id="creative")
    _scheduler.add_job(job_close_auctions, CronTrigger(minute="*/1"), args=[bot], id="close_auctions")
    _scheduler.add_job(job_assign_daily_quests, CronTrigger(hour=0, minute=0), args=[bot], id="assign_daily_quests")
    _scheduler.add_job(job_update_team_wars, CronTrigger(minute="*/1"), args=[bot], id="update_team_wars")
    _scheduler.add_job(job_aggregate_daily_stats, CronTrigger(hour=23, minute=59), args=[bot], id="aggregate_daily_stats")
    _scheduler.add_job(job_sync_chat_members, CronTrigger(hour=3, minute=0), args=[bot], id="sync_chat_members")
    _scheduler.start()