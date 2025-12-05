"""Глобальный слушатель сообщений из всех топиков супергруппы."""

import logging
from aiogram import Router, F
from aiogram.types import Message
from typing import Optional, List, Dict

from app.services.vector_db import vector_db
from app.utils import utc_now

logger = logging.getLogger(__name__)

router = Router()


class TopicListener:
    """
    Глобальный слушатель сообщений из всех топиков.
    
    Обрабатывает сообщения из любого топика супергруппы и сохраняет
    их в RAG с привязкой к chat_id и topic_id для меж-топикового восприятия.
    """
    
    COLLECTION_NAME = "chat_messages"
    
    def __init__(self):
        self._vector_db = vector_db
    
    def extract_topic_id(self, message: Message) -> Optional[int]:
        """
        Извлекает topic_id из сообщения.
        
        Args:
            message: Сообщение Telegram
            
        Returns:
            topic_id или None если сообщение не в топике
        """
        return getattr(message, 'message_thread_id', None)
    
    async def store_to_rag(self, message: Message) -> None:
        """
        Сохраняет сообщение в RAG с привязкой к топику.
        
        Args:
            message: Сообщение Telegram
        """
        if not message.text:
            return
        
        chat_id = message.chat.id
        topic_id = self.extract_topic_id(message)
        user_id = message.from_user.id if message.from_user else 0
        username = message.from_user.username if message.from_user else None
        
        try:
            self._vector_db.store_message(
                collection_name=self.COLLECTION_NAME,
                text=message.text,
                chat_id=chat_id,
                topic_id=topic_id,
                user_id=user_id,
                username=username,
                message_id=message.message_id
            )
            logger.debug(
                f"Сообщение сохранено в RAG: chat={chat_id}, topic={topic_id}, "
                f"user={username or user_id}"
            )
        except Exception as e:
            logger.error(f"Ошибка при сохранении сообщения в RAG: {e}")
    
    def get_cross_topic_context(self, chat_id: int, query: str, n_results: int = 5) -> List[Dict]:
        """
        Получает контекст из всех топиков чата (cross-topic retrieval).
        
        Args:
            chat_id: ID чата
            query: Запрос для поиска релевантного контекста
            n_results: Количество результатов
            
        Returns:
            Список релевантных сообщений из всех топиков чата
        """
        try:
            return self._vector_db.search_cross_topic(
                collection_name=self.COLLECTION_NAME,
                query=query,
                chat_id=chat_id,
                n_results=n_results
            )
        except Exception as e:
            logger.error(f"Ошибка при получении cross-topic контекста: {e}")
            return []
    
    def format_context_with_topic_info(self, facts: List[Dict]) -> str:
        """
        Форматирует контекст с информацией о топиках.
        
        Args:
            facts: Список фактов из RAG
            
        Returns:
            Отформатированная строка контекста с указанием топиков
        """
        if not facts:
            return ""
        
        context_parts = []
        for fact in facts:
            metadata = fact.get('metadata', {})
            topic_id = metadata.get('topic_id', -1)
            username = metadata.get('username', 'Unknown')
            text = fact.get('text', '')
            
            # Форматируем с указанием топика
            topic_label = f"[Topic {topic_id}]" if topic_id != -1 else "[General]"
            context_parts.append(f"{topic_label} @{username}: {text}")
        
        return "\n".join(context_parts)
    
    async def on_message(self, message: Message) -> None:
        """
        Обрабатывает сообщение из любого топика.
        
        Args:
            message: Сообщение Telegram
        """
        # Сохраняем только текстовые сообщения из групп/супергрупп
        if message.chat.type not in ("group", "supergroup"):
            return
        
        if not message.text:
            return
        
        await self.store_to_rag(message)


# Глобальный экземпляр слушателя
topic_listener = TopicListener()


@router.message(F.text)
async def handle_all_messages(message: Message):
    """
    Глобальный обработчик всех текстовых сообщений для RAG.
    
    Этот обработчик должен быть зарегистрирован с низким приоритетом,
    чтобы не блокировать другие обработчики.
    """
    await topic_listener.on_message(message)
