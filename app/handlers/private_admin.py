"""Обработчик админ-панели в личных сообщениях."""

import logging
from typing import Optional
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from datetime import datetime, timedelta

from app.database.session import get_session
from app.database.models import User, ModerationConfig, ChatConfig, Admin, Blacklist
from app.services.ollama_client import gather_comprehensive_chat_stats

logger = logging.getLogger(__name__)

router = Router()


async def get_bot_chats_list(bot, user_id: int):
    """
    Получает список чатов, где бот админ и пользователь тоже админ.

    Args:
        bot: Экземпляр бота
        user_id: ID пользователя, который вызывает команду

    Returns:
        Список чатов, где пользователь может настроить бота
    """
    # В реальной реализации нужно:
    # 1. Получить список всех чатов, где бот админ
    # 2. Проверить, является ли пользователь админом в каждом из них
    # 3. Выбрать только те, которые еще не настроены через систему

    # Это заглушка - в реальности потребуется сохранять список чатов где бот админ
    # и проверять права пользователя через bot.get_chat_member()
    return [
        {"id": -1001234567890, "name": "Тестовый чат 1"},
        {"id": -1009876543210, "name": "Тестовый чат 2"}
    ]


@router.message(Command("setup"))
async def cmd_setup(msg: Message):
    """Команда для настройки новых чатов."""
    if msg.chat.type != 'private':
        await msg.reply("Эту команду можно использовать только в личных сообщениях.")
        return

    # Получить список чатов, где пользователь админ и бот тоже админ
    chats = await get_bot_chats_list(msg.bot, msg.from_user.id)

    if not chats:
        await msg.reply("Не найдено чатов, где ты админ и бот тоже админ.")
        return

    # Проверим, какие чаты уже настроены
    async_session = get_session()
    async with async_session() as session:
        setup_chats_res = await session.execute(select(ChatConfig))
        setup_chats = setup_chats_res.scalars().all()
        setup_chat_ids = {chat.chat_id for chat in setup_chats}

    # Отфильтруем уже настроенные чаты
    new_chats = [chat for chat in chats if chat['id'] not in setup_chat_ids]

    if not new_chats:
        await msg.reply("Все доступные чаты уже настроены.")
        return

    # Показать список чатов для настройки
    if len(new_chats) == 1:
        # Если чат один, сразу начать настройку
        await start_setup_process(msg, new_chats[0])
    else:
        # Если чатов несколько, показать список с выбором
        keyboard = InlineKeyboardBuilder()
        for i, chat in enumerate(new_chats, 1):
            keyboard.button(
                text=f"{i}. {chat['name']}",
                callback_data=f"setup_select_{chat['id']}"
            )
        keyboard.adjust(1)

        await msg.reply(
            "📋 Обнаружены новые чаты:\n" +
            "\n".join([f"{i}. {chat['name']} (ID: {chat['id']})" for i, chat in enumerate(new_chats, 1)]) +
            "\n\nВыбери номер чата для настройки или /cancel для отмены.",
            reply_markup=keyboard.as_markup()
        )


async def start_setup_process(msg: Message, chat_info: dict):
    """Начинает процесс настройки выбранного чата."""
    # Сохраняем информацию о чате в контексте пользователя для продолжения
    # В реальной реализации используем FSM (Finite State Machine) для управления состоянием

    # Запрашиваем тип чата
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Основной", callback_data="setup_type_main")
    keyboard.button(text="Вспомогательный", callback_data="setup_type_aux")
    keyboard.adjust(1)

    await msg.reply(
        f"⚙️ Настройка чата: {chat_info['name']}\n\n"
        f"1️⃣ Выбери тип чата:",
        reply_markup=keyboard.as_markup()
    )


async def save_chat_config(chat_id: int, chat_name: str, chat_type: str,
                          moderation_mode: str, dailysummary_topic_id: int,
                          memes_topic_id: Optional[int] = None):
    """Сохраняет конфигурацию чата в базу данных."""
    async_session = get_session()

    async with async_session() as session:
        # Проверяем, существует ли уже конфигурация для этого чата
        config_res = await session.execute(
            select(ChatConfig).filter_by(chat_id=chat_id)
        )
        config = config_res.scalars().first()

        if config:
            # Обновляем существующую конфигурацию
            config.chat_name = chat_name
            config.chat_type = chat_type
            config.moderation_mode = moderation_mode
            config.dailysummary_topic_id = dailysummary_topic_id
            config.memes_topic_id = memes_topic_id
        else:
            # Создаем новую конфигурацию
            config = ChatConfig(
                chat_id=chat_id,
                chat_name=chat_name,
                chat_type=chat_type,
                moderation_mode=moderation_mode,
                dailysummary_topic_id=dailysummary_topic_id,
                memes_topic_id=memes_topic_id
            )
            session.add(config)

        await session.commit()
        return config


async def add_admin_to_chat(user_id: int, username: Optional[str], chat_id: int, role: str, added_by_user_id: int):
    """Добавляет администратора в чат."""
    async_session = get_session()

    async with async_session() as session:
        # Проверяем, существует ли уже админ с такими параметрами
        admin_res = await session.execute(
            select(Admin).filter_by(user_id=user_id, chat_id=chat_id)
        )
        admin = admin_res.scalars().first()

        if admin:
            # Обновляем роль
            admin.role = role
        else:
            # Создаем новую запись
            admin = Admin(
                user_id=user_id,
                username=username,
                chat_id=chat_id,
                role=role,
                added_by_user_id=added_by_user_id
            )
            session.add(admin)

        await session.commit()
        return admin


async def is_user_blacklisted(user_id: int, chat_id: Optional[int] = None) -> bool:
    """Проверяет, находится ли пользователь в черном списке."""
    async_session = get_session()

    async with async_session() as session:
        if chat_id:
            # Проверяем локальный бан (для конкретного чата)
            blacklist_res = await session.execute(
                select(Blacklist).filter_by(user_id=user_id, chat_id=chat_id)
            )
        else:
            # Проверяем глобальный бан (для всех чатов)
            blacklist_res = await session.execute(
                select(Blacklist).filter_by(user_id=user_id, chat_id=None)
            )

        return blacklist_res.scalars().first() is not None


@router.message(Command("chats"))
async def cmd_chats(msg: Message):
    """Показывает список чатов с кнопками управления."""
    if msg.chat.type != 'private':
        await msg.reply("Эту команду можно использовать только в личных сообщениях.")
        return

    async_session = get_session()
    async with async_session() as session:
        # Получаем все сконфигурированные чаты
        chat_configs_res = await session.execute(select(ChatConfig))
        chat_configs = chat_configs_res.scalars().all()

        if not chat_configs:
            await msg.reply("Нет сконфигурированных чатов.")
            return

        keyboard = InlineKeyboardBuilder()
        for config in chat_configs:
            # Создаем кнопки для каждого чата
            keyboard.row(
                InlineKeyboardButton(
                    text=config.chat_name,
                    callback_data=f"chat_select_{config.id}"
                )
            )
            keyboard.row(
                InlineKeyboardButton(text="⚙️ Настройки", callback_data=f"chat_settings_{config.chat_id}"),
                InlineKeyboardButton(text="📊 Статистика", callback_data=f"chat_stats_{config.chat_id}"),
                InlineKeyboardButton(text="🗑 Отключить", callback_data=f"chat_remove_{config.chat_id}")
            )

        response_text = "💬 Мои чаты:\n\n"
        for i, config in enumerate(chat_configs, 1):
            response_text += f"{i}. {config.chat_name}\n"

        await msg.reply(response_text, reply_markup=keyboard.as_markup())


@router.message(Command("admins"))
async def cmd_admins(msg: Message):
    """Меню управления админами для выбранного чата."""
    if msg.chat.type != 'private':
        await msg.reply("Эту команду можно использовать только в личных сообщениях.")
        return

    async_session = get_session()
    async with async_session() as session:
        # Получаем все сконфигурированные чаты
        chat_configs_res = await session.execute(select(ChatConfig))
        chat_configs = chat_configs_res.scalars().all()

        if not chat_configs:
            await msg.reply("Нет сконфигурированных чатов.")
            return

        if len(chat_configs) == 1:
            # Если один чат, сразу показать админов этого чата
            chat = chat_configs[0]
            await show_chat_admins(msg, chat.chat_id, chat.chat_name)
        else:
            # Если несколько чатов, предложить выбрать
            keyboard = InlineKeyboardBuilder()
            for chat in chat_configs:
                button_text = chat.chat_name
                if len(button_text) > 30:  # Ограничиваем длину имени чата
                    button_text = button_text[:27] + "..."
                keyboard.button(text=button_text, callback_data=f"show_admins_{chat.chat_id}")
            keyboard.adjust(1)

            await msg.reply("Выбери чат для управления админами:", reply_markup=keyboard.as_markup())


async def show_chat_admins(msg: Message, chat_id: int, chat_name: str):
    """Показывает список админов для указанного чата."""
    async_session = get_session()
    async with async_session() as session:
        # Получаем админов этого чата
        admins_res = await session.execute(
            select(Admin).filter_by(chat_id=chat_id)
        )
        admins = admins_res.scalars().all()

        keyboard = InlineKeyboardBuilder()

        # Кнопки "Добавить админа" и "Удалить админа"
        keyboard.button(text="➕ Добавить админа", callback_data=f"add_admin_{chat_id}")
        if admins:
            keyboard.button(text="➖ Удалить админа", callback_data=f"remove_admin_{chat_id}")
        keyboard.button(text="🔙 Назад", callback_data="back_to_admin_menu")
        keyboard.adjust(1)

        # Формируем список админов
        admins_list = []
        if admins:
            for admin in admins:
                role_emoji = "👑" if admin.role == "owner" else "👮"
                username = f"@{admin.username}" if admin.username else f"ID: {admin.user_id}"
                admins_list.append(f"{role_emoji} {username} — {admin.role}")
        else:
            admins_list.append("Нет администраторов")

        response_text = f"👥 Админы чата: {chat_name}\n\n"
        response_text += "Текущие администраторы:\n" + "\n".join(admins_list) + "\n"

        await msg.reply(response_text, reply_markup=keyboard.as_markup())


@router.message(Command("blacklist"))
async def cmd_blacklist(msg: Message):
    """Меню черного списка для выбранного чата."""
    if msg.chat.type != 'private':
        await msg.reply("Эту команду можно использовать только в личных сообщениях.")
        return

    async_session = get_session()
    async with async_session() as session:
        # Получаем все сконфигурированные чаты
        chat_configs_res = await session.execute(select(ChatConfig))
        chat_configs = chat_configs_res.scalars().all()

        if not chat_configs:
            await msg.reply("Нет сконфигурированных чатов.")
            return

        if len(chat_configs) == 1:
            # Если один чат, сразу показать черный список этого чата
            chat = chat_configs[0]
            await show_chat_blacklist(msg, chat.chat_id, chat.chat_name)
        else:
            # Если несколько чатов, предложить выбрать
            keyboard = InlineKeyboardBuilder()
            for chat in chat_configs:
                button_text = chat.chat_name
                if len(button_text) > 30:  # Ограничиваем длину имени чата
                    button_text = button_text[:27] + "..."
                keyboard.button(text=button_text, callback_data=f"show_blacklist_{chat.chat_id}")
            keyboard.adjust(1)

            await msg.reply("Выбери чат для управления черным списком:", reply_markup=keyboard.as_markup())


async def show_chat_blacklist(msg: Message, chat_id: int, chat_name: str):
    """Показывает список заблокированных пользователей для указанного чата."""
    async_session = get_session()
    async with async_session() as session:
        # Получаем пользователей из черного списка этого чата
        blacklist_res = await session.execute(
            select(Blacklist).filter_by(chat_id=chat_id)
        )
        blacklist_entries = blacklist_res.scalars().all()

        keyboard = InlineKeyboardBuilder()

        # Кнопки управления
        keyboard.button(text="➕ Добавить", callback_data=f"add_to_blacklist_{chat_id}")
        if blacklist_entries:
            keyboard.button(text="➖ Удалить", callback_data=f"remove_from_blacklist_{chat_id}")
        keyboard.button(text="🔙 Назад", callback_data="back_to_admin_menu")
        keyboard.adjust(1)

        # Формируем список заблокированных
        blacklist_list = []
        if blacklist_entries:
            for entry in blacklist_entries:
                username = f"@{entry.username}" if entry.username else f"ID: {entry.user_id}"
                blacklist_list.append(f"• {username} — {entry.reason}")
        else:
            blacklist_list.append("Нет заблокированных пользователей")

        response_text = f"🚫 Черный список для чата: {chat_name}\n\n"
        response_text += "Забаненные пользователи:\n" + "\n".join(blacklist_list) + "\n"

        await msg.reply(response_text, reply_markup=keyboard.as_markup())


@router.message(Command("admin"))
async def cmd_admin_panel(msg: Message):
    """Главное меню админ-панели."""
    if msg.chat.type != 'private':
        await msg.reply("Эту команду можно использовать только в личных сообщениях.")
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="💬 Мои чаты", callback_data="admin_chats")
    keyboard.button(text="👥 Управление админами", callback_data="admin_manage_admins")
    keyboard.button(text="🚫 Черный список", callback_data="admin_blacklist")
    keyboard.button(text="📊 Общая статистика", callback_data="admin_stats")
    keyboard.button(text="⚙️ Настройки бота", callback_data="admin_bot_settings")
    keyboard.button(text="📖 Документация", callback_data="admin_docs")
    keyboard.adjust(1)

    await msg.reply("🛠 Админ-панель Олега", reply_markup=keyboard.as_markup())


async def show_general_stats(msg: Message):
    """Показывает общую статистику по всем чатам."""
    async_session = get_session()

    # В реальной реализации собираем статистику из всех чатов
    # Для примера используем тестовые данные
    total_chats = 2
    total_messages = 14832
    tokens_used = "2.3M"
    cost_approx = "$4.50"

    top_chats = [
        {"name": "Steam Deck Overclocking", "messages": 12000},
        {"name": "Тестовая группа", "messages": 2832}
    ]

    response_text = (
        f"📊 Статистика за последние 7 дней:\n\n"
        f"Всего чатов: {total_chats}\n"
        f"Общее кол-во сообщений: {total_messages:,}\n"
        f"Использовано токенов: {tokens_used} (~{cost_approx})\n\n"
        f"Топ-5 активных чатов:\n"
    )

    for i, chat in enumerate(top_chats, 1):
        response_text += f"{i}. {chat['name']} — {chat['messages']:,} сообщений\n"

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Назад", callback_data="back_to_admin_menu")
    keyboard.adjust(1)

    await msg.reply(response_text, reply_markup=keyboard.as_markup())


@router.message(Command("reset"))
async def cmd_reset_context(msg: Message):
    """
    Сброс контекста в личных сообщениях.
    """
    if msg.chat.type != 'private':
        await msg.reply("Эту команду можно использовать только в личных сообщениях.")
        return

    # В реальной реализации нужно очистить историю сообщений для этого пользователя
    await msg.reply("Контекст диалога сброшен. Олег теперь не помнит, что ты тролль.")


@router.message(Command("help"))
async def cmd_help(msg: Message):
    """Интерактивное меню документации."""
    if msg.chat.type != 'private':
        await msg.reply("Эту команду можно использовать только в личных сообщениях.")
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🎮 Игры", callback_data="help_games")
    keyboard.button(text="🎨 Цитаты", callback_data="help_quotes")
    keyboard.button(text="🛡 Модерация", callback_data="help_moderation")
    keyboard.button(text="👨‍💻 Для админов", callback_data="help_admins")
    keyboard.button(text="📥 Загрузка контента", callback_data="help_downloads")
    keyboard.adjust(2)

    await msg.reply(
        "📖 Документация Олега\n\n"
        "Выбери раздел:",
        reply_markup=keyboard.as_markup()
    )




async def show_bot_settings(msg: Message):
    """Показывает глобальные настройки бота."""

    response_text = (
        "⚙️ Глобальные настройки:\n\n"
        "• Частота случайных ответов: [Средняя]\n"
        "• Автозагрузка видео: [✅ Включено]\n"
        "• Максимальный размер видео: [50 МБ]\n"
        "• Токсичность Олега: [Зависит от чата]\n\n"
        "Выберите параметр для изменения:"
    )

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📡 Частота ответов", callback_data="setting_response_freq")
    keyboard.button(text="💾 Автозагрузка", callback_data="setting_auto_download")
    keyboard.button(text="📏 Макс. размер файла", callback_data="setting_max_file_size")
    keyboard.button(text="😤 Стиль Олега", callback_data="setting_oleg_style")
    keyboard.button(text="🔙 Назад", callback_data="back_to_admin_menu")
    keyboard.adjust(1)

    await msg.reply(response_text, reply_markup=keyboard.as_markup())


# Добавим обработчик для команды /start, чтобы приветствовать пользователя
@router.message(Command("start"))
async def cmd_start_private(msg: Message):
    """Приветствие в личных сообщениях."""
    if msg.chat.type != 'private':
        await msg.reply("Привет! Я Олег - бот для управления чатом. Используй меня в личных сообщениях для настройки чатов и управления.")
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🛠 Админ-панель", callback_data="admin_main_menu")
    keyboard.button(text="🎮 Играть", callback_data="play_games")
    keyboard.button(text="📖 Помощь", callback_data="help_main")
    keyboard.adjust(1)

    welcome_text = (
        "Привет! Я Олег, твой личный ассистент для управления ботом в чатах.\n\n"
        "Вот что я умею:\n"
        "• Управлять настройками чатов\n"
        "• Настраивать модерацию\n"
        "• Играть с тобой в разные игры\n"
        "• Генерировать цитаты\n"
        "• Скачивать контент по ссылкам\n\n"
        "Используй кнопки ниже для начала работы."
    )

    await msg.reply(welcome_text, reply_markup=keyboard.as_markup())


# Обработчики callback'ов
@router.callback_query(F.data == "admin_main_menu")
async def admin_main_menu(callback: CallbackQuery):
    """Главное меню админ-панели через callback."""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="💬 Мои чаты", callback_data="admin_chats")
    keyboard.button(text="👥 Управление админами", callback_data="admin_manage_admins")
    keyboard.button(text="🚫 Черный список", callback_data="admin_blacklist")
    keyboard.button(text="📊 Общая статистика", callback_data="admin_stats")
    keyboard.button(text="⚙️ Настройки бота", callback_data="admin_bot_settings")
    keyboard.button(text="📖 Документация", callback_data="admin_docs")
    keyboard.adjust(1)

    await callback.message.edit_text("🛠 Админ-панель Олега", reply_markup=keyboard.as_markup())
    await callback.answer()


@router.callback_query(F.data == "play_games")
async def play_games(callback: CallbackQuery):
    """Меню игр."""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="/grow - Вырастить пиписю", callback_data="game_grow")
    keyboard.button(text="/pvp - Дуэль", callback_data="game_pvp")
    keyboard.button(text="/casino - Казино", callback_data="game_casino")
    keyboard.button(text="/top - Топ игроков", callback_data="game_top")
    keyboard.button(text="🔙 Назад", callback_data="back_to_main")
    keyboard.adjust(1)

    await callback.message.edit_text("🎮 Игры Олега:\n\nВыбери игру:", reply_markup=keyboard.as_markup())
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    """Возврат в главное меню."""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🛠 Админ-панель", callback_data="admin_main_menu")
    keyboard.button(text="🎮 Играть", callback_data="play_games")
    keyboard.button(text="📖 Помощь", callback_data="help_main")
    keyboard.adjust(1)

    await callback.message.edit_text(
        "Привет! Я Олег, твой личный ассистент для управления ботом в чатах.\n\n"
        "Вот что я умею:\n"
        "• Управлять настройками чатов\n"
        "• Настраивать модерацию\n"
        "• Играть с тобой в разные игры\n"
        "• Генерировать цитаты\n"
        "• Скачивать контент по ссылкам\n\n"
        "Используй кнопки ниже для начала работы.",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("chat_"))
async def handle_chat_callbacks(callback: CallbackQuery):
    """Обработка callback'ов для управления чатами."""
    data_parts = callback.data.split("_")
    action = data_parts[1]
    chat_id = int(data_parts[2]) if len(data_parts) > 2 else None

    async_session = get_session()
    async with async_session() as session:
        chat_res = await session.execute(
            select(ChatConfig).filter_by(chat_id=chat_id)
        )
        chat_config = chat_res.scalars().first()

        if not chat_config:
            await callback.message.edit_text("Чат не найден.")
            await callback.answer()
            return

    if action == "settings":
        # Показать настройки чата
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="📝 Изменить режим модерации", callback_data=f"change_mode_{chat_id}")
        keyboard.button(text="🏷️ Изменить темы", callback_data=f"change_topics_{chat_id}")
        keyboard.button(text="🗑 Отключить чат", callback_data=f"confirm_remove_{chat_id}")
        keyboard.button(text="🔙 Назад", callback_data="admin_chats")
        keyboard.adjust(1)

        mode_names = {
            "light": "Лайт",
            "normal": "Норма",
            "dictatorship": "Диктатура"
        }

        response_text = (
            f"⚙️ Настройки чата: {chat_config.chat_name}\n\n"
            f"Тип чата: {chat_config.chat_type}\n"
            f"Режим модерации: {mode_names.get(chat_config.moderation_mode, chat_config.moderation_mode)}\n"
            f"Тема для #dailysummary: {chat_config.dailysummary_topic_id}\n"
            f"Тема для мемов/цитат: {chat_config.memes_topic_id or 'не установлена'}"
        )

        await callback.message.edit_text(response_text, reply_markup=keyboard.as_markup())
    elif action == "stats":
        # Показать статистику чата (в реальной реализации нужно получить данные)
        response_text = (
            f"📊 Статистика чата: {chat_config.chat_name}\n\n"
            f"Сообщений за сегодня: 156\n"
            f"Активных пользователей: 24\n"
            f"Команд использовано: 32\n"
            f"Цитат создано: 5"
        )
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔙 Назад", callback_data="admin_chats")
        keyboard.adjust(1)

        await callback.message.edit_text(response_text, reply_markup=keyboard.as_markup())
    elif action == "remove":
        # Подтверждение удаления чата
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="✅ Да, отключить", callback_data=f"remove_confirmed_{chat_id}")
        keyboard.button(text="❌ Нет, отмена", callback_data="admin_chats")
        keyboard.adjust(1)

        await callback.message.edit_text(
            f"Вы уверены, что хотите отключить чат '{chat_config.chat_name}'?\n"
            f"Все настройки будут потеряны!",
            reply_markup=keyboard.as_markup()
        )
    elif action == "confirm_remove":
        # Подтверждение удаления
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="✅ Да, отключить", callback_data=f"remove_confirmed_{chat_id}")
        keyboard.button(text="❌ Нет, отмена", callback_data="admin_chats")
        keyboard.adjust(1)

        await callback.message.edit_text(
            f"Подтвердите отключение чата '{chat_config.chat_name}':\n"
            f"Все настройки будут сброшены!",
            reply_markup=keyboard.as_markup()
        )
    elif action == "remove_confirmed":
        # Фактически удаляем чат из настроек
        async_session = get_session()
        async with async_session() as session:
            # Удаляем конфигурацию чата
            await session.delete(chat_config)
            await session.commit()

        await callback.message.edit_text(f"Чат '{chat_config.chat_name}' успешно отключен.")
        await callback.answer()
        return  # Не нужно вызывать callback.answer() второй раз

    await callback.answer()


@router.callback_query(F.data.startswith("setting_"))
async def handle_setting_callbacks(callback: CallbackQuery):
    """Обработка callback'ов для изменения настроек бота."""
    setting = callback.data.split("_")[1]

    if setting == "response_freq":
        # Изменение частоты ответов
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text=" rare ", callback_data="freq_rare")
        keyboard.button(text=" medium ", callback_data="freq_medium")
        keyboard.button(text=" high ", callback_data="freq_high")
        keyboard.button(text="🔙 Назад", callback_data="admin_bot_settings")
        keyboard.adjust(2)

        await callback.message.edit_text("📡 Выберите частоту случайных ответов:", reply_markup=keyboard.as_markup())
    elif setting == "auto_download":
        # Переключение автозагрузки
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="✅ Включить", callback_data="autodl_enable")
        keyboard.button(text="❌ Отключить", callback_data="autodl_disable")
        keyboard.button(text="🔙 Назад", callback_data="admin_bot_settings")
        keyboard.adjust(1)

        await callback.message.edit_text("💾 Автозагрузка контента:", reply_markup=keyboard.as_markup())

    await callback.answer()


@router.callback_query(F.data.startswith("freq_"))
async def handle_freq_change(callback: CallbackQuery):
    """Изменение частоты ответов."""
    freq_texts = {
        "rare": "редкая",
        "medium": "средняя",
        "high": "высокая"
    }

    freq = callback.data.split("_")[1]
    new_freq_text = freq_texts.get(freq, freq)

    # Здесь в реальности нужно сохранить настройку в БД
    await callback.message.edit_text(f"Частота случайных ответов изменена на: {new_freq_text}")

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="⚙️ Настройки бота", callback_data="admin_bot_settings")
    keyboard.button(text="🔙 Назад", callback_data="admin_main_menu")
    keyboard.adjust(1)

    await callback.message.edit_reply_markup(reply_markup=keyboard.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("autodl_"))
async def handle_autodl_change(callback: CallbackQuery):
    """Изменение настройки автозагрузки."""
    status = "включена" if "enable" in callback.data else "отключена"

    # Здесь в реальности нужно сохранить настройку в БД
    await callback.message.edit_text(f"Автозагрузка контента теперь: {status}")

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="⚙️ Настройки бота", callback_data="admin_bot_settings")
    keyboard.button(text="🔙 Назад", callback_data="admin_main_menu")
    keyboard.adjust(1)

    await callback.message.edit_reply_markup(reply_markup=keyboard.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("help_"))
async def handle_help_callbacks(callback: CallbackQuery):
    """Обработка callback'ов меню документации."""
    action = callback.data.split("_", 1)[1]

    if action == "games":
        text = (
            "🎮 Игры\n\n"
            "/grow — Вырастить пиписю (таймер 12-24 часа).\n"
            "/pvp @username — Вызвать на дуэль.\n"
            "/casino [ставка] — Сыграть в казино.\n"
            "/top — Топ игроков.\n\n"
            "Ранги:\n"
            "1-10 см: Микрочелик\n"
            "11-20 см: Кнопочный воин\n"
            "21-50 см: Среднячок\n"
            "51-100 см: Хороший экземпляр\n"
            "101-200 см: Гигачад\n"
            "201-500 см: Легенда\n"
            "500+ см: Космический бур"
        )
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="◀️ Назад", callback_data="back_to_help")
        await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    elif action == "quotes":
        text = (
            "🎨 Цитаты\n\n"
            "/q — Создать цитату из сообщения.\n"
            "/q [число] — Цитата из нескольких сообщений.\n"
            "/q * — Режим 'прожарки' с комментарием Олега.\n"
            "/qs — Добавить цитату в стикерпак (админы).\n"
            "/qd — Удалить цитату из стикерпака (админы).\n\n"
            "Цитаты с более чем 5 лайками попадают в 'золотой фонд'."
        )
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="◀️ Назад", callback_data="back_to_help")
        await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    elif action == "moderation":
        text = (
            "🛡 Модерация\n\n"
            "Команды (доступны админам):\n"
            "олег бан @[ник]/[reply] [время] [причина] — Забанить\n"
            "олег мут @[ник]/[reply] [время] [причина] — Замутить\n"
            "олег кик @[ник]/[reply] [причина] — Кикнуть\n\n"
            "Режимы модерации:\n"
            "- Лайт: только анти-рейд\n"
            "- Норма: флуд + спам контроль\n"
            "- Диктатура: жесткий контроль"
        )
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="◀️ Назад", callback_data="back_to_help")
        await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    elif action == "admins":
        text = (
            "👨‍💻 Для админов\n\n"
            "/setup — Подключить чат\n"
            "/chats — Управление чатами\n"
            "/admins — Управление админами\n"
            "/blacklist — Черный список\n"
            "/admin — Админ-панель"
        )
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="◀️ Назад", callback_data="back_to_help")
        await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    elif action == "downloads":
        text = (
            "📥 Загрузка контента\n\n"
            "Поддерживаемые платформы:\n"
            "• YouTube (включая Shorts)\n"
            "• TikTok (без водяных знаков)\n"
            "• VK Видео\n"
            "• SoundCloud, Яндекс.Музыка, Spotify, VK Музыка\n\n"
            "Автозагрузка происходит при отправке ссылки в чат (если включено)."
        )
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="◀️ Назад", callback_data="back_to_help")
        await callback.message.edit_text(text, reply_markup=keyboard.as_markup())

    await callback.answer()


@router.callback_query(F.data == "back_to_help")
async def back_to_help(callback: CallbackQuery):
    """Возврат в меню документации."""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🎮 Игры", callback_data="help_games")
    keyboard.button(text="🎨 Цитаты", callback_data="help_quotes")
    keyboard.button(text="🛡 Модерация", callback_data="help_moderation")
    keyboard.button(text="👨‍💻 Для админов", callback_data="help_admins")
    keyboard.button(text="📥 Загрузка контента", callback_data="help_downloads")
    keyboard.adjust(2)

    await callback.message.edit_text(
        "📖 Документация Олега\n\n"
        "Выбери раздел:",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


# Callback handlers
@router.callback_query(F.data.startswith("admin_"))
async def handle_admin_callbacks(callback: CallbackQuery):
    """Обработка callback'ов главного меню админки."""
    action = callback.data.split("_", 1)[1]
    
    if action == "chats":
        await callback.message.edit_text("Список чатов...", reply_markup=InlineKeyboardBuilder().as_markup())
    elif action == "manage_admins":
        await callback.message.edit_text("Управление админами...", reply_markup=InlineKeyboardBuilder().as_markup())
    elif action == "blacklist":
        await callback.message.edit_text("Черный список...", reply_markup=InlineKeyboardBuilder().as_markup())
    elif action == "stats":
        await callback.message.edit_text("Общая статистика...", reply_markup=InlineKeyboardBuilder().as_markup())
    elif action == "bot_settings":
        await callback.message.edit_text("Настройки бота...", reply_markup=InlineKeyboardBuilder().as_markup())
    elif action == "docs":
        await callback.message.edit_text("Документация...", reply_markup=InlineKeyboardBuilder().as_markup())
    
    await callback.answer()


@router.callback_query(F.data.startswith("help_"))
async def handle_help_callbacks(callback: CallbackQuery):
    """Обработка callback'ов меню документации."""
    action = callback.data.split("_", 1)[1]
    
    if action == "games":
        text = (
            "🎮 Игры\n\n"
            "/grow — Вырастить пиписю (таймер 12-24 часа).\n"
            "/pvp @username — Вызвать на дуэль.\n"
            "/casino [ставка] — Сыграть в казино.\n"
            "/top — Топ игроков.\n\n"
            "Ранги:\n"
            "1-10 см: Микрочелик\n"
            "11-20 см: Кнопочный воин\n"
            "...\n"
            "500+ см: Космический бур\n"
        )
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="◀️ Назад", callback_data="back_to_help")
        await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    elif action == "quotes":
        text = (
            "🎨 Цитаты\n\n"
            "/q — Создать цитату из сообщения.\n"
            "/q [число] — Цитата из нескольких сообщений.\n"
            "/q * — Цитата с комментарием Олега.\n"
            "/qs — Добавить цитату в стикерпак.\n"
            "/qd — Удалить стикер (админы)."
        )
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="◀️ Назад", callback_data="back_to_help")
        await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    elif action == "moderation":
        text = "🛡 Модерация\n\n• Команды: олег бан/мут/кик\n• Режимы: light, normal, dictatorship\n• Черный список"
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="◀️ Назад", callback_data="back_to_help")
        await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    elif action == "admins":
        text = "👨‍💻 Для админов\n\n• /setup — Подключить чат\n• /chats — Управление чатами\n• /admins — Управление админами\n• /blacklist — Черный список"
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="◀️ Назад", callback_data="back_to_help")
        await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    elif action == "downloads":
        text = "📥 Загрузка контента\n\n• Поддерживаемые платформы: YouTube, TikTok, VK, SoundCloud, Spotify, Яндекс.Музыка\n• Автозагрузка при отправке ссылки"
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="◀️ Назад", callback_data="back_to_help")
        await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    
    await callback.answer()


@router.callback_query(F.data == "back_to_help")
async def back_to_help(callback: CallbackQuery):
    """Возврат в меню документации."""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🎮 Игры", callback_data="help_games")
    keyboard.button(text="🎨 Цитаты", callback_data="help_quotes")
    keyboard.button(text="🛡 Модерация", callback_data="help_moderation")
    keyboard.button(text="👨‍💻 Для админов", callback_data="help_admins")
    keyboard.button(text="📥 Загрузка контента", callback_data="help_downloads")
    keyboard.adjust(2)

    await callback.message.edit_text(
        "📖 Документация Олега\n\n"
        "Выбери раздел:",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()


# Добавим обработку личных сообщений от пользователей
@router.message(F.chat.type == "private", ~F.text.startswith("/"))
async def handle_private_message(msg: Message):
    """
    Обработка личных сообщений от пользователей.
    В ЛС бот работает как обычный чат-бот с адаптивным поведением.
    """
    from app.services.ollama_client import generate_reply
    
    # Проверяем, является ли пользователь администратором или нет
    # для определения уровня вежливости или агрессивности ответа
    
    try:
        # Получим уровень токсичности или поведения пользователя (заглушка)
        toxicity_level = 0.0  # В реальной реализации это будет анализ поведения
        
        reply = await generate_reply(
            user_text=msg.text,
            username=msg.from_user.username,
            toxicity_level=toxicity_level
        )
        await msg.reply(reply, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in private message handler: {e}")
        await msg.reply("Сервер сломался. Но только ненадолго, обещаю.")


@router.message(Command("reset"))
async def cmd_reset_context(msg: Message):
    """
    Сброс контекста в личных сообщениях.
    """
    if msg.chat.type != 'private':
        await msg.reply("Эту команду можно использовать только в личных сообщениях.")
        return

    # В реальной реализации нужно очистить историю сообщений для этого пользователя
    await msg.reply("Контекст диалога сброшен. Олег теперь не помнит, что ты тролль.")