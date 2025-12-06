"""DEFCON Filter Middleware for Citadel Protection System.

This middleware applies DEFCON-level restrictions to incoming messages,
including profanity filtering, sticker limits, forward blocking, and
new user restrictions based on the current protection level.

**Feature: fortress-update**
**Validates: Requirements 1.2, 1.3, 1.4**
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Awaitable, Optional

from aiogram import BaseMiddleware
from aiogram.types import Message, ChatPermissions

logger = logging.getLogger(__name__)

# Sticker tracking per user per chat
_sticker_counts: Dict[tuple, list] = {}  # (user_id, chat_id) -> [timestamps]
STICKER_WINDOW_SECONDS = 60


class DEFCONFilterMiddleware(BaseMiddleware):
    """
    Middleware that applies DEFCON-level restrictions to messages.
    
    Restrictions by level:
    - DEFCON 1 (Peaceful): Anti-spam link filtering only
    - DEFCON 2 (Strict): + Profanity filter, sticker limit (3), forward blocking
    - DEFCON 3 (Martial Law): + Full media/link restriction for new users
    """
    
    def __init__(self, citadel_service=None):
        """
        Initialize DEFCON filter middleware.
        
        Args:
            citadel_service: Optional CitadelService instance. If not provided,
                           will import the global instance.
        """
        self._citadel_service = citadel_service
        super().__init__()
    
    @property
    def citadel_service(self):
        """Lazy load citadel service to avoid circular imports."""
        if self._citadel_service is None:
            from app.services.citadel import citadel_service
            self._citadel_service = citadel_service
        return self._citadel_service
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        """
        Process message through DEFCON filters.
        
        Args:
            handler: Next handler in the chain
            event: Incoming message
            data: Handler data
            
        Returns:
            Handler result or None if message was blocked
        """
        # Skip non-message events and service messages
        if not isinstance(event, Message):
            return await handler(event, data)
        
        # Skip service messages
        if event.content_type in ['new_chat_members', 'left_chat_member', 
                                   'new_chat_title', 'new_chat_photo',
                                   'delete_chat_photo', 'pinned_message']:
            return await handler(event, data)
        
        # Skip private chats
        if event.chat.type == 'private':
            return await handler(event, data)
        
        chat_id = event.chat.id
        user_id = event.from_user.id if event.from_user else None
        
        if user_id is None:
            return await handler(event, data)
        
        try:
            # Get DEFCON config for this chat
            config = await self.citadel_service.get_config(chat_id)
            
            # Store config in data for downstream handlers
            data['defcon_config'] = config
            data['defcon_level'] = config.defcon_level.value
            
            # Apply DEFCON-level restrictions
            blocked = await self._apply_restrictions(event, config, user_id, chat_id)
            
            if blocked:
                return None  # Message was blocked, don't continue
            
        except Exception as e:
            logger.error(f"DEFCON filter error for chat {chat_id}: {e}")
            # On error, allow message through (fail open)
        
        return await handler(event, data)
    
    async def _apply_restrictions(
        self,
        event: Message,
        config,
        user_id: int,
        chat_id: int
    ) -> bool:
        """
        Apply DEFCON-level restrictions to a message.
        
        Args:
            event: Incoming message
            config: CitadelConfigData for the chat
            user_id: User ID
            chat_id: Chat ID
            
        Returns:
            True if message was blocked, False otherwise
        """
        from app.services.citadel import DEFCONLevel
        
        # DEFCON 2+ restrictions
        if config.defcon_level >= DEFCONLevel.STRICT:
            # Check forward blocking
            if config.forward_block_enabled and await self._is_forward(event):
                await self._handle_blocked_forward(event)
                return True
            
            # Check sticker limit
            if config.sticker_limit > 0 and event.sticker:
                if await self._check_sticker_limit(event, config.sticker_limit, user_id, chat_id):
                    return True
            
            # Check profanity (if enabled)
            if config.profanity_filter_enabled:
                if await self._check_profanity(event):
                    await self._handle_profanity(event)
                    return True
        
        # DEFCON 3 / Raid mode restrictions
        if config.defcon_level >= DEFCONLevel.MARTIAL_LAW or config.is_raid_mode_active:
            # Check if new user trying to send restricted content
            if self.citadel_service.is_new_user(user_id, chat_id, config.new_user_restriction_hours):
                if await self._is_restricted_content(event):
                    await self._handle_new_user_restriction(event)
                    return True
        
        return False
    
    async def _is_forward(self, event: Message) -> bool:
        """Check if message is a forward from a channel."""
        return event.forward_from_chat is not None or event.forward_from is not None
    
    async def _handle_blocked_forward(self, event: Message) -> None:
        """Handle a blocked forward message."""
        try:
            await event.delete()
            logger.info(f"Blocked forward from user {event.from_user.id} in chat {event.chat.id}")
        except Exception as e:
            logger.error(f"Failed to delete forward: {e}")
    
    async def _check_sticker_limit(
        self,
        event: Message,
        limit: int,
        user_id: int,
        chat_id: int
    ) -> bool:
        """
        Check if user has exceeded sticker limit.
        
        Args:
            event: Sticker message
            limit: Maximum consecutive stickers allowed
            user_id: User ID
            chat_id: Chat ID
            
        Returns:
            True if limit exceeded and message should be blocked
        """
        key = (user_id, chat_id)
        now = datetime.utcnow()
        
        # Initialize or clean up old entries
        if key not in _sticker_counts:
            _sticker_counts[key] = []
        
        # Remove old timestamps
        cutoff = now - timedelta(seconds=STICKER_WINDOW_SECONDS)
        _sticker_counts[key] = [t for t in _sticker_counts[key] if t > cutoff]
        
        # Add current sticker
        _sticker_counts[key].append(now)
        
        # Check if limit exceeded
        if len(_sticker_counts[key]) > limit:
            try:
                await event.delete()
                await event.answer(
                    f"⚠️ Превышен лимит стикеров ({limit} подряд). "
                    f"Подожди немного перед отправкой следующего."
                )
                logger.info(f"Sticker limit exceeded by user {user_id} in chat {chat_id}")
            except Exception as e:
                logger.error(f"Failed to handle sticker limit: {e}")
            return True
        
        return False
    
    async def _check_profanity(self, event: Message) -> bool:
        """
        Check message for profanity.
        
        This is a basic implementation. In production, this would integrate
        with the toxicity analyzer for more sophisticated detection.
        
        Args:
            event: Message to check
            
        Returns:
            True if profanity detected
        """
        text = event.text or event.caption or ""
        if not text:
            return False
        
        # Basic profanity patterns (Russian)
        # In production, this would use a more comprehensive list or ML model
        profanity_patterns = [
            r'\b(бля|хуй|пизд|ебан|сук[аи]|мудак|пидор)\w*\b',
        ]
        
        text_lower = text.lower()
        for pattern in profanity_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        
        return False
    
    async def _handle_profanity(self, event: Message) -> None:
        """Handle a message with profanity."""
        try:
            await event.delete()
            await event.answer(
                f"⚠️ @{event.from_user.username or event.from_user.id}, "
                f"сообщение удалено за нарушение правил чата."
            )
            logger.info(f"Profanity deleted from user {event.from_user.id} in chat {event.chat.id}")
        except Exception as e:
            logger.error(f"Failed to handle profanity: {e}")
    
    async def _is_restricted_content(self, event: Message) -> bool:
        """
        Check if message contains restricted content for new users.
        
        Restricted content includes:
        - Links/URLs
        - Media (photos, videos, documents)
        - Forwards
        
        Args:
            event: Message to check
            
        Returns:
            True if message contains restricted content
        """
        # Check for forwards
        if event.forward_from or event.forward_from_chat:
            return True
        
        # Check for media
        if event.photo or event.video or event.document or event.animation:
            return True
        
        # Check for links in text
        text = event.text or event.caption or ""
        if text:
            url_pattern = r'https?://[^\s]+'
            if re.search(url_pattern, text):
                return True
            
            # Check for Telegram links
            tg_pattern = r't\.me/[^\s]+'
            if re.search(tg_pattern, text):
                return True
        
        # Check for entities with URLs
        entities = event.entities or event.caption_entities or []
        for entity in entities:
            if entity.type in ['url', 'text_link']:
                return True
        
        return False
    
    async def _handle_new_user_restriction(self, event: Message) -> None:
        """Handle restricted content from a new user."""
        try:
            await event.delete()
            await event.answer(
                f"⚠️ @{event.from_user.username or event.from_user.id}, "
                f"новые участники не могут отправлять ссылки и медиа. "
                f"Подожди немного, чтобы получить полные права."
            )
            logger.info(
                f"Restricted content from new user {event.from_user.id} "
                f"deleted in chat {event.chat.id}"
            )
        except Exception as e:
            logger.error(f"Failed to handle new user restriction: {e}")


# Factory function for creating middleware
def create_defcon_middleware(citadel_service=None) -> DEFCONFilterMiddleware:
    """
    Create a DEFCON filter middleware instance.
    
    Args:
        citadel_service: Optional CitadelService instance
        
    Returns:
        DEFCONFilterMiddleware instance
    """
    return DEFCONFilterMiddleware(citadel_service)
