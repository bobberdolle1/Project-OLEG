"""League Service - ELO Rating System.

This module provides the League system for ranking players based on ELO ratings.

**Feature: fortress-update**
**Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.6, 11.7**
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import UserElo, GameStat
from app.database.session import get_session
from app.utils import utc_now

logger = logging.getLogger(__name__)


# ============================================================================
# League Definitions
# ============================================================================

class League(Enum):
    """
    League tiers with their emoji, min ELO, and max ELO thresholds.
    
    **Validates: Requirements 11.1, 11.2, 11.3, 11.4**
    """
    SCRAP = ("🥉", 0, 1199)       # Initial league (Requirement 11.1)
    SILICON = ("🥈", 1200, 1499)  # Promotion at 1200 (Requirement 11.2)
    QUANTUM = ("🥇", 1500, 1999)  # Promotion at 1500 (Requirement 11.3)
    ELITE = ("💎", 2000, float('inf'))  # Top tier or top 10 (Requirement 11.4)
    
    def __init__(self, emoji: str, min_elo: int, max_elo: float):
        self.emoji = emoji
        self.min_elo = min_elo
        self.max_elo = max_elo
    
    @property
    def display_name(self) -> str:
        """Get display name with emoji."""
        names = {
            "SCRAP": "Scrap League",
            "SILICON": "Silicon League", 
            "QUANTUM": "Quantum League",
            "ELITE": "Oleg's Elite"
        }
        return f"{self.emoji} {names.get(self.name, self.name)}"


# ============================================================================
# Constants
# ============================================================================

# Initial ELO for new players (Requirement 11.1)
INITIAL_ELO = 1000

# K-factor for ELO calculation (Requirement 11.6)
K_FACTOR = 32

# League thresholds
SCRAP_MAX = 1199
SILICON_MIN = 1200
SILICON_MAX = 1499
QUANTUM_MIN = 1500
QUANTUM_MAX = 1999
ELITE_MIN = 2000


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class LeagueStatus:
    """
    Current league status for a user.
    
    Attributes:
        user_id: Telegram user ID
        league: Current league tier
        elo: Current ELO rating
        progress_to_next: Progress to next league (0.0-1.0)
        is_top_10: Whether user is in top 10 globally
        season_wins: Number of season wins
    """
    user_id: int
    league: League
    elo: int
    progress_to_next: float
    is_top_10: bool = False
    season_wins: int = 0


@dataclass 
class EloChange:
    """
    Result of an ELO calculation.
    
    Attributes:
        winner_new_elo: Winner's new ELO
        loser_new_elo: Loser's new ELO
        winner_change: Change in winner's ELO
        loser_change: Change in loser's ELO
    """
    winner_new_elo: int
    loser_new_elo: int
    winner_change: int
    loser_change: int


# ============================================================================
# League Service
# ============================================================================

class LeagueService:
    """
    Service for managing user ELO ratings and league standings.
    
    Provides methods for:
    - Getting user league status
    - Updating ELO after matches
    - Calculating league from ELO
    - Managing season rewards
    
    **Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.6, 11.7**
    """
    
    def __init__(self):
        """Initialize LeagueService."""
        # In-memory cache for ELO ratings
        self._cache: Dict[int, LeagueStatus] = {}
    
    # =========================================================================
    # Core League Methods
    # =========================================================================
    
    def get_league_for_elo(self, elo: int, is_top_10: bool = False) -> League:
        """
        Determine league based on ELO rating.
        
        Args:
            elo: Current ELO rating
            is_top_10: Whether user is in top 10 globally
            
        Returns:
            League enum value
            
        **Validates: Requirements 11.1, 11.2, 11.3, 11.4**
        """
        # Top 10 players are always Elite (Requirement 11.4)
        if is_top_10:
            return League.ELITE
        
        # Determine league by ELO thresholds
        if elo >= ELITE_MIN:
            return League.ELITE
        elif elo >= QUANTUM_MIN:
            return League.QUANTUM
        elif elo >= SILICON_MIN:
            return League.SILICON
        else:
            return League.SCRAP
    
    def calculate_progress_to_next(self, elo: int, current_league: League) -> float:
        """
        Calculate progress to next league tier.
        
        Args:
            elo: Current ELO rating
            current_league: Current league tier
            
        Returns:
            Progress as float from 0.0 to 1.0
        """
        if current_league == League.ELITE:
            # Already at top, no progress needed
            return 1.0
        
        # Get thresholds for current league
        if current_league == League.SCRAP:
            min_elo = 0
            next_threshold = SILICON_MIN
        elif current_league == League.SILICON:
            min_elo = SILICON_MIN
            next_threshold = QUANTUM_MIN
        elif current_league == League.QUANTUM:
            min_elo = QUANTUM_MIN
            next_threshold = ELITE_MIN
        else:
            return 0.0
        
        # Calculate progress within current league
        range_size = next_threshold - min_elo
        progress = (elo - min_elo) / range_size
        
        return max(0.0, min(1.0, progress))
    
    def calculate_elo_change(
        self,
        winner_elo: int,
        loser_elo: int,
        k_factor: int = K_FACTOR
    ) -> EloChange:
        """
        Calculate ELO changes after a match using standard ELO formula.
        
        Formula:
        - Expected score: E = 1 / (1 + 10^((opponent_elo - player_elo) / 400))
        - New ELO: new_elo = old_elo + K * (actual - expected)
        
        Args:
            winner_elo: Winner's current ELO
            loser_elo: Loser's current ELO
            k_factor: K-factor for calculation (default 32)
            
        Returns:
            EloChange with new ratings and changes
            
        **Validates: Requirements 11.6**
        """
        # Calculate expected scores
        winner_expected = 1 / (1 + math.pow(10, (loser_elo - winner_elo) / 400))
        loser_expected = 1 / (1 + math.pow(10, (winner_elo - loser_elo) / 400))
        
        # Calculate ELO changes
        # Winner gets actual=1, loser gets actual=0
        winner_change = round(k_factor * (1 - winner_expected))
        loser_change = round(k_factor * (0 - loser_expected))
        
        # Calculate new ELOs (minimum 0)
        winner_new = max(0, winner_elo + winner_change)
        loser_new = max(0, loser_elo + loser_change)
        
        return EloChange(
            winner_new_elo=winner_new,
            loser_new_elo=loser_new,
            winner_change=winner_change,
            loser_change=loser_change
        )
    
    async def get_status(
        self,
        user_id: int,
        session: Optional[AsyncSession] = None
    ) -> LeagueStatus:
        """
        Get league status for a user.
        
        If no ELO record exists, returns default status (ELO=1000, SCRAP league).
        
        Args:
            user_id: Telegram user ID
            session: Optional database session
            
        Returns:
            LeagueStatus with current ELO and league
            
        **Validates: Requirements 11.1, 11.7**
        """
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            # Get user's ELO record
            result = await session.execute(
                select(UserElo).filter_by(user_id=user_id)
            )
            db_record = result.scalar_one_or_none()
            
            if db_record is None:
                # Return default status for new player
                return LeagueStatus(
                    user_id=user_id,
                    league=League.SCRAP,
                    elo=INITIAL_ELO,
                    progress_to_next=0.0,
                    is_top_10=False,
                    season_wins=0
                )
            
            # Check if user is in top 10
            is_top_10 = await self._check_top_10(user_id, session)
            
            # Determine league
            league = self.get_league_for_elo(db_record.elo, is_top_10)
            
            # Calculate progress
            progress = self.calculate_progress_to_next(db_record.elo, league)
            
            return LeagueStatus(
                user_id=user_id,
                league=league,
                elo=db_record.elo,
                progress_to_next=progress,
                is_top_10=is_top_10,
                season_wins=db_record.season_wins
            )
            
        finally:
            if close_session:
                await session.close()
    
    async def update_elo(
        self,
        winner_id: int,
        loser_id: int,
        k_factor: int = K_FACTOR,
        session: Optional[AsyncSession] = None
    ) -> Tuple[LeagueStatus, LeagueStatus]:
        """
        Update ELO ratings after a match.
        
        Args:
            winner_id: Winner's user ID
            loser_id: Loser's user ID
            k_factor: K-factor for calculation
            session: Optional database session
            
        Returns:
            Tuple of (winner_status, loser_status)
            
        **Validates: Requirements 11.6**
        """
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            # Get or create winner's ELO record
            winner_result = await session.execute(
                select(UserElo).filter_by(user_id=winner_id)
            )
            winner_record = winner_result.scalar_one_or_none()
            
            if winner_record is None:
                winner_record = UserElo(
                    user_id=winner_id,
                    elo=INITIAL_ELO,
                    league='scrap',
                    season_wins=0
                )
                session.add(winner_record)
            
            # Get or create loser's ELO record
            loser_result = await session.execute(
                select(UserElo).filter_by(user_id=loser_id)
            )
            loser_record = loser_result.scalar_one_or_none()
            
            if loser_record is None:
                loser_record = UserElo(
                    user_id=loser_id,
                    elo=INITIAL_ELO,
                    league='scrap',
                    season_wins=0
                )
                session.add(loser_record)
            
            # Calculate ELO changes
            elo_change = self.calculate_elo_change(
                winner_record.elo,
                loser_record.elo,
                k_factor
            )
            
            # Update records
            winner_record.elo = elo_change.winner_new_elo
            winner_record.updated_at = utc_now()
            
            loser_record.elo = elo_change.loser_new_elo
            loser_record.updated_at = utc_now()
            
            # Update league strings
            winner_league = self.get_league_for_elo(winner_record.elo)
            loser_league = self.get_league_for_elo(loser_record.elo)
            
            winner_record.league = winner_league.name.lower()
            loser_record.league = loser_league.name.lower()
            
            await session.commit()
            
            # Build status objects
            winner_status = LeagueStatus(
                user_id=winner_id,
                league=winner_league,
                elo=winner_record.elo,
                progress_to_next=self.calculate_progress_to_next(
                    winner_record.elo, winner_league
                ),
                is_top_10=False,  # Will be recalculated on next get_status
                season_wins=winner_record.season_wins
            )
            
            loser_status = LeagueStatus(
                user_id=loser_id,
                league=loser_league,
                elo=loser_record.elo,
                progress_to_next=self.calculate_progress_to_next(
                    loser_record.elo, loser_league
                ),
                is_top_10=False,
                season_wins=loser_record.season_wins
            )
            
            logger.info(
                f"ELO updated: winner {winner_id} ({elo_change.winner_change:+d} -> {winner_record.elo}), "
                f"loser {loser_id} ({elo_change.loser_change:+d} -> {loser_record.elo})"
            )
            
            return winner_status, loser_status
            
        finally:
            if close_session:
                await session.close()
    
    async def initialize_user(
        self,
        user_id: int,
        session: Optional[AsyncSession] = None
    ) -> LeagueStatus:
        """
        Initialize a new user with default ELO.
        
        Args:
            user_id: Telegram user ID
            session: Optional database session
            
        Returns:
            LeagueStatus with initial values
            
        **Validates: Requirements 11.1**
        """
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            # Check if already exists
            result = await session.execute(
                select(UserElo).filter_by(user_id=user_id)
            )
            db_record = result.scalar_one_or_none()
            
            if db_record is not None:
                # Already initialized
                league = self.get_league_for_elo(db_record.elo)
                return LeagueStatus(
                    user_id=user_id,
                    league=league,
                    elo=db_record.elo,
                    progress_to_next=self.calculate_progress_to_next(
                        db_record.elo, league
                    ),
                    is_top_10=False,
                    season_wins=db_record.season_wins
                )
            
            # Create new record
            db_record = UserElo(
                user_id=user_id,
                elo=INITIAL_ELO,
                league='scrap',
                season_wins=0
            )
            session.add(db_record)
            await session.commit()
            
            logger.info(f"Initialized ELO for user {user_id}")
            
            return LeagueStatus(
                user_id=user_id,
                league=League.SCRAP,
                elo=INITIAL_ELO,
                progress_to_next=0.0,
                is_top_10=False,
                season_wins=0
            )
            
        finally:
            if close_session:
                await session.close()
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    async def _check_top_10(
        self,
        user_id: int,
        session: AsyncSession
    ) -> bool:
        """Check if user is in top 10 by ELO."""
        # Get top 10 user IDs
        result = await session.execute(
            select(UserElo.user_id)
            .order_by(UserElo.elo.desc())
            .limit(10)
        )
        top_10_ids = [row[0] for row in result.fetchall()]
        
        return user_id in top_10_ids
    
    async def get_top_players(
        self,
        limit: int = 10,
        session: Optional[AsyncSession] = None
    ) -> List[LeagueStatus]:
        """
        Get top players by ELO.
        
        Args:
            limit: Number of players to return
            session: Optional database session
            
        Returns:
            List of LeagueStatus for top players
        """
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            result = await session.execute(
                select(UserElo)
                .order_by(UserElo.elo.desc())
                .limit(limit)
            )
            records = result.scalars().all()
            
            top_10_ids = [r.user_id for r in records[:10]]
            
            statuses = []
            for record in records:
                is_top_10 = record.user_id in top_10_ids
                league = self.get_league_for_elo(record.elo, is_top_10)
                
                statuses.append(LeagueStatus(
                    user_id=record.user_id,
                    league=league,
                    elo=record.elo,
                    progress_to_next=self.calculate_progress_to_next(
                        record.elo, league
                    ),
                    is_top_10=is_top_10,
                    season_wins=record.season_wins
                ))
            
            return statuses
            
        finally:
            if close_session:
                await session.close()
    
    def format_league_display(self, status: LeagueStatus) -> str:
        """
        Format league status for display.
        
        Args:
            status: LeagueStatus to format
            
        Returns:
            Formatted string for display
            
        **Validates: Requirements 11.7**
        """
        progress_bar = self._make_progress_bar(status.progress_to_next)
        
        lines = [
            f"{status.league.display_name}",
            f"ELO: {status.elo}",
            f"Progress: {progress_bar} {int(status.progress_to_next * 100)}%"
        ]
        
        if status.is_top_10:
            lines.append("⭐ Top 10 Player!")
        
        if status.season_wins > 0:
            lines.append(f"🏆 Season Wins: {status.season_wins}")
        
        return "\n".join(lines)
    
    def _make_progress_bar(self, progress: float, length: int = 10) -> str:
        """Create a text progress bar."""
        filled = int(progress * length)
        empty = length - filled
        return "█" * filled + "░" * empty


# Global service instance
league_service = LeagueService()
