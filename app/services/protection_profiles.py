"""Protection Profiles Manager - Preset Protection Configurations.

This module provides the Protection Profiles system for managing chat protection
settings through preset configurations (Standard, Strict, Bunker) or custom settings.

**Feature: shield-economy-v65**
**Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5**
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ProtectionProfileConfig
from app.database.session import get_session
from app.services.redis_client import redis_client
from app.utils import utc_now

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Redis key prefix for profile data
REDIS_KEY_PREFIX = "protection_profile:"

# Redis TTL for profile data (seconds)
REDIS_TTL = 300

# Maximum time for settings to be applied (seconds) - Requirement 10.5
SETTINGS_APPLY_TIMEOUT = 5


# ============================================================================
# Enums
# ============================================================================

class ProtectionProfile(Enum):
    """
    Protection profile types.
    
    - STANDARD: Basic protection with link anti-spam and button captcha
    - STRICT: Enhanced protection with neural ad filter and forward blocking
    - BUNKER: Maximum protection with newcomer muting and media blocking
    - CUSTOM: User-defined settings
    """
    STANDARD = "standard"
    STRICT = "strict"
    BUNKER = "bunker"
    CUSTOM = "custom"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ProfileSettings:
    """
    Protection profile settings.
    
    Attributes:
        anti_spam_links: Enable link anti-spam protection
        captcha_type: Type of captcha ("button" or "hard")
        profanity_allowed: Whether profanity is allowed
        neural_ad_filter: Enable neural network ad detection
        block_forwards: Block forwarded messages
        sticker_limit: Maximum stickers per message (0 = unlimited)
        mute_newcomers: Mute new users until captcha passed
        block_media_non_admin: Block media from non-admins
        aggressive_profanity: Enable aggressive profanity filter
    """
    anti_spam_links: bool = True
    captcha_type: str = "button"
    profanity_allowed: bool = True
    neural_ad_filter: bool = False
    block_forwards: bool = False
    sticker_limit: int = 0
    mute_newcomers: bool = False
    block_media_non_admin: bool = False
    aggressive_profanity: bool = False
    
    def to_dict(self) -> Dict:
        """Convert settings to dictionary."""
        return {
            "anti_spam_links": self.anti_spam_links,
            "captcha_type": self.captcha_type,
            "profanity_allowed": self.profanity_allowed,
            "neural_ad_filter": self.neural_ad_filter,
            "block_forwards": self.block_forwards,
            "sticker_limit": self.sticker_limit,
            "mute_newcomers": self.mute_newcomers,
            "block_media_non_admin": self.block_media_non_admin,
            "aggressive_profanity": self.aggressive_profanity,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ProfileSettings":
        """Create settings from dictionary."""
        return cls(
            anti_spam_links=data.get("anti_spam_links", True),
            captcha_type=data.get("captcha_type", "button"),
            profanity_allowed=data.get("profanity_allowed", True),
            neural_ad_filter=data.get("neural_ad_filter", False),
            block_forwards=data.get("block_forwards", False),
            sticker_limit=data.get("sticker_limit", 0),
            mute_newcomers=data.get("mute_newcomers", False),
            block_media_non_admin=data.get("block_media_non_admin", False),
            aggressive_profanity=data.get("aggressive_profanity", False),
        )


# ============================================================================
# Profile Presets
# ============================================================================

PROFILE_PRESETS: Dict[ProtectionProfile, ProfileSettings] = {
    # Standard: Basic protection (Requirement 10.1)
    # - Link anti-spam enabled
    # - Button captcha
    # - Profanity allowed
    ProtectionProfile.STANDARD: ProfileSettings(
        anti_spam_links=True,
        captcha_type="button",
        profanity_allowed=True,
        neural_ad_filter=False,
        block_forwards=False,
        sticker_limit=0,
        mute_newcomers=False,
        block_media_non_admin=False,
        aggressive_profanity=False,
    ),
    
    # Strict: Enhanced protection (Requirement 10.2)
    # - Neural ad filter enabled
    # - Block forwards enabled
    # - Sticker limit = 3
    ProtectionProfile.STRICT: ProfileSettings(
        anti_spam_links=True,
        captcha_type="button",
        profanity_allowed=False,
        neural_ad_filter=True,
        block_forwards=True,
        sticker_limit=3,
        mute_newcomers=False,
        block_media_non_admin=False,
        aggressive_profanity=False,
    ),
    
    # Bunker: Maximum protection (Requirement 10.3)
    # - Mute newcomers until captcha
    # - Block media from non-admins
    # - Aggressive profanity filter
    ProtectionProfile.BUNKER: ProfileSettings(
        anti_spam_links=True,
        captcha_type="hard",
        profanity_allowed=False,
        neural_ad_filter=True,
        block_forwards=True,
        sticker_limit=0,
        mute_newcomers=True,
        block_media_non_admin=True,
        aggressive_profanity=True,
    ),
}


# ============================================================================
# Protection Profile Manager
# ============================================================================

class ProtectionProfileManager:
    """
    Manager for chat protection profiles.
    
    Provides methods for:
    - Getting current profile and settings for a chat
    - Setting a protection profile
    - Setting custom settings
    - Getting effective settings (profile + overrides)
    
    Uses Redis for fast access with database fallback.
    
    **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5**
    """
    
    def __init__(self):
        """Initialize ProtectionProfileManager with in-memory fallback cache."""
        self._memory_cache: Dict[int, Tuple[ProtectionProfile, ProfileSettings]] = {}
    
    # =========================================================================
    # Redis Key Helpers
    # =========================================================================
    
    def _get_redis_key(self, chat_id: int) -> str:
        """Generate Redis key for chat profile data."""
        return f"{REDIS_KEY_PREFIX}{chat_id}"
    
    # =========================================================================
    # Core Profile Methods
    # =========================================================================
    
    async def get_profile(
        self,
        chat_id: int
    ) -> Tuple[ProtectionProfile, ProfileSettings]:
        """
        Get the current protection profile and settings for a chat.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            Tuple of (profile, settings)
            
        **Validates: Requirements 10.1, 10.2, 10.3, 10.4**
        """
        # Try cache first
        if chat_id in self._memory_cache:
            return self._memory_cache[chat_id]
        
        # Try Redis
        if redis_client.is_available:
            redis_key = self._get_redis_key(chat_id)
            data = await redis_client.get_json(redis_key)
            if data:
                profile, settings = self._deserialize_profile_data(data)
                self._memory_cache[chat_id] = (profile, settings)
                return profile, settings
        
        # Load from database
        profile, settings = await self._load_from_db(chat_id)
        self._memory_cache[chat_id] = (profile, settings)
        
        return profile, settings
    
    async def set_profile(
        self,
        chat_id: int,
        profile: ProtectionProfile
    ) -> ProfileSettings:
        """
        Set a protection profile for a chat.
        
        When a preset profile is selected, the corresponding settings are applied.
        
        Args:
            chat_id: Telegram chat ID
            profile: Protection profile to apply
            
        Returns:
            The applied settings
            
        **Validates: Requirements 10.1, 10.2, 10.3, 10.5**
        """
        # Get settings for the profile
        if profile == ProtectionProfile.CUSTOM:
            # For custom, load existing custom settings or use standard as base
            _, current_settings = await self.get_profile(chat_id)
            settings = current_settings
        else:
            # Use preset settings
            settings = PROFILE_PRESETS[profile]
        
        # Save to storage
        await self._save_profile(chat_id, profile, settings)
        
        logger.info(f"Protection profile set for chat {chat_id}: {profile.value}")
        
        return settings
    
    async def set_custom_settings(
        self,
        chat_id: int,
        settings: ProfileSettings
    ) -> None:
        """
        Set custom protection settings for a chat.
        
        This automatically sets the profile to CUSTOM.
        
        Args:
            chat_id: Telegram chat ID
            settings: Custom settings to apply
            
        **Validates: Requirements 10.4, 10.5**
        """
        await self._save_profile(chat_id, ProtectionProfile.CUSTOM, settings)
        logger.info(f"Custom protection settings applied for chat {chat_id}")
    
    async def get_settings(
        self,
        chat_id: int
    ) -> ProfileSettings:
        """
        Get the effective protection settings for a chat.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            Current effective settings
        """
        _, settings = await self.get_profile(chat_id)
        return settings
    
    async def update_setting(
        self,
        chat_id: int,
        setting_name: str,
        value: any
    ) -> ProfileSettings:
        """
        Update a single setting for a chat.
        
        This automatically switches to CUSTOM profile if not already.
        
        Args:
            chat_id: Telegram chat ID
            setting_name: Name of the setting to update
            value: New value for the setting
            
        Returns:
            Updated settings
            
        **Validates: Requirements 10.4**
        """
        _, current_settings = await self.get_profile(chat_id)
        
        # Create new settings with the update
        settings_dict = current_settings.to_dict()
        if setting_name in settings_dict:
            settings_dict[setting_name] = value
            new_settings = ProfileSettings.from_dict(settings_dict)
            await self._save_profile(chat_id, ProtectionProfile.CUSTOM, new_settings)
            return new_settings
        
        raise ValueError(f"Unknown setting: {setting_name}")
    
    # =========================================================================
    # Cache Management
    # =========================================================================
    
    def invalidate_cache(self, chat_id: int) -> None:
        """Invalidate cached profile for a chat."""
        self._memory_cache.pop(chat_id, None)
    
    # =========================================================================
    # Private Helper Methods - Storage
    # =========================================================================
    
    async def _save_profile(
        self,
        chat_id: int,
        profile: ProtectionProfile,
        settings: ProfileSettings
    ) -> None:
        """Save profile and settings to Redis and database."""
        # Update memory cache
        self._memory_cache[chat_id] = (profile, settings)
        
        # Save to Redis
        if redis_client.is_available:
            redis_key = self._get_redis_key(chat_id)
            data = self._serialize_profile_data(profile, settings)
            await redis_client.set_json(redis_key, data, ex=REDIS_TTL)
        
        # Save to database
        await self._save_to_db(chat_id, profile, settings)
    
    def _serialize_profile_data(
        self,
        profile: ProtectionProfile,
        settings: ProfileSettings
    ) -> Dict:
        """Serialize profile and settings for Redis storage."""
        return {
            "profile": profile.value,
            "settings": settings.to_dict(),
        }
    
    def _deserialize_profile_data(
        self,
        data: Dict
    ) -> Tuple[ProtectionProfile, ProfileSettings]:
        """Deserialize profile and settings from Redis."""
        profile = ProtectionProfile(data.get("profile", "standard"))
        settings = ProfileSettings.from_dict(data.get("settings", {}))
        return profile, settings
    
    async def _load_from_db(
        self,
        chat_id: int
    ) -> Tuple[ProtectionProfile, ProfileSettings]:
        """Load profile and settings from database."""
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(ProtectionProfileConfig).filter_by(chat_id=chat_id)
            )
            db_record = result.scalar_one_or_none()
            
            if db_record is None:
                # Return default (Standard profile)
                return ProtectionProfile.STANDARD, PROFILE_PRESETS[ProtectionProfile.STANDARD]
            
            profile = ProtectionProfile(db_record.profile)
            
            # For preset profiles, use preset settings
            # For custom, use stored settings
            if profile != ProtectionProfile.CUSTOM:
                settings = PROFILE_PRESETS.get(profile, PROFILE_PRESETS[ProtectionProfile.STANDARD])
            else:
                settings = ProfileSettings(
                    anti_spam_links=db_record.anti_spam_links,
                    captcha_type=db_record.captcha_type,
                    profanity_allowed=db_record.profanity_allowed,
                    neural_ad_filter=db_record.neural_ad_filter,
                    block_forwards=db_record.block_forwards,
                    sticker_limit=db_record.sticker_limit,
                    mute_newcomers=db_record.mute_newcomers,
                    block_media_non_admin=db_record.block_media_non_admin,
                    aggressive_profanity=db_record.aggressive_profanity,
                )
            
            return profile, settings
    
    async def _save_to_db(
        self,
        chat_id: int,
        profile: ProtectionProfile,
        settings: ProfileSettings
    ) -> None:
        """Save profile and settings to database."""
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(
                select(ProtectionProfileConfig).filter_by(chat_id=chat_id)
            )
            db_record = result.scalar_one_or_none()
            
            if db_record is None:
                # Create new record
                db_record = ProtectionProfileConfig(
                    chat_id=chat_id,
                    profile=profile.value,
                    anti_spam_links=settings.anti_spam_links,
                    captcha_type=settings.captcha_type,
                    profanity_allowed=settings.profanity_allowed,
                    neural_ad_filter=settings.neural_ad_filter,
                    block_forwards=settings.block_forwards,
                    sticker_limit=settings.sticker_limit,
                    mute_newcomers=settings.mute_newcomers,
                    block_media_non_admin=settings.block_media_non_admin,
                    aggressive_profanity=settings.aggressive_profanity,
                )
                session.add(db_record)
            else:
                # Update existing record
                db_record.profile = profile.value
                db_record.anti_spam_links = settings.anti_spam_links
                db_record.captcha_type = settings.captcha_type
                db_record.profanity_allowed = settings.profanity_allowed
                db_record.neural_ad_filter = settings.neural_ad_filter
                db_record.block_forwards = settings.block_forwards
                db_record.sticker_limit = settings.sticker_limit
                db_record.mute_newcomers = settings.mute_newcomers
                db_record.block_media_non_admin = settings.block_media_non_admin
                db_record.aggressive_profanity = settings.aggressive_profanity
                db_record.updated_at = utc_now()
            
            await session.commit()


# Global service instance
protection_profile_manager = ProtectionProfileManager()
