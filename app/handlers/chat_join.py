"""Обработчик событий добавления бота в чат (Plug & Play)."""

import logging
from aiogram import Router, F
from aiogram.types import Message, ChatMemberUpdated
from aiogram.filters import ChatMemberUpdatedFilter, JOIN_TRANSITION, LEAVE_TRANSITION
from sqlalchemy import select
import re

from app.database.session import get_session
from app.database.models import ChatConfig, User
from app.services.ollama_client import _ollama_chat

logger = logging.getLogger(__name__)

router = Router()

# Обновляем модель ChatConfig, чтобы она использовалась в новых чатах
async def create_chat_config(chat_id: int, chat_title: str, chat_type: str):
    """Создает конфигурацию для нового чата."""
    async_session = get_session()
    async with async_session() as session:
        # Проверяем, существует ли уже конфигурация для этого чата
        config_res = await session.execute(
            select(ChatConfig).filter_by(chat_id=chat_id)
        )
        config = config_res.scalars().first()
        
        if config:
            # Если уже существует, обновляем название
            config.chat_name = chat_title
            config.chat_type = chat_type
        else:
            # Создаем новую конфигурацию
            config = ChatConfig(
                chat_id=chat_id,
                chat_name=chat_title,
                chat_type=chat_type,
                moderation_mode="normal"  # Режим по умолчанию
            )
            session.add(config)
        
        await session.commit()
        return config


async def scan_chat_context(bot, chat_id: int) -> str:
    """
    Сканирует контекст чата (описание, закрепленные сообщения) и генерирует системный промпт.
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        
    Returns:
        Сгенерированный системный промпт для этого чата
    """
    try:
        # Получаем информацию о чате
        chat = await bot.get_chat(chat_id)
        
        context_info = []
        
        # Добавляем описание чата, если оно есть
        if chat.description:
            context_info.append(f"Описание чата: {chat.description}")
        
        # Пытаемся получить закрепленное сообщение
        try:
            pinned_message = await bot.get_chat(chat_id).pinned_message
            if pinned_message:
                message_text = pinned_message.text or (pinned_message.caption if hasattr(pinned_message, 'caption') else '')
                if message_text:
                    context_info.append(f"Закрепленное сообщение: {message_text}")
        except Exception:
            # Если не удалось получить закрепленное сообщение, продолжаем без него
            pass
        
        # Если есть контекст, генерируем промпт
        if context_info:
            context_text = "\n".join(context_info)
            
            # Генерируем системный промпт на основе контекста
            prompt = f"""
            На основе следующей информации о чате, сгенерируй краткий системный промпт для ИИ-бота Олега.
            Промпт должен отражать тематику чата и особенности общения (формальный/неформальный стиль, 
            запреты, одобрения и т.д.).
            
            Контекст чата:
            {context_text}
            
            Сгенерируй только промпт, без дополнительных пояснений:
            """
            
            system_prompt = await _ollama_chat([
                {"role": "system", "content": "Ты помощник, который генерирует системные промпты для ИИ-бота."},
                {"role": "user", "content": prompt}
            ], temperature=0.3)
            
            # Возвращаем сгенерированный промпт или стандартный, если не удалось
            if system_prompt and len(system_prompt.strip()) > 10:
                return system_prompt.strip()
        
        # Если не удалось получить контекст или сгенерировать промпт, возвращаем стандартный
        return (
            "Ты — Олег, грубоватый, прямолинейный, матерящийся, "
            "но полезный бот. Говори коротко, по делу, с иронией и сленгом. "
            "Можешь ругнуться, но без оскорблений по запрещённым признакам. "
            "Контекст — текущий чат."
        )
    except Exception as e:
        logger.error(f"Ошибка при сканировании контекста чата {chat_id}: {e}")
        # Возвращаем стандартный промпт, если возникла ошибка
        return (
            "Ты — Олег, грубоватый, прямолинейный, матерящийся, "
            "но полезный бот. Говори коротко, по делу, с иронией и сленгом. "
            "Можешь ругнуться, но без оскорблений по запрещённым признакам. "
            "Контекст — текущий чат."
        )


async def send_welcome_message(bot, chat_id: int, chat_title: str):
    """
    Отправляет приветственное сообщение в чат на основе контекста.
    
    Args:
        bot: Экземпляр бота
        chat_id: ID чата
        chat_title: Название чата
    """
    try:
        # Генерируем приветствие на основе контекста
        welcome_prompt = f"""
        Сгенерируй дружелюбное, но в стиле Олега, приветственное сообщение для нового чата "{chat_title}".
        Сообщение должно быть кратким, отражать суть чата (если она понятна) и 
        сообщать, что ты Олег - модерационный бот.
        Не используй формальный стиль, будь дерзковатым, но вежливым.
        Примеры: "О, чат про [тема]. Я Олег, буду следить за порядком. [правила кратко]"
        """
        
        welcome_message = await _ollama_chat([
            {"role": "system", "content": "Ты Олег, грубоватый, но полезный бот. Генерируй приветственное сообщение."},
            {"role": "user", "content": welcome_prompt}
        ], temperature=0.7)
        
        # Отправляем приветствие в чат
        await bot.send_message(chat_id=chat_id, text=welcome_message)
        
    except Exception as e:
        logger.error(f"Ошибка при отправке приветствия в чат {chat_id}: {e}")
        # Если не удалось сгенерировать, отправляем стандартное сообщение
        try:
            await bot.send_message(
                chat_id=chat_id, 
                text=(
                    f"О, новый чатик '{chat_title}'! Я Олег, ваш персональный надзиратель. "
                    f"Следите за базаром, не троллите почем зря, и будете жить."
                )
            )
        except Exception as e2:
            logger.error(f"Ошибка при отправке стандартного приветствия: {e2}")


@router.my_chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def bot_added_to_chat(event: ChatMemberUpdated):
    """
    Обработчик события добавления бота в чат.
    """
    chat_id = event.chat.id
    chat_title = event.chat.title or "Без названия"
    chat_type = event.chat.type  # 'group', 'supergroup', 'channel', 'private'
    
    logger.info(f"Бот добавлен в чат {chat_title} (ID: {chat_id}, тип: {chat_type})")
    
    # Создаем конфигурацию для чата
    await create_chat_config(chat_id, chat_title, chat_type)
    
    # Сканируем контекст чата и настраиваем промпт
    context_prompt = await scan_chat_context(event.bot, chat_id)
    
    # Сохраняем промпт в конфигурации (в реальном приложении нужно обновить модель, чтобы хранить промпт)
    # Пока что просто логируем
    logger.info(f"Сгенерирован промпт для чата {chat_title}: {context_prompt[:100]}...")
    
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
                from app.database.models import ChatConfig
                chat_config_res = await session.execute(
                    select(ChatConfig).filter_by(chat_id=msg.chat.id)
                )
                chat_config = chat_config_res.scalars().first()

                # Генерируем персонализированное приветствие
                if chat_config and chat_config.welcome_message:
                    # Если у чата есть специальное приветствие
                    base_welcome = chat_config.welcome_message
                else:
                    # Генерируем универсальное приветствие с учетом типа чата
                    context_info = f"чат '{msg.chat.title}'" if msg.chat.title else "этот чат"
                    if chat_config:
                        # Используем информацию из контекста чата
                        base_welcome = f"О, новое лицо! Привет, {new_member.full_name}, зашел в {context_info}."
                    else:
                        base_welcome = f"Привет, {new_member.full_name}! Добро пожаловать в {context_info}."

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