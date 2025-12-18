"""
Owner Panel - Расширенная админ-панель для ВЛАДЕЛЬЦА бота.

Функции:
- Авторизация по OWNER_ID из .env
- Управление функциями бота (вкл/выкл модулей)
- Рассылка сообщений
- Статус системы
- Глобальные настройки
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func

from app.config import settings
from app.database.session import get_session
from app.database.models import Chat, User, PrivateChat

logger = logging.getLogger(__name__)

router = Router()


# ============================================================================
# Состояние функций бота (runtime, сбрасывается при перезапуске)
# ============================================================================

class BotFeatures:
    """Управление функциями бота в runtime."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_features()
        return cls._instance
    
    def _init_features(self):
        """Инициализация состояния функций из настроек."""
        self.features: Dict[str, bool] = {
            "voice_recognition": settings.voice_recognition_enabled,
            "content_download": settings.content_download_enabled,
            "toxicity_analysis": settings.toxicity_analysis_enabled,
            "rate_limit": settings.rate_limit_enabled,
            "web_search": settings.ollama_web_search_enabled,
            "games": True,  # Игры всегда включены по умолчанию
            "quotes": True,  # Цитаты
            "vision": True,  # Анализ изображений
            "random_responses": True,  # Случайные ответы
            "summarizer": True,  # Пересказ контента
        }
    
    def toggle(self, feature: str) -> bool:
        """Переключить функцию. Возвращает новое состояние."""
        if feature in self.features:
            self.features[feature] = not self.features[feature]
            return self.features[feature]
        return False
    
    def get(self, feature: str) -> bool:
        """Получить состояние функции."""
        return self.features.get(feature, False)
    
    def set(self, feature: str, value: bool):
        """Установить состояние функции."""
        if feature in self.features:
            self.features[feature] = value
    
    def get_all(self) -> Dict[str, bool]:
        """Получить все функции."""
        return self.features.copy()


# Глобальный экземпляр
bot_features = BotFeatures()


# ============================================================================
# Названия функций
# ============================================================================

FEATURE_NAMES = {
    "voice_recognition": "🎤 Распознавание голоса",
    "content_download": "📥 Загрузка контента",
    "toxicity_analysis": "🧪 Анализ токсичности",
    "rate_limit": "⏱ Rate Limiting",
    "web_search": "🌐 Веб-поиск",
    "games": "🎮 Игры",
    "quotes": "💬 Цитаты",
    "vision": "👁 Анализ изображений",
    "random_responses": "🎲 Случайные ответы",
    "summarizer": "📝 Пересказ контента",
}


# ============================================================================
# FSM States
# ============================================================================

class OwnerStates(StatesGroup):
    """FSM состояния для панели владельца."""
    waiting_broadcast_text = State()
    waiting_broadcast_confirm = State()


# ============================================================================
# Проверка владельца
# ============================================================================

def is_owner(user_id: int) -> bool:
    """Проверка, является ли пользователь владельцем бота."""
    return user_id == settings.owner_id


# ============================================================================
# Главное меню владельца
# ============================================================================

def build_owner_main_menu() -> InlineKeyboardBuilder:
    """Построить главное меню владельца."""
    kb = InlineKeyboardBuilder()
    
    kb.button(text="⚙️ Функции бота", callback_data="owner_features")
    kb.button(text="📢 Рассылка", callback_data="owner_broadcast")
    kb.button(text="📊 Статус системы", callback_data="owner_status")
    kb.button(text="💬 Управление чатами", callback_data="owner_chats")
    kb.button(text="🔧 Настройки", callback_data="owner_settings")
    
    kb.adjust(2, 2, 1)
    return kb


# ============================================================================
# Команда /owner - главная точка входа
# ============================================================================

@router.message(Command("owner"))
async def cmd_owner(msg: Message):
    """
    /owner - панель владельца бота.
    Доступна только пользователю с OWNER_ID из .env
    """
    if msg.chat.type != 'private':
        await msg.reply("🔒 Панель владельца доступна только в личных сообщениях.")
        return
    
    if not is_owner(msg.from_user.id):
        await msg.answer("⛔ Доступ запрещён. Эта команда только для владельца бота.")
        logger.warning(f"Unauthorized /owner access attempt by user {msg.from_user.id}")
        return
    
    kb = build_owner_main_menu()
    
    await msg.answer(
        "👑 <b>Панель владельца</b>\n\n"
        f"Привет, босс! ID: <code>{msg.from_user.id}</code>\n\n"
        "Выбери раздел:",
        reply_markup=kb.as_markup()
    )


# ============================================================================
# Возврат в главное меню
# ============================================================================

@router.callback_query(F.data == "owner_main")
async def cb_owner_main(callback: CallbackQuery):
    """Возврат в главное меню владельца."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = build_owner_main_menu()
    
    await callback.message.edit_text(
        "👑 <b>Панель владельца</b>\n\n"
        f"ID: <code>{callback.from_user.id}</code>\n\n"
        "Выбери раздел:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


# ============================================================================
# Управление функциями
# ============================================================================

def build_features_menu() -> InlineKeyboardBuilder:
    """Построить меню функций."""
    kb = InlineKeyboardBuilder()
    
    features = bot_features.get_all()
    
    for feature_id, enabled in features.items():
        name = FEATURE_NAMES.get(feature_id, feature_id)
        status = "✅" if enabled else "❌"
        kb.button(
            text=f"{status} {name}",
            callback_data=f"owner_toggle_{feature_id}"
        )
    
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(1)
    return kb


@router.callback_query(F.data == "owner_features")
async def cb_owner_features(callback: CallbackQuery):
    """Показать меню управления функциями."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = build_features_menu()
    
    await callback.message.edit_text(
        "⚙️ <b>Управление функциями</b>\n\n"
        "Нажми на функцию, чтобы включить/выключить.\n"
        "✅ = включено, ❌ = выключено\n\n"
        "⚠️ Изменения действуют до перезапуска бота.",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("owner_toggle_"))
async def cb_toggle_feature(callback: CallbackQuery):
    """Переключить функцию."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    feature_id = callback.data.replace("owner_toggle_", "")
    new_state = bot_features.toggle(feature_id)
    
    feature_name = FEATURE_NAMES.get(feature_id, feature_id)
    status = "включена ✅" if new_state else "выключена ❌"
    
    await callback.answer(f"{feature_name} {status}", show_alert=True)
    
    # Обновить меню
    kb = build_features_menu()
    await callback.message.edit_reply_markup(reply_markup=kb.as_markup())


# ============================================================================
# Статус системы
# ============================================================================

@router.callback_query(F.data == "owner_status")
async def cb_owner_status(callback: CallbackQuery, bot: Bot):
    """Показать статус системы."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer("Загружаю статус...", show_alert=False)
    
    # Собираем статистику
    async with get_session()() as session:
        # Количество чатов
        chats_count = await session.scalar(select(func.count(Chat.id)))
        
        # Количество пользователей
        users_count = await session.scalar(select(func.count(User.id)))
        
        # Количество приватных чатов
        private_count = await session.scalar(
            select(func.count(PrivateChat.user_id))
            .where(PrivateChat.is_blocked == False)
        )
    
    # Проверка сервисов
    services_status = []
    has_critical_issues = False
    
    # Ollama - реальная проверка доступности
    try:
        from app.services.ollama_client import is_ollama_available, check_model_available
        ollama_ok = await is_ollama_available()
        if ollama_ok:
            # Проверяем основную модель
            model_ok = await check_model_available(settings.ollama_base_model)
            if model_ok:
                services_status.append(f"✅ Ollama ({settings.ollama_base_model})")
            else:
                # Проверяем fallback
                if settings.ollama_fallback_enabled:
                    fallback_ok = await check_model_available(settings.ollama_fallback_model)
                    if fallback_ok:
                        services_status.append(f"⚠️ Ollama (fallback: {settings.ollama_fallback_model})")
                    else:
                        services_status.append("❌ Ollama (модели недоступны)")
                        has_critical_issues = True
                else:
                    services_status.append(f"❌ Ollama (модель {settings.ollama_base_model} недоступна)")
                    has_critical_issues = True
        else:
            services_status.append("❌ Ollama (сервер недоступен)")
            has_critical_issues = True
    except Exception as e:
        services_status.append(f"❌ Ollama ({e})")
        has_critical_issues = True
    
    # Redis
    if settings.redis_enabled:
        try:
            from app.services.redis_client import redis_client
            if redis_client._client:
                services_status.append("✅ Redis")
            else:
                services_status.append("⚠️ Redis (не подключен)")
        except Exception:
            services_status.append("❌ Redis")
    else:
        services_status.append("⏸ Redis (отключен)")
    
    # ChromaDB
    try:
        from app.services.vector_db import vector_db
        if vector_db.client:
            # Пробуем сделать heartbeat запрос
            try:
                vector_db.client.heartbeat()
                services_status.append("✅ ChromaDB")
            except Exception:
                services_status.append("⚠️ ChromaDB (нет связи)")
                has_critical_issues = True
        else:
            services_status.append("⚠️ ChromaDB (не инициализирован)")
            has_critical_issues = True
    except Exception as e:
        services_status.append(f"❌ ChromaDB ({e})")
        has_critical_issues = True
    
    # Whisper (faster-whisper)
    if settings.voice_recognition_enabled:
        try:
            from app.services.voice_recognition import is_available
            if is_available():
                services_status.append("✅ Whisper")
            else:
                services_status.append("⚠️ Whisper (не загружен)")
        except Exception:
            services_status.append("❌ Whisper")
    else:
        services_status.append("⏸ Whisper (отключен)")
    
    # Формируем текст
    text = (
        "📊 <b>Статус системы</b>\n\n"
        f"<b>Статистика:</b>\n"
        f"├ Групп: {chats_count or 0}\n"
        f"├ Пользователей: {users_count or 0}\n"
        f"└ Приватных чатов: {private_count or 0}\n\n"
        f"<b>Сервисы:</b>\n"
    )
    
    for status in services_status:
        text += f"├ {status}\n"
    
    # Определяем используется ли fallback
    using_fallback = False
    try:
        from app.services.ollama_client import check_model_available
        primary_ok = await check_model_available(settings.ollama_base_model)
        if not primary_ok and settings.ollama_fallback_enabled:
            fallback_ok = await check_model_available(settings.ollama_fallback_model)
            if fallback_ok:
                using_fallback = True
    except Exception:
        pass
    
    # Текущий режим работы
    if using_fallback:
        text += f"\n🔄 <b>РЕЖИМ: FALLBACK</b>\n"
        text += f"├ Используется: {settings.ollama_fallback_model}\n"
        text += f"└ Основная недоступна: {settings.ollama_base_model}\n"
    else:
        text += f"\n✅ <b>РЕЖИМ: ОСНОВНОЙ</b>\n"
        text += f"└ Используется: {settings.ollama_base_model}\n"
    
    text += f"\n<b>Настроенные модели:</b>\n"
    text += f"├ Base: {settings.ollama_base_model}\n"
    text += f"├ Vision: {settings.ollama_vision_model}\n"
    text += f"└ Memory: {settings.ollama_memory_model}\n"
    
    if settings.ollama_fallback_enabled:
        text += f"\n<b>Fallback модели (резерв):</b>\n"
        text += f"├ Base: {settings.ollama_fallback_model}\n"
        text += f"├ Vision: {settings.ollama_fallback_vision_model}\n"
        text += f"└ Memory: {settings.ollama_fallback_memory_model}\n"
    else:
        text += f"\n⏸ <b>Fallback отключен</b>\n"
    
    # Предупреждение о критических проблемах
    if has_critical_issues:
        text += "\n⚠️ <b>Есть критические проблемы!</b>"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Обновить", callback_data="owner_status")
    if has_critical_issues:
        kb.button(text="🔔 Тест уведомления", callback_data="owner_test_notify")
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(2)
    
    try:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        # Игнорируем ошибку "message is not modified"
        await callback.answer("Статус не изменился", show_alert=False)


@router.callback_query(F.data == "owner_test_notify")
async def cb_owner_test_notify(callback: CallbackQuery):
    """Тестовое уведомление о проблемах."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    try:
        from app.services.ollama_client import notify_owner_service_down
        await notify_owner_service_down("Тест", "Это тестовое уведомление о проблемах с сервисами")
        await callback.answer("✅ Уведомление отправлено!", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# ============================================================================
# Управление чатами
# ============================================================================

@router.callback_query(F.data == "owner_chats")
async def cb_owner_chats(callback: CallbackQuery, bot: Bot):
    """Показать список чатов."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    async with get_session()() as session:
        result = await session.execute(
            select(Chat).order_by(Chat.created_at.desc()).limit(20)
        )
        chats = result.scalars().all()
    
    if not chats:
        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 Назад", callback_data="owner_main")
        
        await callback.message.edit_text(
            "💬 <b>Чаты</b>\n\nНет подключенных чатов.",
            reply_markup=kb.as_markup()
        )
        await callback.answer()
        return
    
    kb = InlineKeyboardBuilder()
    
    for chat in chats:
        title = chat.title[:25] + "..." if len(chat.title) > 25 else chat.title
        kb.button(text=f"💬 {title}", callback_data=f"owner_chat_{chat.id}")
    
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(1)
    
    await callback.message.edit_text(
        f"💬 <b>Управление чатами</b>\n\n"
        f"Всего чатов: {len(chats)}\n"
        f"Выбери чат для управления:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("owner_chat_"))
async def cb_owner_chat_detail(callback: CallbackQuery, bot: Bot):
    """Детали чата."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split("_")[2])
    
    async with get_session()() as session:
        chat = await session.get(Chat, chat_id)
    
    if not chat:
        await callback.answer("Чат не найден", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🚪 Покинуть чат", callback_data=f"owner_leavechat:{chat_id}")
    kb.button(text="🔙 К списку", callback_data="owner_chats")
    kb.adjust(1)
    
    text = (
        f"💬 <b>{chat.title}</b>\n\n"
        f"ID: <code>{chat.id}</code>\n"
        f"Тип: {'Форум' if chat.is_forum else 'Группа'}\n"
        f"Режим модерации: {chat.moderation_mode or 'normal'}\n"
        f"Добавлен: {chat.created_at.strftime('%d.%m.%Y') if chat.created_at else 'N/A'}\n"
    )
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("owner_leavechat:"))
async def cb_owner_leave_chat(callback: CallbackQuery, bot: Bot):
    """Покинуть чат."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split(":")[1])
    
    try:
        await bot.leave_chat(chat_id)
        
        # Удалить из БД
        async with get_session()() as session:
            chat = await session.get(Chat, chat_id)
            if chat:
                await session.delete(chat)
                await session.commit()
        
        await callback.answer("✅ Бот покинул чат", show_alert=True)
        
        # Вернуться к списку
        await cb_owner_chats(callback, bot)
        
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}", show_alert=True)


# ============================================================================
# Рассылка (интеграция с broadcast)
# ============================================================================

@router.callback_query(F.data == "owner_broadcast")
async def cb_owner_broadcast(callback: CallbackQuery, state: FSMContext):
    """Меню рассылки."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 В ЛС бота", callback_data="owner_bc_target_private")
    kb.button(text="👥 В группы", callback_data="owner_bc_target_groups")
    kb.button(text="🌍 Везде", callback_data="owner_bc_target_all")
    kb.button(text="📢 Полный мастер", callback_data="owner_bc_wizard")
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(3, 1, 1)
    
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "Выбери куда отправить:\n\n"
        "• <b>В ЛС бота</b> - пользователям, которые писали боту\n"
        "• <b>В группы</b> - во все группы где есть бот\n"
        "• <b>Везде</b> - и в ЛС, и в группы\n\n"
        "Или используй <b>Полный мастер</b> для отправки фото/видео/кружочков",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("owner_bc_target_"))
async def cb_owner_bc_target(callback: CallbackQuery, state: FSMContext):
    """Выбор цели рассылки."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    target = callback.data.replace("owner_bc_target_", "")
    await state.update_data(broadcast_target=target)
    await state.set_state(OwnerStates.waiting_broadcast_text)
    
    target_labels = {
        "private": "👤 в ЛС бота",
        "groups": "👥 в группы",
        "all": "🌍 везде"
    }
    
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data="owner_broadcast")
    
    await callback.message.edit_text(
        f"📝 <b>Текстовая рассылка</b>\n\n"
        f"Цель: {target_labels.get(target, target)}\n\n"
        "Отправь текст сообщения для рассылки:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.message(OwnerStates.waiting_broadcast_text)
async def handle_broadcast_text(msg: Message, state: FSMContext, bot: Bot):
    """Обработка текста для рассылки."""
    if not is_owner(msg.from_user.id):
        return
    
    if not msg.text:
        await msg.reply("❌ Отправь текстовое сообщение.")
        return
    
    data = await state.get_data()
    target = data.get("broadcast_target", "groups")
    
    await state.update_data(broadcast_text=msg.text)
    await state.set_state(OwnerStates.waiting_broadcast_confirm)
    
    # Получить количество получателей в зависимости от цели
    async with get_session()() as session:
        groups_count = await session.scalar(select(func.count(Chat.id)))
        private_count = await session.scalar(
            select(func.count(PrivateChat.user_id))
            .where(PrivateChat.is_blocked == False)
        )
    
    if target == "private":
        recipients_text = f"{private_count or 0} пользователей (ЛС)"
    elif target == "groups":
        recipients_text = f"{groups_count or 0} групп"
    else:  # all
        recipients_text = f"{(private_count or 0) + (groups_count or 0)} ({private_count or 0} ЛС + {groups_count or 0} групп)"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 Отправить", callback_data="owner_bc_send")
    kb.button(text="❌ Отмена", callback_data="owner_broadcast")
    kb.adjust(2)
    
    preview = msg.text[:300] + "..." if len(msg.text) > 300 else msg.text
    
    await msg.answer(
        f"📢 <b>Подтверждение рассылки</b>\n\n"
        f"<b>Текст:</b>\n{preview}\n\n"
        f"<b>Получатели:</b> {recipients_text}\n\n"
        f"Подтвердить отправку?",
        reply_markup=kb.as_markup()
    )


@router.callback_query(F.data == "owner_bc_send")
async def cb_owner_bc_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Отправить рассылку."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    data = await state.get_data()
    text = data.get("broadcast_text")
    target = data.get("broadcast_target", "groups")
    
    if not text:
        await callback.answer("❌ Текст не найден", show_alert=True)
        await state.clear()
        return
    
    await callback.answer("🚀 Отправка...", show_alert=False)
    
    await callback.message.edit_text("📢 <b>Рассылка в процессе...</b>\n\n⏳ Подождите...")
    
    # Получить ID получателей в зависимости от цели
    chat_ids = []
    async with get_session()() as session:
        if target in ("groups", "all"):
            result = await session.execute(select(Chat.id))
            chat_ids.extend([row[0] for row in result.all()])
        
        if target in ("private", "all"):
            result = await session.execute(
                select(PrivateChat.user_id).where(PrivateChat.is_blocked == False)
            )
            chat_ids.extend([row[0] for row in result.all()])
    
    sent = 0
    failed = 0
    
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id=chat_id, text=text)
            sent += 1
        except Exception as e:
            logger.warning(f"Failed to send broadcast to {chat_id}: {e}")
            failed += 1
        
        await asyncio.sleep(0.05)  # Flood protection
    
    await state.clear()
    
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 Ещё рассылка", callback_data="owner_broadcast")
    kb.button(text="🔙 Главное меню", callback_data="owner_main")
    kb.adjust(2)
    
    await callback.message.edit_text(
        f"📢 <b>Рассылка завершена!</b>\n\n"
        f"✅ Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}\n"
        f"📊 Всего: {sent + failed}",
        reply_markup=kb.as_markup()
    )


@router.callback_query(F.data == "owner_bc_wizard")
async def cb_owner_bc_wizard(callback: CallbackQuery):
    """Перенаправление на полный мастер рассылки."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📢 <b>Полный мастер рассылки</b>\n\n"
        "Используй команду /broadcast для запуска пошагового мастера "
        "с выбором типа контента (текст, фото, видео, кружочек)."
    )
    await callback.answer()


# ============================================================================
# Настройки
# ============================================================================

@router.callback_query(F.data == "owner_settings")
async def cb_owner_settings(callback: CallbackQuery):
    """Показать настройки."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🛡️ Антиспам", callback_data="owner_antispam")
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(1)
    
    text = (
        "🔧 <b>Текущие настройки</b>\n\n"
        f"<b>Telegram:</b>\n"
        f"├ Owner ID: <code>{settings.owner_id}</code>\n\n"
        f"<b>Ollama:</b>\n"
        f"├ URL: {settings.ollama_base_url}\n"
        f"├ Модель: {settings.ollama_base_model}\n"
        f"├ Vision: {settings.ollama_vision_model}\n"
        f"├ Memory: {settings.ollama_memory_model}\n"
        f"├ Timeout: {settings.ollama_timeout}s\n\n"
        f"<b>Лимиты:</b>\n"
        f"├ Rate limit: {settings.rate_limit_requests}/{settings.rate_limit_window}s\n"
        f"├ Токсичность: {settings.toxicity_threshold}%\n\n"
        f"<b>Медиа:</b>\n"
        f"├ Whisper: {settings.whisper_model}\n"
        f"├ Голос: {'✅' if settings.voice_recognition_enabled else '❌'}\n"
        f"├ Загрузка: {'✅' if settings.content_download_enabled else '❌'}\n\n"
        f"Нажми <b>Антиспам</b> для настройки лимитов запросов."
    )
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# ============================================================================
# Антиспам настройки
# ============================================================================

@router.callback_query(F.data == "owner_antispam")
async def cb_owner_antispam(callback: CallbackQuery):
    """Меню настроек антиспама."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    from app.services.token_limiter import token_limiter
    
    stats = token_limiter.get_stats()
    
    kb = InlineKeyboardBuilder()
    # Burst лимит
    kb.button(text="➖", callback_data="owner_as_burst_dec")
    kb.button(text=f"⚡ Burst: {stats['burst_limit']}/мин", callback_data="owner_as_noop")
    kb.button(text="➕", callback_data="owner_as_burst_inc")
    # Часовой лимит
    kb.button(text="➖", callback_data="owner_as_hourly_dec")
    kb.button(text=f"⏱ Час: {stats['hourly_limit']}/час", callback_data="owner_as_noop")
    kb.button(text="➕", callback_data="owner_as_hourly_inc")
    # Действия
    kb.button(text="🔄 Сбросить статистику", callback_data="owner_as_reset_stats")
    kb.button(text="🔙 Назад", callback_data="owner_settings")
    kb.adjust(3, 3, 1, 1)
    
    text = (
        "🛡️ <b>Настройки антиспама</b>\n\n"
        f"<b>Текущие лимиты:</b>\n"
        f"├ ⚡ Burst: <b>{stats['burst_limit']}</b> запросов/минуту\n"
        f"└ ⏱ Часовой: <b>{stats['hourly_limit']}</b> запросов/час\n\n"
        f"<b>Статистика:</b>\n"
        f"├ Пользователей: {stats['total_users']}\n"
        f"├ В whitelist: {stats['whitelisted']}\n"
        f"└ Заблокировано: {stats['total_blocked']}\n\n"
        "Используй ➖/➕ для изменения лимитов."
    )
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "owner_as_noop")
async def cb_owner_as_noop(callback: CallbackQuery):
    """Пустой callback для кнопок-индикаторов."""
    await callback.answer()


@router.callback_query(F.data == "owner_as_burst_dec")
async def cb_owner_as_burst_dec(callback: CallbackQuery):
    """Уменьшить burst лимит."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    from app.services.token_limiter import token_limiter
    
    new_limit = max(1, token_limiter.burst_limit - 1)
    token_limiter.set_burst_limit(new_limit)
    await callback.answer(f"Burst: {new_limit}/мин")
    await cb_owner_antispam(callback)


@router.callback_query(F.data == "owner_as_burst_inc")
async def cb_owner_as_burst_inc(callback: CallbackQuery):
    """Увеличить burst лимит."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    from app.services.token_limiter import token_limiter
    
    new_limit = min(30, token_limiter.burst_limit + 1)
    token_limiter.set_burst_limit(new_limit)
    await callback.answer(f"Burst: {new_limit}/мин")
    await cb_owner_antispam(callback)


@router.callback_query(F.data == "owner_as_hourly_dec")
async def cb_owner_as_hourly_dec(callback: CallbackQuery):
    """Уменьшить часовой лимит."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    from app.services.token_limiter import token_limiter
    
    new_limit = max(10, token_limiter.hourly_limit - 10)
    token_limiter.set_hourly_limit(new_limit)
    await callback.answer(f"Часовой: {new_limit}/час")
    await cb_owner_antispam(callback)


@router.callback_query(F.data == "owner_as_hourly_inc")
async def cb_owner_as_hourly_inc(callback: CallbackQuery):
    """Увеличить часовой лимит."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    from app.services.token_limiter import token_limiter
    
    new_limit = min(500, token_limiter.hourly_limit + 10)
    token_limiter.set_hourly_limit(new_limit)
    await callback.answer(f"Часовой: {new_limit}/час")
    await cb_owner_antispam(callback)


@router.callback_query(F.data == "owner_as_reset_stats")
async def cb_owner_as_reset_stats(callback: CallbackQuery):
    """Сбросить статистику антиспама."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    from app.services.token_limiter import token_limiter
    
    token_limiter.users.clear()
    token_limiter.total_blocked = 0
    
    await callback.answer("✅ Статистика сброшена!", show_alert=True)
    await cb_owner_antispam(callback)


# ============================================================================
# Экспорт функции проверки состояния функций
# ============================================================================

def is_feature_enabled(feature: str) -> bool:
    """
    Проверить, включена ли функция.
    Используется в других модулях для проверки состояния.
    """
    return bot_features.get(feature)


# ============================================================================
# Экстренные действия
# ============================================================================

@router.callback_query(F.data == "owner_emergency")
async def cb_owner_emergency(callback: CallbackQuery):
    """Экстренные действия."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔴 Выключить все функции", callback_data="owner_em_disable_all")
    kb.button(text="🟢 Включить все функции", callback_data="owner_em_enable_all")
    kb.button(text="🗑 Вайп (выборочный)", callback_data="owner_wipe_menu")
    kb.button(text="🔄 Перезапуск бота", callback_data="owner_em_restart")
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "🚨 <b>Экстренные действия</b>\n\n"
        "⚠️ Используй с осторожностью!",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "owner_em_disable_all")
async def cb_disable_all_features(callback: CallbackQuery):
    """Выключить все функции."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    for feature in bot_features.features:
        bot_features.set(feature, False)
    
    await callback.answer("🔴 Все функции выключены!", show_alert=True)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🟢 Включить все", callback_data="owner_em_enable_all")
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "🔴 <b>Все функции выключены</b>\n\n"
        "Бот работает в минимальном режиме.",
        reply_markup=kb.as_markup()
    )


@router.callback_query(F.data == "owner_em_enable_all")
async def cb_enable_all_features(callback: CallbackQuery):
    """Включить все функции."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    for feature in bot_features.features:
        bot_features.set(feature, True)
    
    await callback.answer("🟢 Все функции включены!", show_alert=True)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад", callback_data="owner_main")
    
    await callback.message.edit_text(
        "🟢 <b>Все функции включены</b>\n\n"
        "Бот работает в полном режиме.",
        reply_markup=kb.as_markup()
    )


@router.callback_query(F.data == "owner_em_restart")
async def cb_owner_restart(callback: CallbackQuery):
    """Перезапуск бота."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, перезапустить", callback_data="owner_em_restart_confirm")
    kb.button(text="❌ Отмена", callback_data="owner_main")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "⚠️ <b>Подтверждение перезапуска</b>\n\n"
        "Бот будет перезапущен.\n"
        "Все текущие операции будут прерваны.\n\n"
        "Продолжить?",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "owner_em_restart_confirm")
async def cb_owner_restart_confirm(callback: CallbackQuery):
    """Подтверждение перезапуска."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔄 <b>Перезапуск бота...</b>\n\n"
        "Бот будет недоступен несколько секунд."
    )
    await callback.answer("Перезапуск инициирован", show_alert=True)
    
    logger.warning(f"Bot restart requested by owner {callback.from_user.id}")
    
    import sys
    sys.exit(0)


# ============================================================================
# ВАЙП ПАМЯТИ И БАЗЫ ДАННЫХ
# ============================================================================

@router.callback_query(F.data == "owner_wipe_confirm")
async def cb_owner_wipe_confirm(callback: CallbackQuery):
    """Перенаправление на меню выборочного вайпа."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    # Перенаправляем на новое меню вайпа
    await cb_owner_wipe_menu(callback)


@router.callback_query(F.data == "owner_wipe_execute")
async def cb_owner_wipe_execute(callback: CallbackQuery):
    """Выполнение вайпа."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await callback.message.edit_text("🗑 <b>Выполняется вайп...</b>\n\n⏳ Подождите...")
    
    results = []
    
    # 1. Очистка ChromaDB (память)
    try:
        from app.services.vector_db import vector_db
        if vector_db.client:
            # Получаем все коллекции и удаляем их
            collections = vector_db.client.list_collections()
            for col in collections:
                vector_db.client.delete_collection(col.name)
            results.append(f"✅ ChromaDB: удалено {len(collections)} коллекций")
        else:
            results.append("⚠️ ChromaDB: не инициализирована")
    except Exception as e:
        results.append(f"❌ ChromaDB: {str(e)[:50]}")
    
    # 2. Очистка базы данных
    try:
        from app.database.session import get_session
        from app.database.models import (
            User, MessageLog, GameStat, Wallet, Achievement, UserAchievement,
            TradeOffer, Auction, Bid, Quest, UserQuest, Guild, GuildMember,
            TeamWar, TeamWarParticipant, DuoTeam, DuoStat, GlobalStats,
            UserQuestionHistory, SpamPattern, Warning, ToxicityConfig, ToxicityLog,
            Quote, ModerationConfig, Chat, Admin, Blacklist, PrivateChat,
            PendingVerification, GameChallenge, UserBalance, CitadelConfig,
            UserReputation, ReputationHistory, Tournament, TournamentScore,
            UserElo, NotificationConfig, StickerPack
        )
        from sqlalchemy import delete
        
        async with get_session()() as session:
            # Порядок важен из-за foreign keys
            tables_to_clear = [
                (TournamentScore, "TournamentScore"),
                (Tournament, "Tournament"),
                (ReputationHistory, "ReputationHistory"),
                (UserReputation, "UserReputation"),
                (NotificationConfig, "NotificationConfig"),
                (CitadelConfig, "CitadelConfig"),
                (UserBalance, "UserBalance"),
                (GameChallenge, "GameChallenge"),
                (PendingVerification, "PendingVerification"),
                (PrivateChat, "PrivateChat"),
                (Blacklist, "Blacklist"),
                (Admin, "Admin"),
                (ModerationConfig, "ModerationConfig"),
                (Quote, "Quote"),
                (ToxicityLog, "ToxicityLog"),
                (ToxicityConfig, "ToxicityConfig"),
                (Warning, "Warning"),
                (SpamPattern, "SpamPattern"),
                (UserQuestionHistory, "UserQuestionHistory"),
                (GlobalStats, "GlobalStats"),
                (DuoStat, "DuoStat"),
                (DuoTeam, "DuoTeam"),
                (TeamWarParticipant, "TeamWarParticipant"),
                (TeamWar, "TeamWar"),
                (GuildMember, "GuildMember"),
                (Guild, "Guild"),
                (UserQuest, "UserQuest"),
                (Quest, "Quest"),
                (Bid, "Bid"),
                (Auction, "Auction"),
                (TradeOffer, "TradeOffer"),
                (UserAchievement, "UserAchievement"),
                (Achievement, "Achievement"),
                (Wallet, "Wallet"),
                (GameStat, "GameStat"),
                (MessageLog, "MessageLog"),
                (StickerPack, "StickerPack"),
                (Chat, "Chat"),
                (User, "User"),
                (UserElo, "UserElo"),
            ]
            
            deleted_count = 0
            for model, name in tables_to_clear:
                try:
                    result = await session.execute(delete(model))
                    deleted_count += result.rowcount
                except Exception as e:
                    logger.warning(f"Ошибка при очистке {name}: {e}")
            
            await session.commit()
            results.append(f"✅ База данных: очищено {len(tables_to_clear)} таблиц")
            
    except Exception as e:
        results.append(f"❌ База данных: {str(e)[:50]}")
        logger.error(f"Ошибка при вайпе БД: {e}")
    
    # 3. Восстановление дефолтных знаний
    try:
        from app.services.vector_db import vector_db
        from app.config import settings
        
        if vector_db.client:
            # Переинициализируем коллекцию
            collection_name = settings.chromadb_collection_name
            load_result = vector_db.load_default_knowledge(collection_name)
            
            if load_result.get("error"):
                results.append(f"⚠️ Дефолтные знания: {load_result['error']}")
            else:
                results.append(f"✅ Дефолтные знания: загружено {load_result['loaded']} фактов (v{load_result.get('version', '?')})")
        else:
            results.append("⚠️ Дефолтные знания: ChromaDB не инициализирована")
    except Exception as e:
        results.append(f"❌ Дефолтные знания: {str(e)[:50]}")
    
    logger.warning(f"WIPE executed by owner {callback.from_user.id}")
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад", callback_data="owner_main")
    
    await callback.message.edit_text(
        "🗑 <b>ВАЙП ЗАВЕРШЁН</b>\n\n"
        "<b>Результаты:</b>\n" +
        "\n".join(results) +
        "\n\n✅ Бот готов к работе с чистого листа!\n"
        "📚 Дефолтные знания восстановлены.",
        reply_markup=kb.as_markup()
    )
    await callback.answer("Вайп выполнен!", show_alert=True)


# ============================================================================
# Список групп и топ пользователей
# ============================================================================

# Хранилище замученных групп (в памяти, сбрасывается при перезапуске)
_muted_groups: set[int] = set()


def is_group_muted(chat_id: int) -> bool:
    """Проверить, замучена ли группа."""
    return chat_id in _muted_groups


@router.callback_query(F.data == "owner_groups_list")
async def cb_owner_groups_list(callback: CallbackQuery):
    """Показать список всех групп где есть бот."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    async_session = get_session()
    async with async_session() as session:
        # Получаем все чаты
        result = await session.execute(select(Chat))
        chats = result.scalars().all()
    
    if not chats:
        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 Назад", callback_data="owner_main")
        await callback.message.edit_text(
            "📭 Бот пока не добавлен ни в одну группу",
            reply_markup=kb.as_markup()
        )
        await callback.answer()
        return
    
    text = f"👥 <b>Список групп ({len(chats)})</b>\n\n"
    text += "Нажми на группу для управления:\n\n"
    
    kb = InlineKeyboardBuilder()
    for chat in chats[:15]:  # Показываем первые 15
        muted = "🔇" if is_group_muted(chat.id) else ""
        forum_icon = "📋" if chat.is_forum else "💬"
        title = chat.title[:25] + "..." if len(chat.title) > 25 else chat.title
        kb.button(text=f"{muted}{forum_icon} {title}", callback_data=f"owner_group:{chat.id}")
    
    if len(chats) > 15:
        text += f"\n... и ещё {len(chats) - 15} групп"
    
    kb.button(text="🔄 Обновить", callback_data="owner_groups_list")
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("owner_group:"))
async def cb_owner_group_actions(callback: CallbackQuery):
    """Показать действия для конкретной группы."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split(":")[1])
    
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(select(Chat).filter_by(id=chat_id))
        chat = result.scalars().first()
    
    if not chat:
        await callback.answer("Группа не найдена", show_alert=True)
        return
    
    muted = is_group_muted(chat_id)
    mute_text = "🔊 Размутить" if muted else "🔇 Замутить"
    
    text = f"⚙️ <b>Управление группой</b>\n\n"
    text += f"📋 <b>Название:</b> {chat.title}\n"
    text += f"🆔 <b>ID:</b> <code>{chat.id}</code>\n"
    text += f"📌 <b>Форум:</b> {'Да' if chat.is_forum else 'Нет'}\n"
    text += f"🔇 <b>Мут:</b> {'Да' if muted else 'Нет'}\n"
    
    kb = InlineKeyboardBuilder()
    kb.button(text=mute_text, callback_data=f"owner_mute_group:{chat_id}")
    kb.button(text="🚪 Выйти из группы", callback_data=f"owner_leave_group:{chat_id}")
    kb.button(text="🔙 К списку", callback_data="owner_groups_list")
    kb.adjust(2, 1)
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("owner_mute_group:"))
async def cb_owner_mute_group(callback: CallbackQuery):
    """Замутить/размутить группу."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split(":")[1])
    
    if chat_id in _muted_groups:
        _muted_groups.remove(chat_id)
        await callback.answer("🔊 Группа размучена!", show_alert=True)
    else:
        _muted_groups.add(chat_id)
        await callback.answer("🔇 Группа замучена! Бот не будет отвечать.", show_alert=True)
    
    # Возвращаемся к действиям группы
    await cb_owner_group_actions(callback)


@router.callback_query(F.data.startswith("owner_leave_group:"))
async def cb_owner_leave_group(callback: CallbackQuery):
    """Подтверждение выхода из группы."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split(":")[1])
    
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(select(Chat).filter_by(id=chat_id))
        chat = result.scalars().first()
    
    title = chat.title if chat else f"ID: {chat_id}"
    
    text = f"⚠️ <b>Подтверждение выхода</b>\n\n"
    text += f"Ты уверен, что хочешь выйти из группы?\n"
    text += f"<b>{title}</b>\n\n"
    text += "Это действие нельзя отменить!"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, выйти", callback_data=f"owner_leave_confirm:{chat_id}")
    kb.button(text="❌ Отмена", callback_data=f"owner_group:{chat_id}")
    kb.adjust(2)
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("owner_leave_confirm:"))
async def cb_owner_leave_confirm(callback: CallbackQuery):
    """Выполнить выход из группы."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    chat_id = int(callback.data.split(":")[1])
    
    try:
        await callback.bot.leave_chat(chat_id)
        
        # Удаляем из БД
        async_session = get_session()
        async with async_session() as session:
            result = await session.execute(select(Chat).filter_by(id=chat_id))
            chat = result.scalars().first()
            if chat:
                await session.delete(chat)
                await session.commit()
        
        # Удаляем из мута если был
        _muted_groups.discard(chat_id)
        
        await callback.answer("🚪 Бот вышел из группы!", show_alert=True)
        
        # Возвращаемся к списку групп
        await cb_owner_groups_list(callback)
        
    except Exception as e:
        logger.error(f"Failed to leave chat {chat_id}: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "owner_top_users")
async def cb_owner_top_users(callback: CallbackQuery):
    """Показать топ пользователей бота."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    async_session = get_session()
    async with async_session() as session:
        from app.database.models import GameStat, MessageLog
        
        # Топ по количеству сообщений (самые активные)
        msg_result = await session.execute(
            select(
                MessageLog.user_id,
                MessageLog.username,
                func.count(MessageLog.id).label('msg_count')
            )
            .group_by(MessageLog.user_id, MessageLog.username)
            .order_by(func.count(MessageLog.id).desc())
            .limit(10)
        )
        top_active = msg_result.all()
        
        # Топ по репутации
        rep_result = await session.execute(
            select(User).order_by(User.reputation_score.desc()).limit(10)
        )
        top_rep = rep_result.scalars().all()
        
        # Общее количество пользователей
        count_result = await session.execute(select(func.count(User.id)))
        total_users = count_result.scalar()
    
    text = f"🏆 <b>Топ пользователей</b>\n"
    text += f"📊 Всего: {total_users} пользователей\n\n"
    
    text += "<b>💬 Топ по активности (сообщения):</b>\n"
    for i, row in enumerate(top_active, 1):
        name = f"@{row.username}" if row.username else f"id:{row.user_id}"
        text += f"{i}. {name} — {row.msg_count:,} сообщений\n"
    
    text += "\n<b>🎖 Топ по репутации:</b>\n"
    for i, user in enumerate(top_rep, 1):
        name = f"@{user.username}" if user.username else user.first_name or f"id:{user.tg_user_id}"
        text += f"{i}. {name} — {user.reputation_score} очков\n"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Обновить", callback_data="owner_top_users")
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(2)
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "owner_stats")
async def cb_owner_stats(callback: CallbackQuery):
    """Показать общую статистику бота."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer("📊 Загружаю статистику...", show_alert=False)
    
    async_session = get_session()
    async with async_session() as session:
        from app.database.models import GameStat, Quote, MessageLog
        from datetime import timedelta
        
        # Общее количество пользователей
        total_users = await session.scalar(select(func.count(User.id)))
        
        # Количество групп
        total_groups = await session.scalar(select(func.count(Chat.id)))
        
        # Количество приватных чатов
        total_private = await session.scalar(
            select(func.count(PrivateChat.user_id))
            .where(PrivateChat.is_blocked == False)
        )
        
        # Всего сообщений
        total_messages = await session.scalar(select(func.count(MessageLog.id)))
        
        # Сообщений за сегодня
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        messages_today = await session.scalar(
            select(func.count(MessageLog.id))
            .where(MessageLog.created_at >= today)
        )
        
        # Сообщений за неделю
        week_ago = today - timedelta(days=7)
        messages_week = await session.scalar(
            select(func.count(MessageLog.id))
            .where(MessageLog.created_at >= week_ago)
        )
        
        # Активных пользователей сегодня (уникальные user_id в сообщениях)
        active_today = await session.scalar(
            select(func.count(func.distinct(MessageLog.user_id)))
            .where(MessageLog.created_at >= today)
        )
        
        # Игровая статистика
        total_players = await session.scalar(select(func.count(GameStat.user_id)))
        
        # Сумма всех размеров
        total_size = await session.scalar(select(func.sum(GameStat.size_cm))) or 0
        
        # Всего PvP побед
        total_pvp_wins = await session.scalar(select(func.sum(GameStat.pvp_wins))) or 0
        
        # Всего grow операций
        total_grows = await session.scalar(select(func.sum(GameStat.grow_count))) or 0
        
        # Количество цитат
        total_quotes = await session.scalar(select(func.count(Quote.id)))
        
        # Лайков на цитатах
        total_likes = await session.scalar(select(func.sum(Quote.likes_count))) or 0
    
    text = "📈 <b>Общая статистика бота</b>\n\n"
    
    text += "<b>👥 Пользователи:</b>\n"
    text += f"├ Всего: {total_users or 0}\n"
    text += f"├ Активных сегодня: {active_today or 0}\n"
    text += f"└ Приватных чатов: {total_private or 0}\n\n"
    
    text += "<b>💬 Сообщения:</b>\n"
    text += f"├ Всего: {total_messages or 0:,}\n"
    text += f"├ За сегодня: {messages_today or 0:,}\n"
    text += f"└ За неделю: {messages_week or 0:,}\n\n"
    
    text += "<b>👥 Группы:</b>\n"
    text += f"└ Всего: {total_groups or 0}\n\n"
    
    text += "<b>🎮 Игры:</b>\n"
    text += f"├ Игроков: {total_players or 0}\n"
    text += f"├ Общий размер: {total_size:,} см\n"
    text += f"├ PvP побед: {total_pvp_wins:,}\n"
    text += f"└ Grow операций: {total_grows:,}\n\n"
    
    text += "<b>💬 Цитаты:</b>\n"
    text += f"├ Всего: {total_quotes or 0}\n"
    text += f"└ Лайков: {total_likes:,}\n"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Обновить", callback_data="owner_stats")
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(2)
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


# ============================================================================
# Обновление главного меню с экстренными действиями
# ============================================================================

def build_owner_main_menu() -> InlineKeyboardBuilder:
    """Построить главное меню владельца."""
    kb = InlineKeyboardBuilder()
    
    kb.button(text="⚙️ Функции бота", callback_data="owner_features")
    kb.button(text="📢 Рассылка", callback_data="owner_broadcast")
    kb.button(text="📊 Статус системы", callback_data="owner_status")
    kb.button(text="📈 Общая статистика", callback_data="owner_stats")
    kb.button(text="💬 Управление чатами", callback_data="owner_chats")
    kb.button(text="👥 Список групп", callback_data="owner_groups_list")
    kb.button(text="🏆 Топ пользователей", callback_data="owner_top_users")
    kb.button(text="👤 Управление юзерами", callback_data="owner_users")
    kb.button(text="🔧 Настройки", callback_data="owner_settings")
    kb.button(text="🚨 Экстренные действия", callback_data="owner_emergency")
    
    kb.adjust(2, 2, 2, 2, 2)
    return kb


# ============================================================================
# Управление пользователями
# ============================================================================

class UserManagementStates(StatesGroup):
    """FSM состояния для управления пользователями."""
    waiting_user_search = State()


@router.callback_query(F.data == "owner_users")
async def cb_owner_users(callback: CallbackQuery):
    """Меню управления пользователями."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    async_session = get_session()
    async with async_session() as session:
        total_users = await session.scalar(select(func.count(User.id)))
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔍 Поиск пользователя", callback_data="owner_user_search")
    kb.button(text="🏆 Топ активных", callback_data="owner_top_users")
    kb.button(text="📋 Последние юзеры", callback_data="owner_users_recent")
    kb.button(text="🔙 Назад", callback_data="owner_main")
    kb.adjust(1)
    
    await callback.message.edit_text(
        f"👤 <b>Управление пользователями</b>\n\n"
        f"📊 Всего пользователей: {total_users or 0}\n\n"
        "Выбери действие:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "owner_user_search")
async def cb_owner_user_search(callback: CallbackQuery, state: FSMContext):
    """Начать поиск пользователя."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await state.set_state(UserManagementStates.waiting_user_search)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data="owner_users")
    
    await callback.message.edit_text(
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Отправь:\n"
        "• @username\n"
        "• ID пользователя\n"
        "• Часть имени",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.message(UserManagementStates.waiting_user_search)
async def handle_user_search(msg: Message, state: FSMContext):
    """Обработка поиска пользователя."""
    if not is_owner(msg.from_user.id):
        return
    
    await state.clear()
    query = msg.text.strip()
    
    async_session = get_session()
    async with async_session() as session:
        users = []
        
        # Поиск по ID
        if query.isdigit():
            result = await session.execute(
                select(User).where(User.tg_user_id == int(query))
            )
            users = list(result.scalars().all())
        
        # Поиск по username
        if not users and query.startswith("@"):
            username = query[1:]
            result = await session.execute(
                select(User).where(User.username.ilike(f"%{username}%"))
            )
            users = list(result.scalars().all())
        
        # Поиск по имени
        if not users:
            result = await session.execute(
                select(User).where(
                    (User.first_name.ilike(f"%{query}%")) |
                    (User.username.ilike(f"%{query}%"))
                ).limit(10)
            )
            users = list(result.scalars().all())
    
    if not users:
        kb = InlineKeyboardBuilder()
        kb.button(text="🔍 Искать снова", callback_data="owner_user_search")
        kb.button(text="🔙 Назад", callback_data="owner_users")
        kb.adjust(1)
        
        await msg.answer(
            f"❌ Пользователь не найден: <code>{query}</code>",
            reply_markup=kb.as_markup()
        )
        return
    
    if len(users) == 1:
        # Показать профиль сразу
        await show_user_profile(msg, users[0])
    else:
        # Показать список
        kb = InlineKeyboardBuilder()
        for user in users[:10]:
            name = f"@{user.username}" if user.username else user.first_name or f"id:{user.tg_user_id}"
            kb.button(text=name, callback_data=f"owner_user:{user.tg_user_id}")
        kb.button(text="🔙 Назад", callback_data="owner_users")
        kb.adjust(1)
        
        await msg.answer(
            f"🔍 Найдено {len(users)} пользователей:",
            reply_markup=kb.as_markup()
        )


async def show_user_profile(msg_or_callback, user: User, edit: bool = False):
    """Показать профиль пользователя."""
    async_session = get_session()
    async with async_session() as session:
        from app.database.models import GameStat, MessageLog
        
        # Статистика сообщений
        msg_count = await session.scalar(
            select(func.count(MessageLog.id))
            .where(MessageLog.user_id == user.tg_user_id)
        )
        
        # Игровая статистика
        game_stat = await session.scalar(
            select(GameStat).where(GameStat.tg_user_id == user.tg_user_id)
        )
    
    name = f"@{user.username}" if user.username else user.first_name or "Без имени"
    
    text = f"👤 <b>Профиль пользователя</b>\n\n"
    text += f"<b>Имя:</b> {user.first_name or 'N/A'}\n"
    text += f"<b>Username:</b> @{user.username or 'N/A'}\n"
    text += f"<b>ID:</b> <code>{user.tg_user_id}</code>\n"
    text += f"<b>Репутация:</b> {user.reputation_score}\n"
    text += f"<b>Сообщений:</b> {msg_count or 0:,}\n"
    
    if game_stat:
        text += f"\n<b>🎮 Игровая статистика:</b>\n"
        text += f"├ Размер: {game_stat.size_cm} см\n"
        text += f"├ PvP побед: {game_stat.pvp_wins}\n"
        text += f"└ Grow: {game_stat.grow_count}\n"
    
    text += f"\n<b>Создан:</b> {user.created_at.strftime('%d.%m.%Y %H:%M') if user.created_at else 'N/A'}"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Сбросить репутацию", callback_data=f"owner_user_reset_rep:{user.tg_user_id}")
    kb.button(text="🎮 Сбросить игру", callback_data=f"owner_user_reset_game:{user.tg_user_id}")
    kb.button(text="🗑 Удалить юзера", callback_data=f"owner_user_delete:{user.tg_user_id}")
    kb.button(text="🔙 Назад", callback_data="owner_users")
    kb.adjust(2, 1, 1)
    
    if edit and hasattr(msg_or_callback, 'message'):
        await msg_or_callback.message.edit_text(text, reply_markup=kb.as_markup())
    else:
        await msg_or_callback.answer(text, reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("owner_user:"))
async def cb_owner_user_profile(callback: CallbackQuery):
    """Показать профиль пользователя по callback."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    tg_user_id = int(callback.data.split(":")[1])
    
    async_session = get_session()
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.tg_user_id == tg_user_id)
        )
    
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    
    await show_user_profile(callback, user, edit=True)
    await callback.answer()


@router.callback_query(F.data.startswith("owner_user_reset_rep:"))
async def cb_owner_reset_reputation(callback: CallbackQuery):
    """Сбросить репутацию пользователя."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    tg_user_id = int(callback.data.split(":")[1])
    
    async_session = get_session()
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.tg_user_id == tg_user_id)
        )
        if user:
            user.reputation_score = 0
            await session.commit()
    
    await callback.answer("✅ Репутация сброшена!", show_alert=True)
    
    # Обновить профиль
    if user:
        await show_user_profile(callback, user, edit=True)


@router.callback_query(F.data.startswith("owner_user_reset_game:"))
async def cb_owner_reset_game(callback: CallbackQuery):
    """Сбросить игровую статистику пользователя."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    tg_user_id = int(callback.data.split(":")[1])
    
    async_session = get_session()
    async with async_session() as session:
        from app.database.models import GameStat
        
        game_stat = await session.scalar(
            select(GameStat).where(GameStat.tg_user_id == tg_user_id)
        )
        if game_stat:
            game_stat.size_cm = 0
            game_stat.pvp_wins = 0
            game_stat.grow_count = 0
            game_stat.casino_jackpots = 0
            await session.commit()
    
    await callback.answer("✅ Игровая статистика сброшена!", show_alert=True)
    
    # Обновить профиль
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.tg_user_id == tg_user_id)
        )
    if user:
        await show_user_profile(callback, user, edit=True)


@router.callback_query(F.data.startswith("owner_user_delete:"))
async def cb_owner_delete_user(callback: CallbackQuery):
    """Подтверждение удаления пользователя."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    tg_user_id = int(callback.data.split(":")[1])
    
    kb = InlineKeyboardBuilder()
    kb.button(text="⚠️ Да, удалить", callback_data=f"owner_user_delete_confirm:{tg_user_id}")
    kb.button(text="❌ Отмена", callback_data=f"owner_user:{tg_user_id}")
    kb.adjust(2)
    
    await callback.message.edit_text(
        f"⚠️ <b>Подтверждение удаления</b>\n\n"
        f"Удалить пользователя <code>{tg_user_id}</code>?\n\n"
        "Это удалит все данные пользователя!",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("owner_user_delete_confirm:"))
async def cb_owner_delete_user_confirm(callback: CallbackQuery):
    """Выполнить удаление пользователя."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    tg_user_id = int(callback.data.split(":")[1])
    
    async_session = get_session()
    async with async_session() as session:
        from app.database.models import GameStat, MessageLog
        from sqlalchemy import delete
        
        # Удаляем связанные данные
        await session.execute(delete(GameStat).where(GameStat.tg_user_id == tg_user_id))
        await session.execute(delete(MessageLog).where(MessageLog.user_id == tg_user_id))
        
        # Удаляем пользователя
        user = await session.scalar(select(User).where(User.tg_user_id == tg_user_id))
        if user:
            await session.delete(user)
        
        await session.commit()
    
    await callback.answer("✅ Пользователь удалён!", show_alert=True)
    
    # Вернуться к списку
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 К управлению", callback_data="owner_users")
    
    await callback.message.edit_text(
        f"✅ Пользователь <code>{tg_user_id}</code> удалён.",
        reply_markup=kb.as_markup()
    )


@router.callback_query(F.data == "owner_users_recent")
async def cb_owner_users_recent(callback: CallbackQuery):
    """Показать последних зарегистрированных пользователей."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    async_session = get_session()
    async with async_session() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(15)
        )
        users = result.scalars().all()
    
    if not users:
        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 Назад", callback_data="owner_users")
        await callback.message.edit_text(
            "📭 Нет пользователей",
            reply_markup=kb.as_markup()
        )
        await callback.answer()
        return
    
    text = "📋 <b>Последние пользователи</b>\n\n"
    
    kb = InlineKeyboardBuilder()
    for user in users:
        name = f"@{user.username}" if user.username else user.first_name or f"id:{user.tg_user_id}"
        date = user.created_at.strftime('%d.%m') if user.created_at else "?"
        kb.button(text=f"{date} {name}", callback_data=f"owner_user:{user.tg_user_id}")
    
    kb.button(text="🔙 Назад", callback_data="owner_users")
    kb.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()

# ============================================================================
# РАСШИРЕННОЕ МЕНЮ ВАЙПА (Selective Wipe)
# ============================================================================

@router.callback_query(F.data == "owner_wipe_menu")
async def cb_owner_wipe_menu(callback: CallbackQuery):
    """Меню выборочного вайпа."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🧠 RAG память (ChromaDB)", callback_data="owner_wipe_rag")
    kb.button(text="🎮 Игровая статистика", callback_data="owner_wipe_games")
    kb.button(text="💬 Цитаты", callback_data="owner_wipe_quotes")
    kb.button(text="📝 Логи сообщений", callback_data="owner_wipe_messages")
    kb.button(text="👥 Пользователи и чаты", callback_data="owner_wipe_users")
    kb.button(text="🏆 Достижения и квесты", callback_data="owner_wipe_achievements")
    kb.button(text="⚠️ ВСЁ СРАЗУ", callback_data="owner_wipe_all_confirm")
    kb.button(text="🔙 Назад", callback_data="owner_emergency")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "🗑 <b>Выборочный вайп</b>\n\n"
        "Выбери что хочешь сбросить:\n\n"
        "• <b>RAG память</b> — векторная БД (ChromaDB)\n"
        "• <b>Игровая статистика</b> — размеры, PvP, казино\n"
        "• <b>Цитаты</b> — все сохранённые цитаты\n"
        "• <b>Логи сообщений</b> — история сообщений\n"
        "• <b>Пользователи и чаты</b> — все юзеры и группы\n"
        "• <b>Достижения и квесты</b> — прогресс игроков\n\n"
        "⚠️ Действия необратимы!",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "owner_wipe_rag")
async def cb_owner_wipe_rag(callback: CallbackQuery):
    """Подтверждение вайпа RAG памяти."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🧠 Вайп + восстановить дефолт", callback_data="owner_wipe_rag_exec:restore")
    kb.button(text="🗑 Полный вайп (без дефолта)", callback_data="owner_wipe_rag_exec:clean")
    kb.button(text="❌ Отмена", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "🧠 <b>Вайп RAG памяти (ChromaDB)</b>\n\n"
        "Это удалит всю векторную память бота:\n"
        "• Запомненные факты из чатов\n"
        "• Контекст разговоров\n"
        "• Выученную информацию\n\n"
        "Выбери режим:\n"
        "• <b>С восстановлением</b> — загрузит дефолтные знания\n"
        "• <b>Полный вайп</b> — оставит память пустой",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("owner_wipe_rag_exec:"))
async def cb_owner_wipe_rag_exec(callback: CallbackQuery):
    """Выполнение вайпа RAG памяти."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    mode = callback.data.split(":")[1]  # restore или clean
    restore_default = mode == "restore"
    
    await callback.message.edit_text("🧠 <b>Вайп RAG памяти...</b>\n\n⏳ Подождите...")
    
    results = []
    
    try:
        from app.services.vector_db import vector_db
        if vector_db.client:
            collections = vector_db.client.list_collections()
            for col in collections:
                vector_db.client.delete_collection(col.name)
            results.append(f"✅ Удалено {len(collections)} коллекций")
        else:
            results.append("⚠️ ChromaDB не инициализирована")
    except Exception as e:
        results.append(f"❌ Ошибка: {str(e)[:50]}")

    
    if restore_default:
        try:
            from app.services.vector_db import vector_db
            from app.config import settings
            if vector_db.client:
                collection_name = settings.chromadb_collection_name
                load_result = vector_db.load_default_knowledge(collection_name)
                if load_result.get("error"):
                    results.append(f"⚠️ Дефолт: {load_result['error']}")
                else:
                    results.append(f"✅ Загружено {load_result['loaded']} дефолтных фактов")
        except Exception as e:
            results.append(f"❌ Дефолт: {str(e)[:50]}")
    
    logger.warning(f"RAG WIPE executed by owner {callback.from_user.id}, restore={restore_default}")
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 К меню вайпа", callback_data="owner_wipe_menu")
    kb.button(text="🏠 Главное меню", callback_data="owner_main")
    kb.adjust(2)
    
    await callback.message.edit_text(
        "🧠 <b>Вайп RAG памяти завершён</b>\n\n" +
        "\n".join(results),
        reply_markup=kb.as_markup()
    )
    await callback.answer("Готово!", show_alert=True)


@router.callback_query(F.data == "owner_wipe_games")
async def cb_owner_wipe_games(callback: CallbackQuery):
    """Подтверждение вайпа игровой статистики."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, сбросить игры", callback_data="owner_wipe_games_exec")
    kb.button(text="❌ Отмена", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "🎮 <b>Вайп игровой статистики</b>\n\n"
        "Это удалит:\n"
        "• Все размеры игроков\n"
        "• PvP статистику и победы\n"
        "• Казино джекпоты\n"
        "• ELO рейтинги и лиги\n"
        "• Кошельки и балансы\n\n"
        "⚠️ Все игроки начнут с нуля!",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "owner_wipe_games_exec")
async def cb_owner_wipe_games_exec(callback: CallbackQuery):
    """Выполнение вайпа игровой статистики."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    await callback.message.edit_text("🎮 <b>Вайп игр...</b>\n\n⏳ Подождите...")
    
    results = []
    
    try:
        from app.database.models import GameStat, Wallet, UserElo
        from sqlalchemy import delete
        
        async with get_session()() as session:
            r1 = await session.execute(delete(GameStat))
            r2 = await session.execute(delete(Wallet))
            try:
                r3 = await session.execute(delete(UserElo))
                results.append(f"✅ UserElo: {r3.rowcount}")
            except Exception:
                pass
            await session.commit()
            results.append(f"✅ GameStat: {r1.rowcount} записей")
            results.append(f"✅ Wallet: {r2.rowcount} записей")
    except Exception as e:
        results.append(f"❌ Ошибка: {str(e)[:50]}")

    
    logger.warning(f"GAMES WIPE executed by owner {callback.from_user.id}")
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 К меню вайпа", callback_data="owner_wipe_menu")
    kb.button(text="🏠 Главное меню", callback_data="owner_main")
    kb.adjust(2)
    
    await callback.message.edit_text(
        "🎮 <b>Вайп игр завершён</b>\n\n" +
        "\n".join(results),
        reply_markup=kb.as_markup()
    )
    await callback.answer("Готово!", show_alert=True)


@router.callback_query(F.data == "owner_wipe_quotes")
async def cb_owner_wipe_quotes(callback: CallbackQuery):
    """Подтверждение вайпа цитат."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, удалить цитаты", callback_data="owner_wipe_quotes_exec")
    kb.button(text="❌ Отмена", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "💬 <b>Вайп цитат</b>\n\n"
        "Это удалит все сохранённые цитаты пользователей.\n\n"
        "⚠️ Действие необратимо!",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "owner_wipe_quotes_exec")
async def cb_owner_wipe_quotes_exec(callback: CallbackQuery):
    """Выполнение вайпа цитат."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    try:
        from app.database.models import Quote
        from sqlalchemy import delete
        
        async with get_session()() as session:
            result = await session.execute(delete(Quote))
            await session.commit()
            count = result.rowcount
    except Exception as e:
        count = f"Ошибка: {e}"

    
    logger.warning(f"QUOTES WIPE executed by owner {callback.from_user.id}")
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 К меню вайпа", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        f"💬 <b>Вайп цитат завершён</b>\n\n✅ Удалено: {count}",
        reply_markup=kb.as_markup()
    )
    await callback.answer("Готово!", show_alert=True)


@router.callback_query(F.data == "owner_wipe_messages")
async def cb_owner_wipe_messages(callback: CallbackQuery):
    """Подтверждение вайпа логов сообщений."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, очистить логи", callback_data="owner_wipe_messages_exec")
    kb.button(text="❌ Отмена", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "📝 <b>Вайп логов сообщений</b>\n\n"
        "Это удалит:\n"
        "• Историю всех сообщений\n"
        "• Историю вопросов пользователей\n\n"
        "⚠️ Статистика активности будет потеряна!",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "owner_wipe_messages_exec")
async def cb_owner_wipe_messages_exec(callback: CallbackQuery):
    """Выполнение вайпа логов."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    results = []
    try:
        from app.database.models import MessageLog, UserQuestionHistory
        from sqlalchemy import delete
        
        async with get_session()() as session:
            r1 = await session.execute(delete(MessageLog))
            r2 = await session.execute(delete(UserQuestionHistory))
            await session.commit()
            results.append(f"✅ Сообщений: {r1.rowcount}")
            results.append(f"✅ История вопросов: {r2.rowcount}")
    except Exception as e:
        results.append(f"❌ Ошибка: {str(e)[:50]}")

    
    logger.warning(f"MESSAGES WIPE executed by owner {callback.from_user.id}")
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 К меню вайпа", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "📝 <b>Вайп логов завершён</b>\n\n" + "\n".join(results),
        reply_markup=kb.as_markup()
    )
    await callback.answer("Готово!", show_alert=True)


@router.callback_query(F.data == "owner_wipe_users")
async def cb_owner_wipe_users(callback: CallbackQuery):
    """Подтверждение вайпа пользователей."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="⚠️ Да, удалить всех", callback_data="owner_wipe_users_exec")
    kb.button(text="❌ Отмена", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "👥 <b>Вайп пользователей и чатов</b>\n\n"
        "Это удалит:\n"
        "• Всех пользователей\n"
        "• Все группы/чаты\n"
        "• Приватные чаты\n"
        "• Админов и блеклисты\n\n"
        "⚠️ <b>ОПАСНО!</b> Бот забудет всех!",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "owner_wipe_users_exec")
async def cb_owner_wipe_users_exec(callback: CallbackQuery):
    """Выполнение вайпа пользователей."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    results = []
    try:
        from app.database.models import User, Chat, PrivateChat, Admin, Blacklist
        from sqlalchemy import delete
        
        async with get_session()() as session:
            # Порядок важен из-за FK
            r1 = await session.execute(delete(Admin))
            r2 = await session.execute(delete(Blacklist))
            r3 = await session.execute(delete(PrivateChat))
            r4 = await session.execute(delete(Chat))
            # User удаляем последним (много FK ссылаются на него)
            await session.commit()
            results.append(f"✅ Админы: {r1.rowcount}")
            results.append(f"✅ Блеклист: {r2.rowcount}")
            results.append(f"✅ Приватные чаты: {r3.rowcount}")
            results.append(f"✅ Группы: {r4.rowcount}")
    except Exception as e:
        results.append(f"❌ Ошибка: {str(e)[:50]}")

    
    logger.warning(f"USERS WIPE executed by owner {callback.from_user.id}")
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 К меню вайпа", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "👥 <b>Вайп пользователей завершён</b>\n\n" + "\n".join(results),
        reply_markup=kb.as_markup()
    )
    await callback.answer("Готово!", show_alert=True)


@router.callback_query(F.data == "owner_wipe_achievements")
async def cb_owner_wipe_achievements(callback: CallbackQuery):
    """Подтверждение вайпа достижений."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, сбросить прогресс", callback_data="owner_wipe_achievements_exec")
    kb.button(text="❌ Отмена", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "🏆 <b>Вайп достижений и квестов</b>\n\n"
        "Это удалит:\n"
        "• Все достижения пользователей\n"
        "• Прогресс квестов\n"
        "• Гильдии и участников\n"
        "• Турниры и рейтинги\n\n"
        "⚠️ Весь прогресс будет потерян!",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "owner_wipe_achievements_exec")
async def cb_owner_wipe_achievements_exec(callback: CallbackQuery):
    """Выполнение вайпа достижений."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    results = []
    try:
        from app.database.models import (
            UserAchievement, Achievement, UserQuest, Quest,
            GuildMember, Guild, TournamentScore, Tournament,
            UserReputation, ReputationHistory
        )
        from sqlalchemy import delete
        
        async with get_session()() as session:
            tables = [
                (TournamentScore, "TournamentScore"),
                (Tournament, "Tournament"),
                (ReputationHistory, "ReputationHistory"),
                (UserReputation, "UserReputation"),
                (UserAchievement, "UserAchievement"),
                (Achievement, "Achievement"),
                (UserQuest, "UserQuest"),
                (Quest, "Quest"),
                (GuildMember, "GuildMember"),
                (Guild, "Guild"),
            ]
            for model, name in tables:
                try:
                    r = await session.execute(delete(model))
                    results.append(f"✅ {name}: {r.rowcount}")
                except Exception as e:
                    results.append(f"⚠️ {name}: {str(e)[:30]}")
            await session.commit()
    except Exception as e:
        results.append(f"❌ Ошибка: {str(e)[:50]}")

    
    logger.warning(f"ACHIEVEMENTS WIPE executed by owner {callback.from_user.id}")
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 К меню вайпа", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "🏆 <b>Вайп достижений завершён</b>\n\n" + "\n".join(results),
        reply_markup=kb.as_markup()
    )
    await callback.answer("Готово!", show_alert=True)


@router.callback_query(F.data == "owner_wipe_all_confirm")
async def cb_owner_wipe_all_confirm(callback: CallbackQuery):
    """Финальное подтверждение полного вайпа."""
    if not is_owner(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    
    kb = InlineKeyboardBuilder()
    kb.button(text="⚠️ ДА, УДАЛИТЬ ВСЁ", callback_data="owner_wipe_execute")
    kb.button(text="❌ Отмена", callback_data="owner_wipe_menu")
    kb.adjust(1)
    
    await callback.message.edit_text(
        "🗑 <b>ПОЛНЫЙ ВАЙП</b>\n\n"
        "⚠️ <b>ВНИМАНИЕ!</b> Это действие:\n"
        "• Удалит ВСЮ память бота (ChromaDB)\n"
        "• Очистит ВСЕ таблицы базы данных\n"
        "• Удалит всех пользователей, чаты, статистику\n"
        "• Удалит все цитаты, достижения, квесты\n\n"
        "❗ <b>ЭТО ДЕЙСТВИЕ НЕОБРАТИМО!</b>\n\n"
        "Ты уверен?",
        reply_markup=kb.as_markup()
    )
    await callback.answer()
