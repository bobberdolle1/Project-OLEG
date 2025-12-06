"""Permission Checker Service - Bot Permission Verification.

This module provides the PermissionChecker service for verifying bot permissions
before moderation actions and silently reporting missing permissions to administrators.

**Feature: shield-economy-v65**
**Validates: Requirements 7.1, 7.2, 7.3, 7.4**
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from aiogram import Bot
from aiogram.types import ChatMemberAdministrator

from app.utils import utc_now

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

CACHE_TTL_SECONDS = 60  # Permission cache TTL (Requirement 7.4)


# ============================================================================
# Enums
# ============================================================================

class ModerationAction(str, Enum):
    """Types of moderation actions that require permission checks."""
    DELETE_MESSAGE = "delete_messages"
    RESTRICT_MEMBER = "restrict_members"
    BAN_USER = "ban_users"
    PIN_MESSAGE = "pin_messages"
    INVITE_USERS = "invite_users"
    MANAGE_CHAT = "manage_chat"


# Action display names for notifications (in Russian)
ACTION_DISPLAY_NAMES = {
    ModerationAction.DELETE_MESSAGE: "удаление сообщений",
    ModerationAction.RESTRICT_MEMBER: "ограничение пользователей",
    ModerationAction.BAN_USER: "бан пользователей",
    ModerationAction.PIN_MESSAGE: "закрепление сообщений",
    ModerationAction.INVITE_USERS: "приглашение пользователей",
    ModerationAction.MANAGE_CHAT: "управление чатом",
}


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class BotPermissions:
    """
    Bot permissions in a specific chat.
    
    Attributes:
        chat_id: Telegram chat ID
        can_delete_messages: Permission to delete messages
        can_restrict_members: Permission to restrict/mute users
        can_ban_users: Permission to ban users (promote_members in Telegram API)
        can_pin_messages: Permission to pin messages
        can_invite_users: Permission to invite users
        can_manage_chat: Permission to manage chat settings
        cached_at: When these permissions were cached
    """
    chat_id: int
    can_delete_messages: bool = False
    can_restrict_members: bool = False
    can_ban_users: bool = False
    can_pin_messages: bool = False
    can_invite_users: bool = False
    can_manage_chat: bool = False
    cached_at: datetime = field(default_factory=utc_now)
    
    def has_permission(self, action: ModerationAction) -> bool:
        """
        Check if bot has permission for a specific action.
        
        Args:
            action: The moderation action to check
            
        Returns:
            True if bot has the required permission
        """
        permission_map = {
            ModerationAction.DELETE_MESSAGE: self.can_delete_messages,
            ModerationAction.RESTRICT_MEMBER: self.can_restrict_members,
            ModerationAction.BAN_USER: self.can_ban_users,
            ModerationAction.PIN_MESSAGE: self.can_pin_messages,
            ModerationAction.INVITE_USERS: self.can_invite_users,
            ModerationAction.MANAGE_CHAT: self.can_manage_chat,
        }
        return permission_map.get(action, False)
    
    def get_missing_permissions(self, actions: List[ModerationAction]) -> List[ModerationAction]:
        """
        Get list of missing permissions for given actions.
        
        Args:
            actions: List of actions to check
            
        Returns:
            List of actions for which bot lacks permissions
        """
        return [action for action in actions if not self.has_permission(action)]
    
    def is_cache_valid(self) -> bool:
        """
        Check if cached permissions are still valid.
        
        Returns:
            True if cache is still valid (within TTL)
        """
        age = utc_now() - self.cached_at
        return age < timedelta(seconds=CACHE_TTL_SECONDS)


@dataclass
class PermissionCheckResult:
    """
    Result of a permission check.
    
    Attributes:
        allowed: Whether the action is allowed
        missing_permissions: List of missing permissions if not allowed
        message: Optional message explaining the result
    """
    allowed: bool
    missing_permissions: List[ModerationAction] = field(default_factory=list)
    message: Optional[str] = None


# ============================================================================
# Permission Checker Service
# ============================================================================

class PermissionChecker:
    """
    Service for checking bot permissions before moderation actions.
    
    This service:
    - Verifies bot permissions via get_chat_member API (Requirement 7.1)
    - Caches permissions for 60 seconds (Requirement 7.4)
    - Silently reports missing permissions to administrators (Requirement 7.2)
    - Prevents threatening messages when bot lacks permissions (Requirement 7.3)
    
    Usage:
        checker = PermissionChecker()
        
        # Check before moderation action
        result = await checker.can_perform_action(chat_id, ModerationAction.BAN_USER, bot)
        if not result.allowed:
            await checker.report_missing_permission(chat_id, ModerationAction.BAN_USER, bot)
            return  # Don't send threatening message
    """
    
    def __init__(self):
        """Initialize PermissionChecker with empty cache."""
        self._cache: Dict[int, BotPermissions] = {}
    
    # =========================================================================
    # Permission Checking (Requirements 7.1, 7.4)
    # =========================================================================
    
    async def check_permissions(
        self,
        chat_id: int,
        bot: Bot
    ) -> BotPermissions:
        """
        Check and cache bot permissions for a chat.
        
        **Validates: Requirements 7.1, 7.4**
        WHEN OLEG_Bot attempts a moderation action THEN OLEG_Bot SHALL first
        verify its permissions via get_chat_member API.
        WHEN OLEG_Bot's permissions change THEN OLEG_Bot SHALL update its
        cached permissions within 60 seconds.
        
        Args:
            chat_id: Telegram chat ID
            bot: Telegram Bot instance
            
        Returns:
            BotPermissions with current permission state
        """
        # Check cache first
        if chat_id in self._cache:
            cached = self._cache[chat_id]
            if cached.is_cache_valid():
                logger.debug(f"Using cached permissions for chat {chat_id}")
                return cached
        
        # Fetch fresh permissions from Telegram API
        permissions = await self._fetch_permissions(chat_id, bot)
        
        # Update cache
        self._cache[chat_id] = permissions
        
        return permissions
    
    async def _fetch_permissions(
        self,
        chat_id: int,
        bot: Bot
    ) -> BotPermissions:
        """
        Fetch bot permissions from Telegram API.
        
        Args:
            chat_id: Telegram chat ID
            bot: Telegram Bot instance
            
        Returns:
            BotPermissions with fetched permission state
        """
        try:
            bot_member = await bot.get_chat_member(chat_id, bot.id)
            
            # Check if bot is an administrator
            if isinstance(bot_member, ChatMemberAdministrator):
                return BotPermissions(
                    chat_id=chat_id,
                    can_delete_messages=bot_member.can_delete_messages or False,
                    can_restrict_members=bot_member.can_restrict_members or False,
                    can_ban_users=bot_member.can_restrict_members or False,  # Ban requires restrict permission
                    can_pin_messages=bot_member.can_pin_messages or False,
                    can_invite_users=bot_member.can_invite_users or False,
                    can_manage_chat=bot_member.can_manage_chat or False,
                    cached_at=utc_now(),
                )
            
            # Bot is not an administrator - no permissions
            logger.warning(f"Bot is not an administrator in chat {chat_id}")
            return BotPermissions(chat_id=chat_id, cached_at=utc_now())
            
        except Exception as e:
            logger.error(f"Failed to fetch bot permissions for chat {chat_id}: {e}")
            # Return empty permissions on error (fail-safe)
            return BotPermissions(chat_id=chat_id, cached_at=utc_now())
    
    async def can_perform_action(
        self,
        chat_id: int,
        action: ModerationAction,
        bot: Bot
    ) -> bool:
        """
        Check if bot can perform a specific moderation action.
        
        **Validates: Requirements 7.1**
        WHEN OLEG_Bot attempts a moderation action (mute/ban/delete) THEN
        OLEG_Bot SHALL first verify its permissions via get_chat_member API.
        
        Args:
            chat_id: Telegram chat ID
            action: The moderation action to check
            bot: Telegram Bot instance
            
        Returns:
            True if bot has permission for the action, False otherwise
        """
        permissions = await self.check_permissions(chat_id, bot)
        return permissions.has_permission(action)
    
    async def check_action_with_details(
        self,
        chat_id: int,
        action: ModerationAction,
        bot: Bot
    ) -> PermissionCheckResult:
        """
        Check if bot can perform a specific moderation action with detailed result.
        
        This is an extended version of can_perform_action that returns
        detailed information about missing permissions.
        
        Args:
            chat_id: Telegram chat ID
            action: The moderation action to check
            bot: Telegram Bot instance
            
        Returns:
            PermissionCheckResult indicating if action is allowed with details
        """
        permissions = await self.check_permissions(chat_id, bot)
        
        if permissions.has_permission(action):
            return PermissionCheckResult(allowed=True)
        
        action_name = ACTION_DISPLAY_NAMES.get(action, str(action))
        return PermissionCheckResult(
            allowed=False,
            missing_permissions=[action],
            message=f"У меня нет прав на {action_name}"
        )
    
    async def can_perform_actions(
        self,
        chat_id: int,
        actions: List[ModerationAction],
        bot: Bot
    ) -> PermissionCheckResult:
        """
        Check if bot can perform multiple moderation actions.
        
        Args:
            chat_id: Telegram chat ID
            actions: List of moderation actions to check
            bot: Telegram Bot instance
            
        Returns:
            PermissionCheckResult indicating if all actions are allowed
        """
        permissions = await self.check_permissions(chat_id, bot)
        missing = permissions.get_missing_permissions(actions)
        
        if not missing:
            return PermissionCheckResult(allowed=True)
        
        missing_names = [ACTION_DISPLAY_NAMES.get(a, str(a)) for a in missing]
        return PermissionCheckResult(
            allowed=False,
            missing_permissions=missing,
            message=f"У меня нет прав на: {', '.join(missing_names)}"
        )
    
    # =========================================================================
    # Missing Permission Reporting (Requirement 7.2)
    # =========================================================================
    
    async def report_missing_permission(
        self,
        chat_id: int,
        action: ModerationAction,
        bot: Bot,
        admin_ids: Optional[List[int]] = None
    ) -> None:
        """
        Silently report missing permission to administrators.
        
        **Validates: Requirements 7.2**
        WHEN OLEG_Bot lacks required permissions for an action THEN OLEG_Bot
        SHALL silently report to administrators "У меня нет прав на [action],
        сделайте что-нибудь!"
        
        Args:
            chat_id: Telegram chat ID where permission is missing
            action: The action that requires permission
            bot: Telegram Bot instance
            admin_ids: Optional list of admin user IDs to notify.
                      If not provided, will fetch from chat.
        """
        action_name = ACTION_DISPLAY_NAMES.get(action, str(action))
        message = f"⚠️ У меня нет прав на {action_name}, сделайте что-нибудь!"
        
        # Get admin IDs if not provided
        if admin_ids is None:
            admin_ids = await self._get_chat_admin_ids(chat_id, bot)
        
        if not admin_ids:
            logger.warning(f"No admins found to notify about missing permission in chat {chat_id}")
            return
        
        # Send notification to each admin via private message
        for admin_id in admin_ids:
            try:
                # Try to get chat title for context
                try:
                    chat = await bot.get_chat(chat_id)
                    chat_title = chat.title or f"Chat {chat_id}"
                except Exception:
                    chat_title = f"Chat {chat_id}"
                
                full_message = f"🔔 Чат: {chat_title}\n\n{message}"
                await bot.send_message(admin_id, full_message)
                logger.info(f"Notified admin {admin_id} about missing permission in chat {chat_id}")
            except Exception as e:
                # Admin may have blocked the bot or never started a conversation
                logger.debug(f"Could not notify admin {admin_id}: {e}")
                continue
    
    async def _get_chat_admin_ids(
        self,
        chat_id: int,
        bot: Bot
    ) -> List[int]:
        """
        Get list of administrator user IDs for a chat.
        
        Args:
            chat_id: Telegram chat ID
            bot: Telegram Bot instance
            
        Returns:
            List of admin user IDs (excluding bots)
        """
        try:
            admins = await bot.get_chat_administrators(chat_id)
            # Filter out bots and return user IDs
            return [
                admin.user.id
                for admin in admins
                if not admin.user.is_bot
            ]
        except Exception as e:
            logger.error(f"Failed to get admins for chat {chat_id}: {e}")
            return []
    
    # =========================================================================
    # Cache Management
    # =========================================================================
    
    def invalidate_cache(self, chat_id: int) -> None:
        """
        Invalidate cached permissions for a chat.
        
        Call this when you know permissions have changed.
        
        Args:
            chat_id: Telegram chat ID to invalidate
        """
        self._cache.pop(chat_id, None)
        logger.debug(f"Invalidated permission cache for chat {chat_id}")
    
    def clear_cache(self) -> None:
        """Clear all cached permissions."""
        self._cache.clear()
        logger.debug("Cleared all permission cache")
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def should_send_threat(
        self,
        permission_result: PermissionCheckResult
    ) -> bool:
        """
        Determine if a threatening message should be sent to violator.
        
        **Validates: Requirements 7.3**
        WHEN OLEG_Bot lacks permissions THEN OLEG_Bot SHALL NOT send
        threatening messages to violators.
        
        Args:
            permission_result: Result from can_perform_action
            
        Returns:
            True if threat can be sent (bot has permissions), False otherwise
        """
        return permission_result.allowed


# Global service instance
permission_checker = PermissionChecker()
