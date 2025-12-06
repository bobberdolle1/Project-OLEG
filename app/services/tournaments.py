"""Tournament Service - Periodic Competitions System.

This module provides the Tournament system for tracking periodic competitions
across different disciplines (grow, pvp, roulette).

**Feature: fortress-update**
**Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6**
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Tournament, TournamentScore, UserAchievement, Achievement, User
from app.database.session import get_session
from app.utils import utc_now

logger = logging.getLogger(__name__)


# ============================================================================
# Tournament Type and Discipline Enums
# ============================================================================

class TournamentType(Enum):
    """
    Types of tournaments based on duration.
    
    **Validates: Requirements 10.1, 10.2, 10.3**
    """
    DAILY = "daily"       # Resets at 00:00 UTC (Requirement 10.1)
    WEEKLY = "weekly"     # Resets on Monday 00:00 UTC (Requirement 10.2)
    GRAND_CUP = "grand_cup"  # Monthly tournament (Requirement 10.3)


class TournamentDiscipline(Enum):
    """
    Disciplines tracked in tournaments.
    
    **Validates: Requirements 10.1**
    """
    GROW = "grow"         # /grow gains
    PVP = "pvp"           # /pvp wins
    ROULETTE = "roulette" # /roulette survival streaks


# ============================================================================
# Constants
# ============================================================================

# Number of winners to announce per discipline (Requirement 10.4)
TOP_WINNERS_COUNT = 3

# Achievement codes for tournament wins
ACHIEVEMENT_CODES = {
    TournamentType.DAILY: "daily_champion",
    TournamentType.WEEKLY: "weekly_champion",
    TournamentType.GRAND_CUP: "grand_cup_champion",
}


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class TournamentStanding:
    """
    A single standing entry in tournament rankings.
    
    Attributes:
        user_id: Telegram user ID
        username: Username for display
        score: Current score in the discipline
        rank: Position in rankings (1-based)
    """
    user_id: int
    username: Optional[str]
    score: int
    rank: int


@dataclass
class TournamentInfo:
    """
    Information about a tournament.
    
    Attributes:
        id: Tournament database ID
        type: Tournament type (daily, weekly, grand_cup)
        start_at: Tournament start time
        end_at: Tournament end time
        status: Current status (active, completed)
        standings: Dict mapping discipline to list of standings
    """
    id: int
    type: TournamentType
    start_at: datetime
    end_at: datetime
    status: str
    standings: Dict[TournamentDiscipline, List[TournamentStanding]] = field(default_factory=dict)


@dataclass
class TournamentWinner:
    """
    A tournament winner entry.
    
    Attributes:
        user_id: Telegram user ID
        username: Username for display
        discipline: The discipline won
        score: Final score
        rank: Final rank (1, 2, or 3)
        tournament_type: Type of tournament won
    """
    user_id: int
    username: Optional[str]
    discipline: TournamentDiscipline
    score: int
    rank: int
    tournament_type: TournamentType


# ============================================================================
# Tournament Service
# ============================================================================

class TournamentService:
    """
    Service for managing tournaments and tracking scores.
    
    Provides methods for:
    - Starting and ending tournaments
    - Updating scores for disciplines
    - Getting current standings
    - Recording achievements for winners
    
    **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5, 10.6**
    """
    
    def __init__(self):
        """Initialize TournamentService."""
        pass
    
    # =========================================================================
    # Tournament Lifecycle Methods
    # =========================================================================
    
    async def start_tournament(
        self,
        tournament_type: TournamentType,
        session: Optional[AsyncSession] = None
    ) -> TournamentInfo:
        """
        Start a new tournament of the specified type.
        
        Calculates appropriate start and end times based on tournament type.
        
        Args:
            tournament_type: Type of tournament to start
            session: Optional database session
            
        Returns:
            TournamentInfo for the new tournament
            
        **Validates: Requirements 10.1, 10.2, 10.3**
        """
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            now = utc_now()
            
            # Calculate start and end times based on tournament type
            if tournament_type == TournamentType.DAILY:
                # Daily: starts now, ends at next 00:00 UTC
                start_at = now
                end_at = (now + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            elif tournament_type == TournamentType.WEEKLY:
                # Weekly: starts now, ends next Monday 00:00 UTC
                start_at = now
                days_until_monday = (7 - now.weekday()) % 7
                if days_until_monday == 0:
                    days_until_monday = 7  # If today is Monday, end next Monday
                end_at = (now + timedelta(days=days_until_monday)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            else:  # GRAND_CUP (monthly)
                # Monthly: starts now, ends on 1st of next month 00:00 UTC
                start_at = now
                if now.month == 12:
                    end_at = now.replace(
                        year=now.year + 1, month=1, day=1,
                        hour=0, minute=0, second=0, microsecond=0
                    )
                else:
                    end_at = now.replace(
                        month=now.month + 1, day=1,
                        hour=0, minute=0, second=0, microsecond=0
                    )
            
            # Create tournament record
            tournament = Tournament(
                type=tournament_type.value,
                start_at=start_at,
                end_at=end_at,
                status='active'
            )
            session.add(tournament)
            await session.commit()
            await session.refresh(tournament)
            
            logger.info(
                f"Started {tournament_type.value} tournament (ID: {tournament.id}), "
                f"ends at {end_at}"
            )
            
            return TournamentInfo(
                id=tournament.id,
                type=tournament_type,
                start_at=start_at,
                end_at=end_at,
                status='active',
                standings={}
            )
            
        finally:
            if close_session:
                await session.close()
    
    async def end_tournament(
        self,
        tournament_id: int,
        session: Optional[AsyncSession] = None
    ) -> List[TournamentWinner]:
        """
        End a tournament and determine winners.
        
        Returns top 3 winners for each discipline and records achievements.
        
        Args:
            tournament_id: ID of tournament to end
            session: Optional database session
            
        Returns:
            List of TournamentWinner for all disciplines (top 3 each)
            
        **Validates: Requirements 10.4, 10.6**
        """
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            # Get tournament
            result = await session.execute(
                select(Tournament).filter_by(id=tournament_id)
            )
            tournament = result.scalar_one_or_none()
            
            if tournament is None:
                logger.warning(f"Tournament {tournament_id} not found")
                return []
            
            if tournament.status == 'completed':
                logger.warning(f"Tournament {tournament_id} already completed")
                return []
            
            tournament_type = TournamentType(tournament.type)
            winners: List[TournamentWinner] = []
            
            # Get top 3 for each discipline
            for discipline in TournamentDiscipline:
                standings = await self._get_discipline_standings(
                    tournament_id, discipline, limit=TOP_WINNERS_COUNT, session=session
                )
                
                for standing in standings:
                    winner = TournamentWinner(
                        user_id=standing.user_id,
                        username=standing.username,
                        discipline=discipline,
                        score=standing.score,
                        rank=standing.rank,
                        tournament_type=tournament_type
                    )
                    winners.append(winner)
                    
                    # Record achievement for 1st place winners (Requirement 10.6)
                    if standing.rank == 1:
                        await self._record_achievement(
                            standing.user_id, tournament_type, discipline, session
                        )
            
            # Mark tournament as completed
            tournament.status = 'completed'
            await session.commit()
            
            logger.info(
                f"Ended {tournament_type.value} tournament (ID: {tournament_id}), "
                f"{len(winners)} winners determined"
            )
            
            return winners
            
        finally:
            if close_session:
                await session.close()
    
    # =========================================================================
    # Score Management Methods
    # =========================================================================
    
    async def update_score(
        self,
        user_id: int,
        discipline: TournamentDiscipline,
        delta: int,
        username: Optional[str] = None,
        session: Optional[AsyncSession] = None
    ) -> int:
        """
        Update a user's score in the current active tournaments.
        
        Updates score in all active tournaments (daily, weekly, monthly).
        
        Args:
            user_id: Telegram user ID
            discipline: The discipline to update
            delta: Amount to add to score (can be negative)
            username: Optional username for display
            session: Optional database session
            
        Returns:
            New total score across all active tournaments
            
        **Validates: Requirements 10.1**
        """
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            now = utc_now()
            total_score = 0
            
            # Get all active tournaments
            result = await session.execute(
                select(Tournament).filter(
                    Tournament.status == 'active',
                    Tournament.start_at <= now,
                    Tournament.end_at > now
                )
            )
            active_tournaments = result.scalars().all()
            
            for tournament in active_tournaments:
                # Get or create score record
                score_result = await session.execute(
                    select(TournamentScore).filter_by(
                        tournament_id=tournament.id,
                        user_id=user_id,
                        discipline=discipline.value
                    )
                )
                score_record = score_result.scalar_one_or_none()
                
                if score_record is None:
                    score_record = TournamentScore(
                        tournament_id=tournament.id,
                        user_id=user_id,
                        discipline=discipline.value,
                        score=0
                    )
                    session.add(score_record)
                
                # Update score
                score_record.score += delta
                total_score += score_record.score
            
            await session.commit()
            
            logger.debug(
                f"Updated tournament score: user={user_id}, "
                f"discipline={discipline.value}, delta={delta}"
            )
            
            return total_score
            
        finally:
            if close_session:
                await session.close()
    
    # =========================================================================
    # Standings Methods
    # =========================================================================
    
    async def get_standings(
        self,
        tournament_id: int,
        discipline: TournamentDiscipline,
        limit: int = 10,
        session: Optional[AsyncSession] = None
    ) -> List[TournamentStanding]:
        """
        Get current standings for a tournament discipline.
        
        Args:
            tournament_id: Tournament ID
            discipline: Discipline to get standings for
            limit: Maximum number of standings to return
            session: Optional database session
            
        Returns:
            List of TournamentStanding ordered by score descending
            
        **Validates: Requirements 10.5**
        """
        return await self._get_discipline_standings(
            tournament_id, discipline, limit, session
        )
    
    async def get_current_tournament(
        self,
        tournament_type: TournamentType,
        session: Optional[AsyncSession] = None
    ) -> Optional[TournamentInfo]:
        """
        Get the current active tournament of a specific type.
        
        Args:
            tournament_type: Type of tournament to find
            session: Optional database session
            
        Returns:
            TournamentInfo if found, None otherwise
        """
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            now = utc_now()
            
            result = await session.execute(
                select(Tournament).filter(
                    Tournament.type == tournament_type.value,
                    Tournament.status == 'active',
                    Tournament.start_at <= now,
                    Tournament.end_at > now
                ).order_by(Tournament.start_at.desc()).limit(1)
            )
            tournament = result.scalar_one_or_none()
            
            if tournament is None:
                return None
            
            # Get standings for all disciplines
            standings = {}
            for discipline in TournamentDiscipline:
                standings[discipline] = await self._get_discipline_standings(
                    tournament.id, discipline, limit=10, session=session
                )
            
            return TournamentInfo(
                id=tournament.id,
                type=tournament_type,
                start_at=tournament.start_at,
                end_at=tournament.end_at,
                status=tournament.status,
                standings=standings
            )
            
        finally:
            if close_session:
                await session.close()
    
    async def get_all_active_tournaments(
        self,
        session: Optional[AsyncSession] = None
    ) -> List[TournamentInfo]:
        """
        Get all currently active tournaments.
        
        Args:
            session: Optional database session
            
        Returns:
            List of TournamentInfo for all active tournaments
        """
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            now = utc_now()
            
            result = await session.execute(
                select(Tournament).filter(
                    Tournament.status == 'active',
                    Tournament.start_at <= now,
                    Tournament.end_at > now
                )
            )
            tournaments = result.scalars().all()
            
            infos = []
            for tournament in tournaments:
                tournament_type = TournamentType(tournament.type)
                
                # Get standings for all disciplines
                standings = {}
                for discipline in TournamentDiscipline:
                    standings[discipline] = await self._get_discipline_standings(
                        tournament.id, discipline, limit=10, session=session
                    )
                
                infos.append(TournamentInfo(
                    id=tournament.id,
                    type=tournament_type,
                    start_at=tournament.start_at,
                    end_at=tournament.end_at,
                    status=tournament.status,
                    standings=standings
                ))
            
            return infos
            
        finally:
            if close_session:
                await session.close()
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    async def _get_discipline_standings(
        self,
        tournament_id: int,
        discipline: TournamentDiscipline,
        limit: int,
        session: Optional[AsyncSession] = None
    ) -> List[TournamentStanding]:
        """Get standings for a specific discipline."""
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            # Get scores ordered by score descending
            result = await session.execute(
                select(TournamentScore)
                .filter_by(
                    tournament_id=tournament_id,
                    discipline=discipline.value
                )
                .order_by(TournamentScore.score.desc())
                .limit(limit)
            )
            scores = result.scalars().all()
            
            standings = []
            for rank, score_record in enumerate(scores, start=1):
                # Try to get username from User table
                username = None
                user_result = await session.execute(
                    select(User).filter_by(tg_user_id=score_record.user_id)
                )
                user = user_result.scalar_one_or_none()
                if user:
                    username = user.username or user.first_name
                
                standings.append(TournamentStanding(
                    user_id=score_record.user_id,
                    username=username,
                    score=score_record.score,
                    rank=rank
                ))
            
            return standings
            
        finally:
            if close_session:
                await session.close()
    
    async def _record_achievement(
        self,
        user_id: int,
        tournament_type: TournamentType,
        discipline: TournamentDiscipline,
        session: AsyncSession
    ) -> bool:
        """
        Record an achievement for a tournament winner.
        
        **Validates: Requirements 10.6**
        """
        try:
            # Get user from database
            user_result = await session.execute(
                select(User).filter_by(tg_user_id=user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if user is None:
                logger.warning(f"User {user_id} not found for achievement recording")
                return False
            
            # Get or create achievement
            achievement_code = f"{ACHIEVEMENT_CODES[tournament_type]}_{discipline.value}"
            achievement_result = await session.execute(
                select(Achievement).filter_by(code=achievement_code)
            )
            achievement = achievement_result.scalar_one_or_none()
            
            if achievement is None:
                # Create the achievement if it doesn't exist
                achievement = Achievement(
                    code=achievement_code,
                    name=f"{tournament_type.value.title()} {discipline.value.title()} Champion",
                    description=f"Won 1st place in {tournament_type.value} {discipline.value} tournament"
                )
                session.add(achievement)
                await session.flush()
            
            # Check if user already has this achievement
            existing_result = await session.execute(
                select(UserAchievement).filter_by(
                    user_id=user.id,
                    achievement_id=achievement.id
                )
            )
            existing = existing_result.scalar_one_or_none()
            
            if existing is None:
                # Award achievement
                user_achievement = UserAchievement(
                    user_id=user.id,
                    achievement_id=achievement.id
                )
                session.add(user_achievement)
                
                logger.info(
                    f"Recorded achievement {achievement_code} for user {user_id}"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to record achievement: {e}")
            return False
    
    # =========================================================================
    # Formatting Methods
    # =========================================================================
    
    def format_standings(
        self,
        standings: List[TournamentStanding],
        discipline: TournamentDiscipline
    ) -> str:
        """
        Format standings for display.
        
        Args:
            standings: List of standings to format
            discipline: The discipline being displayed
            
        Returns:
            Formatted string for display
        """
        if not standings:
            return f"Нет участников в {discipline.value}"
        
        # Emoji for ranks
        rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉"}
        
        lines = []
        for standing in standings:
            emoji = rank_emoji.get(standing.rank, f"{standing.rank}.")
            name = standing.username or f"User {standing.user_id}"
            lines.append(f"{emoji} {name}: {standing.score}")
        
        return "\n".join(lines)
    
    def format_tournament_info(self, info: TournamentInfo) -> str:
        """
        Format tournament info for display.
        
        Args:
            info: Tournament info to format
            
        Returns:
            Formatted string for display
        """
        type_names = {
            TournamentType.DAILY: "🌅 Дневной турнир",
            TournamentType.WEEKLY: "📅 Недельный турнир",
            TournamentType.GRAND_CUP: "🏆 Гранд Кубок"
        }
        
        discipline_names = {
            TournamentDiscipline.GROW: "📏 Рост",
            TournamentDiscipline.PVP: "⚔️ PvP",
            TournamentDiscipline.ROULETTE: "🔫 Рулетка"
        }
        
        lines = [
            f"{type_names.get(info.type, info.type.value)}",
            f"Статус: {'🟢 Активен' if info.status == 'active' else '🔴 Завершён'}",
            f"Окончание: {info.end_at.strftime('%d.%m.%Y %H:%M')} UTC",
            ""
        ]
        
        for discipline, standings in info.standings.items():
            lines.append(f"{discipline_names.get(discipline, discipline.value)}:")
            if standings:
                lines.append(self.format_standings(standings[:3], discipline))
            else:
                lines.append("  Нет участников")
            lines.append("")
        
        return "\n".join(lines)


# Global service instance
tournament_service = TournamentService()
