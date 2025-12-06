"""Tournament command handlers.

This module provides command handlers for tournament-related functionality.

**Feature: fortress-update**
**Validates: Requirements 10.5**
"""

import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from app.services.tournaments import (
    tournament_service,
    TournamentType,
    TournamentDiscipline
)

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("tournament"))
async def cmd_tournament(msg: Message):
    """
    Command /tournament - Show current tournament standings.
    
    Displays standings for all active tournaments (daily, weekly, monthly).
    
    **Validates: Requirements 10.5**
    """
    user_id = msg.from_user.id
    
    try:
        # Get all active tournaments
        active_tournaments = await tournament_service.get_all_active_tournaments()
        
        if not active_tournaments:
            await msg.reply(
                "🏆 <b>Турниры</b>\n\n"
                "Сейчас нет активных турниров.\n"
                "Новый дневной турнир начнётся в 00:00 UTC.",
                parse_mode="HTML"
            )
            return
        
        # Build response message
        lines = ["🏆 <b>Активные турниры</b>\n"]
        
        for tournament_info in active_tournaments:
            lines.append(tournament_service.format_tournament_info(tournament_info))
            lines.append("")
        
        lines.append("━━━━━━━━━━━━━━━")
        lines.append("📋 /grow · /pvp · /roulette · /profile")
        
        await msg.reply("\n".join(lines), parse_mode="HTML")
        
        logger.info(f"Tournament standings requested by user {user_id}")
        
    except Exception as e:
        logger.error(f"Error getting tournament standings: {e}")
        await msg.reply(
            "❌ Ошибка при получении данных турнира. Попробуй позже.",
            parse_mode="HTML"
        )


@router.message(Command("tournament_daily"))
async def cmd_tournament_daily(msg: Message):
    """
    Command /tournament_daily - Show daily tournament standings.
    """
    await _show_tournament_standings(msg, TournamentType.DAILY, "🌅 Дневной турнир")


@router.message(Command("tournament_weekly"))
async def cmd_tournament_weekly(msg: Message):
    """
    Command /tournament_weekly - Show weekly tournament standings.
    """
    await _show_tournament_standings(msg, TournamentType.WEEKLY, "📅 Недельный турнир")


@router.message(Command("tournament_monthly"))
async def cmd_tournament_monthly(msg: Message):
    """
    Command /tournament_monthly - Show Grand Cup (monthly) standings.
    """
    await _show_tournament_standings(msg, TournamentType.GRAND_CUP, "🏆 Гранд Кубок")


async def _show_tournament_standings(
    msg: Message,
    tournament_type: TournamentType,
    title: str
):
    """
    Helper to show standings for a specific tournament type.
    """
    user_id = msg.from_user.id
    
    try:
        tournament_info = await tournament_service.get_current_tournament(tournament_type)
        
        if tournament_info is None:
            await msg.reply(
                f"{title}\n\n"
                f"Нет активного турнира этого типа.\n"
                f"Новый турнир начнётся автоматически.",
                parse_mode="HTML"
            )
            return
        
        # Build response
        lines = [f"<b>{title}</b>\n"]
        lines.append(f"Статус: {'🟢 Активен' if tournament_info.status == 'active' else '🔴 Завершён'}")
        lines.append(f"Окончание: {tournament_info.end_at.strftime('%d.%m.%Y %H:%M')} UTC\n")
        
        discipline_names = {
            TournamentDiscipline.GROW: "📏 Рост",
            TournamentDiscipline.PVP: "⚔️ PvP",
            TournamentDiscipline.ROULETTE: "🔫 Рулетка"
        }
        
        for discipline, standings in tournament_info.standings.items():
            lines.append(f"<b>{discipline_names.get(discipline, discipline.value)}:</b>")
            if standings:
                for standing in standings[:5]:  # Top 5
                    rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉"}.get(standing.rank, f"{standing.rank}.")
                    name = standing.username or f"User {standing.user_id}"
                    lines.append(f"  {rank_emoji} {name}: {standing.score}")
            else:
                lines.append("  Нет участников")
            lines.append("")
        
        lines.append("━━━━━━━━━━━━━━━")
        lines.append("📋 /tournament · /grow · /pvp · /roulette")
        
        await msg.reply("\n".join(lines), parse_mode="HTML")
        
        logger.info(f"{tournament_type.value} standings requested by user {user_id}")
        
    except Exception as e:
        logger.error(f"Error getting {tournament_type.value} standings: {e}")
        await msg.reply(
            "❌ Ошибка при получении данных турнира. Попробуй позже.",
            parse_mode="HTML"
        )
