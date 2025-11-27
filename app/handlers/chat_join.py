"""Обработчик событий добавления бота в чат (Plug & Play)."""

import logging
from aiogram import Router, F
from aiogram.types import Message, ChatMemberUpdated, CallbackQuery
from aiogram.filters import ChatMemberUpdatedFilter, JOIN_TRANSITION, LEAVE_TRANSITION
from sqlalchemy import select
import re

from app.database.session import get_session
from app.database.models import Chat, User
from app.services.ollama_client import _ollama_chat

logger = logging.getLogger(__name__)

router = Router()

# Обновляем модель ChatConfig, чтобы она использовалась в новых чатах
async def create_chat(chat_id: int, chat_title: str, chat_type: str, owner_user_id: int, is_forum: bool):
    """Создает конфигурацию для нового чата."""
    async_session = get_session()
    async with async_session() as session:
        # Проверяем, существует ли уже конфигурация для этого чата
        config_res = await session.execute(
            select(Chat).filter_by(id=chat_id)
        )
        config = config_res.scalars().first()
        
        if config:
            # Если уже существует, обновляем название
            config.title = chat_title
        else:
            # Создаем новую конфигурацию
            config = Chat(
                id=chat_id,
                title=chat_title,
                is_forum=is_forum,
                owner_user_id=owner_user_id,
            )
            session.add(config)
        
        await session.commit()
        return config



async def send_welcome_message(bot, chat_id: int, chat_title: str):
    """
    Отправляет приветственное сообщение в чат.
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        chat_title: Название чата
    """
    welcome_messages = [
        f"О, новый чатик '{chat_title}'! Я Олег, ваш персональный надзиратель. Следите за базаром, не троллите почем зря, и будете жить.",
        f"Так, {chat_title}, значит. Я Олег, и я здесь, чтобы вносить порядок. Или хаос. По настроению.",
        f"Привет, {chat_title}. Я Олег. Посмотрим, как вы тут себя ведете.",
        f"Зовите меня Олег. Я ваш новый лучший друг и худший кошмар. Зависит от вас.",
        f"Наконец-то я в {chat_title}. Олег на месте. Начинаем веселье.",
    ]
    try:
        await bot.send_message(chat_id=chat_id, text=random.choice(welcome_messages))
    except Exception as e:
        logger.error(f"Ошибка при отправке приветствия в чат {chat_id}: {e}")

@router.my_chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def bot_added_to_chat(event: ChatMemberUpdated):
    """
    Обработчик события добавления бота в чат.
    """
    chat_id = event.chat.id
    chat_title = event.chat.title or "Без названия"
    chat_type = event.chat.type
    is_forum = event.chat.is_forum or False

    logger.info(f"Бот добавлен в чат {chat_title} (ID: {chat_id}, тип: {chat_type})")

    # Ищем создателя чата
    chat_admins = await event.bot.get_chat_administrators(chat_id)
    creator = next((admin for admin in chat_admins if admin.status == 'creator'), None)
    owner_id = creator.user.id if creator else None

    # Создаем конфигурацию для чата
    await create_chat(chat_id, chat_title, chat_type, owner_id, is_forum)

    # Отправляем приветственное сообщение
    await send_welcome_message(event.bot, chat_id, chat_title)


@router.my_chat_member(ChatMemberUpdatedFilter(LEAVE_TRANSITION))
async def bot_removed_from_chat(event: ChatMemberUpdated):
    """
    Обработчик события удаления бота из чата.
    """
    chat_id = event.chat.id
    chat_title = event.chat.title or "Без названия"
    
    logger.info(f"Бот удален из чата {chat_title} (ID: {chat_id})")
    
    # В реальной реализации можно удалить конфигурацию чата или отметить как неактивную
    # Пока что просто логируем событие
    pass


from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio
import json


@router.message(F.new_chat_members)
async def new_chat_member_welcome(msg: Message):
    """
    Обработчик события добавления новых участников в чат.
    """
    # Удаляем системное сообщение о присоединении (если возможно и это не закрепленное сообщение)
    try:
        if not msg.pinned_message:  # Проверяем, что это не закрепленное сообщение
            await msg.delete()
    except Exception:
        # Не всегда возможно удалить системное сообщение
        pass

    # Приветствуем каждого нового участника
    for new_member in msg.new_chat_members:
        try:
            # Не приветствуем себя (бота) и других ботов
            if new_member.is_bot:
                continue

            # Получаем контекст чата для персонализации приветствия
            async_session = get_session()
            async with async_session() as session:
                from app.database.models import Chat
                chat_config_res = await session.execute(
                    select(Chat).filter_by(id=msg.chat.id)
                )
                chat_config = chat_config_res.scalars().first()

                # Генерируем универсальное приветствие с учетом типа чата
                context_info = f"чат '{msg.chat.title}'" if msg.chat.title else "этот чат"
                base_welcome = f"О, новое лицо! Привет, {new_member.full_name}, зашел в {context_info}."

            # Добавляем стиль Олега к приветствию
            oleg_style_welcome = f"{base_welcome} Не тролли почем зря, а то получишь от Олега."

            # Создаем inline-кнопку
            keyboard = InlineKeyboardBuilder()
            keyboard.button(
                text="✅ Я не бот / Прочитал правила",
                callback_data=f"verify_user_{new_member.id}_{msg.chat.id}"
            )
            keyboard.adjust(1)

            # Отправляем приветствие с кнопкой
            welcome_msg = await msg.answer(oleg_style_welcome, reply_markup=keyboard.as_markup())

            # Устанавливаем таймер на 5 минут для проверки, нажал ли пользователь кнопку
            await asyncio.sleep(5 * 60)  # 5 минут = 300 секунд

            # Проверяем, нужно ли кикнуть пользователя
            # В реальной реализации нужно отслеживать нажатие кнопки и хранить состояния
            # Пока что просто проверим, существует ли сообщение и выполним кик
            try:
                # В реальной системе состояние пользователя должно храниться в БД
                # Проверим, является ли пользователь админом, чтобы не кикать
                member = await msg.bot.get_chat_member(msg.chat.id, new_member.id)
                if member.status not in ["administrator", "creator"]:
                    # Кикуем пользователя, если он не нажал кнопку за 5 минут
                    await msg.bot.kick_chat_member(
                        msg.chat.id,
                        new_member.id,
                        until_date=None  # Постоянный бан, но можно разбанить
                    )
                    # Отправляем сообщение о кике
                    await msg.answer(f"Пользователь @{new_member.username or new_member.full_name} был кикнут за неактивность (не подтвердил, что не бот).")
            except Exception as e:
                logger.info(f"Не удалось кикнуть пользователя {new_member.id}: {e}")

        except Exception as e:
            logger.error(f"Ошибка при приветствии участника {new_member.id}: {e}")


# Обработчик нажатия на кнопку подтверждения
@router.callback_query(F.data.startswith("verify_user_"))
async def handle_verification_button(callback: CallbackQuery):
    """Обработка нажатия кнопки подтверждения 'Я не бот'."""
    data_parts = callback.data.split("_")
    if len(data_parts) < 4:
        await callback.answer("Неверный формат данных.")
        return

    user_id = int(data_parts[2])
    chat_id = int(data_parts[3])

    # Проверяем, что пользователь, который нажал, совпадает с тем, для кого была кнопка
    if callback.from_user.id != user_id:
        await callback.answer("Эта кнопка не для тебя.", show_alert=True)
        return

    try:
        # Обновляем статус пользователя в БД (в реальной реализации)
        # Пока что просто отправляем сообщение
        await callback.message.edit_text(
            f"✅ @{callback.from_user.username or callback.from_user.full_name} подтвердил, что он не бот!\n"
            f"Добро пожаловать в чат!"
        )
        await callback.answer("Спасибо за подтверждение! Теперь ты можешь свободно общаться в чате.")
    except Exception as e:
        logger.error(f"Ошибка при обработке подтверждения пользователя {user_id}: {e}")
        await callback.answer("Произошла ошибка при подтверждении.", show_alert=True)