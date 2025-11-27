"""Middleware для управления режимами модерации."""

import logging
import json
import re
from typing import Callable, Awaitable, Dict, Any
from aiogram import BaseMiddleware
from aiogram.types import Message, ChatPermissions
from datetime import timedelta, datetime
from sqlalchemy import select

from app.database.session import get_session
from app.database.models import ModerationConfig

logger = logging.getLogger(__name__)

# Кэш для хранения настроек модерации
_moderation_cache = {}
_last_cache_update = datetime.min


class ModeFilterMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        # Пропускаем служебные сообщения
        if event.content_type in ['chat_member_left', 'chat_member_joined', 'message_pinned']:
            return await handler(event, data)

        # Получаем настройки модерации для чата
        config = await self.get_moderation_config(event.chat.id)

        # Проверяем, нужно ли обрабатывать сообщение в зависимости от режима
        if config.mode == "light":
            # В "лайт" режиме только защита от рейдов
            return await handler(event, data)
        elif config.mode in ["normal", "dictatorship"]:
            # В "норма" и "диктатура" режимах проверяем по полному сценарию
            action_taken = await self.check_and_apply_moderation(event, config)
            if action_taken:
                # Если было применено модерационное действие, не передаем дальше
                return
        
        return await handler(event, data)

    async def get_moderation_config(self, chat_id: int) -> ModerationConfig:
        """Получает настройки модерации для чата с кэшированием."""
        global _moderation_cache, _last_cache_update
        
        # Обновляем кэш каждые 5 минут
        if (datetime.now() - _last_cache_update).seconds > 300:
            await self._refresh_cache()
        
        if chat_id in _moderation_cache:
            return _moderation_cache[chat_id]
        
        # Если в кэше нет, создаем конфигурацию по умолчанию
        default_config = ModerationConfig(
            chat_id=chat_id,
            mode="normal",  # режим по умолчанию
            flood_threshold=5,
            spam_link_protection=True,
            swear_filter=True,
            auto_warn_threshold=3
        )
        return default_config

    async def _refresh_cache(self):
        """Обновляет кэш настроек модерации из базы данных."""
        global _moderation_cache, _last_cache_update
        
        async_session = get_session()
        async with async_session() as session:
            configs_res = await session.execute(select(ModerationConfig))
            configs = configs_res.scalars().all()
            
            _moderation_cache = {config.chat_id: config for config in configs}
            _last_cache_update = datetime.now()
        
        logger.debug(f"Кэш модерации обновлён, всего конфигураций: {len(_moderation_cache)}")

    async def check_and_apply_moderation(self, event: Message, config: ModerationConfig) -> bool:
        """
        Проверяет сообщение и применяет модерационные меры в зависимости от режима.
        
        Args:
            event: Сообщение
            config: Настройки модерации
            
        Returns:
            True если было применено модерационное действие
        """
        if not event.text and not event.caption:
            return False

        text = event.text or event.caption or ""
        user_id = event.from_user.id
        chat_id = event.chat.id

        logger.debug(f"Проверка модерации для режима {config.mode}, сообщение: {text[:50]}...")

        # В зависимости от режима применяем разные проверки
        if config.mode == "dictatorship":
            # Жесткий режим: проверяем всё
            checks = [
                self._check_flood,
                self._check_links,
                self._check_banned_words,
                self._check_toxicity
            ]
        elif config.mode == "normal":
            # Нормальный режим: основные проверки
            checks = [
                self._check_flood,
                self._check_links,
                self._check_banned_words
            ]
        else:
            # Другие режимы - возвращаем False
            return False

        for check_func in checks:
            action_taken = await check_func(event, config)
            if action_taken:
                return True

        return False

    async def _check_flood(self, event: Message, config: ModerationConfig) -> bool:
        """Проверяет флуд."""
        # Для простоты пока просто возвращаем False
        # В реальной реализации нужно отслеживать частоту сообщений от пользователя
        return False

    async def _check_links(self, event: Message, config: ModerationConfig) -> bool:
        """Проверяет ссылки в сообщении."""
        if not config.spam_link_protection:
            return False

        text = event.text or event.caption or ""
        
        # Проверяем наличие ссылок в тексте
        link_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        if link_pattern.search(text):
            if config.mode == "dictatorship":
                # В диктаторском режиме удаляем сообщение и мутим на час
                try:
                    await event.delete()
                    await event.chat.restrict(
                        user_id=event.from_user.id,
                        permissions=ChatPermissions(can_send_messages=False),
                        until_date=timedelta(hours=1)
                    )
                    await event.answer(
                        f"Пользователь @{event.from_user.username or event.from_user.id} "
                        f"получил мут за отправку ссылки в диктаторском режиме."
                    )
                    logger.info(f"Пользователь {event.from_user.id} замучен за ссылку в режиме диктатуры")
                    return True
                except Exception as e:
                    logger.error(f"Ошибка при модерации ссылки: {e}")
            elif config.mode == "normal":
                # В нормальном режиме просто предупреждаем
                try:
                    await event.answer(
                        f"@{event.from_user.username or event.from_user.id}, "
                        f"ссылки в этом режиме не приветствуются!"
                    )
                except Exception:
                    pass  # Игнорируем ошибки при отправке сообщения
        return False

    async def _check_banned_words(self, event: Message, config: ModerationConfig) -> bool:
        """Проверяет запрещенные слова."""
        text = event.text or event.caption or ""
        text_lower = text.lower()

        # Получаем список запрещенных слов из конфигурации
        banned_words = []
        if config.banned_words:
            try:
                banned_words = json.loads(config.banned_words)
            except json.JSONDecodeError:
                logger.warning(f"Ошибка при разборе запрещенных слов для чата {config.chat_id}")

        # Проверяем наличие запрещенных слов
        for word in banned_words:
            if word.lower() in text_lower:
                if config.mode == "dictatorship":
                    # В диктаторском режиме удаляем сообщение и мутим
                    try:
                        await event.delete()
                        await event.chat.restrict(
                            user_id=event.from_user.id,
                            permissions=ChatPermissions(can_send_messages=False),
                            until_date=timedelta(hours=2)
                        )
                        await event.answer(
                            f"Пользователь @{event.from_user.username or event.from_user.id} "
                            f"получил мут за использование запрещенного слова: '{word}'"
                        )
                        logger.info(f"Пользователь {event.from_user.id} замучен за запрещенное слово: {word}")
                        return True
                    except Exception as e:
                        logger.error(f"Ошибка при модерации запрещенного слова: {e}")
                elif config.mode == "normal":
                    # В нормальном режиме просто предупреждаем
                    try:
                        await event.delete()
                        await event.answer(
                            f"@{event.from_user.username or event.from_user.id}, "
                            f"слово '{word}' запрещено в этом чате!"
                        )
                    except Exception:
                        pass  # Игнорируем ошибки
                return True
        return False

    async def _check_toxicity(self, event: Message, config: ModerationConfig) -> bool:
        """
        Проверяет токсичность сообщения.
        В реальной реализации здесь будет вызов соответствующей функции анализа токсичности.
        """
        # Пока что просто возвращаем False
        # В будущем будет интеграция с системой анализа токсичности
        return False


async def set_moderation_mode(chat_id: int, mode: str, db_session=None) -> bool:
    """
    Устанавливает режим модерации для чата.
    
    Args:
        chat_id: ID чата
        mode: Режим модерации ('light', 'normal', 'dictatorship')
        db_session: Сессия базы данных (опционально)
        
    Returns:
        True если успешно
    """
    if mode not in ["light", "normal", "dictatorship"]:
        logger.warning(f"Неподдерживаемый режим модерации: {mode}")
        return False

    local_session = False
    if not db_session:
        db_session = get_session()
        local_session = True

    try:
        async with db_session() as session:
            # Проверяем, есть ли уже конфигурация для этого чата
            config_res = await session.execute(
                select(ModerationConfig).filter_by(chat_id=chat_id)
            )
            config = config_res.scalar_one_or_none()

            if config:
                # Обновляем существующую конфигурацию
                config.mode = mode
                config.updated_at = datetime.now()
            else:
                # Создаем новую конфигурацию
                config = ModerationConfig(
                    chat_id=chat_id,
                    mode=mode
                )
                session.add(config)

            await session.commit()
            logger.info(f"Режим модерации для чата {chat_id} изменен на {mode}")

            # Обновляем кэш
            _moderation_cache[chat_id] = config

            return True
    except Exception as e:
        logger.error(f"Ошибка при изменении режима модерации: {e}")
        return False
    finally:
        if local_session:
            await db_session.close()


async def get_moderation_mode(chat_id: int) -> str:
    """
    Получает текущий режим модерации для чата.
    
    Args:
        chat_id: ID чата
        
    Returns:
        Режим модерации
    """
    config = await _get_moderation_config_db(chat_id)
    return config.mode if config else "normal"


async def _get_moderation_config_db(chat_id: int) -> ModerationConfig:
    """Получает конфигурацию модерации из базы данных."""
    async_session = get_session()
    async with async_session() as session:
        config_res = await session.execute(
            select(ModerationConfig).filter_by(chat_id=chat_id)
        )
        return config_res.scalar_one_or_none()