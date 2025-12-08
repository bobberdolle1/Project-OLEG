"""Citadel Service - DEFCON Protection System.

This module provides the Citadel protection system with multi-level DEFCON
security for chat moderation. It manages protection levels, raid detection,
and user restriction policies.

**Feature: fortress-update**
**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7**
"""

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Any, Deque, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CitadelConfig as CitadelConfigModel, Chat
from app.database.session import get_session
from app.utils import utc_now

logger = logging.getLogger(__name__)


# ============================================================================
# DEFCON Level Definitions
# ============================================================================

class DEFCONLevel(IntEnum):
    """
    DEFCON protection levels for chat security.
    
    Level 1 (Peaceful): Basic protection - anti-spam links + basic captcha
    Level 2 (Strict): Enhanced protection - profanity filter, sticker limit, forward block
    Level 3 (Martial Law): Maximum protection - full media restriction for new users, hard captcha
    """
    PEACEFUL = 1      # Anti-spam links + basic captcha
    STRICT = 2        # + Profanity filter, sticker limit (3), forward block
    MARTIAL_LAW = 3   # + Full media restriction for new users, Hard Captcha


# ============================================================================
# Configuration Dataclass
# ============================================================================

@dataclass
class CitadelConfigData:
    """
    Configuration data for Citadel protection system.
    
    Attributes:
        chat_id: Telegram chat ID
        defcon_level: Current DEFCON protection level
        raid_mode_until: When raid mode expires (None if not active)
        anti_spam_enabled: Whether anti-spam link filtering is enabled
        profanity_filter_enabled: Whether profanity filter is enabled
        sticker_limit: Maximum consecutive stickers (0 = disabled)
        forward_block_enabled: Whether channel forward blocking is enabled
        new_user_restriction_hours: Hours to restrict new users
        hard_captcha_enabled: Whether hard captcha (AI puzzles) is enabled
        gif_patrol_enabled: Whether GIF moderation is enabled (work in progress)
    """
    chat_id: int
    defcon_level: DEFCONLevel = DEFCONLevel.PEACEFUL
    raid_mode_until: Optional[datetime] = None
    anti_spam_enabled: bool = True
    profanity_filter_enabled: bool = False
    sticker_limit: int = 0  # 0 = disabled
    forward_block_enabled: bool = False
    new_user_restriction_hours: int = 24
    hard_captcha_enabled: bool = False
    gif_patrol_enabled: bool = False  # GIF moderation (work in progress)
    
    @property
    def is_raid_mode_active(self) -> bool:
        """Check if raid mode is currently active."""
        if self.raid_mode_until is None:
            return False
        return utc_now() < self.raid_mode_until
    
    def get_features_for_level(self) -> Dict[str, Any]:
        """Get feature settings based on current DEFCON level."""
        return DEFCON_FEATURES.get(self.defcon_level, DEFCON_FEATURES[DEFCONLevel.PEACEFUL])


# ============================================================================
# DEFCON Feature Mappings
# ============================================================================

# Feature settings for each DEFCON level
DEFCON_FEATURES: Dict[DEFCONLevel, Dict[str, Any]] = {
    DEFCONLevel.PEACEFUL: {
        "anti_spam_enabled": True,
        "profanity_filter_enabled": False,
        "sticker_limit": 0,
        "forward_block_enabled": False,
        "new_user_restriction_enabled": False,
        "hard_captcha_enabled": False,
    },
    DEFCONLevel.STRICT: {
        "anti_spam_enabled": True,
        "profanity_filter_enabled": True,
        "sticker_limit": 3,
        "forward_block_enabled": True,
        "new_user_restriction_enabled": False,
        "hard_captcha_enabled": False,
    },
    DEFCONLevel.MARTIAL_LAW: {
        "anti_spam_enabled": True,
        "profanity_filter_enabled": True,
        "sticker_limit": 3,
        "forward_block_enabled": True,
        "new_user_restriction_enabled": True,
        "hard_captcha_enabled": True,
    },
}

# Raid detection thresholds
RAID_JOIN_THRESHOLD = 5  # Number of joins
RAID_WINDOW_SECONDS = 60  # Time window in seconds
RAID_MODE_DURATION_MINUTES = 15  # Duration of raid mode


# ============================================================================
# Citadel Service
# ============================================================================

class CitadelService:
    """
    Service for managing Citadel DEFCON protection system.
    
    Provides methods for:
    - Getting and setting DEFCON levels
    - Raid detection and activation
    - User restriction management
    - Feature configuration based on protection level
    """
    
    def __init__(self):
        """Initialize CitadelService with in-memory caches."""
        # In-memory cache for configs (reduces DB queries)
        self._config_cache: Dict[int, CitadelConfigData] = {}
        self._cache_ttl: Dict[int, datetime] = {}
        self._cache_duration = timedelta(minutes=5)
        
        # In-memory tracking for raid detection
        self._join_events: Dict[int, Deque[datetime]] = defaultdict(deque)
        
        # Track user join times for "new user" detection
        self._user_join_times: Dict[Tuple[int, int], datetime] = {}  # (user_id, chat_id) -> join_time
    
    # =========================================================================
    # Configuration Management
    # =========================================================================
    
    async def get_config(self, chat_id: int, session: Optional[AsyncSession] = None) -> CitadelConfigData:
        """
        Get Citadel configuration for a chat.
        
        If no configuration exists, creates a default one with DEFCON 1.
        
        Args:
            chat_id: Telegram chat ID
            session: Optional database session
            
        Returns:
            CitadelConfigData with current settings
        """
        # Check cache first
        if self._is_cache_valid(chat_id):
            return self._config_cache[chat_id]
        
        # Load from database
        config_data = await self._load_config_from_db(chat_id, session)
        
        # Cache the result
        self._config_cache[chat_id] = config_data
        self._cache_ttl[chat_id] = utc_now()
        
        return config_data
    
    async def set_defcon(
        self,
        chat_id: int,
        level: DEFCONLevel,
        session: Optional[AsyncSession] = None
    ) -> CitadelConfigData:
        """
        Set DEFCON level for a chat.
        
        Updates the protection level and applies corresponding feature settings.
        
        Args:
            chat_id: Telegram chat ID
            level: New DEFCON level to set
            session: Optional database session
            
        Returns:
            Updated CitadelConfigData
        """
        if not isinstance(level, DEFCONLevel):
            try:
                level = DEFCONLevel(level)
            except ValueError:
                raise ValueError(f"Invalid DEFCON level: {level}. Must be 1, 2, or 3.")
        
        # Get feature settings for the new level
        features = DEFCON_FEATURES[level]
        
        # Update in database
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            # Get or create config
            result = await session.execute(
                select(CitadelConfigModel).filter_by(chat_id=chat_id)
            )
            db_config = result.scalar_one_or_none()
            
            if db_config is None:
                db_config = CitadelConfigModel(chat_id=chat_id)
                session.add(db_config)
            
            # Update fields
            db_config.defcon_level = level.value
            db_config.anti_spam_enabled = features["anti_spam_enabled"]
            db_config.profanity_filter_enabled = features["profanity_filter_enabled"]
            db_config.sticker_limit = features["sticker_limit"]
            db_config.forward_block_enabled = features["forward_block_enabled"]
            db_config.hard_captcha_enabled = features["hard_captcha_enabled"]
            db_config.updated_at = utc_now()
            
            await session.commit()
            
            # Update cache
            config_data = self._db_model_to_dataclass(db_config)
            self._config_cache[chat_id] = config_data
            self._cache_ttl[chat_id] = utc_now()
            
            logger.info(f"DEFCON level set to {level.name} for chat {chat_id}")
            
            return config_data
            
        finally:
            if close_session:
                await session.close()
    
    async def register_chat(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> CitadelConfigData:
        """
        Register a new chat with default DEFCON 1 settings.
        
        This is called when a chat is first registered with the bot.
        
        Args:
            chat_id: Telegram chat ID
            session: Optional database session
            
        Returns:
            CitadelConfigData with default settings (DEFCON 1)
        """
        return await self.set_defcon(chat_id, DEFCONLevel.PEACEFUL, session)
    
    # =========================================================================
    # Raid Detection and Management
    # =========================================================================
    
    def record_join(self, chat_id: int, user_id: int) -> None:
        """
        Record a user join event for raid detection.
        
        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID who joined
        """
        now = utc_now()
        
        # Record join event
        self._join_events[chat_id].append(now)
        
        # Record user join time
        self._user_join_times[(user_id, chat_id)] = now
        
        # Clean up old events
        self._cleanup_old_join_events(chat_id, now)
    
    def check_raid_condition(self, chat_id: int) -> bool:
        """
        Check if raid condition is met (5+ joins in 60 seconds).
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            True if raid condition is detected
        """
        now = utc_now()
        self._cleanup_old_join_events(chat_id, now)
        
        join_count = len(self._join_events[chat_id])
        is_raid = join_count >= RAID_JOIN_THRESHOLD
        
        if is_raid:
            logger.warning(f"Raid condition detected in chat {chat_id}: {join_count} joins in {RAID_WINDOW_SECONDS}s")
        
        return is_raid
    
    async def activate_raid_mode(
        self,
        chat_id: int,
        duration_minutes: int = RAID_MODE_DURATION_MINUTES,
        session: Optional[AsyncSession] = None
    ) -> CitadelConfigData:
        """
        Activate raid mode for a chat.
        
        Sets DEFCON to level 3 and enables raid mode timer.
        
        Args:
            chat_id: Telegram chat ID
            duration_minutes: How long raid mode should last
            session: Optional database session
            
        Returns:
            Updated CitadelConfigData
        """
        now = utc_now()
        raid_until = now + timedelta(minutes=duration_minutes)
        
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            # Get or create config
            result = await session.execute(
                select(CitadelConfigModel).filter_by(chat_id=chat_id)
            )
            db_config = result.scalar_one_or_none()
            
            if db_config is None:
                db_config = CitadelConfigModel(chat_id=chat_id)
                session.add(db_config)
            
            # Set raid mode and DEFCON 3
            db_config.raid_mode_until = raid_until
            db_config.defcon_level = DEFCONLevel.MARTIAL_LAW.value
            
            # Apply DEFCON 3 features
            features = DEFCON_FEATURES[DEFCONLevel.MARTIAL_LAW]
            db_config.anti_spam_enabled = features["anti_spam_enabled"]
            db_config.profanity_filter_enabled = features["profanity_filter_enabled"]
            db_config.sticker_limit = features["sticker_limit"]
            db_config.forward_block_enabled = features["forward_block_enabled"]
            db_config.hard_captcha_enabled = features["hard_captcha_enabled"]
            db_config.updated_at = now
            
            await session.commit()
            
            # Update cache
            config_data = self._db_model_to_dataclass(db_config)
            self._config_cache[chat_id] = config_data
            self._cache_ttl[chat_id] = now
            
            logger.warning(f"Raid mode activated for chat {chat_id} until {raid_until}")
            
            return config_data
            
        finally:
            if close_session:
                await session.close()
    
    async def deactivate_raid_mode(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> CitadelConfigData:
        """
        Deactivate raid mode for a chat.
        
        Clears the raid mode timer but keeps current DEFCON level.
        
        Args:
            chat_id: Telegram chat ID
            session: Optional database session
            
        Returns:
            Updated CitadelConfigData
        """
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            result = await session.execute(
                select(CitadelConfigModel).filter_by(chat_id=chat_id)
            )
            db_config = result.scalar_one_or_none()
            
            if db_config:
                db_config.raid_mode_until = None
                db_config.updated_at = utc_now()
                await session.commit()
            
            # Update cache
            config_data = await self._load_config_from_db(chat_id, session)
            self._config_cache[chat_id] = config_data
            self._cache_ttl[chat_id] = utc_now()
            
            logger.info(f"Raid mode deactivated for chat {chat_id}")
            
            return config_data
            
        finally:
            if close_session:
                await session.close()
    
    # =========================================================================
    # User Status Checks
    # =========================================================================
    
    def is_new_user(
        self,
        user_id: int,
        chat_id: int,
        threshold_hours: int = 24
    ) -> bool:
        """
        Check if a user is considered "new" in the chat.
        
        A user is new if they joined within the threshold period.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            threshold_hours: Hours threshold for "new" status
            
        Returns:
            True if user is new (joined within threshold)
        """
        join_time = self._user_join_times.get((user_id, chat_id))
        
        if join_time is None:
            # Unknown join time - assume not new (conservative)
            return False
        
        now = utc_now()
        threshold = timedelta(hours=threshold_hours)
        
        return (now - join_time) < threshold
    
    def set_user_join_time(
        self,
        user_id: int,
        chat_id: int,
        join_time: Optional[datetime] = None
    ) -> None:
        """
        Set or update a user's join time.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            join_time: Join time (defaults to now)
        """
        self._user_join_times[(user_id, chat_id)] = join_time or utc_now()
    
    # =========================================================================
    # Feature Checks
    # =========================================================================
    
    async def should_filter_profanity(self, chat_id: int) -> bool:
        """Check if profanity filter should be applied."""
        config = await self.get_config(chat_id)
        return config.profanity_filter_enabled
    
    async def should_block_forwards(self, chat_id: int) -> bool:
        """Check if channel forwards should be blocked."""
        config = await self.get_config(chat_id)
        return config.forward_block_enabled
    
    async def get_sticker_limit(self, chat_id: int) -> int:
        """Get sticker limit (0 = no limit)."""
        config = await self.get_config(chat_id)
        return config.sticker_limit
    
    async def should_restrict_new_user(
        self,
        user_id: int,
        chat_id: int
    ) -> bool:
        """
        Check if a new user should have media/link restrictions.
        
        Only applies at DEFCON 3 or during raid mode.
        """
        config = await self.get_config(chat_id)
        
        # Only restrict at DEFCON 3 or during raid mode
        if config.defcon_level < DEFCONLevel.MARTIAL_LAW and not config.is_raid_mode_active:
            return False
        
        return self.is_new_user(user_id, chat_id, config.new_user_restriction_hours)
    
    async def should_use_hard_captcha(self, chat_id: int) -> bool:
        """Check if hard captcha (AI puzzles) should be used."""
        config = await self.get_config(chat_id)
        return config.hard_captcha_enabled
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _is_cache_valid(self, chat_id: int) -> bool:
        """Check if cached config is still valid."""
        if chat_id not in self._config_cache:
            return False
        
        cache_time = self._cache_ttl.get(chat_id)
        if cache_time is None:
            return False
        
        return (utc_now() - cache_time) < self._cache_duration
    
    async def _load_config_from_db(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> CitadelConfigData:
        """Load config from database or create default."""
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            result = await session.execute(
                select(CitadelConfigModel).filter_by(chat_id=chat_id)
            )
            db_config = result.scalar_one_or_none()
            
            if db_config is None:
                # Return default config (DEFCON 1)
                return CitadelConfigData(chat_id=chat_id)
            
            return self._db_model_to_dataclass(db_config)
            
        finally:
            if close_session:
                await session.close()
    
    def _db_model_to_dataclass(self, db_config: CitadelConfigModel) -> CitadelConfigData:
        """Convert database model to dataclass."""
        return CitadelConfigData(
            chat_id=db_config.chat_id,
            defcon_level=DEFCONLevel(db_config.defcon_level),
            raid_mode_until=db_config.raid_mode_until,
            anti_spam_enabled=db_config.anti_spam_enabled,
            profanity_filter_enabled=db_config.profanity_filter_enabled,
            sticker_limit=db_config.sticker_limit,
            forward_block_enabled=db_config.forward_block_enabled,
            new_user_restriction_hours=db_config.new_user_restriction_hours,
            hard_captcha_enabled=db_config.hard_captcha_enabled,
            gif_patrol_enabled=getattr(db_config, 'gif_patrol_enabled', False),
        )
    
    def _cleanup_old_join_events(self, chat_id: int, now: datetime) -> None:
        """Remove join events outside the detection window."""
        events = self._join_events[chat_id]
        cutoff = now - timedelta(seconds=RAID_WINDOW_SECONDS)
        
        while events and events[0] < cutoff:
            events.popleft()
    
    def invalidate_cache(self, chat_id: int) -> None:
        """Invalidate cached config for a chat."""
        self._config_cache.pop(chat_id, None)
        self._cache_ttl.pop(chat_id, None)


# Global service instance
citadel_service = CitadelService()
