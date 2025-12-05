"""
Admin Dashboard - Owner Panel for bot management.
Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7
"""

import logging
import io
from typing import Optional, List
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func, desc

from app.database.session import get_session
from app.database.models import (
    Chat, User, Blacklist, ToxicityLog, MessageLog
)
from app.config import settings
from app.utils import utc_now

logger = logging.getLogger(__name__)

router = Router()


class AdminStates(StatesGroup):
    """FSM states for admin dashboard."""
    waiting_for_blacklist_user = State()
    waiting_for_blacklist_reason = State()


class AdminDashboard:
    """
    Admin dashboard for bot owner management.
    Provides inline button menu for managing chats, moderation, behavior, and statistics.
    Requirements: 7.1, 7.2
    """
    
    MODERATION_MODES = ["light", "normal", "toxic"]
    MODE_NAMES = {
        "light": "🟢 Лайт",
        "normal": "🟡 Норма", 
        "toxic": "🔴 Токсик"
    }
    
    @staticmethod
    async def get_owner_chats(bot: Bot, user_id: int) -> List[Chat]:
        """
        Get list of chats where user is owner/creator.
        Requirements: 7.1
        """
        async with get_session()() as session:
            result = await session.execute(select(Chat))
            all_chats = result.scalars().all()
        
        owner_chats = []
        
        # Bot owner sees all chats
        if user_id == settings.owner_id:
            return list(all_chats)
        
        for chat in all_chats:
            try:
                member = await bot.get_chat_member(chat.id, user_id)
                if member.status == 'creator':
                    owner_chats.append(chat)
            except Exception as e:
                logger.debug(f"Could not check chat {chat.id}: {e}")
                continue
        
        return owner_chats
    
    @staticmethod
    def build_main_menu(chats: List[Chat]) -> InlineKeyboardBuilder:
        """
        Build main menu with chat list.
        Requirements: 7.1
        """
        keyboard = InlineKeyboardBuilder()
        
        for chat in chats:
            title = chat.title[:30] + "..." if len(chat.title) > 30 else chat.title
            keyboard.button(text=f"💬 {title}", callback_data=f"adm_chat_{chat.id}")
        
        keyboard.adjust(1)
        return keyboard
    
    @staticmethod
    def build_chat_menu(chat_id: int) -> InlineKeyboardBuilder:
        """
        Build chat settings menu with sections.
        Requirements: 7.2
        """
        keyboard = InlineKeyboardBuilder()
        
        keyboard.button(text="🛡 Модерация", callback_data=f"adm_mod_{chat_id}")
        keyboard.button(text="⚙️ Поведение", callback_data=f"adm_beh_{chat_id}")
        keyboard.button(text="🎬 Действия", callback_data=f"adm_act_{chat_id}")
        keyboard.button(text="📊 Статистика", callback_data=f"adm_stats_{chat_id}")
        keyboard.button(text="🔙 Назад", callback_data="adm_back_main")
        
        keyboard.adjust(2, 2, 1)
        return keyboard
    
    @staticmethod
    async def build_moderation_menu(chat_id: int) -> InlineKeyboardBuilder:
        """
        Build moderation section menu.
        Requirements: 7.3
        """
        async with get_session()() as session:
            chat = await session.get(Chat, chat_id)
            current_mode = chat.moderation_mode if chat else "normal"
        
        mode_display = AdminDashboard.MODE_NAMES.get(current_mode, current_mode)
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text=f"Режим: {mode_display}", callback_data=f"adm_mode_{chat_id}")
        keyboard.button(text="🔨 Банхаммер", callback_data=f"adm_ban_{chat_id}")
        keyboard.button(text="🔙 Назад", callback_data=f"adm_chat_{chat_id}")
        
        keyboard.adjust(1)
        return keyboard
    
    @staticmethod
    async def build_behavior_menu(chat_id: int) -> InlineKeyboardBuilder:
        """
        Build behavior section menu.
        Requirements: 7.4
        """
        async with get_session()() as session:
            chat = await session.get(Chat, chat_id)
            auto_reply_pct = int((chat.auto_reply_chance or 0) * 100) if chat else 0
            active_topic = chat.active_topic_id if chat else None
        
        topic_text = f"#{active_topic}" if active_topic else "Везде"
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(
            text=f"🎲 Автоответ: {auto_reply_pct}%", 
            callback_data=f"adm_autoreply_{chat_id}"
        )
        keyboard.button(
            text=f"📍 Топик: {topic_text}", 
            callback_data=f"adm_topic_{chat_id}"
        )
        keyboard.button(text="🔙 Назад", callback_data=f"adm_chat_{chat_id}")
        
        keyboard.adjust(1)
        return keyboard
    
    @staticmethod
    def build_actions_menu(chat_id: int) -> InlineKeyboardBuilder:
        """
        Build actions section menu.
        Requirements: 7.5
        """
        keyboard = InlineKeyboardBuilder()
        
        keyboard.button(text="📝 Дневной отчёт", callback_data=f"adm_summary_{chat_id}")
        keyboard.button(text="📖 Сгенерить историю", callback_data=f"adm_story_{chat_id}")
        keyboard.button(text="💬 Сгенерить цитаты", callback_data=f"adm_quotes_{chat_id}")
        keyboard.button(text="🧹 Очистить контекст", callback_data=f"adm_clear_{chat_id}")
        keyboard.button(text="🔄 Перезапуск бота", callback_data=f"adm_restart_{chat_id}")
        keyboard.button(text="🔙 Назад", callback_data=f"adm_chat_{chat_id}")
        
        keyboard.adjust(2, 2, 1, 1)
        return keyboard
    
    @staticmethod
    async def get_chat_statistics(chat_id: int) -> dict:
        """
        Gather statistics for a chat.
        Requirements: 7.6
        """
        async with get_session()() as session:
            # Get message count for last 24h
            yesterday = utc_now() - timedelta(hours=24)
            
            msg_count_result = await session.execute(
                select(func.count(MessageLog.id))
                .where(MessageLog.chat_id == chat_id)
                .where(MessageLog.created_at >= yesterday)
            )
            message_count = msg_count_result.scalar() or 0
            
            # Get top toxic users
            toxic_result = await session.execute(
                select(
                    ToxicityLog.user_id,
                    func.count(ToxicityLog.id).label('count'),
                    func.avg(ToxicityLog.score).label('avg_score')
                )
                .where(ToxicityLog.chat_id == chat_id)
                .where(ToxicityLog.created_at >= yesterday)
                .group_by(ToxicityLog.user_id)
                .order_by(desc('count'))
                .limit(5)
            )
            top_toxic = toxic_result.all()
            
            # Get active users count
            active_users_result = await session.execute(
                select(func.count(func.distinct(MessageLog.user_id)))
                .where(MessageLog.chat_id == chat_id)
                .where(MessageLog.created_at >= yesterday)
            )
            active_users = active_users_result.scalar() or 0
            
        return {
            "message_count": message_count,
            "active_users": active_users,
            "top_toxic": top_toxic
        }
    
    @staticmethod
    async def generate_activity_graph(chat_id: int) -> Optional[bytes]:
        """
        Generate activity graph image for chat.
        Requirements: 7.6
        """
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            
            async with get_session()() as session:
                # Get hourly message counts for last 24h
                now = utc_now()
                yesterday = now - timedelta(hours=24)
                
                result = await session.execute(
                    select(MessageLog.created_at)
                    .where(MessageLog.chat_id == chat_id)
                    .where(MessageLog.created_at >= yesterday)
                )
                messages = result.scalars().all()
            
            # Group by hour
            hours = [0] * 24
            for msg_time in messages:
                hour_diff = int((now - msg_time).total_seconds() // 3600)
                if 0 <= hour_diff < 24:
                    hours[23 - hour_diff] += 1
            
            # Create plot
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.bar(range(24), hours, color='#4CAF50')
            ax.set_xlabel('Часы назад')
            ax.set_ylabel('Сообщений')
            ax.set_title('Активность за 24 часа')
            ax.set_xticks(range(0, 24, 3))
            ax.set_xticklabels([f'-{24-i}ч' for i in range(0, 24, 3)])
            
            # Save to bytes
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)
            
            return buf.getvalue()
            
        except ImportError:
            logger.warning("matplotlib not installed, cannot generate graph")
            return None
        except Exception as e:
            logger.error(f"Error generating activity graph: {e}")
            return None


# Instantiate dashboard
dashboard = AdminDashboard()


def is_owner(user_id: int) -> bool:
    """Check if user is bot owner. Requirements: 7.1, 7.7"""
    return user_id == settings.owner_id



# ============================================================================
# Command Handlers - Requirements: 7.1, 7.7
# ============================================================================

@router.message(Command("admin"))
async def cmd_admin(msg: Message, bot: Bot):
    """
    /admin command - show owner dashboard.
    Requirements: 7.1, 7.7
    """
    if msg.chat.type != 'private':
        await msg.reply("Админка доступна только в личных сообщениях. Напиши мне в ЛС.")
        return
    
    if not is_owner(msg.from_user.id):
        await msg.answer("Эта команда только для владельца бота. Иди отсюда.")
        return
    
    chats = await dashboard.get_owner_chats(bot, msg.from_user.id)
    
    if not chats:
        await msg.answer(
            "Нет чатов для управления.\n"
            "Добавь меня в группу и дай права админа."
        )
        return
    
    keyboard = dashboard.build_main_menu(chats)
    await msg.answer(
        f"🎛 <b>Админ-панель Олега</b>\n\n"
        f"Доступно чатов: {len(chats)}\n"
        f"Выбери чат для настройки:",
        reply_markup=keyboard.as_markup()
    )


# ============================================================================
# Main Navigation Callbacks
# ============================================================================

@router.callback_query(F.data == "adm_back_main")
async def cb_back_main(callback: CallbackQuery, bot: Bot):
    """Return to main menu."""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    chats = await dashboard.get_owner_chats(bot, callback.from_user.id)
    keyboard = dashboard.build_main_menu(chats)
    
    await callback.message.edit_text(
        f"🎛 <b>Админ-панель Олега</b>\n\n"
        f"Доступно чатов: {len(chats)}\n"
        f"Выбери чат для настройки:",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_chat_"))
async def cb_chat_menu(callback: CallbackQuery):
    """Show chat settings menu. Requirements: 7.2"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[2])
    
    async with get_session()() as session:
        chat = await session.get(Chat, chat_id)
    
    if not chat:
        await callback.answer("Чат не найден", show_alert=True)
        return
    
    keyboard = dashboard.build_chat_menu(chat_id)
    
    await callback.message.edit_text(
        f"⚙️ <b>Настройки: {chat.title}</b>\n\n"
        f"Тип: {'Супергруппа' if chat.is_forum else 'Группа'}\n"
        f"Выбери раздел:",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


# ============================================================================
# Moderation Section - Requirements: 7.3
# ============================================================================

@router.callback_query(F.data.startswith("adm_mod_"))
async def cb_moderation_menu(callback: CallbackQuery):
    """Show moderation section. Requirements: 7.3"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[2])
    keyboard = await dashboard.build_moderation_menu(chat_id)
    
    await callback.message.edit_text(
        "🛡 <b>Модерация</b>\n\n"
        "Настройки модерации чата:",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_mode_"))
async def cb_cycle_mode(callback: CallbackQuery):
    """Cycle moderation mode. Requirements: 7.3"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[2])
    
    async with get_session()() as session:
        chat = await session.get(Chat, chat_id)
        if not chat:
            await callback.answer("Чат не найден", show_alert=True)
            return
        
        # Cycle through modes: light -> normal -> toxic -> light
        current_idx = dashboard.MODERATION_MODES.index(chat.moderation_mode) \
            if chat.moderation_mode in dashboard.MODERATION_MODES else 1
        next_idx = (current_idx + 1) % len(dashboard.MODERATION_MODES)
        new_mode = dashboard.MODERATION_MODES[next_idx]
        
        chat.moderation_mode = new_mode
        await session.commit()
    
    mode_display = dashboard.MODE_NAMES.get(new_mode, new_mode)
    await callback.answer(f"Режим изменён на: {mode_display}", show_alert=True)
    
    # Refresh menu
    keyboard = await dashboard.build_moderation_menu(chat_id)
    await callback.message.edit_reply_markup(reply_markup=keyboard.as_markup())


@router.callback_query(F.data.startswith("adm_ban_"))
async def cb_banhammer_menu(callback: CallbackQuery):
    """Show banhammer menu. Requirements: 7.3"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[2])
    
    # Get current blacklist
    async with get_session()() as session:
        result = await session.execute(
            select(Blacklist)
            .where(Blacklist.chat_id == chat_id)
            .order_by(Blacklist.added_at.desc())
            .limit(10)
        )
        blacklist = result.scalars().all()
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="➕ Добавить в ЧС", callback_data=f"adm_ban_add_{chat_id}")
    
    for entry in blacklist:
        name = entry.username or str(entry.user_id)
        keyboard.button(
            text=f"❌ {name[:20]}", 
            callback_data=f"adm_ban_rm_{chat_id}_{entry.id}"
        )
    
    keyboard.button(text="🔙 Назад", callback_data=f"adm_mod_{chat_id}")
    keyboard.adjust(1)
    
    text = "🔨 <b>Банхаммер</b>\n\n"
    if blacklist:
        text += f"В чёрном списке: {len(blacklist)} чел.\n"
        text += "Нажми на имя, чтобы удалить из ЧС."
    else:
        text += "Чёрный список пуст."
    
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("adm_ban_add_"))
async def cb_ban_add_start(callback: CallbackQuery, state: FSMContext):
    """Start adding user to blacklist. Requirements: 7.3"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[3])
    await state.set_state(AdminStates.waiting_for_blacklist_user)
    await state.update_data(chat_id=chat_id)
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="❌ Отмена", callback_data=f"adm_ban_{chat_id}")
    
    await callback.message.edit_text(
        "Введи ID пользователя или @username для добавления в ЧС:",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_blacklist_user)
async def handle_blacklist_user_input(msg: Message, state: FSMContext, bot: Bot):
    """Handle user input for blacklist. Requirements: 7.3"""
    if not is_owner(msg.from_user.id):
        return
    
    data = await state.get_data()
    chat_id = data.get('chat_id')
    
    user_input = msg.text.strip()
    user_id = None
    username = None
    
    # Parse user ID or username
    if user_input.startswith('@'):
        username = user_input[1:]
        # Try to resolve username
        try:
            chat_member = await bot.get_chat(f"@{username}")
            user_id = chat_member.id
        except Exception:
            pass
    elif user_input.isdigit():
        user_id = int(user_input)
    
    if not user_id:
        await msg.reply("Не удалось найти пользователя. Введи корректный ID или @username.")
        return
    
    await state.update_data(target_user_id=user_id, target_username=username)
    await state.set_state(AdminStates.waiting_for_blacklist_reason)
    
    await msg.reply("Введи причину бана (или 'skip' чтобы пропустить):")


@router.message(AdminStates.waiting_for_blacklist_reason)
async def handle_blacklist_reason(msg: Message, state: FSMContext):
    """Handle reason input for blacklist. Requirements: 7.3"""
    if not is_owner(msg.from_user.id):
        return
    
    data = await state.get_data()
    chat_id = data.get('chat_id')
    user_id = data.get('target_user_id')
    username = data.get('target_username')
    
    reason = msg.text.strip()
    if reason.lower() == 'skip':
        reason = "Без причины"
    
    # Add to blacklist
    async with get_session()() as session:
        # Check if already exists
        existing = await session.execute(
            select(Blacklist)
            .where(Blacklist.user_id == user_id)
            .where(Blacklist.chat_id == chat_id)
        )
        if existing.scalar():
            await msg.reply("Пользователь уже в чёрном списке.")
            await state.clear()
            return
        
        entry = Blacklist(
            user_id=user_id,
            username=username,
            chat_id=chat_id,
            reason=reason,
            added_by_user_id=msg.from_user.id
        )
        session.add(entry)
        await session.commit()
    
    await state.clear()
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 К банхаммеру", callback_data=f"adm_ban_{chat_id}")
    
    await msg.reply(
        f"✅ Пользователь {username or user_id} добавлен в ЧС.\n"
        f"Причина: {reason}",
        reply_markup=keyboard.as_markup()
    )


@router.callback_query(F.data.startswith("adm_ban_rm_"))
async def cb_ban_remove(callback: CallbackQuery):
    """Remove user from blacklist. Requirements: 7.3"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    parts = callback.data.split("_")
    chat_id = int(parts[3])
    entry_id = int(parts[4])
    
    async with get_session()() as session:
        entry = await session.get(Blacklist, entry_id)
        if entry:
            await session.delete(entry)
            await session.commit()
            await callback.answer("Удалён из ЧС", show_alert=True)
        else:
            await callback.answer("Запись не найдена", show_alert=True)
    
    # Refresh banhammer menu
    async with get_session()() as session:
        result = await session.execute(
            select(Blacklist)
            .where(Blacklist.chat_id == chat_id)
            .order_by(Blacklist.added_at.desc())
            .limit(10)
        )
        blacklist = result.scalars().all()
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="➕ Добавить в ЧС", callback_data=f"adm_ban_add_{chat_id}")
    
    for entry in blacklist:
        name = entry.username or str(entry.user_id)
        keyboard.button(
            text=f"❌ {name[:20]}", 
            callback_data=f"adm_ban_rm_{chat_id}_{entry.id}"
        )
    
    keyboard.button(text="🔙 Назад", callback_data=f"adm_mod_{chat_id}")
    keyboard.adjust(1)
    
    text = "🔨 <b>Банхаммер</b>\n\n"
    if blacklist:
        text += f"В чёрном списке: {len(blacklist)} чел."
    else:
        text += "Чёрный список пуст."
    
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())


# ============================================================================
# Behavior Section - Requirements: 7.4
# ============================================================================

@router.callback_query(F.data.startswith("adm_beh_"))
async def cb_behavior_menu(callback: CallbackQuery):
    """Show behavior section. Requirements: 7.4"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[2])
    keyboard = await dashboard.build_behavior_menu(chat_id)
    
    await callback.message.edit_text(
        "⚙️ <b>Поведение</b>\n\n"
        "Настройки поведения бота:",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_autoreply_"))
async def cb_autoreply_menu(callback: CallbackQuery):
    """Show auto-reply options. Requirements: 7.4"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[2])
    
    keyboard = InlineKeyboardBuilder()
    for pct in [0, 5, 10, 20, 30, 50]:
        label = "Выкл" if pct == 0 else f"{pct}%"
        keyboard.button(text=label, callback_data=f"adm_setreply_{chat_id}_{pct}")
    keyboard.button(text="🔙 Назад", callback_data=f"adm_beh_{chat_id}")
    keyboard.adjust(3, 3, 1)
    
    await callback.message.edit_text(
        "🎲 <b>Шанс автоответа</b>\n\n"
        "Выбери вероятность автоматического ответа на сообщения:",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_setreply_"))
async def cb_set_autoreply(callback: CallbackQuery):
    """Set auto-reply chance. Requirements: 7.4"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    parts = callback.data.split("_")
    chat_id = int(parts[2])
    pct = int(parts[3])
    
    async with get_session()() as session:
        chat = await session.get(Chat, chat_id)
        if chat:
            chat.auto_reply_chance = pct / 100.0
            await session.commit()
    
    await callback.answer(f"Автоответ установлен на {pct}%", show_alert=True)
    
    # Return to behavior menu
    keyboard = await dashboard.build_behavior_menu(chat_id)
    await callback.message.edit_text(
        "⚙️ <b>Поведение</b>\n\n"
        "Настройки поведения бота:",
        reply_markup=keyboard.as_markup()
    )


@router.callback_query(F.data.startswith("adm_topic_"))
async def cb_topic_menu(callback: CallbackQuery):
    """Show topic configuration. Requirements: 7.4"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[2])
    
    async with get_session()() as session:
        chat = await session.get(Chat, chat_id)
        active_topic = chat.active_topic_id if chat else None
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🌐 Везде (все топики)", callback_data=f"adm_settopic_{chat_id}_0")
    keyboard.button(text="📝 Ввести ID топика", callback_data=f"adm_settopic_input_{chat_id}")
    keyboard.button(text="🔙 Назад", callback_data=f"adm_beh_{chat_id}")
    keyboard.adjust(1)
    
    current = f"#{active_topic}" if active_topic else "Везде"
    
    await callback.message.edit_text(
        f"📍 <b>Активный топик</b>\n\n"
        f"Текущий: {current}\n\n"
        f"Бот будет отвечать только в выбранном топике.\n"
        f"'Везде' = бот активен во всех топиках.",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_settopic_") & ~F.data.contains("input"))
async def cb_set_topic(callback: CallbackQuery):
    """Set active topic. Requirements: 7.4"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    parts = callback.data.split("_")
    chat_id = int(parts[2])
    topic_id = int(parts[3]) if parts[3] != '0' else None
    
    async with get_session()() as session:
        chat = await session.get(Chat, chat_id)
        if chat:
            chat.active_topic_id = topic_id
            await session.commit()
    
    topic_text = f"#{topic_id}" if topic_id else "Везде"
    await callback.answer(f"Активный топик: {topic_text}", show_alert=True)
    
    # Return to behavior menu
    keyboard = await dashboard.build_behavior_menu(chat_id)
    await callback.message.edit_text(
        "⚙️ <b>Поведение</b>\n\n"
        "Настройки поведения бота:",
        reply_markup=keyboard.as_markup()
    )


@router.callback_query(F.data.startswith("adm_settopic_input_"))
async def cb_topic_input_prompt(callback: CallbackQuery, state: FSMContext):
    """Prompt for topic ID input. Requirements: 7.4"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[3])
    
    # For simplicity, we'll use a simple approach - ask user to type topic ID
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Отмена", callback_data=f"adm_topic_{chat_id}")
    
    await callback.message.edit_text(
        "Введи ID топика (число).\n\n"
        "Чтобы узнать ID, перешли сообщение из нужного топика.",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


# ============================================================================
# Actions Section - Requirements: 7.5
# ============================================================================

@router.callback_query(F.data.startswith("adm_act_"))
async def cb_actions_menu(callback: CallbackQuery):
    """Show actions section. Requirements: 7.5"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[2])
    keyboard = dashboard.build_actions_menu(chat_id)
    
    await callback.message.edit_text(
        "🎬 <b>Действия</b>\n\n"
        "Выбери действие для выполнения:",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_summary_"))
async def cb_generate_summary(callback: CallbackQuery, bot: Bot):
    """Generate daily summary. Requirements: 7.5"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[2])
    
    await callback.answer("Генерирую отчёт...", show_alert=False)
    
    try:
        from app.services.ollama_client import summarize_chat
        
        async with get_session()() as session:
            chat = await session.get(Chat, chat_id)
            chat_title = chat.title if chat else "Чат"
        
        summary = await summarize_chat(chat_id)
        
        # Send summary to the chat
        target_topic = chat.summary_topic_id if chat else None
        await bot.send_message(
            chat_id=chat_id,
            text=summary,
            message_thread_id=target_topic
        )
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Назад", callback_data=f"adm_act_{chat_id}")
        
        await callback.message.edit_text(
            f"✅ Отчёт отправлен в чат '{chat_title}'",
            reply_markup=keyboard.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Назад", callback_data=f"adm_act_{chat_id}")
        
        await callback.message.edit_text(
            f"❌ Ошибка генерации отчёта: {str(e)[:100]}",
            reply_markup=keyboard.as_markup()
        )


@router.callback_query(F.data.startswith("adm_story_"))
async def cb_generate_story(callback: CallbackQuery, bot: Bot):
    """Generate story. Requirements: 7.5"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[2])
    
    await callback.answer("Генерирую историю...", show_alert=False)
    
    try:
        from app.services.ollama_client import generate_creative
        
        async with get_session()() as session:
            chat = await session.get(Chat, chat_id)
            chat_title = chat.title if chat else "Чат"
        
        story = await generate_creative(chat_id)
        
        # Send story to the chat
        target_topic = chat.creative_topic_id if chat else None
        await bot.send_message(
            chat_id=chat_id,
            text=story,
            message_thread_id=target_topic
        )
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Назад", callback_data=f"adm_act_{chat_id}")
        
        await callback.message.edit_text(
            f"✅ Контент отправлен в чат '{chat_title}'",
            reply_markup=keyboard.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Error generating story: {e}")
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Назад", callback_data=f"adm_act_{chat_id}")
        
        await callback.message.edit_text(
            f"❌ Ошибка генерации истории: {str(e)[:100]}",
            reply_markup=keyboard.as_markup()
        )


@router.callback_query(F.data.startswith("adm_quotes_"))
async def cb_generate_quotes(callback: CallbackQuery, bot: Bot):
    """Generate quotes. Requirements: 7.5"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[2])
    
    await callback.answer("Генерирую цитаты...", show_alert=False)
    
    try:
        from app.services.ollama_client import generate_creative
        
        async with get_session()() as session:
            chat = await session.get(Chat, chat_id)
            chat_title = chat.title if chat else "Чат"
        
        # generate_creative randomly picks quotes, story, joke, or poem
        # Call it to get creative content
        quotes = await generate_creative(chat_id)
        
        # Send quotes to the chat
        target_topic = chat.creative_topic_id if chat else None
        await bot.send_message(
            chat_id=chat_id,
            text=quotes,
            message_thread_id=target_topic
        )
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Назад", callback_data=f"adm_act_{chat_id}")
        
        await callback.message.edit_text(
            f"✅ Контент отправлен в чат '{chat_title}'",
            reply_markup=keyboard.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Error generating quotes: {e}")
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Назад", callback_data=f"adm_act_{chat_id}")
        
        await callback.message.edit_text(
            f"❌ Ошибка генерации цитат: {str(e)[:100]}",
            reply_markup=keyboard.as_markup()
        )


@router.callback_query(F.data.startswith("adm_clear_"))
async def cb_clear_context(callback: CallbackQuery):
    """Clear dialog context. Requirements: 7.5"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[2])
    
    try:
        from app.services.vector_db import vector_db
        
        # Clear RAG context for this chat
        # Note: This deletes all stored messages for the chat from ChromaDB
        collection = vector_db.collection
        if collection:
            # Get all IDs for this chat and delete them
            results = collection.get(
                where={"chat_id": chat_id}
            )
            if results and results['ids']:
                collection.delete(ids=results['ids'])
                deleted_count = len(results['ids'])
            else:
                deleted_count = 0
        else:
            deleted_count = 0
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Назад", callback_data=f"adm_act_{chat_id}")
        
        await callback.message.edit_text(
            f"✅ Контекст очищен.\n"
            f"Удалено записей: {deleted_count}",
            reply_markup=keyboard.as_markup()
        )
        await callback.answer("Контекст очищен", show_alert=True)
        
    except Exception as e:
        logger.error(f"Error clearing context: {e}")
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Назад", callback_data=f"adm_act_{chat_id}")
        
        await callback.message.edit_text(
            f"❌ Ошибка очистки контекста: {str(e)[:100]}",
            reply_markup=keyboard.as_markup()
        )


@router.callback_query(F.data.startswith("adm_restart_"))
async def cb_restart_bot(callback: CallbackQuery):
    """Restart bot (show confirmation). Requirements: 7.5"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[2])
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✅ Да, перезапустить", callback_data=f"adm_restart_confirm_{chat_id}")
    keyboard.button(text="❌ Отмена", callback_data=f"adm_act_{chat_id}")
    keyboard.adjust(1)
    
    await callback.message.edit_text(
        "⚠️ <b>Перезапуск бота</b>\n\n"
        "Это действие перезапустит бота.\n"
        "Все текущие операции будут прерваны.\n\n"
        "Продолжить?",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_restart_confirm_"))
async def cb_restart_confirm(callback: CallbackQuery):
    """Confirm and execute bot restart. Requirements: 7.5"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔄 Перезапуск бота...\n\n"
        "Бот будет недоступен несколько секунд."
    )
    await callback.answer("Перезапуск инициирован", show_alert=True)
    
    # Note: Actual restart would require external process manager (systemd, docker, etc.)
    # Here we just log the request - in production, you'd signal the process manager
    logger.warning(f"Bot restart requested by owner {callback.from_user.id}")
    
    # For now, we'll just notify that restart was requested
    # In production, you might use: os.kill(os.getpid(), signal.SIGTERM)
    import sys
    sys.exit(0)


# ============================================================================
# Statistics Section - Requirements: 7.6
# ============================================================================

@router.callback_query(F.data.startswith("adm_stats_"))
async def cb_statistics_menu(callback: CallbackQuery, bot: Bot):
    """Show statistics section. Requirements: 7.6"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[2])
    
    await callback.answer("Загружаю статистику...", show_alert=False)
    
    try:
        stats = await dashboard.get_chat_statistics(chat_id)
        
        async with get_session()() as session:
            chat = await session.get(Chat, chat_id)
            chat_title = chat.title if chat else "Чат"
        
        # Build statistics text
        text = f"📊 <b>Статистика: {chat_title}</b>\n\n"
        text += f"📨 Сообщений за 24ч: {stats['message_count']}\n"
        text += f"👥 Активных юзеров: {stats['active_users']}\n\n"
        
        if stats['top_toxic']:
            text += "🔥 <b>Топ токсиков:</b>\n"
            for i, (user_id, count, avg_score) in enumerate(stats['top_toxic'], 1):
                # Try to get username
                try:
                    member = await bot.get_chat_member(chat_id, user_id)
                    name = member.user.username or member.user.first_name or str(user_id)
                except Exception:
                    name = str(user_id)
                text += f"{i}. @{name}: {count} нарушений (avg: {avg_score:.0f}%)\n"
        else:
            text += "🔥 Токсиков не обнаружено 👼\n"
        
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="📈 График активности", callback_data=f"adm_graph_{chat_id}")
        keyboard.button(text="🔙 Назад", callback_data=f"adm_chat_{chat_id}")
        keyboard.adjust(1)
        
        await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
        
    except Exception as e:
        logger.error(f"Error loading statistics: {e}")
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Назад", callback_data=f"adm_chat_{chat_id}")
        
        await callback.message.edit_text(
            f"❌ Ошибка загрузки статистики: {str(e)[:100]}",
            reply_markup=keyboard.as_markup()
        )


@router.callback_query(F.data.startswith("adm_graph_"))
async def cb_activity_graph(callback: CallbackQuery):
    """Generate and send activity graph. Requirements: 7.6"""
    if not is_owner(callback.from_user.id):
        await callback.answer("Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[2])
    
    await callback.answer("Генерирую график...", show_alert=False)
    
    try:
        graph_data = await dashboard.generate_activity_graph(chat_id)
        
        if graph_data:
            # Send graph as photo
            photo = BufferedInputFile(graph_data, filename="activity.png")
            await callback.message.answer_photo(
                photo=photo,
                caption="📈 График активности за 24 часа"
            )
            await callback.answer("График отправлен", show_alert=False)
        else:
            await callback.answer(
                "Не удалось сгенерировать график. Возможно, matplotlib не установлен.",
                show_alert=True
            )
            
    except Exception as e:
        logger.error(f"Error generating graph: {e}")
        await callback.answer(f"Ошибка: {str(e)[:50]}", show_alert=True)

