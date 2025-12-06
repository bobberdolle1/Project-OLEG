"""Toxicity filter middleware for detecting and handling toxic messages.

Fortress Update: Integrated with CitadelService for DEFCON-aware moderation
and ReputationService for tracking user behavior.

**Feature: fortress-update**
**Validates: Requirements 2.2, 4.3, 4.4, 15.3**
"""

import logging
from typing import Callable, Awaitable, Dict, Any
from aiogram import BaseMiddleware
from aiogram.types import Message
from datetime import timedelta

from app.database.session import get_session
from app.services.toxicity_analyzer import (
    analyze_toxicity,
    get_action_for_score,
    log_incident,
    ModerationAction,
    ToxicityResult,
)
from app.services.citadel import citadel_service, DEFCONLevel
from app.services.reputation import reputation_service
from app.services.notifications import notification_service
from app.config import settings

logger = logging.getLogger(__name__)


class ToxicityFilterMiddleware(BaseMiddleware):
    """
    Middleware for AI-powered toxicity detection and moderation.
    
    Integrates with:
    - CitadelService: Gets current DEFCON level for action mapping
    - ReputationService: Applies reputation penalties for violations
    - ToxicityAnalyzer: Performs AI-based toxicity analysis
    - NotificationService: Sends toxicity warnings to chat owners
    
    **Validates: Requirements 2.2, 4.3, 4.4, 15.3**
    """
    
    # Track incident counts per chat for periodic toxicity checks
    _incident_counts: Dict[int, int] = {}
    # Check toxicity increase every N incidents
    _check_interval: int = 10
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        # Skip if no text or toxicity analysis is disabled
        if not event.text or not settings.toxicity_analysis_enabled:
            return await handler(event, data)
        
        # Skip private chats (only moderate group chats)
        if event.chat.type == "private":
            return await handler(event, data)
        
        chat_id = event.chat.id
        user_id = event.from_user.id
        
        # Get current DEFCON level for this chat
        try:
            citadel_config = await citadel_service.get_config(chat_id)
            defcon_level = citadel_config.defcon_level
        except Exception as e:
            logger.warning(f"Failed to get DEFCON level for chat {chat_id}: {e}")
            defcon_level = DEFCONLevel.PEACEFUL
        
        # Analyze toxicity
        async_session = get_session()
        async with async_session() as session:
            toxicity_result = await analyze_toxicity(session, event.text)
        
        # Determine action based on score and DEFCON level
        action = get_action_for_score(
            toxicity_result.score,
            defcon_level,
            settings.toxicity_threshold
        )
        
        # If no action needed, continue to handler
        if action == ModerationAction.NONE:
            return await handler(event, data)
        
        # Handle toxic message based on action
        await self._handle_toxic_message(
            event=event,
            result=toxicity_result,
            action=action,
            defcon_level=defcon_level
        )
        
        # Don't continue to handler - message was handled
        return None
    
    async def _handle_toxic_message(
        self,
        event: Message,
        result: ToxicityResult,
        action: ModerationAction,
        defcon_level: DEFCONLevel
    ) -> None:
        """
        Handle a detected toxic message based on the determined action.
        
        Actions:
        - WARN: Send warning message, apply reputation penalty
        - DELETE: Delete message, apply reputation penalty
        - DELETE_AND_MUTE: Delete message, mute user, apply reputation penalties
        
        **Validates: Requirements 2.2, 4.3, 4.4**
        """
        user_id = event.from_user.id
        chat_id = event.chat.id
        username = event.from_user.username or str(user_id)
        
        logger.warning(
            f"Toxic message detected: user={user_id}, chat={chat_id}, "
            f"score={result.score}, category={result.category}, "
            f"action={action.value}, defcon={defcon_level.name}"
        )
        
        rep_info = ""
        
        try:
            if action == ModerationAction.WARN:
                # Just warn - apply warning reputation penalty
                try:
                    rep_status = await reputation_service.apply_warning(user_id, chat_id)
                    rep_info = f" Репутация: {rep_status.score}"
                    if rep_status.is_read_only:
                        rep_info += " (только чтение)"
                except Exception as rep_error:
                    logger.warning(f"Failed to update reputation on warning: {rep_error}")
                
                await event.reply(
                    f"⚠️ Предупреждение: обнаружено токсичное сообщение "
                    f"(уровень: {result.score}).{rep_info}"
                )
                
            elif action == ModerationAction.DELETE:
                # Delete message - apply message deleted reputation penalty
                await event.delete()
                
                try:
                    rep_status = await reputation_service.apply_message_deleted(user_id, chat_id)
                    rep_info = f" Репутация: {rep_status.score}"
                    if rep_status.is_read_only:
                        rep_info += " (только чтение)"
                except Exception as rep_error:
                    logger.warning(f"Failed to update reputation on delete: {rep_error}")
                
                await event.answer(
                    f"🗑️ Сообщение удалено за токсичность "
                    f"(уровень: {result.score}).{rep_info}"
                )
                
            elif action == ModerationAction.DELETE_AND_MUTE:
                # Delete message and mute user
                await event.delete()
                
                # Apply message deleted penalty first
                try:
                    await reputation_service.apply_message_deleted(user_id, chat_id)
                except Exception as rep_error:
                    logger.warning(f"Failed to update reputation on delete: {rep_error}")
                
                # Mute user for 2 minutes
                try:
                    await event.chat.restrict(
                        user_id=user_id,
                        permissions={},  # No permissions = mute
                        until_date=timedelta(minutes=2)
                    )
                except Exception as mute_error:
                    logger.error(f"Failed to mute user {user_id}: {mute_error}")
                
                # Apply mute reputation penalty (Requirement 4.3)
                try:
                    rep_status = await reputation_service.apply_mute(user_id, chat_id)
                    rep_info = f" Репутация: {rep_status.score}"
                    if rep_status.is_read_only:
                        rep_info += " (только чтение)"
                except Exception as rep_error:
                    logger.warning(f"Failed to update reputation on mute: {rep_error}")
                
                await event.answer(
                    f"🔇 Пользователь @{username} замучен на 2 минуты "
                    f"за токсичное сообщение (уровень: {result.score}).{rep_info}"
                )
            
            # Log the incident (Requirement 2.4)
            try:
                await log_incident(
                    chat_id=chat_id,
                    user_id=user_id,
                    message_text=event.text,
                    result=result,
                    action_taken=action.value
                )
            except Exception as log_error:
                logger.error(f"Failed to log toxicity incident: {log_error}")
            
            # Check for toxicity increase periodically (Requirement 15.3)
            await self._check_toxicity_increase_periodic(
                chat_id=chat_id,
                chat_title=event.chat.title or f"Chat {chat_id}"
            )
                
        except Exception as e:
            logger.error(f"Failed to handle toxic message: {e}")


    async def _check_toxicity_increase_periodic(
        self,
        chat_id: int,
        chat_title: str
    ) -> None:
        """
        Periodically check for toxicity increase and notify owner if needed.
        
        Called after each toxicity incident. Checks every N incidents
        to avoid excessive database queries.
        
        **Validates: Requirements 15.3**
        WHEN the chat's average toxicity level increases significantly
        (more than 20% over 24 hours) THEN the Notification System SHALL
        automatically send a warning to the chat owner.
        
        Args:
            chat_id: Telegram chat ID
            chat_title: Title of the chat
        """
        # Increment incident count for this chat
        self._incident_counts[chat_id] = self._incident_counts.get(chat_id, 0) + 1
        
        # Only check every N incidents to avoid excessive queries
        if self._incident_counts[chat_id] % self._check_interval != 0:
            return
        
        try:
            # Check for toxicity increase
            notification = await notification_service.check_toxicity_increase(
                chat_id=chat_id,
                chat_title=chat_title
            )
            
            if notification:
                # Get owner_id from notification config
                config = await notification_service.get_config(chat_id)
                
                if config.owner_id:
                    # Import bot here to avoid circular imports
                    from app.main import bot
                    
                    # Send notification to owner
                    try:
                        await bot.send_message(
                            chat_id=config.owner_id,
                            text=f"{notification.title}\n\n{notification.message}",
                            parse_mode="HTML"
                        )
                        logger.info(
                            f"Sent toxicity warning to owner {config.owner_id} "
                            f"for chat {chat_id}"
                        )
                    except Exception as send_error:
                        logger.warning(
                            f"Failed to send toxicity warning to owner: {send_error}"
                        )
                        
        except Exception as e:
            logger.error(f"Failed to check toxicity increase for chat {chat_id}: {e}")


# Convenience function to create middleware instance
def create_toxicity_filter_middleware() -> ToxicityFilterMiddleware:
    """Create and return a ToxicityFilterMiddleware instance."""
    return ToxicityFilterMiddleware()
