"""Panic Mode Controller - Automatic Raid Protection.

This module provides the Panic Mode system for automatic detection and
response to raid attacks on Telegram chats.

**Feature: shield-economy-v65**
**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**
"""

import logging
import random
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Deque, Dict, List, Optional, Set, Tuple

from aiogram import Bot
from aiogram.types import ChatPermissions
from sqlalchemy import select, delete

from app.services.citadel import citadel_service, DEFCONLevel
from app.services.redis_client import redis_client
from app.utils import utc_now

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Panic mode activation thresholds
JOIN_THRESHOLD = 10  # Number of joins to trigger panic mode
JOIN_WINDOW_SECONDS = 10  # Time window for join detection

MESSAGE_THRESHOLD = 20  # Messages per second to trigger panic mode
MESSAGE_WINDOW_SECONDS = 1  # Time window for message flood detection

# Panic mode settings
PANIC_MODE_DURATION_MINUTES = 30  # How long panic mode lasts
NEW_USER_THRESHOLD_HOURS = 24  # Users joined within this period get restricted
RO_DURATION_MINUTES = 30  # Read-only duration for restricted users

# Redis key prefixes
REDIS_PANIC_PREFIX = "panic:"
REDIS_JOIN_PREFIX = "panic_joins:"
REDIS_MSG_PREFIX = "panic_msgs:"
REDIS_TTL = 3600  # 1 hour TTL for panic mode data


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class PanicModeState:
    """
    Current panic mode state for a chat.
    
    Attributes:
        chat_id: Telegram chat ID
        active: Whether panic mode is currently active
        activated_at: When panic mode was activated
        deactivates_at: When panic mode will automatically deactivate
        trigger_reason: What triggered panic mode ("mass_join" or "message_flood")
        restricted_users: Set of user IDs that have been restricted
    """
    chat_id: int
    active: bool = False
    activated_at: Optional[datetime] = None
    deactivates_at: Optional[datetime] = None
    trigger_reason: str = ""
    restricted_users: Set[int] = field(default_factory=set)


@dataclass
class CaptchaChallenge:
    """
    Captcha challenge for panic mode verification.
    
    Attributes:
        question: The math question to display
        answer: The correct answer
    """
    question: str
    answer: str


# ============================================================================
# Panic Mode Controller
# ============================================================================

class PanicModeController:
    """
    Controller for automatic panic mode activation and management.
    
    Provides methods for:
    - Detecting mass join raids (10+ joins in 10 seconds)
    - Detecting message flood attacks (20+ messages per second)
    - Activating and deactivating panic mode
    - Applying restrictions to recent users
    - Generating and verifying hard captchas
    
    Integrates with CitadelService for DEFCON level management.
    
    **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**
    """
    
    def __init__(self):
        """Initialize PanicModeController with in-memory tracking."""
        # In-memory tracking for join events
        self._join_events: Dict[int, Deque[datetime]] = defaultdict(deque)
        
        # In-memory tracking for message events (user_id -> timestamp)
        self._message_events: Dict[int, Deque[Tuple[int, datetime]]] = defaultdict(deque)
        
        # Panic mode state per chat
        self._panic_states: Dict[int, PanicModeState] = {}
        
        # Captcha answers storage (user_id, chat_id) -> answer
        self._captcha_answers: Dict[Tuple[int, int], str] = {}
    
    # =========================================================================
    # Trigger Detection Methods
    # =========================================================================
    
    def record_join(self, chat_id: int, user_id: int) -> None:
        """
        Record a user join event for raid detection.
        
        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID who joined
        """
        now = utc_now()
        self._join_events[chat_id].append(now)
        self._cleanup_old_join_events(chat_id, now)
        
        # Also record in CitadelService for its tracking
        citadel_service.record_join(chat_id, user_id)
    
    def record_message(self, chat_id: int, user_id: int) -> None:
        """
        Record a message event for flood detection.
        
        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID who sent the message
        """
        now = utc_now()
        self._message_events[chat_id].append((user_id, now))
        self._cleanup_old_message_events(chat_id, now)
    
    def check_join_trigger(self, chat_id: int) -> bool:
        """
        Check if mass join raid condition is met.
        
        Triggers when 10+ users join within 10 seconds.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            True if raid condition is detected
            
        **Validates: Requirements 6.1**
        """
        now = utc_now()
        self._cleanup_old_join_events(chat_id, now)
        
        join_count = len(self._join_events[chat_id])
        is_raid = join_count >= JOIN_THRESHOLD
        
        if is_raid:
            logger.warning(
                f"Mass join raid detected in chat {chat_id}: "
                f"{join_count} joins in {JOIN_WINDOW_SECONDS}s"
            )
        
        return is_raid
    
    def check_message_trigger(self, chat_id: int) -> bool:
        """
        Check if message flood condition is met.
        
        Triggers when 20+ messages per second from different users.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            True if flood condition is detected
            
        **Validates: Requirements 6.2**
        """
        now = utc_now()
        self._cleanup_old_message_events(chat_id, now)
        
        events = self._message_events[chat_id]
        
        # Count unique users in the window
        unique_users = set()
        for user_id, _ in events:
            unique_users.add(user_id)
        
        message_count = len(events)
        is_flood = message_count >= MESSAGE_THRESHOLD and len(unique_users) > 1
        
        if is_flood:
            logger.warning(
                f"Message flood detected in chat {chat_id}: "
                f"{message_count} messages from {len(unique_users)} users in {MESSAGE_WINDOW_SECONDS}s"
            )
        
        return is_flood
    
    # =========================================================================
    # Panic Mode Activation/Deactivation
    # =========================================================================
    
    async def activate_panic_mode(
        self,
        chat_id: int,
        reason: str,
        bot: Optional[Bot] = None
    ) -> PanicModeState:
        """
        Activate panic mode for a chat.
        
        This will:
        1. Set panic mode state to active
        2. Escalate DEFCON level via CitadelService
        3. Optionally apply restrictions to recent users
        
        Args:
            chat_id: Telegram chat ID
            reason: Trigger reason ("mass_join" or "message_flood")
            bot: Optional Bot instance for applying restrictions
            
        Returns:
            Updated PanicModeState
            
        **Validates: Requirements 6.1, 6.2**
        """
        now = utc_now()
        deactivates_at = now + timedelta(minutes=PANIC_MODE_DURATION_MINUTES)
        
        state = PanicModeState(
            chat_id=chat_id,
            active=True,
            activated_at=now,
            deactivates_at=deactivates_at,
            trigger_reason=reason,
            restricted_users=set()
        )
        
        self._panic_states[chat_id] = state
        
        # Save to Redis for persistence
        await self._save_panic_state(state)
        
        # Activate raid mode in CitadelService (escalates to DEFCON 3)
        await citadel_service.activate_raid_mode(
            chat_id,
            duration_minutes=PANIC_MODE_DURATION_MINUTES
        )
        
        logger.warning(
            f"Panic mode activated for chat {chat_id} due to {reason}. "
            f"Will deactivate at {deactivates_at}"
        )
        
        return state
    
    async def deactivate_panic_mode(self, chat_id: int) -> PanicModeState:
        """
        Deactivate panic mode for a chat.
        
        This will:
        1. Set panic mode state to inactive
        2. Deactivate raid mode in CitadelService
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            Updated PanicModeState
        """
        state = self._panic_states.get(chat_id)
        
        if state is None:
            state = PanicModeState(chat_id=chat_id)
        
        state.active = False
        state.deactivates_at = None
        
        self._panic_states[chat_id] = state
        
        # Save to Redis
        await self._save_panic_state(state)
        
        # Deactivate raid mode in CitadelService
        await citadel_service.deactivate_raid_mode(chat_id)
        
        logger.info(f"Panic mode deactivated for chat {chat_id}")
        
        return state
    
    async def is_panic_mode_active(self, chat_id: int) -> bool:
        """
        Check if panic mode is currently active for a chat.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            True if panic mode is active
        """
        state = await self.get_panic_state(chat_id)
        
        if not state.active:
            return False
        
        # Check if panic mode has expired
        now = utc_now()
        if state.deactivates_at and state.deactivates_at <= now:
            await self.deactivate_panic_mode(chat_id)
            return False
        
        return True
    
    async def get_panic_state(self, chat_id: int) -> PanicModeState:
        """
        Get current panic mode state for a chat.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            Current PanicModeState
        """
        # Check memory first
        if chat_id in self._panic_states:
            return self._panic_states[chat_id]
        
        # Try to load from Redis
        state = await self._load_panic_state(chat_id)
        self._panic_states[chat_id] = state
        
        return state
    
    # =========================================================================
    # Welcome Message Control
    # =========================================================================
    
    async def should_send_welcome(self, chat_id: int) -> bool:
        """
        Check if welcome messages should be sent.
        
        Welcome messages are silenced during panic mode.
        
        Args:
            chat_id: Telegram chat ID
            
        Returns:
            True if welcome messages should be sent
            
        **Validates: Requirements 6.3**
        """
        is_active = await self.is_panic_mode_active(chat_id)
        return not is_active
    
    # =========================================================================
    # User Restriction Methods
    # =========================================================================
    
    async def apply_lockdown(
        self,
        chat_id: int,
        bot: Bot,
        recent_user_ids: Optional[List[int]] = None
    ) -> List[int]:
        """
        Apply RO restrictions to recent users during panic mode.
        
        Restricts users who joined within the last 24 hours.
        
        Args:
            chat_id: Telegram chat ID
            bot: Bot instance for applying restrictions
            recent_user_ids: Optional list of user IDs to restrict
            
        Returns:
            List of user IDs that were restricted
            
        **Validates: Requirements 6.4**
        """
        state = await self.get_panic_state(chat_id)
        
        if not state.active:
            return []
        
        restricted = []
        
        if recent_user_ids:
            for user_id in recent_user_ids:
                success = await self._restrict_user(chat_id, user_id, bot)
                if success:
                    restricted.append(user_id)
                    state.restricted_users.add(user_id)
        
        # Update state
        self._panic_states[chat_id] = state
        await self._save_panic_state(state)
        
        logger.info(
            f"Applied lockdown in chat {chat_id}: "
            f"{len(restricted)} users restricted"
        )
        
        return restricted
    
    async def is_user_restricted(
        self,
        chat_id: int,
        user_id: int
    ) -> bool:
        """
        Check if a user is restricted due to panic mode.
        
        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID
            
        Returns:
            True if user is restricted
        """
        state = await self.get_panic_state(chat_id)
        return user_id in state.restricted_users
    
    async def _restrict_user(
        self,
        chat_id: int,
        user_id: int,
        bot: Bot
    ) -> bool:
        """
        Apply RO restriction to a single user.
        
        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID
            bot: Bot instance
            
        Returns:
            True if restriction was applied successfully
        """
        try:
            until_date = utc_now() + timedelta(minutes=RO_DURATION_MINUTES)
            
            permissions = ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False
            )
            
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=permissions,
                until_date=until_date
            )
            
            logger.debug(f"Restricted user {user_id} in chat {chat_id} until {until_date}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restrict user {user_id} in chat {chat_id}: {e}")
            return False
    
    # =========================================================================
    # Captcha Methods
    # =========================================================================
    
    def generate_hard_captcha(self) -> CaptchaChallenge:
        """
        Generate a hard captcha (math problem).
        
        Returns:
            CaptchaChallenge with question and answer
            
        **Validates: Requirements 6.5**
        """
        # Generate two random numbers for addition/subtraction
        a = random.randint(10, 50)
        b = random.randint(1, 20)
        
        # Randomly choose operation
        if random.choice([True, False]):
            # Addition
            question = f"{a} + {b} = ?"
            answer = str(a + b)
        else:
            # Subtraction (ensure positive result)
            question = f"{a} - {b} = ?"
            answer = str(a - b)
        
        return CaptchaChallenge(question=question, answer=answer)
    
    def store_captcha_answer(
        self,
        user_id: int,
        chat_id: int,
        answer: str
    ) -> None:
        """
        Store the expected captcha answer for a user in memory cache.
        
        For persistent storage, use store_captcha_answer_db() instead.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            answer: Expected answer
        """
        self._captcha_answers[(user_id, chat_id)] = answer
    
    async def store_captcha_answer_db(
        self,
        user_id: int,
        chat_id: int,
        answer: str,
        reason: str = "panic_mode_captcha"
    ) -> bool:
        """
        Store the expected captcha answer in SilentBan database record.
        
        Creates or updates a SilentBan record with the captcha answer.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            answer: Expected captcha answer
            reason: Reason for the silent ban
            
        Returns:
            True if stored successfully
            
        **Validates: Requirements 6.5**
        """
        from app.database.session import get_session
        from app.database.models import SilentBan
        
        try:
            async with get_session()() as session:
                # Check if record exists
                stmt = select(SilentBan).where(
                    SilentBan.user_id == user_id,
                    SilentBan.chat_id == chat_id
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()
                
                if existing:
                    # Update existing record
                    existing.captcha_answer = answer
                    existing.reason = reason
                else:
                    # Create new record
                    silent_ban = SilentBan(
                        user_id=user_id,
                        chat_id=chat_id,
                        reason=reason,
                        captcha_answer=answer
                    )
                    session.add(silent_ban)
                
                await session.commit()
                
                # Also store in memory cache for fast access
                self._captcha_answers[(user_id, chat_id)] = answer
                
                logger.debug(
                    f"Stored captcha answer for user {user_id} in chat {chat_id}"
                )
                return True
                
        except Exception as e:
            logger.error(f"Failed to store captcha answer in DB: {e}")
            # Fall back to memory-only storage
            self._captcha_answers[(user_id, chat_id)] = answer
            return False
    
    def verify_captcha(
        self,
        user_id: int,
        chat_id: int,
        answer: str
    ) -> bool:
        """
        Verify a user's captcha answer from memory cache.
        
        For database verification, use verify_captcha_db() instead.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            answer: User's answer
            
        Returns:
            True if answer is correct
            
        **Validates: Requirements 6.5**
        """
        expected = self._captcha_answers.get((user_id, chat_id))
        
        if expected is None:
            return False
        
        # Clean up the answer
        answer = answer.strip()
        
        is_correct = answer == expected
        
        if is_correct:
            # Remove the stored answer
            del self._captcha_answers[(user_id, chat_id)]
        
        return is_correct
    
    async def verify_captcha_db(
        self,
        user_id: int,
        chat_id: int,
        answer: str
    ) -> bool:
        """
        Verify a user's captcha answer against the SilentBan database record.
        
        If verification succeeds, removes the SilentBan record.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            answer: User's answer
            
        Returns:
            True if answer is correct
            
        **Validates: Requirements 6.5**
        """
        from app.database.session import get_session
        from app.database.models import SilentBan
        
        # First check memory cache for fast path
        cached_answer = self._captcha_answers.get((user_id, chat_id))
        if cached_answer is not None:
            answer_clean = answer.strip()
            if answer_clean == cached_answer:
                # Remove from cache
                del self._captcha_answers[(user_id, chat_id)]
                # Also remove from database
                await self._remove_silent_ban_db(user_id, chat_id)
                return True
            return False
        
        # Fall back to database lookup
        try:
            async with get_session()() as session:
                stmt = select(SilentBan).where(
                    SilentBan.user_id == user_id,
                    SilentBan.chat_id == chat_id
                )
                result = await session.execute(stmt)
                silent_ban = result.scalar_one_or_none()
                
                if silent_ban is None or silent_ban.captcha_answer is None:
                    return False
                
                answer_clean = answer.strip()
                is_correct = answer_clean == silent_ban.captcha_answer
                
                if is_correct:
                    # Remove the silent ban record
                    await session.delete(silent_ban)
                    await session.commit()
                    logger.info(
                        f"User {user_id} passed captcha in chat {chat_id}, "
                        f"silent ban removed"
                    )
                
                return is_correct
                
        except Exception as e:
            logger.error(f"Failed to verify captcha from DB: {e}")
            return False
    
    async def _remove_silent_ban_db(
        self,
        user_id: int,
        chat_id: int
    ) -> bool:
        """
        Remove a SilentBan record from the database.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            
        Returns:
            True if removed successfully
        """
        from app.database.session import get_session
        from app.database.models import SilentBan
        
        try:
            async with get_session()() as session:
                stmt = delete(SilentBan).where(
                    SilentBan.user_id == user_id,
                    SilentBan.chat_id == chat_id
                )
                await session.execute(stmt)
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to remove silent ban from DB: {e}")
            return False
    
    async def get_captcha_answer_db(
        self,
        user_id: int,
        chat_id: int
    ) -> Optional[str]:
        """
        Get the expected captcha answer from the SilentBan database record.
        
        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            
        Returns:
            Expected captcha answer or None if not found
        """
        from app.database.session import get_session
        from app.database.models import SilentBan
        
        # First check memory cache
        cached = self._captcha_answers.get((user_id, chat_id))
        if cached is not None:
            return cached
        
        # Fall back to database
        try:
            async with get_session()() as session:
                stmt = select(SilentBan).where(
                    SilentBan.user_id == user_id,
                    SilentBan.chat_id == chat_id
                )
                result = await session.execute(stmt)
                silent_ban = result.scalar_one_or_none()
                
                if silent_ban and silent_ban.captcha_answer:
                    # Cache for future lookups
                    self._captcha_answers[(user_id, chat_id)] = silent_ban.captcha_answer
                    return silent_ban.captcha_answer
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to get captcha answer from DB: {e}")
            return None
    
    async def unrestrict_user_on_captcha(
        self,
        chat_id: int,
        user_id: int,
        bot: Bot
    ) -> bool:
        """
        Remove restrictions from a user after successful captcha.
        
        Args:
            chat_id: Telegram chat ID
            user_id: Telegram user ID
            bot: Bot instance
            
        Returns:
            True if unrestriction was successful
        """
        try:
            # Restore full permissions
            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=False
            )
            
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=permissions
            )
            
            # Remove from restricted users set
            state = await self.get_panic_state(chat_id)
            state.restricted_users.discard(user_id)
            self._panic_states[chat_id] = state
            await self._save_panic_state(state)
            
            logger.info(f"Unrestricted user {user_id} in chat {chat_id} after captcha")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unrestrict user {user_id} in chat {chat_id}: {e}")
            return False
    
    # =========================================================================
    # Private Helper Methods - Event Cleanup
    # =========================================================================
    
    def _cleanup_old_join_events(self, chat_id: int, now: datetime) -> None:
        """Remove join events outside the detection window."""
        events = self._join_events[chat_id]
        cutoff = now - timedelta(seconds=JOIN_WINDOW_SECONDS)
        
        while events and events[0] < cutoff:
            events.popleft()
    
    def _cleanup_old_message_events(self, chat_id: int, now: datetime) -> None:
        """Remove message events outside the detection window."""
        events = self._message_events[chat_id]
        cutoff = now - timedelta(seconds=MESSAGE_WINDOW_SECONDS)
        
        while events and events[0][1] < cutoff:
            events.popleft()
    
    # =========================================================================
    # Private Helper Methods - Redis Storage
    # =========================================================================
    
    async def _save_panic_state(self, state: PanicModeState) -> None:
        """Save panic state to Redis."""
        if not redis_client.is_available:
            return
        
        key = f"{REDIS_PANIC_PREFIX}{state.chat_id}"
        data = {
            "active": state.active,
            "activated_at": state.activated_at.isoformat() if state.activated_at else None,
            "deactivates_at": state.deactivates_at.isoformat() if state.deactivates_at else None,
            "trigger_reason": state.trigger_reason,
            "restricted_users": list(state.restricted_users)
        }
        
        await redis_client.set_json(key, data, ex=REDIS_TTL)
    
    async def _load_panic_state(self, chat_id: int) -> PanicModeState:
        """Load panic state from Redis."""
        if not redis_client.is_available:
            return PanicModeState(chat_id=chat_id)
        
        key = f"{REDIS_PANIC_PREFIX}{chat_id}"
        data = await redis_client.get_json(key)
        
        if data is None:
            return PanicModeState(chat_id=chat_id)
        
        activated_at = None
        if data.get("activated_at"):
            activated_at = datetime.fromisoformat(data["activated_at"])
        
        deactivates_at = None
        if data.get("deactivates_at"):
            deactivates_at = datetime.fromisoformat(data["deactivates_at"])
        
        return PanicModeState(
            chat_id=chat_id,
            active=data.get("active", False),
            activated_at=activated_at,
            deactivates_at=deactivates_at,
            trigger_reason=data.get("trigger_reason", ""),
            restricted_users=set(data.get("restricted_users", []))
        )
    
    def invalidate_cache(self, chat_id: int) -> None:
        """Invalidate cached state for a chat."""
        self._panic_states.pop(chat_id, None)
        self._join_events.pop(chat_id, None)
        self._message_events.pop(chat_id, None)


# Global service instance
panic_mode_controller = PanicModeController()
