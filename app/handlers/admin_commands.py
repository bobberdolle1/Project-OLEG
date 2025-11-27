"""Модуль команд администрирования через личные сообщения."""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from datetime import datetime

from app.database.session import get_session
from app.database.models import User, ChatConfig, Admin, Blacklist
from app.services.ollama_client import get_current_chat_toxicity

logger = logging.getLogger(__name__)

router = Router()

# Глобальный список администраторов (в реальной реализации хранится в БД)
SUPER_ADMINS = [123456789]  # Заменить на реальные ID админов


def is_super_admin(user_id: int) -> bool:
    """
    Проверяет, является ли пользователь суперадминистратором.
    
    Args:
        user_id: ID пользователя
        
    Returns:
        True, если пользователь суперадмин
    """
    return user_id in SUPER_ADMINS


@router.message(Command("admin"))
async def cmd_admin_menu(msg: Message):
    """
    Главное меню админ-панели в личных сообщениях.
    """
    if msg.chat.type != 'private':
        await msg.reply("Админ-панель доступна только в личных сообщениях.")
        return

    user_id = msg.from_user.id

    if not is_super_admin(user_id):
        await msg.reply("❌ У вас нет прав администратора для доступа к этой панели.")
        return

    # Отправляем главное меню с inline-кнопками
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📊 Статистика", callback_data="admin_stats")
    keyboard.button(text="💬 Управление чатами", callback_data="admin_chats")
    keyboard.button(text="👥 Администраторы", callback_data="admin_admins")
    keyboard.button(text="🚫 Черный список", callback_data="admin_blacklist")
    keyboard.button(text="🔧 Настройки", callback_data="admin_settings")
    keyboard.button(text="📋 Логи", callback_data="admin_logs")
    keyboard.adjust(2)

    await msg.reply(
        "🛡️ Админ-панель Олега\n\n"
        "Выберите раздел для управления:",
        reply_markup=keyboard.as_markup()
    )


# Добавим reply-кнопки для быстрого доступа к основным командам
@router.message(Command("menu"))
async def cmd_admin_menu_reply(msg: Message):
    """
    Меню админ-панели с	reply-кнопками для быстрого доступа.
    """
    if msg.chat.type != 'private':
        await msg.reply("Меню администратора доступно только в личных сообщениях.")
        return

    if not is_super_admin(msg.from_user.id):
        await msg.reply("❌ У вас нет прав администратора для доступа к этой панели.")
        return

    # Создаем Reply-клавиатуру с основными командами
    keyboard = ReplyKeyboardBuilder()
    keyboard.button(text="📊 Статистика")
    keyboard.button(text="💬 Чаты")
    keyboard.button(text="👥 Админы")
    keyboard.button(text="🚫 Банлист")
    keyboard.button(text="🔧 Настройки")
    keyboard.button(text="📋 Логи")
    keyboard.button(text="🏠 Главное меню")
    keyboard.adjust(2)

    await msg.reply(
        "🛡️ <b>Админ-панель Олега</b>\n\n"
        "<i>Выбери команду через клавиатуру</i>",
        reply_markup=keyboard.as_markup(resize_keyboard=True)
    )


# Обработчик нажатий на reply-кнопки
@router.message(F.text.in_({"📊 Статистика", "💬 Чаты", "👥 Админы", "🚫 Банлист", "🔧 Настройки", "📋 Логи", "🏠 Главное меню"}))
async def handle_reply_buttons(msg: Message):
    """
    Обработчик reply-кнопок админ-панели.
    """
    if msg.chat.type != 'private':
        return  # Обрабатываем только ЛС

    if not is_super_admin(msg.from_user.id):
        await msg.reply("❌ У вас нет прав администратора.")
        return

    action = msg.text.strip()

    if action == "📊 Статистика":
        await show_admin_stats_reply(msg)
    elif action == "💬 Чаты":
        await show_chats_management_reply(msg)
    elif action == "👥 Админы":
        await show_admins_management_reply(msg)
    elif action == "🚫 Банлист":
        await show_blacklist_management_reply(msg)
    elif action == "🔧 Настройки":
        await show_settings_management_reply(msg)
    elif action == "📋 Логи":
        await show_logs_view_reply(msg)
    elif action == "🏠 Главное меню":
        await cmd_admin_menu_reply(msg)


async def show_admin_stats_reply(msg: Message):
    """Показывает статистику с reply-кнопками."""
    # Получаем статистику из базы данных
    async_session = get_session()
    async with async_session() as session:
        # Количество пользователей
        user_count_res = await session.execute(select(func.count(User.id)))
        user_count = user_count_res.scalar()

        # Количество чатов
        chat_count_res = await session.execute(select(func.count(ChatConfig.id)))
        chat_count = chat_count_res.scalar()

        # Количество администраторов
        admin_count_res = await session.execute(select(func.count(Admin.id)))
        admin_count = admin_count_res.scalar()

        # Количество пользователей в черном списке
        blacklist_count_res = await session.execute(select(func.count(Blacklist.id)))
        blacklist_count = blacklist_count_res.scalar()

    stats_text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Пользователей: <code>{user_count}</code>\n"
        f"💬 Чатов: <code>{chat_count}</code>\n"
        f"👮‍♂️ Администраторов: <code>{admin_count}</code>\n"
        f"🚫 В черном списке: <code>{blacklist_count}</code>"
    )

    # Клавиатура с навигацией
    keyboard = ReplyKeyboardBuilder()
    keyboard.button(text="🏠 Главное меню")
    keyboard.button(text="🔄 Обновить")
    keyboard.adjust(1)

    await msg.reply(stats_text, reply_markup=keyboard.as_markup(resize_keyboard=True))


async def show_chats_management_reply(msg: Message):
    """Показывает управление чатами с reply-кнопками."""
    async_session = get_session()
    async with async_session() as session:
        chats_res = await session.execute(select(ChatConfig))
        chats = chats_res.scalars().all()

    if not chats:
        response_text = "❌ Нет подключенных чатов для управления."
    else:
        response_text = "💬 <b>Подключенные чаты:</b>\n\n"
        for i, chat in enumerate(chats, 1):
            mod_modes = {
                "light": "Лайт",
                "normal": "Норма",
                "dictatorship": "Диктатура"
            }
            response_text += (
                f"{i}. <b>{chat.chat_name}</b> (ID: <code>{chat.chat_id}</code>)\n"
                f"   Режим модерации: <i>{mod_modes.get(chat.moderation_mode, chat.moderation_mode)}</i>\n\n"
            )

    # Клавиатура с действиями
    keyboard = ReplyKeyboardBuilder()
    keyboard.button(text="➕ Подключить чат")
    keyboard.button(text="🔄 Обновить")
    keyboard.button(text="🏠 Главное меню")
    keyboard.adjust(1)

    await msg.reply(response_text, reply_markup=keyboard.as_markup(resize_keyboard=True))


async def show_admins_management_reply(msg: Message):
    """Показывает управление админами с reply-кнопками."""
    async_session = get_session()
    async with async_session() as session:
        admins_res = await session.execute(select(Admin))
        admins = admins_res.scalars().all()

    if not admins:
        response_text = "❌ Нет зарегистрированных администраторов."
    else:
        response_text = "👥 <b>Администраторы:</b>\n\n"
        for i, admin in enumerate(admins, 1):
            user_res = await session.execute(select(User).filter_by(id=admin.user_id))
            user = user_res.scalars().first()
            username = user.username if user and user.username else f"ID: {admin.user_id}"
            chat_res = await session.execute(select(ChatConfig).filter_by(chat_id=admin.chat_id))
            chat = chat_res.scalars().first()
            chat_name = chat.chat_name if chat else f"ID: {admin.chat_id}"

            response_text += (
                f"{i}. <b>{username}</b> - админ в <i>{chat_name}</i>\n"
                f"   Роль: <i>{admin.role}</i>\n\n"
            )

    # Клавиатура с действиями
    keyboard = ReplyKeyboardBuilder()
    keyboard.button(text="➕ Добавить админа")
    keyboard.button(text="❌ Удалить админа")
    keyboard.button(text="🔄 Обновить")
    keyboard.button(text="🏠 Главное меню")
    keyboard.adjust(1)

    await msg.reply(response_text, reply_markup=keyboard.as_markup(resize_keyboard=True))


async def show_blacklist_management_reply(msg: Message):
    """Показывает управление черным списком с reply-кнопками."""
    async_session = get_session()
    async with async_session() as session:
        blacklist_res = await session.execute(select(Blacklist))
        blacklist_users = blacklist_res.scalars().all()

    if not blacklist_users:
        response_text = "❌ Нет пользователей в черном списке."
    else:
        response_text = "🚫 <b>Пользователи в черном списке:</b>\n\n"
        for i, bl_user in enumerate(blacklist_users, 1):
            user_res = await session.execute(select(User).filter_by(id=bl_user.user_id))
            user = user_res.scalars().first()
            username = user.username if user and user.username else f"ID: {bl_user.user_id}"
            chat_res = await session.execute(select(ChatConfig).filter_by(chat_id=bl_user.chat_id))
            chat = chat_res.scalars().first()
            chat_name = chat.chat_name if chat else "все чаты"

            response_text += (
                f"{i}. <b>{username}</b> - заблокирован в <i>{chat_name}</i>\n"
                f"   Причина: <i>{bl_user.reason}</i>\n"
                f"   Дата: <i>{bl_user.added_at.strftime('%Y-%m-%d %H:%M')}</i>\n\n"
            )

    # Клавиатура с действиями
    keyboard = ReplyKeyboardBuilder()
    keyboard.button(text="➕ Заблокировать")
    keyboard.button(text="❌ Разблокировать")
    keyboard.button(text="🔄 Обновить")
    keyboard.button(text="🏠 Главное меню")
    keyboard.adjust(1)

    await msg.reply(response_text, reply_markup=keyboard.as_markup(resize_keyboard=True))


async def show_settings_management_reply(msg: Message):
    """Показывает настройки с reply-кнопками."""
    from app.config import settings

    settings_text = (
        "🔧 <b>Настройки бота</b>\n\n"
        f"<b>Модель Ollama:</b> <code>{settings.ollama_model}</code>\n"
        f"<b>Температура:</b> <code>{settings.ollama_temperature}</code>\n"
        f"<b>Timeout:</b> <code>{settings.ollama_timeout}s</code>\n\n"
        "<b>Функции:</b>\n"
        f"• Автоответы: <code>{'вкл' if settings.enable_random_replies else 'выкл'}</code>\n"
        f"• Фильтр токсичности: <code>{'вкл' if settings.enable_toxicity_filter else 'выкл'}</code>\n"
        f"• Защита от спама: <code>{'вкл' if settings.enable_spam_protection else 'выкл'}</code>"
    )

    # Клавиатура с настройками
    keyboard = ReplyKeyboardBuilder()
    keyboard.button(text="⚙️ Изменить настройки")
    keyboard.button(text="🔄 Сбросить к дефолту")
    keyboard.button(text="🏠 Главное меню")
    keyboard.adjust(1)

    await msg.reply(settings_text, reply_markup=keyboard.as_markup(resize_keyboard=True))


async def show_logs_view_reply(msg: Message):
    """Показывает последние логи с reply-кнопками."""
    try:
        with open("logs/oleg.log", "r", encoding="utf-8") as f:
            lines = f.readlines()
            # Берем последние 10 строк
            recent_logs = "".join(lines[-10:]) if lines else "Логи пусты"
    except FileNotFoundError:
        recent_logs = "Файл логов не найден"
    except Exception as e:
        recent_logs = f"Ошибка при чтении логов: {str(e)}"

    logs_text = f"📄 <b>Последние логи:</b>\n\n<pre>{recent_logs}</pre>"

    # Клавиатура с действиями
    keyboard = ReplyKeyboardBuilder()
    keyboard.button(text="🔄 Обновить")
    keyboard.button(text="📤 Экспорт")
    keyboard.button(text="🗑 Очистить")
    keyboard.button(text="🏠 Главное меню")
    keyboard.adjust(1)

    await msg.reply(logs_text, reply_markup=keyboard.as_markup(resize_keyboard=True))


@router.callback_query(F.data.startswith("admin_"))
async def handle_admin_callback(callback: CallbackQuery):
    """
    Обработчик callback'ов админ-панели.
    """
    action = callback.data.split("_", 1)[1]
    
    if not is_super_admin(callback.from_user.id):
        await callback.answer("❌ Нет прав доступа", show_alert=True)
        return
    
    if action == "stats":
        await show_admin_stats(callback)
    elif action == "chats":
        await show_chats_management(callback)
    elif action == "admins":
        await show_admins_management(callback)
    elif action == "blacklist":
        await show_blacklist_management(callback)
    elif action == "settings":
        await show_settings_management(callback)
    elif action == "logs":
        await show_logs_view(callback)
    
    await callback.answer()


async def show_admin_stats(callback: CallbackQuery):
    """Показывает статистику."""
    # Получаем статистику из базы данных
    async_session = get_session()
    async with async_session() as session:
        # Количество пользователей
        user_count_res = await session.execute(select(func.count(User.id)))
        user_count = user_count_res.scalar()
        
        # Количество чатов
        chat_count_res = await session.execute(select(func.count(ChatConfig.id)))
        chat_count = chat_count_res.scalar()
        
        # Количество администраторов
        admin_count_res = await session.execute(select(func.count(Admin.id)))
        admin_count = admin_count_res.scalar()
        
        # Количество пользователей в черном списке
        blacklist_count_res = await session.execute(select(func.count(Blacklist.id)))
        blacklist_count = blacklist_count_res.scalar()
    
    stats_text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 Пользователей: <code>{user_count}</code>\n"
        f"💬 Чатов: <code>{chat_count}</code>\n"
        f"👮‍♂️ Администраторов: <code>{admin_count}</code>\n"
        f"🚫 В черном списке: <code>{blacklist_count}</code>"
    )
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Назад", callback_data="admin_main")
    keyboard.adjust(1)
    
    await callback.message.edit_text(stats_text, reply_markup=keyboard.as_markup())


async def show_chats_management(callback: CallbackQuery):
    """Показывает управление чатами."""
    # Получаем список чатов из базы данных
    async_session = get_session()
    async with async_session() as session:
        chats_res = await session.execute(select(ChatConfig))
        chats = chats_res.scalars().all()
    
    if not chats:
        response_text = "❌ Нет подключенных чатов для управления."
    else:
        response_text = "💬 <b>Подключенные чаты:</b>\n\n"
        for i, chat in enumerate(chats, 1):
            mod_modes = {
                "light": "Лайт",
                "normal": "Норма", 
                "dictatorship": "Диктатура"
            }
            response_text += (
                f"{i}. <b>{chat.chat_name}</b> (ID: <code>{chat.chat_id}</code>)\n"
                f"   Режим модерации: <i>{mod_modes.get(chat.moderation_mode, chat.moderation_mode)}</i>\n\n"
            )
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="➕ Подключить чат", callback_data="connect_new_chat")
    keyboard.button(text="🔄 Обновить", callback_data="admin_chats")
    keyboard.button(text="🔙 Назад", callback_data="admin_main")
    keyboard.adjust(1)
    
    await callback.message.edit_text(response_text, reply_markup=keyboard.as_markup())


async def show_admins_management(callback: CallbackQuery):
    """Показывает управление администраторами."""
    # Получаем список администраторов из базы данных
    async_session = get_session()
    async with async_session() as session:
        admins_res = await session.execute(select(Admin))
        admins = admins_res.scalars().all()
    
    if not admins:
        response_text = "❌ Нет зарегистрированных администраторов."
    else:
        response_text = "👥 <b>Администраторы:</b>\n\n"
        for i, admin in enumerate(admins, 1):
            user_res = await session.execute(select(User).filter_by(id=admin.user_id))
            user = user_res.scalars().first()
            username = user.username if user and user.username else f"ID: {admin.user_id}"
            chat_res = await session.execute(select(ChatConfig).filter_by(chat_id=admin.chat_id))
            chat = chat_res.scalars().first()
            chat_name = chat.chat_name if chat else f"ID: {admin.chat_id}"
            
            response_text += (
                f"{i}. <b>{username}</b> - админ в <i>{chat_name}</i>\n"
                f"   Роль: <i>{admin.role}</i>\n\n"
            )
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="➕ Добавить админа", callback_data="add_admin")
    keyboard.button(text="❌ Удалить админа", callback_data="remove_admin")
    keyboard.button(text="🔄 Обновить", callback_data="admin_admins")
    keyboard.button(text="🔙 Назад", callback_data="admin_main")
    keyboard.adjust(1)
    
    await callback.message.edit_text(response_text, reply_markup=keyboard.as_markup())


async def show_blacklist_management(callback: CallbackQuery):
    """Показывает управление черным списком."""
    # Получаем список пользователей в черном списке
    async_session = get_session()
    async with async_session() as session:
        blacklist_res = await session.execute(select(Blacklist))
        blacklist_users = blacklist_res.scalars().all()
    
    if not blacklist_users:
        response_text = "❌ Нет пользователей в черном списке."
    else:
        response_text = "🚫 <b>Пользователи в черном списке:</b>\n\n"
        for i, bl_user in enumerate(blacklist_users, 1):
            user_res = await session.execute(select(User).filter_by(id=bl_user.user_id))
            user = user_res.scalars().first()
            username = user.username if user and user.username else f"ID: {bl_user.user_id}"
            chat_res = await session.execute(select(ChatConfig).filter_by(chat_id=bl_user.chat_id))
            chat = chat_res.scalars().first()
            chat_name = chat.chat_name if chat else "все чаты"
            
            response_text += (
                f"{i}. <b>{username}</b> - заблокирован в <i>{chat_name}</i>\n"
                f"   Причина: <i>{bl_user.reason}</i>\n"
                f"   Дата: <i>{bl_user.added_at.strftime('%Y-%m-%d %H:%M')}</i>\n\n"
            )
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="➕ Заблокировать", callback_data="block_user")
    keyboard.button(text="❌ Разблокировать", callback_data="unblock_user")
    keyboard.button(text="🔄 Обновить", callback_data="admin_blacklist")
    keyboard.button(text="🔙 Назад", callback_data="admin_main")
    keyboard.adjust(1)
    
    await callback.message.edit_text(response_text, reply_markup=keyboard.as_markup())


async def show_settings_management(callback: CallbackQuery):
    """Показывает настройки бота."""
    # Текущие настройки
    from app.config import settings
    
    settings_text = (
        "🔧 <b>Настройки бота</b>\n\n"
        f"<b>Модель Ollama:</b> <code>{settings.ollama_model}</code>\n"
        f"<b>Температура:</b> <code>{settings.ollama_temperature}</code>\n"
        f"<b>Timeout:</b> <code>{settings.ollama_timeout}s</code>\n\n"
        "<b>Функции:</b>\n"
        f"• Автоответы: <code>{'вкл' if settings.enable_random_replies else 'выкл'}</code>\n"
        f"• Фильтр токсичности: <code>{'вкл' if settings.enable_toxicity_filter else 'выкл'}</code>\n"
        f"• Защита от спама: <code>{'вкл' if settings.enable_spam_protection else 'выкл'}</code>"
    )
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="⚙️ Изменить настройки", callback_data="edit_settings")
    keyboard.button(text="🔄 Сбросить к дефолту", callback_data="reset_settings")
    keyboard.button(text="🔙 Назад", callback_data="admin_main")
    keyboard.adjust(1)
    
    await callback.message.edit_text(settings_text, reply_markup=keyboard.as_markup())


async def show_logs_view(callback: CallbackQuery):
    """Показывает последние логи."""
    # Для примера показываем последние 10 строк из лог-файла
    try:
        with open("logs/oleg.log", "r", encoding="utf-8") as f:
            lines = f.readlines()
            recent_logs = "".join(lines[-10:]) if lines else "Логи пусты"
    except FileNotFoundError:
        recent_logs = "Файл логов не найден"
    except Exception as e:
        recent_logs = f"Ошибка при чтении логов: {str(e)}"
    
    logs_text = f"📄 <b>Последние логи:</b>\n\n<pre>{recent_logs}</pre>"
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔄 Обновить", callback_data="admin_logs")
    keyboard.button(text="📤 Экспорт", callback_data="export_logs")
    keyboard.button(text="🗑 Очистить", callback_data="clear_logs")
    keyboard.button(text="🔙 Назад", callback_data="admin_main")
    keyboard.adjust(1)
    
    await callback.message.edit_text(logs_text, reply_markup=keyboard.as_markup())


# Команда для добавления администратора
@router.message(Command("add_admin"))
async def cmd_add_admin(msg: Message):
    """
    Команда для добавления администратора.
    Использование: /add_admin [reply или @username] [chat_id] [role]
    """
    if msg.chat.type != 'private':
        await msg.reply("Команда доступна только в личных сообщениях.")
        return
    
    if not is_super_admin(msg.from_user.id):
        await msg.reply("❌ У вас нет прав для выполнения этой команды.")
        return
    
    # Разбираем аргументы
    args = msg.text.split()[1:]
    if len(args) < 3:
        await msg.reply("❌ Использование: /add_admin [user_id или @username] [chat_id] [role]")
        return
    
    try:
        user_identifier = args[0]
        chat_id = int(args[1])
        role = args[2]
        
        # Определяем ID пользователя
        user_id = None
        if user_identifier.startswith('@'):
            # Ищем по username в базе данных
            async_session = get_session()
            async with async_session() as session:
                user_res = await session.execute(select(User).filter_by(username=user_identifier[1:]))
                user = user_res.scalars().first()
                if user:
                    user_id = user.tg_user_id
        else:
            user_id = int(user_identifier)
        
        if not user_id:
            await msg.reply("❌ Пользователь не найден в базе данных.")
            return
        
        # Проверяем, существует ли чат
        async_session = get_session()
        async with async_session() as session:
            chat_res = await session.execute(select(ChatConfig).filter_by(chat_id=chat_id))
            chat = chat_res.scalars().first()
            
            if not chat:
                await msg.reply(f"❌ Чат с ID {chat_id} не найден в базе данных.")
                return
            
            # Создаем администратора
            new_admin = Admin(
                user_id=user_id,
                chat_id=chat_id,
                role=role,
                added_by_user_id=msg.from_user.id,
                added_at=datetime.utcnow()
            )
            session.add(new_admin)
            await session.commit()
            
            await msg.reply(f"✅ Пользователь {user_id} добавлен как {role} в чат {chat_id}.")
            logger.info(f"Администратор {user_id} добавлен в чат {chat_id} как {role} пользователем {msg.from_user.id}")
    except ValueError:
        await msg.reply("❌ Некорректный формат. ID чата и пользователя должны быть числами.")
    except Exception as e:
        logger.error(f"Ошибка при добавлении администратора: {e}")
        await msg.reply(f"❌ Ошибка при добавлении администратора: {str(e)}")


# Команда для удаления администратора
@router.message(Command("remove_admin"))
async def cmd_remove_admin(msg: Message):
    """
    Команда для удаления администратора.
    Использование: /remove_admin [user_id] [chat_id]
    """
    if msg.chat.type != 'private':
        await msg.reply("Команда доступна только в личных сообщениях.")
        return
    
    if not is_super_admin(msg.from_user.id):
        await msg.reply("❌ У вас нет прав для выполнения этой команды.")
        return
    
    args = msg.text.split()[1:]
    if len(args) < 2:
        await msg.reply("❌ Использование: /remove_admin [user_id] [chat_id]")
        return
    
    try:
        user_id = int(args[0])
        chat_id = int(args[1])
        
        async_session = get_session()
        async with async_session() as session:
            # Удаляем администратора
            admin_res = await session.execute(
                select(Admin).filter_by(user_id=user_id, chat_id=chat_id)
            )
            admin = admin_res.scalars().first()
            
            if not admin:
                await msg.reply(f"❌ Администратор {user_id} не найден в чате {chat_id}.")
                return
            
            await session.delete(admin)
            await session.commit()
            
            await msg.reply(f"✅ Администратор {user_id} удален из чата {chat_id}.")
            logger.info(f"Администратор {user_id} удален из чата {chat_id} пользователем {msg.from_user.id}")
    except ValueError:
        await msg.reply("❌ Некорректный формат. ID чата и пользователя должны быть числами.")
    except Exception as e:
        logger.error(f"Ошибка при удалении администратора: {e}")
        await msg.reply(f"❌ Ошибка при удалении администратора: {str(e)}")


# Команда для блокировки пользователя
@router.message(Command("block_user"))
async def cmd_block_user(msg: Message):
    """
    Команда для блокировки пользователя.
    Использование: /block_user [user_id] [chat_id] [reason]
    """
    if msg.chat.type != 'private':
        await msg.reply("Команда доступна только в личных сообщениях.")
        return
    
    if not is_super_admin(msg.from_user.id):
        await msg.reply("❌ У вас нет прав для выполнения этой команды.")
        return
    
    args = msg.text.split()[1:]
    if len(args) < 3:
        await msg.reply("❌ Использование: /block_user [user_id] [chat_id] [reason]")
        return
    
    try:
        user_id = int(args[0])
        chat_id = int(args[1])
        reason = " ".join(args[2:])
        
        async_session = get_session()
        async with async_session() as session:
            # Проверяем, существует ли пользователь
            user_res = await session.execute(select(User).filter_by(tg_user_id=user_id))
            user = user_res.scalars().first()
            
            if not user:
                # Создаем пользователя, если его нет
                user = User(tg_user_id=user_id)
                session.add(user)
                await session.flush()
            
            # Создаем запись в черном списке
            blacklist_entry = Blacklist(
                user_id=user.id,
                chat_id=chat_id,
                reason=reason,
                added_by_user_id=msg.from_user.id,
                added_at=datetime.utcnow()
            )
            session.add(blacklist_entry)
            await session.commit()
            
            await msg.reply(f"✅ Пользователь {user_id} заблокирован в чате {chat_id}. Причина: {reason}")
            logger.info(f"Пользователь {user_id} заблокирован в чате {chat_id}, причина: {reason}, админ: {msg.from_user.id}")
    except ValueError:
        await msg.reply("❌ Некорректный формат. ID чата и пользователя должны быть числами.")
    except Exception as e:
        logger.error(f"Ошибка при блокировке пользователя: {e}")
        await msg.reply(f"❌ Ошибка при блокировке пользователя: {str(e)}")


# Команда для разблокировки пользователя
@router.message(Command("unblock_user"))
async def cmd_unblock_user(msg: Message):
    """
    Команда для разблокировки пользователя.
    Использование: /unblock_user [user_id] [chat_id]
    """
    if msg.chat.type != 'private':
        await msg.reply("Команда доступна только в личных сообщениях.")
        return
    
    if not is_super_admin(msg.from_user.id):
        await msg.reply("❌ У вас нет прав для выполнения этой команды.")
        return
    
    args = msg.text.split()[1:]
    if len(args) < 2:
        await msg.reply("❌ Использование: /unblock_user [user_id] [chat_id]")
        return
    
    try:
        user_id = int(args[0])
        chat_id = int(args[1])
        
        async_session = get_session()
        async with async_session() as session:
            # Ищем пользователя в базе
            user_res = await session.execute(select(User).filter_by(tg_user_id=user_id))
            user = user_res.scalars().first()
            
            if not user:
                await msg.reply(f"❌ Пользователь {user_id} не найден в базе данных.")
                return
            
            # Удаляем из черного списка
            blacklist_res = await session.execute(
                select(Blacklist).filter_by(user_id=user.id, chat_id=chat_id)
            )
            blacklist_entry = blacklist_res.scalars().first()
            
            if not blacklist_entry:
                await msg.reply(f"❌ Пользователь {user_id} не заблокирован в чате {chat_id}.")
                return
            
            await session.delete(blacklist_entry)
            await session.commit()
            
            await msg.reply(f"✅ Пользователь {user_id} разблокирован в чате {chat_id}.")
            logger.info(f"Пользователь {user_id} разблокирован в чате {chat_id}, админ: {msg.from_user.id}")
    except ValueError:
        await msg.reply("❌ Некорректный формат. ID чата и пользователя должны быть числами.")
    except Exception as e:
        logger.error(f"Ошибка при разблокировке пользователя: {e}")
        await msg.reply(f"❌ Ошибка при разблокировке пользователя: {str(e)}")