"""Notification Service - Owner Notifications and Tips.

This module provides the Notification system for alerting chat owners
about important moderation events and providing actionable advice.

**Feature: fortress-update**
**Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7, 15.8**
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import NotificationConfig as NotificationConfigModel
from app.database.models import ToxicityLog, Chat
from app.database.session import get_session
from app.utils import utc_now

logger = logging.getLogger(__name__)


# ============================================================================
# Notification Types
# ============================================================================

class NotificationType(str, Enum):
    """
    Types of notifications that can be sent to chat owners.
    
    **Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5, 15.6**
    """
    RAID_ALERT = "raid_alert"                    # Requirement 15.1
    BAN_NOTIFICATION = "ban_notification"        # Requirement 15.2
    TOXICITY_WARNING = "toxicity_warning"        # Requirement 15.3
    DEFCON_RECOMMENDATION = "defcon_recommendation"  # Requirement 15.4
    REPEATED_VIOLATOR = "repeated_violator"      # Requirement 15.5
    DAILY_TIPS = "daily_tips"                    # Requirement 15.6


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class NotificationConfigData:
    """
    Notification configuration for a chat.
    
    Attributes:
        chat_id: Telegram chat ID
        owner_id: Telegram user ID of the chat owner
        enabled_types: Set of enabled notification types
        
    **Validates: Requirements 15.8**
    """
    chat_id: int
    owner_id: int
    enabled_types: Set[NotificationType] = field(default_factory=lambda: set(NotificationType))
    
    @classmethod
    def default(cls, chat_id: int, owner_id: int) -> "NotificationConfigData":
        """
        Create default config with all notifications enabled.
        
        **Property 35: Default notifications enabled**
        *For any* newly registered chat, all notification types SHALL be enabled by default.
        
        **Validates: Requirements 15.8**
        """
        return cls(
            chat_id=chat_id,
            owner_id=owner_id,
            enabled_types=set(NotificationType)  # All types enabled by default
        )
    
    def is_enabled(self, notification_type: NotificationType) -> bool:
        """Check if a notification type is enabled."""
        return notification_type in self.enabled_types


@dataclass
class NotificationData:
    """
    Data for a notification to be sent.
    
    Attributes:
        notification_type: Type of notification
        chat_id: Source chat ID
        title: Notification title
        message: Notification message body
        data: Additional data for the notification
    """
    notification_type: NotificationType
    chat_id: int
    title: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TipRecommendation:
    """
    A tip/recommendation for chat improvement.
    
    Attributes:
        priority: Priority level (1=high, 2=medium, 3=low)
        category: Category of the tip
        message: The tip message
        action: Suggested action to take
    """
    priority: int
    category: str
    message: str
    action: Optional[str] = None


# ============================================================================
# Notification Templates
# ============================================================================

NOTIFICATION_TEMPLATES = {
    NotificationType.RAID_ALERT: {
        "title": "🚨 Обнаружен рейд!",
        "template": (
            "В чате {chat_title} обнаружена подозрительная активность:\n"
            "• {join_count} новых участников за {time_window} секунд\n"
            "• Автоматически активирован DEFCON 3 (Raid Mode)\n"
            "• Режим будет активен {duration} минут\n\n"
            "Рекомендуется проверить новых участников."
        )
    },
    NotificationType.BAN_NOTIFICATION: {
        "title": "🔨 Пользователь забанен",
        "template": (
            "В чате {chat_title} забанен пользователь:\n"
            "• Пользователь: {username} (ID: {user_id})\n"
            "• Причина: {reason}\n"
            "• Время: {timestamp}"
        )
    },
    NotificationType.TOXICITY_WARNING: {
        "title": "⚠️ Рост токсичности",
        "template": (
            "В чате {chat_title} зафиксирован рост токсичности:\n"
            "• Изменение за 24 часа: +{toxicity_change}%\n"
            "• Текущий средний уровень: {current_level}%\n"
            "• Инцидентов за сутки: {incident_count}\n\n"
            "Рекомендуется: {recommendation}"
        )
    },
    NotificationType.DEFCON_RECOMMENDATION: {
        "title": "💡 Рекомендация по DEFCON",
        "template": (
            "Для чата {chat_title} рекомендуется изменить уровень защиты:\n"
            "• Текущий уровень: DEFCON {current_level}\n"
            "• Рекомендуемый: DEFCON {recommended_level}\n"
            "• Причина: {reason}\n\n"
            "Используйте /admin для изменения настроек."
        )
    },
    NotificationType.REPEATED_VIOLATOR: {
        "title": "🔄 Повторные нарушения",
        "template": (
            "В чате {chat_title} обнаружен повторный нарушитель:\n"
            "• Пользователь: {username} (ID: {user_id})\n"
            "• Нарушений за неделю: {violation_count}\n"
            "• Последнее нарушение: {last_violation}\n\n"
            "Рекомендуется рассмотреть постоянный бан."
        )
    },
    NotificationType.DAILY_TIPS: {
        "title": "📊 Ежедневные советы",
        "template": (
            "Советы для чата {chat_title}:\n\n"
            "{tips}\n\n"
            "Используйте /советы для подробного анализа."
        )
    },
}


# ============================================================================
# Notification Service
# ============================================================================

class NotificationService:
    """
    Service for managing owner notifications and tips.
    
    Features:
    - Raid alerts (Requirement 15.1)
    - Ban notifications (Requirement 15.2)
    - Toxicity warnings (Requirement 15.3)
    - DEFCON recommendations (Requirement 15.4)
    - Repeated violator alerts (Requirement 15.5)
    - Daily tips (Requirement 15.6)
    - Tips command (Requirement 15.7)
    - Default notifications enabled (Requirement 15.8)
    
    Properties:
    - Property 35: Default notifications enabled
    """
    
    def __init__(self):
        """Initialize NotificationService with in-memory cache."""
        self._config_cache: Dict[int, NotificationConfigData] = {}
        self._cache_ttl: Dict[int, datetime] = {}
        self._cache_duration = timedelta(minutes=5)
        
        # Track toxicity levels for change detection
        self._toxicity_history: Dict[int, List[float]] = {}

    # =========================================================================
    # Configuration Methods
    # =========================================================================
    
    async def get_config(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> NotificationConfigData:
        """
        Get notification configuration for a chat.
        
        If no configuration exists, returns default config with all
        notifications enabled.
        
        **Property 35: Default notifications enabled**
        *For any* newly registered chat, all notification types SHALL be
        enabled by default.
        
        Args:
            chat_id: Telegram chat ID
            session: Optional database session
            
        Returns:
            NotificationConfigData with current settings
            
        **Validates: Requirements 15.8**
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
    
    async def register_chat(
        self,
        chat_id: int,
        owner_id: int,
        session: Optional[AsyncSession] = None
    ) -> NotificationConfigData:
        """
        Register a new chat with default notification settings.
        
        Creates a new notification config with all notifications enabled.
        
        **Property 35: Default notifications enabled**
        *For any* newly registered chat, all notification types SHALL be
        enabled by default.
        
        Args:
            chat_id: Telegram chat ID
            owner_id: Telegram user ID of the chat owner
            session: Optional database session
            
        Returns:
            NotificationConfigData with default settings
            
        **Validates: Requirements 15.8**
        """
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            # Check if config already exists
            result = await session.execute(
                select(NotificationConfigModel).filter_by(chat_id=chat_id)
            )
            db_config = result.scalar_one_or_none()
            
            if db_config is None:
                # Create new config with all notifications enabled (Property 35)
                db_config = NotificationConfigModel(
                    chat_id=chat_id,
                    owner_id=owner_id,
                    raid_alert=True,
                    ban_notification=True,
                    toxicity_warning=True,
                    defcon_recommendation=True,
                    repeated_violator=True,
                    daily_tips=True
                )
                session.add(db_config)
                await session.commit()
                
                logger.info(f"Registered notification config for chat {chat_id}")
            
            # Convert to dataclass
            config_data = self._db_model_to_dataclass(db_config)
            
            # Update cache
            self._config_cache[chat_id] = config_data
            self._cache_ttl[chat_id] = utc_now()
            
            return config_data
            
        finally:
            if close_session:
                await session.close()
    
    async def toggle_notification(
        self,
        chat_id: int,
        notification_type: NotificationType,
        enabled: bool,
        session: Optional[AsyncSession] = None
    ) -> NotificationConfigData:
        """
        Toggle a specific notification type on or off.
        
        Args:
            chat_id: Telegram chat ID
            notification_type: Type of notification to toggle
            enabled: Whether to enable or disable
            session: Optional database session
            
        Returns:
            Updated NotificationConfigData
        """
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            # Get or create config
            result = await session.execute(
                select(NotificationConfigModel).filter_by(chat_id=chat_id)
            )
            db_config = result.scalar_one_or_none()
            
            if db_config is None:
                # Get owner_id from chat
                chat_result = await session.execute(
                    select(Chat).filter_by(id=chat_id)
                )
                chat = chat_result.scalar_one_or_none()
                owner_id = chat.owner_user_id if chat else 0
                
                db_config = NotificationConfigModel(
                    chat_id=chat_id,
                    owner_id=owner_id,
                    raid_alert=True,
                    ban_notification=True,
                    toxicity_warning=True,
                    defcon_recommendation=True,
                    repeated_violator=True,
                    daily_tips=True
                )
                session.add(db_config)
            
            # Update the specific notification type
            type_to_field = {
                NotificationType.RAID_ALERT: "raid_alert",
                NotificationType.BAN_NOTIFICATION: "ban_notification",
                NotificationType.TOXICITY_WARNING: "toxicity_warning",
                NotificationType.DEFCON_RECOMMENDATION: "defcon_recommendation",
                NotificationType.REPEATED_VIOLATOR: "repeated_violator",
                NotificationType.DAILY_TIPS: "daily_tips",
            }
            
            field_name = type_to_field.get(notification_type)
            if field_name:
                setattr(db_config, field_name, enabled)
            
            await session.commit()
            
            # Update cache
            config_data = self._db_model_to_dataclass(db_config)
            self._config_cache[chat_id] = config_data
            self._cache_ttl[chat_id] = utc_now()
            
            logger.info(
                f"Toggled {notification_type.value} to {enabled} for chat {chat_id}"
            )
            
            return config_data
            
        finally:
            if close_session:
                await session.close()

    # =========================================================================
    # Notification Methods
    # =========================================================================
    
    async def notify_owner(
        self,
        chat_id: int,
        notification_type: NotificationType,
        data: Dict[str, Any],
        session: Optional[AsyncSession] = None
    ) -> Optional[NotificationData]:
        """
        Send a notification to the chat owner.
        
        Checks if the notification type is enabled before creating
        the notification.
        
        Args:
            chat_id: Telegram chat ID
            notification_type: Type of notification
            data: Data to fill the notification template
            session: Optional database session
            
        Returns:
            NotificationData if notification should be sent, None otherwise
            
        **Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5, 15.6**
        """
        config = await self.get_config(chat_id, session)
        
        # Check if this notification type is enabled
        if not config.is_enabled(notification_type):
            logger.debug(
                f"Notification {notification_type.value} disabled for chat {chat_id}"
            )
            return None
        
        # Get template
        template_info = NOTIFICATION_TEMPLATES.get(notification_type)
        if not template_info:
            logger.error(f"No template for notification type: {notification_type}")
            return None
        
        # Format message
        try:
            message = template_info["template"].format(**data)
        except KeyError as e:
            logger.error(f"Missing template key: {e}")
            message = f"Notification: {notification_type.value}"
        
        notification = NotificationData(
            notification_type=notification_type,
            chat_id=chat_id,
            title=template_info["title"],
            message=message,
            data=data
        )
        
        logger.info(
            f"Created notification {notification_type.value} for chat {chat_id}"
        )
        
        return notification
    
    async def notify_raid(
        self,
        chat_id: int,
        chat_title: str,
        join_count: int,
        time_window: int = 60,
        duration: int = 15,
        session: Optional[AsyncSession] = None
    ) -> Optional[NotificationData]:
        """
        Send raid alert notification.
        
        **Validates: Requirements 15.1**
        WHEN Raid Mode is automatically activated THEN the Notification
        System SHALL automatically send a private message to the chat
        owner with details about the raid attempt.
        
        Args:
            chat_id: Telegram chat ID
            chat_title: Title of the chat
            join_count: Number of users who joined
            time_window: Time window in seconds
            duration: Raid mode duration in minutes
            session: Optional database session
            
        Returns:
            NotificationData if notification should be sent
        """
        return await self.notify_owner(
            chat_id=chat_id,
            notification_type=NotificationType.RAID_ALERT,
            data={
                "chat_title": chat_title,
                "join_count": join_count,
                "time_window": time_window,
                "duration": duration
            },
            session=session
        )
    
    async def notify_ban(
        self,
        chat_id: int,
        chat_title: str,
        user_id: int,
        username: str,
        reason: str,
        session: Optional[AsyncSession] = None
    ) -> Optional[NotificationData]:
        """
        Send ban notification.
        
        **Validates: Requirements 15.2**
        WHEN a user is banned for inappropriate content THEN the
        Notification System SHALL automatically notify the chat owner
        with the reason and evidence.
        
        Args:
            chat_id: Telegram chat ID
            chat_title: Title of the chat
            user_id: Banned user's ID
            username: Banned user's username
            reason: Reason for the ban
            session: Optional database session
            
        Returns:
            NotificationData if notification should be sent
        """
        return await self.notify_owner(
            chat_id=chat_id,
            notification_type=NotificationType.BAN_NOTIFICATION,
            data={
                "chat_title": chat_title,
                "user_id": user_id,
                "username": username or f"User {user_id}",
                "reason": reason,
                "timestamp": utc_now().strftime("%Y-%m-%d %H:%M:%S UTC")
            },
            session=session
        )
    
    async def notify_toxicity_increase(
        self,
        chat_id: int,
        chat_title: str,
        toxicity_change: float,
        current_level: float,
        incident_count: int,
        session: Optional[AsyncSession] = None
    ) -> Optional[NotificationData]:
        """
        Send toxicity warning notification.
        
        **Validates: Requirements 15.3**
        WHEN the chat's average toxicity level increases significantly
        (more than 20% over 24 hours) THEN the Notification System SHALL
        automatically send a warning to the chat owner with suggested actions.
        
        Args:
            chat_id: Telegram chat ID
            chat_title: Title of the chat
            toxicity_change: Percentage change in toxicity
            current_level: Current average toxicity level
            incident_count: Number of incidents in 24 hours
            session: Optional database session
            
        Returns:
            NotificationData if notification should be sent
        """
        # Generate recommendation based on toxicity level
        if current_level > 60:
            recommendation = "Повысить DEFCON до уровня 3"
        elif current_level > 40:
            recommendation = "Повысить DEFCON до уровня 2"
        else:
            recommendation = "Следить за ситуацией"
        
        return await self.notify_owner(
            chat_id=chat_id,
            notification_type=NotificationType.TOXICITY_WARNING,
            data={
                "chat_title": chat_title,
                "toxicity_change": round(toxicity_change, 1),
                "current_level": round(current_level, 1),
                "incident_count": incident_count,
                "recommendation": recommendation
            },
            session=session
        )
    
    async def notify_defcon_recommendation(
        self,
        chat_id: int,
        chat_title: str,
        current_level: int,
        recommended_level: int,
        reason: str,
        session: Optional[AsyncSession] = None
    ) -> Optional[NotificationData]:
        """
        Send DEFCON recommendation notification.
        
        **Validates: Requirements 15.4**
        WHEN a new DEFCON level is recommended based on chat activity
        patterns THEN the Notification System SHALL automatically suggest
        the change to the chat owner with explanation.
        
        Args:
            chat_id: Telegram chat ID
            chat_title: Title of the chat
            current_level: Current DEFCON level
            recommended_level: Recommended DEFCON level
            reason: Reason for the recommendation
            session: Optional database session
            
        Returns:
            NotificationData if notification should be sent
        """
        return await self.notify_owner(
            chat_id=chat_id,
            notification_type=NotificationType.DEFCON_RECOMMENDATION,
            data={
                "chat_title": chat_title,
                "current_level": current_level,
                "recommended_level": recommended_level,
                "reason": reason
            },
            session=session
        )
    
    async def notify_repeated_violator(
        self,
        chat_id: int,
        chat_title: str,
        user_id: int,
        username: str,
        violation_count: int,
        last_violation: str,
        session: Optional[AsyncSession] = None
    ) -> Optional[NotificationData]:
        """
        Send repeated violator notification.
        
        **Validates: Requirements 15.5**
        WHEN the bot detects repeated violations from the same user
        THEN the Notification System SHALL automatically advise the
        chat owner to consider permanent action.
        
        Args:
            chat_id: Telegram chat ID
            chat_title: Title of the chat
            user_id: Violator's user ID
            username: Violator's username
            violation_count: Number of violations
            last_violation: Description of last violation
            session: Optional database session
            
        Returns:
            NotificationData if notification should be sent
        """
        return await self.notify_owner(
            chat_id=chat_id,
            notification_type=NotificationType.REPEATED_VIOLATOR,
            data={
                "chat_title": chat_title,
                "user_id": user_id,
                "username": username or f"User {user_id}",
                "violation_count": violation_count,
                "last_violation": last_violation
            },
            session=session
        )

    # =========================================================================
    # Tips Generation (Requirement 15.7)
    # =========================================================================
    
    async def generate_tips(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> List[TipRecommendation]:
        """
        Generate actionable tips for a chat based on recent activity.
        
        Analyzes chat patterns and provides 3-5 recommendations.
        
        **Validates: Requirements 15.7**
        WHEN a chat owner requests advice with "/советы" or "/tips"
        THEN the Notification System SHALL analyze recent chat activity
        and provide 3-5 actionable recommendations.
        
        Args:
            chat_id: Telegram chat ID
            session: Optional database session
            
        Returns:
            List of TipRecommendation objects
        """
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        tips: List[TipRecommendation] = []
        
        try:
            # Analyze toxicity incidents
            toxicity_tips = await self._analyze_toxicity_patterns(chat_id, session)
            tips.extend(toxicity_tips)
            
            # Analyze DEFCON settings
            defcon_tips = await self._analyze_defcon_settings(chat_id, session)
            tips.extend(defcon_tips)
            
            # Analyze activity patterns
            activity_tips = await self._analyze_activity_patterns(chat_id, session)
            tips.extend(activity_tips)
            
            # Sort by priority and limit to 5
            tips.sort(key=lambda t: t.priority)
            tips = tips[:5]
            
            # Ensure at least one tip
            if not tips:
                tips.append(TipRecommendation(
                    priority=3,
                    category="general",
                    message="Чат работает стабильно. Продолжайте в том же духе!",
                    action=None
                ))
            
            return tips
            
        except Exception as e:
            logger.error(f"Failed to generate tips for chat {chat_id}: {e}")
            return [TipRecommendation(
                priority=3,
                category="error",
                message="Не удалось проанализировать чат. Попробуйте позже.",
                action=None
            )]
            
        finally:
            if close_session:
                await session.close()
    
    async def _analyze_toxicity_patterns(
        self,
        chat_id: int,
        session: AsyncSession
    ) -> List[TipRecommendation]:
        """Analyze toxicity patterns and generate tips."""
        tips = []
        
        try:
            # Get toxicity incidents from last 7 days
            week_ago = utc_now() - timedelta(days=7)
            
            result = await session.execute(
                select(ToxicityLog)
                .filter(
                    ToxicityLog.chat_id == chat_id,
                    ToxicityLog.created_at >= week_ago
                )
                .order_by(ToxicityLog.created_at.desc())
            )
            incidents = result.scalars().all()
            
            if not incidents:
                return tips
            
            # Calculate average toxicity
            avg_score = sum(i.score for i in incidents) / len(incidents)
            
            # High toxicity tip
            if avg_score > 50:
                tips.append(TipRecommendation(
                    priority=1,
                    category="toxicity",
                    message=f"Средний уровень токсичности высокий ({avg_score:.0f}%). "
                            "Рекомендуется усилить модерацию.",
                    action="Повысьте DEFCON до уровня 2 или 3"
                ))
            
            # Many incidents tip
            if len(incidents) > 20:
                tips.append(TipRecommendation(
                    priority=1,
                    category="toxicity",
                    message=f"За неделю зафиксировано {len(incidents)} инцидентов. "
                            "Это выше нормы.",
                    action="Проверьте список нарушителей и рассмотрите баны"
                ))
            
            # Check for repeat offenders
            user_counts: Dict[int, int] = {}
            for incident in incidents:
                user_counts[incident.user_id] = user_counts.get(incident.user_id, 0) + 1
            
            repeat_offenders = [uid for uid, count in user_counts.items() if count >= 3]
            if repeat_offenders:
                tips.append(TipRecommendation(
                    priority=1,
                    category="moderation",
                    message=f"Обнаружено {len(repeat_offenders)} повторных нарушителей.",
                    action="Рассмотрите постоянный бан для злостных нарушителей"
                ))
                
        except Exception as e:
            logger.warning(f"Failed to analyze toxicity patterns: {e}")
        
        return tips
    
    async def _analyze_defcon_settings(
        self,
        chat_id: int,
        session: AsyncSession
    ) -> List[TipRecommendation]:
        """Analyze DEFCON settings and generate tips."""
        tips = []
        
        try:
            from app.services.citadel import citadel_service, DEFCONLevel
            
            config = await citadel_service.get_config(chat_id, session)
            
            # Check if DEFCON is too low for activity level
            if config.defcon_level == DEFCONLevel.PEACEFUL:
                # Get recent toxicity incidents
                week_ago = utc_now() - timedelta(days=7)
                result = await session.execute(
                    select(func.count(ToxicityLog.id))
                    .filter(
                        ToxicityLog.chat_id == chat_id,
                        ToxicityLog.created_at >= week_ago
                    )
                )
                incident_count = result.scalar() or 0
                
                if incident_count > 10:
                    tips.append(TipRecommendation(
                        priority=2,
                        category="protection",
                        message="DEFCON 1 может быть недостаточным при текущей активности.",
                        action="Рассмотрите повышение до DEFCON 2"
                    ))
            
            # Check if profanity filter is disabled at high DEFCON
            if config.defcon_level >= DEFCONLevel.STRICT and not config.profanity_filter_enabled:
                tips.append(TipRecommendation(
                    priority=2,
                    category="protection",
                    message="Фильтр нецензурной лексики отключен при DEFCON 2+.",
                    action="Включите фильтр для лучшей защиты"
                ))
                
        except Exception as e:
            logger.warning(f"Failed to analyze DEFCON settings: {e}")
        
        return tips
    
    async def _analyze_activity_patterns(
        self,
        chat_id: int,
        session: AsyncSession
    ) -> List[TipRecommendation]:
        """Analyze activity patterns and generate tips."""
        tips = []
        
        try:
            from app.database.models import MessageLog
            
            # Check message activity
            week_ago = utc_now() - timedelta(days=7)
            result = await session.execute(
                select(func.count(MessageLog.id))
                .filter(
                    MessageLog.chat_id == chat_id,
                    MessageLog.created_at >= week_ago
                )
            )
            message_count = result.scalar() or 0
            
            if message_count < 10:
                tips.append(TipRecommendation(
                    priority=3,
                    category="activity",
                    message="Активность в чате низкая. Это нормально для небольших групп.",
                    action=None
                ))
            elif message_count > 1000:
                tips.append(TipRecommendation(
                    priority=2,
                    category="activity",
                    message="Высокая активность в чате. Убедитесь, что модерация справляется.",
                    action="Рассмотрите добавление модераторов"
                ))
                
        except Exception as e:
            logger.warning(f"Failed to analyze activity patterns: {e}")
        
        return tips
    
    def format_tips(self, tips: List[TipRecommendation]) -> str:
        """
        Format tips for display.
        
        Args:
            tips: List of tips to format
            
        Returns:
            Formatted string with tips
        """
        if not tips:
            return "Нет рекомендаций на данный момент."
        
        lines = ["💡 Рекомендации для вашего чата:", ""]
        
        priority_emoji = {1: "🔴", 2: "🟡", 3: "🟢"}
        
        for i, tip in enumerate(tips, 1):
            emoji = priority_emoji.get(tip.priority, "⚪")
            lines.append(f"{i}. {emoji} {tip.message}")
            if tip.action:
                lines.append(f"   → {tip.action}")
            lines.append("")
        
        return "\n".join(lines)

    # =========================================================================
    # Toxicity Monitoring (Requirement 15.3)
    # =========================================================================
    
    async def check_toxicity_increase(
        self,
        chat_id: int,
        chat_title: str,
        session: Optional[AsyncSession] = None
    ) -> Optional[NotificationData]:
        """
        Check if toxicity has increased significantly and notify if needed.
        
        **Validates: Requirements 15.3**
        WHEN the chat's average toxicity level increases significantly
        (more than 20% over 24 hours) THEN the Notification System SHALL
        automatically send a warning to the chat owner.
        
        Args:
            chat_id: Telegram chat ID
            chat_title: Title of the chat
            session: Optional database session
            
        Returns:
            NotificationData if toxicity increased significantly
        """
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            now = utc_now()
            day_ago = now - timedelta(days=1)
            two_days_ago = now - timedelta(days=2)
            
            # Get toxicity from last 24 hours
            result_today = await session.execute(
                select(func.avg(ToxicityLog.score), func.count(ToxicityLog.id))
                .filter(
                    ToxicityLog.chat_id == chat_id,
                    ToxicityLog.created_at >= day_ago
                )
            )
            row_today = result_today.one()
            avg_today = row_today[0] or 0
            count_today = row_today[1] or 0
            
            # Get toxicity from previous 24 hours
            result_yesterday = await session.execute(
                select(func.avg(ToxicityLog.score))
                .filter(
                    ToxicityLog.chat_id == chat_id,
                    ToxicityLog.created_at >= two_days_ago,
                    ToxicityLog.created_at < day_ago
                )
            )
            avg_yesterday = result_yesterday.scalar() or 0
            
            # Calculate change
            if avg_yesterday > 0:
                change_percent = ((avg_today - avg_yesterday) / avg_yesterday) * 100
            else:
                change_percent = 0 if avg_today == 0 else 100
            
            # Check if increase is significant (> 20%)
            if change_percent > 20:
                return await self.notify_toxicity_increase(
                    chat_id=chat_id,
                    chat_title=chat_title,
                    toxicity_change=change_percent,
                    current_level=avg_today,
                    incident_count=count_today,
                    session=session
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to check toxicity increase for chat {chat_id}: {e}")
            return None
            
        finally:
            if close_session:
                await session.close()
    
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
    ) -> NotificationConfigData:
        """Load config from database or return default."""
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            result = await session.execute(
                select(NotificationConfigModel).filter_by(chat_id=chat_id)
            )
            db_config = result.scalar_one_or_none()
            
            if db_config is None:
                # Return default config with all notifications enabled (Property 35)
                # Get owner_id from chat if possible
                chat_result = await session.execute(
                    select(Chat).filter_by(id=chat_id)
                )
                chat = chat_result.scalar_one_or_none()
                owner_id = chat.owner_user_id if chat else 0
                
                return NotificationConfigData.default(chat_id, owner_id)
            
            return self._db_model_to_dataclass(db_config)
            
        finally:
            if close_session:
                await session.close()
    
    def _db_model_to_dataclass(
        self,
        db_config: NotificationConfigModel
    ) -> NotificationConfigData:
        """Convert database model to dataclass."""
        enabled_types: Set[NotificationType] = set()
        
        if db_config.raid_alert:
            enabled_types.add(NotificationType.RAID_ALERT)
        if db_config.ban_notification:
            enabled_types.add(NotificationType.BAN_NOTIFICATION)
        if db_config.toxicity_warning:
            enabled_types.add(NotificationType.TOXICITY_WARNING)
        if db_config.defcon_recommendation:
            enabled_types.add(NotificationType.DEFCON_RECOMMENDATION)
        if db_config.repeated_violator:
            enabled_types.add(NotificationType.REPEATED_VIOLATOR)
        if db_config.daily_tips:
            enabled_types.add(NotificationType.DAILY_TIPS)
        
        return NotificationConfigData(
            chat_id=db_config.chat_id,
            owner_id=db_config.owner_id,
            enabled_types=enabled_types
        )
    
    def invalidate_cache(self, chat_id: int) -> None:
        """Invalidate cached config for a chat."""
        self._config_cache.pop(chat_id, None)
        self._cache_ttl.pop(chat_id, None)


# Global service instance
notification_service = NotificationService()
