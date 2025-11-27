"Обработчик админ-панели в личных сообщениях."

import logging
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select, func
from datetime import datetime, timedelta

from app.database.session import get_session
from app.database.models import User, ModerationConfig, Chat, Admin, Blacklist
from app.services.ollama_client import gather_comprehensive_chat_stats
from app.config import settings

logger = logging.getLogger(__name__)

router = Router()


class TopicSelection(StatesGroup):
    waiting_for_summary_topic = State()
    waiting_for_creative_topic = State()


async def is_admin_or_owner(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Check if a user is an admin or the owner of the bot."""
    if user_id == settings.owner_id:
        return True
    
    chat_admins = await bot.get_chat_administrators(chat_id)
    for admin in chat_admins:
        if admin.user.id == user_id and admin.status == 'creator':
            return True
    return False

@router.message(Command("start", "admin"))
async def cmd_start(msg: Message, bot: Bot):
    """Main menu for private chat."""
    if msg.chat.type != 'private':
        return

    if msg.from_user.id != settings.owner_id:
        await msg.answer("У вас нет прав для управления этим ботом.")
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="💬 Мои Чаты", callback_data="my_chats")
    keyboard.button(text="📊 Статистика", callback_data="statistics")
    keyboard.button(text="🧠 База Знаний", callback_data="knowledge_base")
    keyboard.button(text="🆘 Помощь", callback_data="help")
    keyboard.adjust(2)
    
    async with get_session()() as session:
        result = await session.execute(select(func.count(Chat.id)))
        chat_count = result.scalar_one()

    await msg.answer(
        f"👋 Привет, Владелец. Я обслуживаю {chat_count} чат(ов).",
        reply_markup=keyboard.as_markup()
    )

@router.callback_query(F.data == "my_chats")
async def my_chats_menu(callback: CallbackQuery, bot: Bot):
    """Shows a list of chats the user can manage."""
    async with get_session()() as session:
        result = await session.execute(select(Chat))
        all_chats = result.scalars().all()

    admin_chats = []
    for chat in all_chats:
        if await is_admin_or_owner(bot, chat.id, callback.from_user.id):
            admin_chats.append(chat)

    if not admin_chats:
        await callback.message.edit_text("Не найдено чатов, которыми вы можете управлять.")
        await callback.answer()
        return

    keyboard = InlineKeyboardBuilder()
    for chat in admin_chats:
        keyboard.button(text=chat.title, callback_data=f"chat_settings_{chat.id}")
    keyboard.button(text="🔙 Назад", callback_data="start_menu")
    keyboard.adjust(1)

    await callback.message.edit_text(
        "Выбери чат для настройки:",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "start_menu")
async def back_to_start_menu(callback: CallbackQuery, bot: Bot):
    """Returns to the main menu."""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="💬 Мои Чаты", callback_data="my_chats")
    keyboard.button(text="📊 Статистика", callback_data="statistics")
    keyboard.button(text="🧠 База Знаний", callback_data="knowledge_base")
    keyboard.button(text="🆘 Помощь", callback_data="help")
    keyboard.adjust(2)
    
    async with get_session()() as session:
        result = await session.execute(select(func.count(Chat.id)))
        chat_count = result.scalar_one()

    await callback.message.edit_text(
        f"👋 Привет, Владелец. Я обслуживаю {chat_count} чат(ов).",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("chat_settings_"))
async def chat_settings_menu(callback: CallbackQuery):
    """Shows the settings for a specific chat."""
    chat_id = int(callback.data.split("_")[2])
    
    async with get_session()() as session:
        chat = await session.get(Chat, chat_id)

    if not chat:
        await callback.message.edit_text("Чат не найден.")
        await callback.answer()
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text=f"🛡 Режим Модерации: {chat.moderation_mode}", callback_data=f"change_moderation_{chat_id}")
    keyboard.button(text=f"📢 Куда слать Отчеты? (Выбрано: #{chat.summary_topic_id or 'General'})", callback_data=f"change_summary_topic_{chat_id}")
    keyboard.button(text=f"🤡 Куда слать Мемы? (Выбрано: #{chat.creative_topic_id or 'General'})", callback_data=f"change_creative_topic_{chat_id}")
    keyboard.button(text="🔙 Назад", callback_data="my_chats")
    keyboard.adjust(1)

    await callback.message.edit_text(
        f"⚙️ Настройки: {chat.title}\nТип: {'Супергруппа' if chat.is_forum else 'Обычная Группа'}",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("change_summary_topic_"))
async def change_summary_topic(callback: CallbackQuery, state: FSMContext):
    """Asks the user to forward a message to set the summary topic."""
    chat_id = int(callback.data.split("_")[3])
    await state.set_state(TopicSelection.waiting_for_summary_topic)
    await state.update_data(chat_id=chat_id)
    await callback.message.edit_text(
        "Перешлите любое сообщение из топика, который вы хотите использовать для отчетов.\n\n"
        "Для выбора основного чата (не топика), перешлите любое сообщение из него."
    )
    await callback.answer()

@router.callback_query(F.data.startswith("change_creative_topic_"))
async def change_creative_topic(callback: CallbackQuery, state: FSMContext):
    """Asks the user to forward a message to set the creative topic."""
    chat_id = int(callback.data.split("_")[4])
    await state.set_state(TopicSelection.waiting_for_creative_topic)
    await state.update_data(chat_id=chat_id)
    await callback.message.edit_text(
        "Перешлите любое сообщение из топика, который вы хотите использовать для мемов.\n\n"
        "Для выбора основного чата (не топика), перешлите любое сообщение из него."
    )
    await callback.answer()

@router.message(TopicSelection.waiting_for_summary_topic)
async def set_summary_topic(msg: Message, state: FSMContext):
    """Sets the summary topic based on the forwarded message."""
    data = await state.get_data()
    chat_id = data['chat_id']
    
    if not msg.forward_from_chat or msg.forward_from_chat.id != chat_id:
        await msg.reply("Пожалуйста, перешлите сообщение из правильного чата.")
        return

    topic_id = msg.forward_from_message_id if msg.is_topic_message else None
    
    async with get_session()() as session:
        chat = await session.get(Chat, chat_id)
        chat.summary_topic_id = topic_id
        await session.commit()

    await state.clear()
    await msg.answer(f"Топик для отчетов в чате '{chat.title}' установлен.")

@router.message(TopicSelection.waiting_for_creative_topic)
async def set_creative_topic(msg: Message, state: FSMContext):
    """Sets the creative topic based on the forwarded message."""
    data = await state.get_data()
    chat_id = data['chat_id']
    
    if not msg.forward_from_chat or msg.forward_from_chat.id != chat_id:
        await msg.reply("Пожалуйста, перешлите сообщение из правильного чата.")
        return

    topic_id = msg.forward_from_message_id if msg.is_topic_message else None
    
    async with get_session()() as session:
        chat = await session.get(Chat, chat_id)
        chat.creative_topic_id = topic_id
        await session.commit()

    await state.clear()
    await msg.answer(f"Топик для мемов в чате '{chat.title}' установлен.")