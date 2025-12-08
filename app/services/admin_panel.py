"""Admin Panel Service for Chat Owners.

This module provides the Admin Panel service for chat owners to manage
their chat settings through private messages with the bot.

Note: This is different from admin_dashboard.py which is for bot owner only.
This service is for chat owners to manage their own chats.

**Feature: fortress-update**
**Validates: Requirements 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7, 16.8, 16.9, 16.10, 16.11, 16.12**
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, Chat as TelegramChat
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Chat, CitadelConfig, NotificationConfig, DailiesConfig
from app.database.session import get_session
from app.services.citadel import DEFCONLevel, citadel_service
from app.services.notifications import NotificationType, notification_service

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Constants
# ============================================================================

class AdminMenuCategory(str, Enum):
    """
    Admin panel menu categories.
    
    **Validates: Requirements 16.3, 16.4, 16.5, 16.6, 16.7, 16.10**
    """
    PROTECTION = "protection"      # DEFCON, anti-spam, profanity filter
    NOTIFICATIONS = "notifications"  # Raid alerts, ban notifications, etc.
    GAMES = "games"                # Game commands, tournaments
    DAILIES = "dailies"            # Morning summary, evening quote, stats
    QUOTES = "quotes"              # Theme, Golden Fund, sticker packs
    ADVANCED = "advanced"          # Toxicity threshold, mute durations


# Category display names and emojis
CATEGORY_DISPLAY = {
    AdminMenuCategory.PROTECTION: ("🛡", "Защита"),
    AdminMenuCategory.NOTIFICATIONS: ("🔔", "Уведомления"),
    AdminMenuCategory.GAMES: ("🎮", "Игры"),
    AdminMenuCategory.DAILIES: ("📅", "Дейлики"),
    AdminMenuCategory.QUOTES: ("💬", "Цитаты"),
    AdminMenuCategory.ADVANCED: ("⚙️", "Расширенные"),
}

# DEFCON level display
DEFCON_DISPLAY = {
    1: ("🟢", "Мирный"),
    2: ("🟡", "Строгий"),
    3: ("🔴", "Военное положение"),
}

# Callback data prefixes for admin panel
CALLBACK_PREFIX = "owner_"  # Prefix to distinguish from bot owner admin panel


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ChatSettings:
    """
    Aggregated chat settings for admin panel display.
    
    Attributes:
        chat_id: Telegram chat ID
        chat_title: Chat title
        defcon_level: Current DEFCON level
        anti_spam_enabled: Anti-spam filter status
        profanity_filter_enabled: Profanity filter status
        sticker_limit: Sticker flood limit (0 = disabled)
        forward_block_enabled: Forward blocking status
        notifications: Dict of notification type -> enabled
        games_enabled: Whether games are enabled
        tournaments_enabled: Whether tournaments are enabled
        dailies: Dict of daily message type -> enabled
        quote_theme: Quote theme (dark/light/auto)
        golden_fund_enabled: Golden Fund participation
        toxicity_threshold: Toxicity threshold (0-100)
        mute_duration: Default mute duration in minutes
    """
    chat_id: int
    chat_title: str
    defcon_level: int = 1
    anti_spam_enabled: bool = True
    profanity_filter_enabled: bool = False
    sticker_limit: int = 0
    forward_block_enabled: bool = False
    notifications: Dict[str, bool] = field(default_factory=dict)
    games_enabled: bool = True
    tournaments_enabled: bool = True
    dailies: Dict[str, bool] = field(default_factory=dict)
    quote_theme: str = "auto"
    golden_fund_enabled: bool = True
    toxicity_threshold: int = 75
    mute_duration: int = 5


# ============================================================================
# Admin Panel Service
# ============================================================================

class AdminPanelService:
    """
    Service for chat owner admin panel in private messages.
    
    This service allows chat owners to manage their chat settings
    through an inline keyboard menu in private messages with the bot.
    
    Features:
    - List chats where user is owner (Requirement 16.1)
    - Main menu with categories (Requirement 16.2)
    - Protection settings (Requirement 16.3)
    - Notification toggles (Requirement 16.4)
    - Game settings (Requirement 16.5)
    - Dailies settings (Requirement 16.6)
    - Quote settings (Requirement 16.7)
    - Setting changes apply immediately (Requirement 16.9)
    - Access control (Requirement 16.10)
    - Advanced settings (Requirement 16.11)
    - PM-only access (Requirement 16.12)
    """
    
    def __init__(self):
        """Initialize AdminPanelService."""
        pass
    
    # =========================================================================
    # Ownership Verification (Requirement 16.10)
    # =========================================================================
    
    async def verify_ownership(
        self,
        bot: Bot,
        user_id: int,
        chat_id: int
    ) -> bool:
        """
        Verify that a user is the owner/creator of a chat.
        
        **Validates: Requirements 16.10**
        WHEN a user tries to access the Admin Panel for a chat they do not own
        THEN the Admin Panel SHALL respond with "У вас нет прав на управление этим чатом"
        
        Args:
            bot: Telegram Bot instance
            user_id: User ID to verify
            chat_id: Chat ID to check ownership
            
        Returns:
            True if user is owner/creator, False otherwise
        """
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            return member.status == 'creator'
        except Exception as e:
            logger.warning(f"Failed to verify ownership for user {user_id} in chat {chat_id}: {e}")
            return False
    
    async def get_owner_chats(
        self,
        bot: Bot,
        user_id: int
    ) -> List[Chat]:
        """
        Get list of chats where user is owner/creator.
        
        **Validates: Requirements 16.1**
        WHEN a chat owner sends "/admin" in private messages to the bot
        THEN the Admin Panel SHALL display a list of chats where the user is owner
        
        Args:
            bot: Telegram Bot instance
            user_id: User ID to find chats for
            
        Returns:
            List of Chat objects where user is owner
        """
        async with get_session()() as session:
            result = await session.execute(select(Chat))
            all_chats = result.scalars().all()
        
        owner_chats = []
        
        for chat in all_chats:
            try:
                if await self.verify_ownership(bot, user_id, chat.id):
                    owner_chats.append(chat)
            except Exception as e:
                logger.debug(f"Could not check chat {chat.id}: {e}")
                continue
        
        return owner_chats

    
    # =========================================================================
    # Settings Loading
    # =========================================================================
    
    async def get_chat_settings(
        self,
        chat_id: int,
        chat_title: str,
        session: Optional[AsyncSession] = None
    ) -> ChatSettings:
        """
        Load all settings for a chat.
        
        Args:
            chat_id: Telegram chat ID
            chat_title: Chat title for display
            session: Optional database session
            
        Returns:
            ChatSettings with all current settings
        """
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            # Load Citadel config
            citadel_config = await citadel_service.get_config(chat_id, session)
            
            # Load notification config
            notif_config = await notification_service.get_config(chat_id, session)
            
            # Load dailies config
            from app.services.dailies import dailies_service
            dailies_config = await dailies_service.get_config(chat_id, session)
            
            # Load toxicity config
            from app.database.models import ToxicityConfig
            tox_result = await session.execute(
                select(ToxicityConfig).filter_by(chat_id=chat_id)
            )
            tox_config = tox_result.scalar_one_or_none()
            
            # Build notifications dict
            notifications = {
                NotificationType.RAID_ALERT.value: notif_config.is_enabled(NotificationType.RAID_ALERT),
                NotificationType.BAN_NOTIFICATION.value: notif_config.is_enabled(NotificationType.BAN_NOTIFICATION),
                NotificationType.TOXICITY_WARNING.value: notif_config.is_enabled(NotificationType.TOXICITY_WARNING),
                NotificationType.DAILY_TIPS.value: notif_config.is_enabled(NotificationType.DAILY_TIPS),
            }
            
            # Build dailies dict
            dailies = {
                "summary": dailies_config.summary_enabled,
                "quote": dailies_config.quote_enabled,
                "stats": dailies_config.stats_enabled,
            }
            
            return ChatSettings(
                chat_id=chat_id,
                chat_title=chat_title,
                defcon_level=citadel_config.defcon_level.value,
                anti_spam_enabled=citadel_config.anti_spam_enabled,
                profanity_filter_enabled=citadel_config.profanity_filter_enabled,
                sticker_limit=citadel_config.sticker_limit,
                forward_block_enabled=citadel_config.forward_block_enabled,
                notifications=notifications,
                dailies=dailies,
                toxicity_threshold=tox_config.threshold if tox_config else 75,
                mute_duration=tox_config.mute_duration if tox_config else 5,
            )
            
        finally:
            if close_session:
                await session.close()

    
    # =========================================================================
    # Menu Building (Requirements 16.1, 16.2, 16.3)
    # =========================================================================
    
    def build_chat_list_menu(self, chats: List[Chat]) -> InlineKeyboardMarkup:
        """
        Build menu with list of chats for selection.
        
        **Validates: Requirements 16.1**
        
        Args:
            chats: List of chats where user is owner
            
        Returns:
            InlineKeyboardMarkup with chat buttons
        """
        keyboard = InlineKeyboardBuilder()
        
        for chat in chats:
            title = chat.title[:25] + "..." if len(chat.title) > 25 else chat.title
            keyboard.button(
                text=f"💬 {title}",
                callback_data=f"{CALLBACK_PREFIX}chat_{chat.id}"
            )
        
        keyboard.adjust(1)
        return keyboard.as_markup()
    
    def build_main_menu(self, chat_id: int) -> InlineKeyboardMarkup:
        """
        Build main menu with configuration categories.
        
        **Validates: Requirements 16.2**
        WHEN the owner selects a chat THEN the Admin Panel SHALL display
        an inline keyboard menu with main configuration categories
        
        Args:
            chat_id: Chat ID for callback data
            
        Returns:
            InlineKeyboardMarkup with category buttons
        """
        keyboard = InlineKeyboardBuilder()
        
        for category in AdminMenuCategory:
            emoji, name = CATEGORY_DISPLAY[category]
            keyboard.button(
                text=f"{emoji} {name}",
                callback_data=f"{CALLBACK_PREFIX}cat_{chat_id}_{category.value}"
            )
        
        keyboard.button(
            text="🔙 К списку чатов",
            callback_data=f"{CALLBACK_PREFIX}back_list"
        )
        
        keyboard.adjust(2, 2, 2, 1)
        return keyboard.as_markup()
    
    async def build_category_menu(
        self,
        chat_id: int,
        category: AdminMenuCategory,
        session: Optional[AsyncSession] = None
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Build menu for a specific category.
        
        **Validates: Requirements 16.3, 16.4, 16.5, 16.6, 16.7, 16.10**
        
        Args:
            chat_id: Chat ID
            category: Category to build menu for
            session: Optional database session
            
        Returns:
            Tuple of (menu text, InlineKeyboardMarkup)
        """
        if category == AdminMenuCategory.PROTECTION:
            return await self._build_protection_menu(chat_id, session)
        elif category == AdminMenuCategory.NOTIFICATIONS:
            return await self._build_notifications_menu(chat_id, session)
        elif category == AdminMenuCategory.GAMES:
            return await self._build_games_menu(chat_id, session)
        elif category == AdminMenuCategory.DAILIES:
            return await self._build_dailies_menu(chat_id, session)
        elif category == AdminMenuCategory.QUOTES:
            return await self._build_quotes_menu(chat_id, session)
        elif category == AdminMenuCategory.ADVANCED:
            return await self._build_advanced_menu(chat_id, session)
        else:
            return "Неизвестная категория", self.build_main_menu(chat_id)

    
    # =========================================================================
    # Protection Menu (Requirement 16.3)
    # =========================================================================
    
    async def _build_protection_menu(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Build Protection category menu.
        
        **Validates: Requirements 16.3**
        WHEN the owner selects "Protection" THEN the Admin Panel SHALL display
        current DEFCON level with buttons to change it and toggle individual features
        
        Args:
            chat_id: Chat ID
            session: Optional database session
            
        Returns:
            Tuple of (menu text, InlineKeyboardMarkup)
        """
        config = await citadel_service.get_config(chat_id, session)
        
        level = config.defcon_level.value
        emoji, name = DEFCON_DISPLAY.get(level, ("❓", "Неизвестно"))
        
        # Get gif_patrol_enabled safely
        gif_patrol_enabled = getattr(config, 'gif_patrol_enabled', False)
        
        text = (
            f"🛡 <b>Защита</b>\n\n"
            f"Текущий уровень: {emoji} DEFCON {level} ({name})\n\n"
            f"<b>Уровни защиты:</b>\n"
            f"🟢 DEFCON 1 — Базовая защита\n"
            f"🟡 DEFCON 2 — Усиленная защита\n"
            f"🔴 DEFCON 3 — Максимальная защита\n\n"
            f"<b>Текущие настройки:</b>\n"
            f"• Антиспам: {'✅' if config.anti_spam_enabled else '❌'}\n"
            f"• Фильтр мата: {'✅' if config.profanity_filter_enabled else '❌'}\n"
            f"• Лимит стикеров: {config.sticker_limit if config.sticker_limit > 0 else 'Выкл'}\n"
            f"• Блок пересылок: {'✅' if config.forward_block_enabled else '❌'}\n"
            f"• GIF-патруль: {'✅' if gif_patrol_enabled else '❌'} <i>(work in progress)</i>"
        )
        
        keyboard = InlineKeyboardBuilder()
        
        # DEFCON level buttons
        for lvl in [1, 2, 3]:
            lvl_emoji, lvl_name = DEFCON_DISPLAY[lvl]
            selected = "✓ " if lvl == level else ""
            keyboard.button(
                text=f"{selected}{lvl_emoji} {lvl}",
                callback_data=f"{CALLBACK_PREFIX}defcon_{chat_id}_{lvl}"
            )
        
        # Feature toggles
        keyboard.button(
            text=f"{'✅' if config.anti_spam_enabled else '❌'} Антиспам",
            callback_data=f"{CALLBACK_PREFIX}toggle_{chat_id}_antispam"
        )
        keyboard.button(
            text=f"{'✅' if config.profanity_filter_enabled else '❌'} Фильтр мата",
            callback_data=f"{CALLBACK_PREFIX}toggle_{chat_id}_profanity"
        )
        keyboard.button(
            text=f"{'✅' if config.sticker_limit > 0 else '❌'} Лимит стикеров",
            callback_data=f"{CALLBACK_PREFIX}toggle_{chat_id}_sticker"
        )
        keyboard.button(
            text=f"{'✅' if config.forward_block_enabled else '❌'} Блок пересылок",
            callback_data=f"{CALLBACK_PREFIX}toggle_{chat_id}_forward"
        )
        keyboard.button(
            text=f"{'✅' if gif_patrol_enabled else '❌'} GIF-патруль 🚧",
            callback_data=f"{CALLBACK_PREFIX}toggle_{chat_id}_gifpatrol"
        )
        
        keyboard.button(
            text="🔙 Назад",
            callback_data=f"{CALLBACK_PREFIX}chat_{chat_id}"
        )
        
        keyboard.adjust(3, 2, 2, 1, 1)
        return text, keyboard.as_markup()

    
    # =========================================================================
    # Notifications Menu (Requirement 16.4)
    # =========================================================================
    
    async def _build_notifications_menu(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Build Notifications category menu.
        
        **Validates: Requirements 16.4**
        WHEN the owner selects "Notifications" THEN the Admin Panel SHALL display
        toggles for each notification type with current status
        
        Args:
            chat_id: Chat ID
            session: Optional database session
            
        Returns:
            Tuple of (menu text, InlineKeyboardMarkup)
        """
        config = await notification_service.get_config(chat_id, session)
        
        text = (
            f"🔔 <b>Уведомления</b>\n\n"
            f"Настройте, какие уведомления вы хотите получать в ЛС:\n\n"
            f"• 🚨 Рейд-алерты: {'✅' if config.is_enabled(NotificationType.RAID_ALERT) else '❌'}\n"
            f"• 🔨 Баны: {'✅' if config.is_enabled(NotificationType.BAN_NOTIFICATION) else '❌'}\n"
            f"• ⚠️ Токсичность: {'✅' if config.is_enabled(NotificationType.TOXICITY_WARNING) else '❌'}\n"
            f"• 💡 Советы: {'✅' if config.is_enabled(NotificationType.DAILY_TIPS) else '❌'}"
        )
        
        keyboard = InlineKeyboardBuilder()
        
        # Notification toggles
        notif_types = [
            (NotificationType.RAID_ALERT, "🚨 Рейд-алерты"),
            (NotificationType.BAN_NOTIFICATION, "🔨 Баны"),
            (NotificationType.TOXICITY_WARNING, "⚠️ Токсичность"),
            (NotificationType.DAILY_TIPS, "💡 Советы"),
        ]
        
        for notif_type, label in notif_types:
            enabled = config.is_enabled(notif_type)
            keyboard.button(
                text=f"{'✅' if enabled else '❌'} {label}",
                callback_data=f"{CALLBACK_PREFIX}notif_{chat_id}_{notif_type.value}"
            )
        
        keyboard.button(
            text="🔙 Назад",
            callback_data=f"{CALLBACK_PREFIX}chat_{chat_id}"
        )
        
        keyboard.adjust(2, 2, 1)
        return text, keyboard.as_markup()
    
    # =========================================================================
    # Games Menu (Requirement 16.5)
    # =========================================================================
    
    async def _build_games_menu(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Build Games category menu.
        
        **Validates: Requirements 16.5**
        WHEN the owner selects "Games" THEN the Admin Panel SHALL display
        toggles for enabling/disabling game commands and tournament participation
        
        Args:
            chat_id: Chat ID
            session: Optional database session
            
        Returns:
            Tuple of (menu text, InlineKeyboardMarkup)
        """
        # For now, games are always enabled - this can be extended with a games config table
        games_enabled = True
        tournaments_enabled = True
        
        text = (
            f"🎮 <b>Игры</b>\n\n"
            f"Управление игровыми командами:\n\n"
            f"• /grow — Выращивание\n"
            f"• /pvp — PvP битвы\n"
            f"• /roulette — Рулетка\n\n"
            f"Статус: {'✅ Включены' if games_enabled else '❌ Выключены'}\n"
            f"Турниры: {'✅ Включены' if tournaments_enabled else '❌ Выключены'}"
        )
        
        keyboard = InlineKeyboardBuilder()
        
        keyboard.button(
            text=f"{'✅' if games_enabled else '❌'} Игровые команды",
            callback_data=f"{CALLBACK_PREFIX}games_{chat_id}_toggle"
        )
        keyboard.button(
            text=f"{'✅' if tournaments_enabled else '❌'} Турниры",
            callback_data=f"{CALLBACK_PREFIX}games_{chat_id}_tournaments"
        )
        
        keyboard.button(
            text="🔙 Назад",
            callback_data=f"{CALLBACK_PREFIX}chat_{chat_id}"
        )
        
        keyboard.adjust(1, 1, 1)
        return text, keyboard.as_markup()

    
    # =========================================================================
    # Dailies Menu (Requirement 16.6)
    # =========================================================================
    
    async def _build_dailies_menu(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Build Dailies category menu.
        
        **Validates: Requirements 16.6**
        WHEN the owner selects "Dailies" THEN the Admin Panel SHALL display
        toggles for morning summary, evening quote, and daily stats
        
        Args:
            chat_id: Chat ID
            session: Optional database session
            
        Returns:
            Tuple of (menu text, InlineKeyboardMarkup)
        """
        from app.services.dailies import dailies_service
        
        config = await dailies_service.get_config(chat_id, session)
        
        text = (
            f"📅 <b>Дейлики</b>\n\n"
            f"Ежедневные автоматические сообщения:\n\n"
            f"• ☀️ Утренняя сводка (09:00 МСК): {'✅' if config.summary_enabled else '❌'}\n"
            f"• 🌙 Вечерняя цитата (21:00 МСК): {'✅' if config.quote_enabled else '❌'}\n"
            f"• 📊 Статистика дня (21:00 МСК): {'✅' if config.stats_enabled else '❌'}"
        )
        
        keyboard = InlineKeyboardBuilder()
        
        keyboard.button(
            text=f"{'✅' if config.summary_enabled else '❌'} Утренняя сводка",
            callback_data=f"{CALLBACK_PREFIX}daily_{chat_id}_summary"
        )
        keyboard.button(
            text=f"{'✅' if config.quote_enabled else '❌'} Вечерняя цитата",
            callback_data=f"{CALLBACK_PREFIX}daily_{chat_id}_quote"
        )
        keyboard.button(
            text=f"{'✅' if config.stats_enabled else '❌'} Статистика дня",
            callback_data=f"{CALLBACK_PREFIX}daily_{chat_id}_stats"
        )
        
        keyboard.button(
            text="🔙 Назад",
            callback_data=f"{CALLBACK_PREFIX}chat_{chat_id}"
        )
        
        keyboard.adjust(1, 1, 1, 1)
        return text, keyboard.as_markup()
    
    # =========================================================================
    # Quotes Menu (Requirement 16.7)
    # =========================================================================
    
    async def _build_quotes_menu(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Build Quotes category menu.
        
        **Validates: Requirements 16.7**
        WHEN the owner selects "Quotes" THEN the Admin Panel SHALL display
        settings for quote themes, Golden Fund participation, and sticker pack management
        
        Args:
            chat_id: Chat ID
            session: Optional database session
            
        Returns:
            Tuple of (menu text, InlineKeyboardMarkup)
        """
        # Default settings - can be extended with a quotes config table
        quote_theme = "auto"
        golden_fund_enabled = True
        
        theme_display = {
            "dark": "🌙 Тёмная",
            "light": "☀️ Светлая",
            "auto": "🔄 Авто"
        }
        
        text = (
            f"💬 <b>Цитаты</b>\n\n"
            f"Настройки генератора цитат:\n\n"
            f"• Тема: {theme_display.get(quote_theme, 'Авто')}\n"
            f"• Золотой Фонд: {'✅ Участвует' if golden_fund_enabled else '❌ Не участвует'}\n\n"
            f"Стикерпак чата управляется автоматически."
        )
        
        keyboard = InlineKeyboardBuilder()
        
        # Theme selection
        for theme, label in theme_display.items():
            selected = "✓ " if theme == quote_theme else ""
            keyboard.button(
                text=f"{selected}{label}",
                callback_data=f"{CALLBACK_PREFIX}quote_{chat_id}_theme_{theme}"
            )
        
        keyboard.button(
            text=f"{'✅' if golden_fund_enabled else '❌'} Золотой Фонд",
            callback_data=f"{CALLBACK_PREFIX}quote_{chat_id}_golden"
        )
        
        keyboard.button(
            text="📦 Стикерпак",
            callback_data=f"{CALLBACK_PREFIX}quote_{chat_id}_stickers"
        )
        
        keyboard.button(
            text="🔙 Назад",
            callback_data=f"{CALLBACK_PREFIX}chat_{chat_id}"
        )
        
        keyboard.adjust(3, 1, 1, 1)
        return text, keyboard.as_markup()

    
    # =========================================================================
    # Advanced Menu (Requirement 16.10)
    # =========================================================================
    
    async def _build_advanced_menu(
        self,
        chat_id: int,
        session: Optional[AsyncSession] = None
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Build Advanced Settings menu.
        
        **Validates: Requirements 16.10**
        WHEN the owner selects "Advanced Settings" THEN the Admin Panel SHALL display
        toxicity threshold slider, mute durations, and custom banned words management
        
        Args:
            chat_id: Chat ID
            session: Optional database session
            
        Returns:
            Tuple of (menu text, InlineKeyboardMarkup)
        """
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            from app.database.models import ToxicityConfig
            
            result = await session.execute(
                select(ToxicityConfig).filter_by(chat_id=chat_id)
            )
            tox_config = result.scalar_one_or_none()
            
            threshold = tox_config.threshold if tox_config else 75
            mute_duration = tox_config.mute_duration if tox_config else 5
            
        finally:
            if close_session:
                await session.close()
        
        text = (
            f"⚙️ <b>Расширенные настройки</b>\n\n"
            f"<b>Токсичность:</b>\n"
            f"• Порог срабатывания: {threshold}%\n"
            f"• Длительность мута: {mute_duration} мин\n\n"
            f"<b>Порог токсичности:</b>\n"
            f"Чем ниже значение, тем строже модерация.\n"
            f"Рекомендуется: 60-80%"
        )
        
        keyboard = InlineKeyboardBuilder()
        
        # Toxicity threshold buttons
        keyboard.button(text="50%", callback_data=f"{CALLBACK_PREFIX}adv_{chat_id}_tox_50")
        keyboard.button(text="60%", callback_data=f"{CALLBACK_PREFIX}adv_{chat_id}_tox_60")
        keyboard.button(text="70%", callback_data=f"{CALLBACK_PREFIX}adv_{chat_id}_tox_70")
        keyboard.button(text="80%", callback_data=f"{CALLBACK_PREFIX}adv_{chat_id}_tox_80")
        keyboard.button(text="90%", callback_data=f"{CALLBACK_PREFIX}adv_{chat_id}_tox_90")
        
        # Mute duration buttons
        keyboard.button(text="1 мин", callback_data=f"{CALLBACK_PREFIX}adv_{chat_id}_mute_1")
        keyboard.button(text="5 мин", callback_data=f"{CALLBACK_PREFIX}adv_{chat_id}_mute_5")
        keyboard.button(text="15 мин", callback_data=f"{CALLBACK_PREFIX}adv_{chat_id}_mute_15")
        keyboard.button(text="30 мин", callback_data=f"{CALLBACK_PREFIX}adv_{chat_id}_mute_30")
        keyboard.button(text="60 мин", callback_data=f"{CALLBACK_PREFIX}adv_{chat_id}_mute_60")
        
        keyboard.button(
            text="📝 Запрещённые слова",
            callback_data=f"{CALLBACK_PREFIX}adv_{chat_id}_words"
        )
        
        keyboard.button(
            text="🔙 Назад",
            callback_data=f"{CALLBACK_PREFIX}chat_{chat_id}"
        )
        
        keyboard.adjust(5, 5, 1, 1)
        return text, keyboard.as_markup()

    
    # =========================================================================
    # Callback Handling (Requirement 16.9)
    # =========================================================================
    
    async def handle_callback(
        self,
        bot: Bot,
        user_id: int,
        chat_id: int,
        action: str,
        value: Any = None,
        session: Optional[AsyncSession] = None
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Handle callback action and return updated menu.
        
        **Validates: Requirements 16.9**
        WHEN the owner changes any setting THEN the Admin Panel SHALL
        immediately apply the change and confirm with an updated menu
        
        Args:
            bot: Telegram Bot instance
            user_id: User ID making the change
            chat_id: Chat ID being configured
            action: Action to perform
            value: Optional value for the action
            session: Optional database session
            
        Returns:
            Tuple of (confirmation message, updated InlineKeyboardMarkup)
        """
        # Verify ownership first
        if not await self.verify_ownership(bot, user_id, chat_id):
            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="🔙 Назад", callback_data=f"{CALLBACK_PREFIX}back_list")
            return "❌ У вас нет прав на управление этим чатом", keyboard.as_markup()
        
        close_session = False
        if session is None:
            async_session = get_session()
            session = async_session()
            close_session = True
        
        try:
            # Handle DEFCON level change
            if action == "defcon":
                level = int(value)
                await citadel_service.set_defcon(chat_id, DEFCONLevel(level), session)
                return await self._build_protection_menu(chat_id, session)
            
            # Handle protection toggles
            elif action == "toggle":
                return await self._handle_protection_toggle(chat_id, value, session)
            
            # Handle notification toggles
            elif action == "notif":
                notif_type = NotificationType(value)
                config = await notification_service.get_config(chat_id, session)
                new_state = not config.is_enabled(notif_type)
                await notification_service.toggle_notification(chat_id, notif_type, new_state, session)
                return await self._build_notifications_menu(chat_id, session)
            
            # Handle dailies toggles
            elif action == "daily":
                return await self._handle_dailies_toggle(chat_id, value, session)
            
            # Handle advanced settings
            elif action == "adv":
                return await self._handle_advanced_setting(chat_id, value, session)
            
            else:
                return "Неизвестное действие", self.build_main_menu(chat_id)
                
        finally:
            if close_session:
                await session.close()
    
    async def _handle_protection_toggle(
        self,
        chat_id: int,
        toggle_type: str,
        session: AsyncSession
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle protection feature toggle."""
        from app.database.models import CitadelConfig as CitadelConfigModel
        
        result = await session.execute(
            select(CitadelConfigModel).filter_by(chat_id=chat_id)
        )
        db_config = result.scalar_one_or_none()
        
        if db_config is None:
            # Create default config
            db_config = CitadelConfigModel(chat_id=chat_id)
            session.add(db_config)
        
        if toggle_type == "antispam":
            db_config.anti_spam_enabled = not db_config.anti_spam_enabled
        elif toggle_type == "profanity":
            db_config.profanity_filter_enabled = not db_config.profanity_filter_enabled
        elif toggle_type == "sticker":
            db_config.sticker_limit = 0 if db_config.sticker_limit > 0 else 3
        elif toggle_type == "forward":
            db_config.forward_block_enabled = not db_config.forward_block_enabled
        elif toggle_type == "gifpatrol":
            # GIF patrol toggle (work in progress)
            current = getattr(db_config, 'gif_patrol_enabled', False)
            db_config.gif_patrol_enabled = not current
        
        await session.commit()
        citadel_service.invalidate_cache(chat_id)
        
        return await self._build_protection_menu(chat_id, session)
    
    async def _handle_dailies_toggle(
        self,
        chat_id: int,
        toggle_type: str,
        session: AsyncSession
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle dailies toggle."""
        from app.services.dailies import dailies_service
        
        config = await dailies_service.get_config(chat_id, session)
        
        if toggle_type == "summary":
            await dailies_service.update_config(
                chat_id, summary_enabled=not config.summary_enabled, session=session
            )
        elif toggle_type == "quote":
            await dailies_service.update_config(
                chat_id, quote_enabled=not config.quote_enabled, session=session
            )
        elif toggle_type == "stats":
            await dailies_service.update_config(
                chat_id, stats_enabled=not config.stats_enabled, session=session
            )
        
        return await self._build_dailies_menu(chat_id, session)

    
    async def _handle_advanced_setting(
        self,
        chat_id: int,
        setting: str,
        session: AsyncSession
    ) -> Tuple[str, InlineKeyboardMarkup]:
        """Handle advanced settings change."""
        from app.database.models import ToxicityConfig
        
        result = await session.execute(
            select(ToxicityConfig).filter_by(chat_id=chat_id)
        )
        tox_config = result.scalar_one_or_none()
        
        if tox_config is None:
            tox_config = ToxicityConfig(chat_id=chat_id)
            session.add(tox_config)
        
        if setting.startswith("tox_"):
            threshold = int(setting.split("_")[1])
            tox_config.threshold = threshold
        elif setting.startswith("mute_"):
            duration = int(setting.split("_")[1])
            tox_config.mute_duration = duration
        
        await session.commit()
        
        return await self._build_advanced_menu(chat_id, session)


# Global service instance
admin_panel_service = AdminPanelService()
