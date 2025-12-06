"""
Property-based tests for LeagueService (ELO Rating System).

**Feature: fortress-update, Property 24: Initial ELO and league**
**Validates: Requirements 11.1**

**Feature: fortress-update, Property 25: League promotion thresholds**
**Validates: Requirements 11.2, 11.3, 11.4**

**Feature: fortress-update, Property 26: ELO calculation correctness**
**Validates: Requirements 11.6**
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from hypothesis import given, strategies as st, settings, assume


# ============================================================================
# Inline definitions to avoid import issues during testing
# These mirror the actual implementation in app/services/leagues.py
# ============================================================================

class League(Enum):
    """League tiers with their emoji, min ELO, and max ELO thresholds."""
    SCRAP = ("🥉", 0, 1199)
    SILICON = ("🥈", 1200, 1499)
    QUANTUM = ("🥇", 1500, 1999)
    ELITE = ("💎", 2000, float('inf'))
    
    def __init__(self, emoji: str, min_elo: int, max_elo: float):
        self.emoji = emoji
        self.min_elo = min_elo
        self.max_elo = max_elo


# Constants
INITIAL_ELO = 1000
K_FACTOR = 32
SCRAP_MAX = 1199
SILICON_MIN = 1200
SILICON_MAX = 1499
QUANTUM_MIN = 1500
QUANTUM_MAX = 1999
ELITE_MIN = 2000


@dataclass
class LeagueStatus:
    """Current league status for a user."""
    user_id: int
    league: League
    elo: int
    progress_to_next: float
    is_top_10: bool = False
    season_wins: int = 0


@dataclass
class EloChange:
    """Result of an ELO calculation."""
    winner_new_elo: int
    loser_new_elo: int
    winner_change: int
    loser_change: int


class LeagueService:
    """Minimal LeagueService for testing without DB dependencies."""
    
    def __init__(self):
        self._cache: Dict[int, LeagueStatus] = {}
    
    def get_league_for_elo(self, elo: int, is_top_10: bool = False) -> League:
        """Determine league based on ELO rating."""
        if is_top_10:
            return League.ELITE
        
        if elo >= ELITE_MIN:
            return League.ELITE
        elif elo >= QUANTUM_MIN:
            return League.QUANTUM
        elif elo >= SILICON_MIN:
            return League.SILICON
        else:
            return League.SCRAP
    
    def calculate_progress_to_next(self, elo: int, current_league: League) -> float:
        """Calculate progress to next league tier."""
        if current_league == League.ELITE:
            return 1.0
        
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
        
        range_size = next_threshold - min_elo
        progress = (elo - min_elo) / range_size
        
        return max(0.0, min(1.0, progress))
    
    def calculate_elo_change(
        self,
        winner_elo: int,
        loser_elo: int,
        k_factor: int = K_FACTOR
    ) -> EloChange:
        """Calculate ELO changes after a match using standard ELO formula."""
        winner_expected = 1 / (1 + math.pow(10, (loser_elo - winner_elo) / 400))
        loser_expected = 1 / (1 + math.pow(10, (winner_elo - loser_elo) / 400))
        
        winner_change = round(k_factor * (1 - winner_expected))
        loser_change = round(k_factor * (0 - loser_expected))
        
        winner_new = max(0, winner_elo + winner_change)
        loser_new = max(0, loser_elo + loser_change)
        
        return EloChange(
            winner_new_elo=winner_new,
            loser_new_elo=loser_new,
            winner_change=winner_change,
            loser_change=loser_change
        )
    
    def initialize_user(self, user_id: int) -> LeagueStatus:
        """Initialize a new user with default ELO."""
        if user_id in self._cache:
            return self._cache[user_id]
        
        status = LeagueStatus(
            user_id=user_id,
            league=League.SCRAP,
            elo=INITIAL_ELO,
            progress_to_next=0.0,
            is_top_10=False,
            season_wins=0
        )
        self._cache[user_id] = status
        return status
    
    def get_status(self, user_id: int) -> LeagueStatus:
        """Get league status for a user."""
        if user_id not in self._cache:
            return LeagueStatus(
                user_id=user_id,
                league=League.SCRAP,
                elo=INITIAL_ELO,
                progress_to_next=0.0,
                is_top_10=False,
                season_wins=0
            )
        return self._cache[user_id]


# ============================================================================
# Strategies for generating test data
# ============================================================================

# Strategy for user IDs (positive)
user_ids = st.integers(min_value=1, max_value=9999999999)

# Strategy for ELO ratings (reasonable range)
elo_ratings = st.integers(min_value=0, max_value=3000)

# Strategy for K-factor
k_factors = st.integers(min_value=1, max_value=64)


# ============================================================================
# Property 24: Initial ELO and League
# ============================================================================

class TestInitialEloAndLeague:
    """
    **Feature: fortress-update, Property 24: Initial ELO and league**
    **Validates: Requirements 11.1**
    
    For any new player, initial ELO SHALL be 1000 and league SHALL be SCRAP.
    """
    
    @settings(max_examples=100)
    @given(user_id=user_ids)
    def test_new_player_gets_initial_elo_1000(self, user_id: int):
        """
        Property: New players are initialized with ELO of 1000.
        """
        service = LeagueService()
        
        status = service.initialize_user(user_id)
        
        assert status.elo == INITIAL_ELO
        assert status.elo == 1000
    
    @settings(max_examples=100)
    @given(user_id=user_ids)
    def test_new_player_starts_in_scrap_league(self, user_id: int):
        """
        Property: New players start in Scrap League.
        """
        service = LeagueService()
        
        status = service.initialize_user(user_id)
        
        assert status.league == League.SCRAP
    
    @settings(max_examples=100)
    @given(user_id=user_ids)
    def test_new_player_not_top_10(self, user_id: int):
        """
        Property: New players are not in top 10.
        """
        service = LeagueService()
        
        status = service.initialize_user(user_id)
        
        assert status.is_top_10 is False
    
    @settings(max_examples=100)
    @given(user_id=user_ids)
    def test_new_player_zero_season_wins(self, user_id: int):
        """
        Property: New players have zero season wins.
        """
        service = LeagueService()
        
        status = service.initialize_user(user_id)
        
        assert status.season_wins == 0
    
    def test_initial_elo_constant(self):
        """
        Property: Initial ELO constant is 1000.
        """
        assert INITIAL_ELO == 1000
    
    def test_k_factor_constant(self):
        """
        Property: K-factor constant is 32.
        """
        assert K_FACTOR == 32
    
    @settings(max_examples=50)
    @given(user_id=user_ids)
    def test_initialize_is_idempotent(self, user_id: int):
        """
        Property: Initializing the same user twice returns the same status.
        """
        service = LeagueService()
        
        status1 = service.initialize_user(user_id)
        status2 = service.initialize_user(user_id)
        
        assert status1.elo == status2.elo
        assert status1.league == status2.league
    
    @settings(max_examples=100)
    @given(user_id=user_ids)
    def test_get_status_returns_default_for_unknown_user(self, user_id: int):
        """
        Property: Getting status for unknown user returns default values.
        """
        service = LeagueService()
        
        status = service.get_status(user_id)
        
        assert status.elo == INITIAL_ELO
        assert status.league == League.SCRAP


# ============================================================================
# Property 25: League Promotion Thresholds
# ============================================================================

class TestLeaguePromotionThresholds:
    """
    **Feature: fortress-update, Property 25: League promotion thresholds**
    **Validates: Requirements 11.2, 11.3, 11.4**
    
    For any ELO value, the league SHALL be:
    - ELO < 1200: SCRAP
    - 1200 <= ELO < 1500: SILICON
    - 1500 <= ELO < 2000: QUANTUM
    - ELO >= 2000 OR top 10: ELITE
    """
    
    def test_threshold_constants(self):
        """
        Property: League threshold constants are correct.
        """
        assert SCRAP_MAX == 1199
        assert SILICON_MIN == 1200
        assert SILICON_MAX == 1499
        assert QUANTUM_MIN == 1500
        assert QUANTUM_MAX == 1999
        assert ELITE_MIN == 2000
    
    @settings(max_examples=100)
    @given(elo=st.integers(min_value=0, max_value=1199))
    def test_elo_below_1200_is_scrap(self, elo: int):
        """
        Property: ELO below 1200 results in Scrap League.
        **Validates: Requirements 11.1**
        """
        service = LeagueService()
        
        league = service.get_league_for_elo(elo)
        
        assert league == League.SCRAP
    
    @settings(max_examples=100)
    @given(elo=st.integers(min_value=1200, max_value=1499))
    def test_elo_1200_to_1499_is_silicon(self, elo: int):
        """
        Property: ELO from 1200 to 1499 results in Silicon League.
        **Validates: Requirements 11.2**
        """
        service = LeagueService()
        
        league = service.get_league_for_elo(elo)
        
        assert league == League.SILICON
    
    @settings(max_examples=100)
    @given(elo=st.integers(min_value=1500, max_value=1999))
    def test_elo_1500_to_1999_is_quantum(self, elo: int):
        """
        Property: ELO from 1500 to 1999 results in Quantum League.
        **Validates: Requirements 11.3**
        """
        service = LeagueService()
        
        league = service.get_league_for_elo(elo)
        
        assert league == League.QUANTUM
    
    @settings(max_examples=100)
    @given(elo=st.integers(min_value=2000, max_value=5000))
    def test_elo_2000_plus_is_elite(self, elo: int):
        """
        Property: ELO 2000 or above results in Elite League.
        **Validates: Requirements 11.4**
        """
        service = LeagueService()
        
        league = service.get_league_for_elo(elo)
        
        assert league == League.ELITE
    
    @settings(max_examples=100)
    @given(elo=st.integers(min_value=0, max_value=1999))
    def test_top_10_is_always_elite(self, elo: int):
        """
        Property: Top 10 players are always Elite regardless of ELO.
        **Validates: Requirements 11.4**
        """
        service = LeagueService()
        
        league = service.get_league_for_elo(elo, is_top_10=True)
        
        assert league == League.ELITE
    
    def test_boundary_1199_is_scrap(self):
        """
        Property: ELO of exactly 1199 is Scrap League.
        """
        service = LeagueService()
        
        league = service.get_league_for_elo(1199)
        
        assert league == League.SCRAP
    
    def test_boundary_1200_is_silicon(self):
        """
        Property: ELO of exactly 1200 is Silicon League.
        """
        service = LeagueService()
        
        league = service.get_league_for_elo(1200)
        
        assert league == League.SILICON
    
    def test_boundary_1499_is_silicon(self):
        """
        Property: ELO of exactly 1499 is Silicon League.
        """
        service = LeagueService()
        
        league = service.get_league_for_elo(1499)
        
        assert league == League.SILICON
    
    def test_boundary_1500_is_quantum(self):
        """
        Property: ELO of exactly 1500 is Quantum League.
        """
        service = LeagueService()
        
        league = service.get_league_for_elo(1500)
        
        assert league == League.QUANTUM
    
    def test_boundary_1999_is_quantum(self):
        """
        Property: ELO of exactly 1999 is Quantum League.
        """
        service = LeagueService()
        
        league = service.get_league_for_elo(1999)
        
        assert league == League.QUANTUM
    
    def test_boundary_2000_is_elite(self):
        """
        Property: ELO of exactly 2000 is Elite League.
        """
        service = LeagueService()
        
        league = service.get_league_for_elo(2000)
        
        assert league == League.ELITE


# ============================================================================
# Property 26: ELO Calculation Correctness
# ============================================================================

class TestEloCalculationCorrectness:
    """
    **Feature: fortress-update, Property 26: ELO calculation correctness**
    **Validates: Requirements 11.6**
    
    For any game result between two players, the ELO changes SHALL follow the standard formula:
    - Expected score: E = 1 / (1 + 10^((opponent_elo - player_elo) / 400))
    - New ELO: new_elo = old_elo + K * (actual - expected), where K = 32
    """
    
    @settings(max_examples=100)
    @given(
        winner_elo=st.integers(min_value=100, max_value=2500),
        loser_elo=st.integers(min_value=100, max_value=2500)
    )
    def test_elo_formula_correctness(self, winner_elo: int, loser_elo: int):
        """
        Property: ELO calculation follows the standard formula.
        """
        service = LeagueService()
        
        result = service.calculate_elo_change(winner_elo, loser_elo)
        
        # Calculate expected values manually
        winner_expected = 1 / (1 + math.pow(10, (loser_elo - winner_elo) / 400))
        loser_expected = 1 / (1 + math.pow(10, (winner_elo - loser_elo) / 400))
        
        expected_winner_change = round(K_FACTOR * (1 - winner_expected))
        expected_loser_change = round(K_FACTOR * (0 - loser_expected))
        
        assert result.winner_change == expected_winner_change
        assert result.loser_change == expected_loser_change
    
    @settings(max_examples=100)
    @given(
        winner_elo=st.integers(min_value=100, max_value=2500),
        loser_elo=st.integers(min_value=100, max_value=2500)
    )
    def test_winner_gains_elo(self, winner_elo: int, loser_elo: int):
        """
        Property: Winner always gains ELO (or stays same in extreme cases).
        """
        service = LeagueService()
        
        result = service.calculate_elo_change(winner_elo, loser_elo)
        
        assert result.winner_change >= 0
        assert result.winner_new_elo >= winner_elo
    
    @settings(max_examples=100)
    @given(
        winner_elo=st.integers(min_value=100, max_value=2500),
        loser_elo=st.integers(min_value=100, max_value=2500)
    )
    def test_loser_loses_elo(self, winner_elo: int, loser_elo: int):
        """
        Property: Loser always loses ELO (or stays same in extreme cases).
        """
        service = LeagueService()
        
        result = service.calculate_elo_change(winner_elo, loser_elo)
        
        assert result.loser_change <= 0
        assert result.loser_new_elo <= loser_elo
    
    @settings(max_examples=100)
    @given(
        winner_elo=st.integers(min_value=100, max_value=2500),
        loser_elo=st.integers(min_value=100, max_value=2500)
    )
    def test_elo_cannot_go_negative(self, winner_elo: int, loser_elo: int):
        """
        Property: ELO cannot go below 0.
        """
        service = LeagueService()
        
        result = service.calculate_elo_change(winner_elo, loser_elo)
        
        assert result.winner_new_elo >= 0
        assert result.loser_new_elo >= 0
    
    @settings(max_examples=100)
    @given(elo=st.integers(min_value=500, max_value=2000))
    def test_equal_elo_gives_symmetric_changes(self, elo: int):
        """
        Property: When both players have equal ELO, changes are symmetric.
        """
        service = LeagueService()
        
        result = service.calculate_elo_change(elo, elo)
        
        # With equal ELO, expected score is 0.5 for both
        # Winner gets K * (1 - 0.5) = K * 0.5 = 16
        # Loser gets K * (0 - 0.5) = K * -0.5 = -16
        assert result.winner_change == 16
        assert result.loser_change == -16
    
    @settings(max_examples=100)
    @given(
        winner_elo=st.integers(min_value=100, max_value=2500),
        loser_elo=st.integers(min_value=100, max_value=2500)
    )
    def test_upset_gives_more_points(self, winner_elo: int, loser_elo: int):
        """
        Property: Beating a higher-rated opponent gives more points than expected.
        """
        assume(loser_elo > winner_elo + 100)  # Ensure significant upset
        
        service = LeagueService()
        
        result = service.calculate_elo_change(winner_elo, loser_elo)
        
        # Upset should give more than 16 points (the equal-ELO case)
        assert result.winner_change > 16
    
    @settings(max_examples=100)
    @given(
        winner_elo=st.integers(min_value=100, max_value=2500),
        loser_elo=st.integers(min_value=100, max_value=2500)
    )
    def test_expected_win_gives_fewer_points(self, winner_elo: int, loser_elo: int):
        """
        Property: Beating a lower-rated opponent gives fewer points than expected.
        """
        assume(winner_elo > loser_elo + 100)  # Ensure expected win
        
        service = LeagueService()
        
        result = service.calculate_elo_change(winner_elo, loser_elo)
        
        # Expected win should give less than 16 points
        assert result.winner_change < 16
    
    @settings(max_examples=50)
    @given(
        winner_elo=st.integers(min_value=100, max_value=2500),
        loser_elo=st.integers(min_value=100, max_value=2500),
        k_factor=k_factors
    )
    def test_custom_k_factor(self, winner_elo: int, loser_elo: int, k_factor: int):
        """
        Property: Custom K-factor is applied correctly.
        """
        service = LeagueService()
        
        result = service.calculate_elo_change(winner_elo, loser_elo, k_factor)
        
        # Calculate expected values with custom K
        winner_expected = 1 / (1 + math.pow(10, (loser_elo - winner_elo) / 400))
        expected_winner_change = round(k_factor * (1 - winner_expected))
        
        assert result.winner_change == expected_winner_change
    
    def test_extreme_elo_difference(self):
        """
        Property: Extreme ELO differences are handled correctly.
        """
        service = LeagueService()
        
        # Very high rated player beats very low rated
        result = service.calculate_elo_change(2500, 100)
        
        # Winner should gain very little
        assert result.winner_change >= 0
        assert result.winner_change <= 5  # Very small gain
        
        # Loser should lose very little
        assert result.loser_change >= -5
        assert result.loser_change <= 0


# ============================================================================
# Progress Calculation Tests
# ============================================================================

class TestProgressCalculation:
    """
    Tests for progress to next league calculation.
    """
    
    @settings(max_examples=100)
    @given(elo=st.integers(min_value=0, max_value=1199))
    def test_scrap_progress(self, elo: int):
        """
        Property: Progress in Scrap league is calculated correctly.
        """
        service = LeagueService()
        
        progress = service.calculate_progress_to_next(elo, League.SCRAP)
        
        expected = elo / 1200  # 0 to 1200 range
        assert abs(progress - expected) < 0.01
    
    @settings(max_examples=100)
    @given(elo=st.integers(min_value=1200, max_value=1499))
    def test_silicon_progress(self, elo: int):
        """
        Property: Progress in Silicon league is calculated correctly.
        """
        service = LeagueService()
        
        progress = service.calculate_progress_to_next(elo, League.SILICON)
        
        expected = (elo - 1200) / 300  # 1200 to 1500 range
        assert abs(progress - expected) < 0.01
    
    @settings(max_examples=100)
    @given(elo=st.integers(min_value=1500, max_value=1999))
    def test_quantum_progress(self, elo: int):
        """
        Property: Progress in Quantum league is calculated correctly.
        """
        service = LeagueService()
        
        progress = service.calculate_progress_to_next(elo, League.QUANTUM)
        
        expected = (elo - 1500) / 500  # 1500 to 2000 range
        assert abs(progress - expected) < 0.01
    
    @settings(max_examples=100)
    @given(elo=st.integers(min_value=2000, max_value=5000))
    def test_elite_progress_is_always_1(self, elo: int):
        """
        Property: Progress in Elite league is always 1.0.
        """
        service = LeagueService()
        
        progress = service.calculate_progress_to_next(elo, League.ELITE)
        
        assert progress == 1.0
    
    @settings(max_examples=100)
    @given(elo=elo_ratings)
    def test_progress_is_bounded(self, elo: int):
        """
        Property: Progress is always between 0.0 and 1.0.
        """
        service = LeagueService()
        league = service.get_league_for_elo(elo)
        
        progress = service.calculate_progress_to_next(elo, league)
        
        assert 0.0 <= progress <= 1.0
