"""
Dailies Service for OLEG v6.0 Fortress Update.

Manages daily scheduled messages including:
- Morning summary (#dailysummary) at 09:00 Moscow time
- Evening quote (#dailyquote) at 21:00 Moscow time
- Evening stats (#dailystats) at 21:00 Moscow time

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
"""

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func, and_, extract, desc
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Minimum activity threshold for sending summary (Requirement 13.5)
MIN_ACTIVITY_FOR_SUMMARY = 1  # At least 1 message to send summary

# Default wisdom quotes when Golden Fund is empty
DEFAULT_WISDOM_QUOTES = [
    "Мудрость приходит с опытом, а опыт — с ошибками.",
    "Лучше сделать и пожалеть, чем не сделать и пожалеть.",
    "Терпение и труд всё перетрут.",
    "Не откладывай на завтра то, что можно сделать сегодня.",
    "Учиться никогда не поздно.",
    "Кто рано встаёт, тому Бог подаёт.",
    "Без труда не выловишь и рыбку из пруда.",
    "Век живи — век учись.",
    "Тише едешь — дальше будешь.",
    "Семь раз отмерь, один раз отрежь.",
]


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class DailiesConfig:
    """
    Configuration for daily messages per chat.
    
    Attributes:
        chat_id: Telegram chat ID
        summary_enabled: Whether morning summary is enabled
        quote_enabled: Whether evening quote is enabled
        stats_enabled: Whether evening stats are enabled
        summary_time_hour: Hour for summary (Moscow time)
        quote_time_hour: Hour for quote/stats (Moscow time)
    """
    chat_id: int
    summary_enabled: bool = True
    quote_enabled: bool = True
    stats_enabled: bool = True
    summary_time_hour: int = 9   # 09:00 Moscow (Requirement 13.1)
    quote_time_hour: int = 21   # 21:00 Moscow (Requirement 13.2, 13.3)


@dataclass
class DailySummary:
    """
    Daily summary data structure.
    
    Attributes:
        chat_id: Telegram chat ID
        date: Date of the summary
        message_count: Total messages yesterday
        active_users: Number of active users
        new_members: Number of new members
        moderation_actions: Count of moderation actions
        top_messages: List of top messages (by reactions)
        has_activity: Whether there was any activity
        toxicity_score: Average toxicity score (0-100)
        toxicity_incidents: Number of toxicity incidents
        hot_topics: List of hot topics with message links
        peak_hour: Hour with most activity
        top_chatters: List of most active users
    """
    chat_id: int
    date: datetime
    message_count: int = 0
    active_users: int = 0
    new_members: int = 0
    moderation_actions: int = 0
    top_messages: List[Dict[str, Any]] = field(default_factory=list)
    has_activity: bool = False
    # New fields for enhanced dailies
    toxicity_score: float = 0.0
    toxicity_incidents: int = 0
    hot_topics: List[Dict[str, Any]] = field(default_factory=list)
    peak_hour: Optional[int] = None
    top_chatters: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DailyQuote:
    """
    Daily quote data structure.
    
    Attributes:
        text: Quote text
        author: Quote author (if from Golden Fund)
        is_from_golden_fund: Whether quote is from Golden Fund
        sticker_file_id: Sticker file ID if available
    """
    text: str
    author: Optional[str] = None
    is_from_golden_fund: bool = False
    sticker_file_id: Optional[str] = None


@dataclass
class DailyStats:
    """
    Daily game statistics data structure.
    
    Attributes:
        chat_id: Telegram chat ID
        date: Date of the stats
        top_growers: List of top growers (username, growth)
        top_losers: List of top losers (username, loss)
        tournament_standings: Current tournament standings
    """
    chat_id: int
    date: datetime
    top_growers: List[Dict[str, Any]] = field(default_factory=list)
    top_losers: List[Dict[str, Any]] = field(default_factory=list)
    tournament_standings: List[Dict[str, Any]] = field(default_factory=list)


# ============================================================================
# Dailies Service
# ============================================================================

class DailiesService:
    """
    Service for managing daily scheduled messages.
    
    Features:
    - Morning summary at 09:00 Moscow (Requirement 13.1)
    - Evening quote at 21:00 Moscow (Requirement 13.2)
    - Evening stats at 21:00 Moscow (Requirement 13.3)
    - Chat-specific settings (Requirement 13.4)
    - Skip summary on no activity (Requirement 13.5)
    
    Properties:
    - Property 33: Daily message respect settings
    - Property 34: Skip summary on no activity
    """
    
    def __init__(self):
        """Initialize DailiesService."""
        self._golden_fund_service = None
    
    @property
    def golden_fund_service(self):
        """Lazy load golden fund service to avoid circular imports."""
        if self._golden_fund_service is None:
            try:
                from app.services.golden_fund import golden_fund_service
                self._golden_fund_service = golden_fund_service
            except Exception as e:
                logger.warning(f"Failed to load golden fund service: {e}")
        return self._golden_fund_service
    
    # =========================================================================
    # Configuration Methods
    # =========================================================================
    
    async def get_config(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> DailiesConfig:
        """
        Get dailies configuration for a chat.
        
        Property 33: Daily message respect settings
        *For any* chat with specific daily message types disabled,
        those messages SHALL NOT be sent.
        
        Requirement 13.4: WHEN sending daily messages THEN the Dailies
        System SHALL respect chat-specific settings for enabled/disabled
        daily messages.
        
        Args:
            chat_id: Telegram chat ID
            session: Optional database session
            
        Returns:
            DailiesConfig for the chat
        """
        from app.database.models import DailiesConfig as DailiesConfigModel
        from app.database.session import get_session
        
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            # Get dailies config from database
            result = await session.execute(
                select(DailiesConfigModel).filter_by(chat_id=chat_id)
            )
            db_config = result.scalar_one_or_none()
            
            if db_config is None:
                # Return default config for chats without explicit settings
                return DailiesConfig(chat_id=chat_id)
            
            # Map database model to dataclass
            return DailiesConfig(
                chat_id=chat_id,
                summary_enabled=db_config.summary_enabled,
                quote_enabled=db_config.quote_enabled,
                stats_enabled=db_config.stats_enabled,
                summary_time_hour=db_config.summary_time_hour,
                quote_time_hour=db_config.quote_time_hour,
            )
            
        except Exception as e:
            logger.warning(f"Failed to get dailies config for chat {chat_id}: {e}")
            # Return default config on error
            return DailiesConfig(chat_id=chat_id)
            
        finally:
            if close_session:
                await session.close()
    
    async def update_config(
        self,
        chat_id: int,
        summary_enabled: Optional[bool] = None,
        quote_enabled: Optional[bool] = None,
        stats_enabled: Optional[bool] = None,
        session: Optional[AsyncSession] = None
    ) -> DailiesConfig:
        """
        Update dailies configuration for a chat.
        
        Requirement 13.4: Respect chat-specific settings for enabled/disabled
        daily messages.
        
        Args:
            chat_id: Telegram chat ID
            summary_enabled: Enable/disable morning summary
            quote_enabled: Enable/disable evening quote
            stats_enabled: Enable/disable evening stats
            session: Optional database session
            
        Returns:
            Updated DailiesConfig
        """
        from app.database.models import DailiesConfig as DailiesConfigModel
        from app.database.session import get_session
        
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            # Get or create config
            result = await session.execute(
                select(DailiesConfigModel).filter_by(chat_id=chat_id)
            )
            db_config = result.scalar_one_or_none()
            
            if db_config is None:
                # Create new config
                db_config = DailiesConfigModel(chat_id=chat_id)
                session.add(db_config)
            
            # Update fields if provided
            if summary_enabled is not None:
                db_config.summary_enabled = summary_enabled
            if quote_enabled is not None:
                db_config.quote_enabled = quote_enabled
            if stats_enabled is not None:
                db_config.stats_enabled = stats_enabled
            
            await session.commit()
            
            # Return updated config as dataclass
            return DailiesConfig(
                chat_id=chat_id,
                summary_enabled=db_config.summary_enabled,
                quote_enabled=db_config.quote_enabled,
                stats_enabled=db_config.stats_enabled,
                summary_time_hour=db_config.summary_time_hour,
                quote_time_hour=db_config.quote_time_hour,
            )
            
        except Exception as e:
            logger.error(f"Failed to update dailies config for chat {chat_id}: {e}")
            if session:
                await session.rollback()
            # Return current config on error
            return await self.get_config(chat_id, session)
            
        finally:
            if close_session:
                await session.close()
    
    def should_send_message(
        self,
        config: DailiesConfig,
        message_type: str
    ) -> bool:
        """
        Check if a specific daily message type should be sent.
        
        Property 33: Daily message respect settings
        *For any* chat with specific daily message types disabled,
        those messages SHALL NOT be sent.
        
        Args:
            config: Chat's dailies configuration
            message_type: Type of message ('summary', 'quote', 'stats')
            
        Returns:
            True if message should be sent, False otherwise
        """
        if message_type == 'summary':
            return config.summary_enabled
        elif message_type == 'quote':
            return config.quote_enabled
        elif message_type == 'stats':
            return config.stats_enabled
        return False
    
    # =========================================================================
    # Summary Generation (Requirement 13.1)
    # =========================================================================
    
    async def generate_summary(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> Optional[DailySummary]:
        """
        Generate daily summary for a chat.
        
        Property 34: Skip summary on no activity
        *For any* chat with zero messages in the past 24 hours,
        the daily summary SHALL be skipped.
        
        Requirement 13.1: WHEN the time reaches 09:00 Moscow time
        THEN the Dailies System SHALL send a #dailysummary message
        with a digest of yesterday's events.
        
        Enhanced with:
        - Toxicity thermometer (average toxicity score)
        - Hot topics with message links
        - Peak activity hour
        - Top chatters
        
        Args:
            chat_id: Telegram chat ID
            session: Optional database session
            
        Returns:
            DailySummary if there was activity, None otherwise
        """
        from app.database.models import MessageLog, User, Warning, ToxicityLog
        from app.database.session import get_session
        from app.utils import utc_now
        
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            now = utc_now()
            yesterday_start = (now - timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            yesterday_end = now.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            
            # Count messages from yesterday
            message_count_result = await session.execute(
                select(func.count(MessageLog.id)).filter(
                    MessageLog.chat_id == chat_id,
                    MessageLog.created_at >= yesterday_start,
                    MessageLog.created_at < yesterday_end
                )
            )
            message_count = message_count_result.scalar() or 0
            
            # Property 34: Skip if no activity
            if message_count < MIN_ACTIVITY_FOR_SUMMARY:
                logger.debug(f"Skipping summary for chat {chat_id}: no activity")
                return DailySummary(
                    chat_id=chat_id,
                    date=yesterday_start,
                    message_count=0,
                    has_activity=False
                )
            
            # Count active users
            active_users_result = await session.execute(
                select(func.count(func.distinct(MessageLog.user_id))).filter(
                    MessageLog.chat_id == chat_id,
                    MessageLog.created_at >= yesterday_start,
                    MessageLog.created_at < yesterday_end
                )
            )
            active_users = active_users_result.scalar() or 0
            
            # Count new members (users created yesterday)
            new_members_result = await session.execute(
                select(func.count(User.id)).filter(
                    User.created_at >= yesterday_start,
                    User.created_at < yesterday_end
                )
            )
            new_members = new_members_result.scalar() or 0
            
            # Count moderation actions (warnings)
            moderation_result = await session.execute(
                select(func.count(Warning.id)).filter(
                    Warning.created_at >= yesterday_start,
                    Warning.created_at < yesterday_end
                )
            )
            moderation_actions = moderation_result.scalar() or 0
            
            # ===== NEW: Toxicity thermometer =====
            toxicity_result = await session.execute(
                select(
                    func.avg(ToxicityLog.score),
                    func.count(ToxicityLog.id)
                ).filter(
                    ToxicityLog.chat_id == chat_id,
                    ToxicityLog.created_at >= yesterday_start,
                    ToxicityLog.created_at < yesterday_end
                )
            )
            toxicity_row = toxicity_result.one()
            toxicity_score = float(toxicity_row[0] or 0)
            toxicity_incidents = toxicity_row[1] or 0
            
            # ===== NEW: Peak activity hour =====
            peak_hour_result = await session.execute(
                select(
                    extract('hour', MessageLog.created_at).label('hour'),
                    func.count(MessageLog.id).label('cnt')
                ).filter(
                    MessageLog.chat_id == chat_id,
                    MessageLog.created_at >= yesterday_start,
                    MessageLog.created_at < yesterday_end
                ).group_by(
                    extract('hour', MessageLog.created_at)
                ).order_by(
                    desc('cnt')
                ).limit(1)
            )
            peak_row = peak_hour_result.first()
            peak_hour = int(peak_row[0]) if peak_row else None
            
            # ===== NEW: Top chatters =====
            top_chatters_result = await session.execute(
                select(
                    MessageLog.username,
                    MessageLog.user_id,
                    func.count(MessageLog.id).label('msg_count')
                ).filter(
                    MessageLog.chat_id == chat_id,
                    MessageLog.created_at >= yesterday_start,
                    MessageLog.created_at < yesterday_end
                ).group_by(
                    MessageLog.user_id, MessageLog.username
                ).order_by(
                    desc('msg_count')
                ).limit(5)
            )
            top_chatters = [
                {
                    "username": row.username or f"User {row.user_id}",
                    "user_id": row.user_id,
                    "count": row.msg_count
                }
                for row in top_chatters_result.all()
            ]
            
            # ===== NEW: Hot topics (extract from messages) =====
            hot_topics = await self._extract_hot_topics(
                chat_id, yesterday_start, yesterday_end, session
            )
            
            return DailySummary(
                chat_id=chat_id,
                date=yesterday_start,
                message_count=message_count,
                active_users=active_users,
                new_members=new_members,
                moderation_actions=moderation_actions,
                has_activity=True,
                toxicity_score=toxicity_score,
                toxicity_incidents=toxicity_incidents,
                hot_topics=hot_topics,
                peak_hour=peak_hour,
                top_chatters=top_chatters
            )
            
        except Exception as e:
            logger.error(f"Failed to generate summary for chat {chat_id}: {e}")
            return None
            
        finally:
            if close_session:
                await session.close()
    
    async def _extract_hot_topics(
        self,
        chat_id: int,
        start_time: datetime,
        end_time: datetime,
        session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Extract hot topics from messages using keyword clustering.
        
        Finds the most discussed topics by analyzing message content
        and returns them with links to representative messages.
        
        Args:
            chat_id: Telegram chat ID
            start_time: Start of time range
            end_time: End of time range
            session: Database session
            
        Returns:
            List of hot topics with message links
        """
        from app.database.models import MessageLog
        from collections import Counter
        import re
        
        try:
            # Get messages with text
            messages_result = await session.execute(
                select(MessageLog).filter(
                    MessageLog.chat_id == chat_id,
                    MessageLog.created_at >= start_time,
                    MessageLog.created_at < end_time,
                    MessageLog.text.isnot(None)
                ).order_by(MessageLog.created_at.desc()).limit(500)
            )
            messages = messages_result.scalars().all()
            
            if not messages:
                return []
            
            # Extract keywords (words 4+ chars, excluding common words)
            stop_words = {
                'это', 'как', 'что', 'для', 'все', 'они', 'его', 'она', 'так',
                'уже', 'или', 'если', 'есть', 'было', 'быть', 'был', 'была',
                'были', 'будет', 'будут', 'очень', 'просто', 'можно', 'нужно',
                'там', 'тут', 'здесь', 'когда', 'потом', 'тоже', 'только',
                'ещё', 'еще', 'вот', 'чтобы', 'этот', 'этого', 'этом', 'этой',
                'который', 'которая', 'которое', 'которые', 'него', 'неё',
                'http', 'https', 'www', 'com', 'org', 'net'
            }
            
            word_messages: Dict[str, List[MessageLog]] = {}
            word_counts: Counter = Counter()
            
            for msg in messages:
                if not msg.text:
                    continue
                # Extract words
                words = re.findall(r'[а-яёa-z]{4,}', msg.text.lower())
                seen_words = set()
                for word in words:
                    if word not in stop_words and word not in seen_words:
                        seen_words.add(word)
                        word_counts[word] += 1
                        if word not in word_messages:
                            word_messages[word] = []
                        if len(word_messages[word]) < 3:
                            word_messages[word].append(msg)
            
            # Get top 5 keywords as topics
            hot_topics = []
            for word, count in word_counts.most_common(5):
                if count < 3:  # Skip topics mentioned less than 3 times
                    continue
                    
                # Get representative message for link
                representative_msg = word_messages[word][0] if word_messages[word] else None
                
                topic = {
                    "keyword": word.capitalize(),
                    "mentions": count,
                    "message_id": representative_msg.message_id if representative_msg else None,
                    "chat_id": chat_id
                }
                hot_topics.append(topic)
            
            return hot_topics
            
        except Exception as e:
            logger.warning(f"Failed to extract hot topics: {e}")
            return []
    
    def _get_toxicity_emoji(self, score: float) -> str:
        """Get toxicity thermometer emoji based on score."""
        if score < 20:
            return "🟢"  # Green - very chill
        elif score < 40:
            return "🟡"  # Yellow - mild
        elif score < 60:
            return "🟠"  # Orange - warming up
        elif score < 80:
            return "🔴"  # Red - hot
        else:
            return "🔥"  # Fire - toxic
    
    def _get_toxicity_label(self, score: float) -> str:
        """Get toxicity label based on score."""
        if score < 20:
            return "Чилл 😎"
        elif score < 40:
            return "Спокойно"
        elif score < 60:
            return "Бурно"
        elif score < 80:
            return "Горячо 🌶️"
        else:
            return "Токсично ☢️"
    
    def should_skip_summary(self, summary: Optional[DailySummary]) -> bool:
        """
        Check if summary should be skipped due to no activity.
        
        Property 34: Skip summary on no activity
        *For any* chat with zero messages in the past 24 hours,
        the daily summary SHALL be skipped.
        
        Args:
            summary: Generated summary or None
            
        Returns:
            True if summary should be skipped, False otherwise
        """
        if summary is None:
            return True
        return not summary.has_activity
    
    def format_summary(self, summary: DailySummary) -> str:
        """
        Format daily summary for display.
        
        Requirement 13.1: Send a #dailysummary message with a digest
        of yesterday's events.
        
        Enhanced with toxicity thermometer, hot topics, and more stats.
        
        Args:
            summary: DailySummary to format
            
        Returns:
            Formatted summary string
        """
        date_str = summary.date.strftime("%d.%m.%Y")
        
        lines = [
            f"📊 #dailysummary за {date_str}",
            "",
            "━━━━━━━━━━━━━━━━━━━━",
            "📈 СТАТИСТИКА",
            "━━━━━━━━━━━━━━━━━━━━",
            f"💬 Сообщений: {summary.message_count}",
            f"👥 Активных: {summary.active_users}",
        ]
        
        if summary.peak_hour is not None:
            lines.append(f"⏰ Пик активности: {summary.peak_hour}:00")
        
        if summary.new_members > 0:
            lines.append(f"🆕 Новичков: {summary.new_members}")
        
        if summary.moderation_actions > 0:
            lines.append(f"⚠️ Модерация: {summary.moderation_actions}")
        
        # Toxicity thermometer
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🌡️ ТЕРМОМЕТР ТОКСИЧНОСТИ")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        
        toxicity_emoji = self._get_toxicity_emoji(summary.toxicity_score)
        toxicity_label = self._get_toxicity_label(summary.toxicity_score)
        
        # Visual thermometer bar
        filled = int(summary.toxicity_score / 10)
        bar = "█" * filled + "░" * (10 - filled)
        
        lines.append(f"{toxicity_emoji} [{bar}] {summary.toxicity_score:.0f}%")
        lines.append(f"Вайб: {toxicity_label}")
        
        if summary.toxicity_incidents > 0:
            lines.append(f"🚨 Инцидентов: {summary.toxicity_incidents}")
        
        # Top chatters
        if summary.top_chatters:
            lines.append("")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("🏆 ТОП БОЛТУНОВ")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
            for i, chatter in enumerate(summary.top_chatters[:5]):
                medal = medals[i] if i < len(medals) else f"{i+1}."
                lines.append(f"{medal} {chatter['username']}: {chatter['count']} сообщ.")
        
        # Hot topics with links
        if summary.hot_topics:
            lines.append("")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("🔥 ГОРЯЧИЕ ТЕМЫ")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            for topic in summary.hot_topics[:5]:
                keyword = topic['keyword']
                mentions = topic['mentions']
                msg_id = topic.get('message_id')
                
                if msg_id and summary.chat_id:
                    # Create message link (works for supergroups)
                    # Format: https://t.me/c/CHAT_ID/MESSAGE_ID
                    # For supergroups, chat_id is negative, we need to remove -100 prefix
                    chat_id_str = str(abs(summary.chat_id))
                    if chat_id_str.startswith("100"):
                        chat_id_str = chat_id_str[3:]
                    link = f"https://t.me/c/{chat_id_str}/{msg_id}"
                    # Make the keyword itself clickable
                    lines.append(f'• <a href="{link}">{keyword}</a> ({mentions}x)')
                else:
                    lines.append(f"• {keyword} ({mentions}x)")
        
        lines.append("")
        lines.append("Хорошего дня! ☀️")
        
        return "\n".join(lines)
    
    # =========================================================================
    # Quote Selection (Requirement 13.2)
    # =========================================================================
    
    async def select_daily_quote(
        self,
        chat_id: Optional[int] = None,
        session: Optional[AsyncSession] = None
    ) -> DailyQuote:
        """
        Select a daily quote (from Golden Fund or generated).
        
        Requirement 13.2: WHEN the time reaches 21:00 Moscow time
        THEN the Dailies System SHALL send a #dailyquote message
        with a wisdom quote (either from Golden Fund or generated).
        
        Args:
            chat_id: Optional chat ID to prefer chat-specific quotes
            session: Optional database session
            
        Returns:
            DailyQuote with selected quote
        """
        # Try to get quote from Golden Fund first
        if self.golden_fund_service:
            try:
                golden_quote = await self.golden_fund_service.get_random_golden_quote(
                    chat_id=chat_id
                )
                
                if golden_quote:
                    return DailyQuote(
                        text=golden_quote.text,
                        author=golden_quote.username,
                        is_from_golden_fund=True,
                        sticker_file_id=golden_quote.sticker_file_id
                    )
            except Exception as e:
                logger.warning(f"Failed to get golden quote: {e}")
        
        # Fall back to default wisdom quotes
        quote_text = random.choice(DEFAULT_WISDOM_QUOTES)
        return DailyQuote(
            text=quote_text,
            author=None,
            is_from_golden_fund=False,
            sticker_file_id=None
        )
    
    def format_quote(self, quote: DailyQuote) -> str:
        """
        Format daily quote for display.
        
        Requirement 13.2: Send a #dailyquote message.
        
        Args:
            quote: DailyQuote to format
            
        Returns:
            Formatted quote string
        """
        lines = ["💭 #dailyquote", ""]
        
        if quote.is_from_golden_fund and quote.author:
            lines.append(f'"{quote.text}"')
            lines.append(f"— {quote.author}")
            lines.append("")
            lines.append("🏆 Из Золотого Фонда")
        else:
            lines.append(f'"{quote.text}"')
        
        return "\n".join(lines)
    
    # =========================================================================
    # Stats Aggregation (Requirement 13.3)
    # =========================================================================
    
    async def aggregate_daily_stats(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> DailyStats:
        """
        Aggregate daily game statistics.
        
        Requirement 13.3: WHEN the time reaches 21:00 Moscow time
        THEN the Dailies System SHALL send a #dailystats message
        with game statistics.
        
        Args:
            chat_id: Telegram chat ID
            session: Optional database session
            
        Returns:
            DailyStats with aggregated statistics
        """
        from app.database.models import GameStat, User
        from app.database.session import get_session
        from app.utils import utc_now
        
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            now = utc_now()
            
            # Get top growers (by size_cm)
            top_growers_result = await session.execute(
                select(GameStat, User)
                .join(User, GameStat.user_id == User.id)
                .order_by(GameStat.size_cm.desc())
                .limit(5)
            )
            top_growers_rows = top_growers_result.all()
            
            top_growers = [
                {
                    "username": user.username or user.first_name or f"User {user.tg_user_id}",
                    "size": game_stat.size_cm
                }
                for game_stat, user in top_growers_rows
            ]
            
            # Get top losers (lowest size_cm, but > 0)
            top_losers_result = await session.execute(
                select(GameStat, User)
                .join(User, GameStat.user_id == User.id)
                .filter(GameStat.size_cm > 0)
                .order_by(GameStat.size_cm.asc())
                .limit(5)
            )
            top_losers_rows = top_losers_result.all()
            
            top_losers = [
                {
                    "username": user.username or user.first_name or f"User {user.tg_user_id}",
                    "size": game_stat.size_cm
                }
                for game_stat, user in top_losers_rows
            ]
            
            # Get tournament standings
            tournament_standings = []
            try:
                from app.services.tournaments import tournament_service, TournamentType
                
                daily_tournament = await tournament_service.get_current_tournament(
                    TournamentType.DAILY, session
                )
                
                if daily_tournament:
                    for discipline, standings in daily_tournament.standings.items():
                        for standing in standings[:3]:
                            tournament_standings.append({
                                "discipline": discipline.value,
                                "username": standing.username or f"User {standing.user_id}",
                                "score": standing.score,
                                "rank": standing.rank
                            })
            except Exception as e:
                logger.warning(f"Failed to get tournament standings: {e}")
            
            return DailyStats(
                chat_id=chat_id,
                date=now,
                top_growers=top_growers,
                top_losers=top_losers,
                tournament_standings=tournament_standings
            )
            
        except Exception as e:
            logger.error(f"Failed to aggregate stats for chat {chat_id}: {e}")
            return DailyStats(chat_id=chat_id, date=utc_now())
            
        finally:
            if close_session:
                await session.close()
    
    def format_stats(self, stats: DailyStats) -> str:
        """
        Format daily stats for display.
        
        Requirement 13.3: Send a #dailystats message with game statistics.
        
        Args:
            stats: DailyStats to format
            
        Returns:
            Formatted stats string
        """
        lines = ["📈 #dailystats", ""]
        
        # Top growers
        if stats.top_growers:
            lines.append("🌱 Топ гроверов:")
            for i, grower in enumerate(stats.top_growers[:3], 1):
                emoji = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
                lines.append(f"  {emoji} {grower['username']}: {grower['size']} см")
            lines.append("")
        
        # Top losers (for fun)
        if stats.top_losers:
            lines.append("📉 Нужна помощь:")
            for i, loser in enumerate(stats.top_losers[:3], 1):
                lines.append(f"  {i}. {loser['username']}: {loser['size']} см")
            lines.append("")
        
        # Tournament standings
        if stats.tournament_standings:
            lines.append("🏆 Турнир дня:")
            for standing in stats.tournament_standings[:5]:
                emoji = ["🥇", "🥈", "🥉"][standing['rank']-1] if standing['rank'] <= 3 else f"{standing['rank']}."
                lines.append(f"  {emoji} {standing['username']}: {standing['score']} ({standing['discipline']})")
        
        if not stats.top_growers and not stats.tournament_standings:
            lines.append("Пока нет статистики. Играйте больше! 🎮")
        
        return "\n".join(lines)
    
    # =========================================================================
    # Combined Daily Messages
    # =========================================================================
    
    async def get_morning_messages(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> List[str]:
        """
        Get all morning messages for a chat.
        
        Requirement 13.1: Morning summary at 09:00 Moscow.
        
        Args:
            chat_id: Telegram chat ID
            session: Optional database session
            
        Returns:
            List of formatted message strings to send
        """
        messages = []
        
        config = await self.get_config(chat_id, session)
        
        # Check if summary is enabled (Property 33)
        if self.should_send_message(config, 'summary'):
            summary = await self.generate_summary(chat_id, session)
            
            # Check if should skip due to no activity (Property 34)
            if not self.should_skip_summary(summary):
                messages.append(self.format_summary(summary))
        
        return messages
    
    async def get_evening_messages(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> List[str]:
        """
        Get all evening messages for a chat.
        
        Requirements 13.2, 13.3: Evening quote and stats at 21:00 Moscow.
        
        Args:
            chat_id: Telegram chat ID
            session: Optional database session
            
        Returns:
            List of formatted message strings to send
        """
        messages = []
        
        config = await self.get_config(chat_id, session)
        
        # Check if quote is enabled (Property 33)
        if self.should_send_message(config, 'quote'):
            quote = await self.select_daily_quote(chat_id, session)
            messages.append(self.format_quote(quote))
        
        # Check if stats is enabled (Property 33)
        if self.should_send_message(config, 'stats'):
            stats = await self.aggregate_daily_stats(chat_id, session)
            messages.append(self.format_stats(stats))
        
        return messages


# Global service instance
dailies_service = DailiesService()
