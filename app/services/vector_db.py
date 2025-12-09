"""Модуль для работы с векторной базой данных (RAG)."""

import logging
import warnings
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional, Tuple, Any
import json
from datetime import datetime
from dataclasses import dataclass


@dataclass
class RAGFactMetadata:
    """
    Metadata schema for RAG facts in ChromaDB.
    
    **Feature: shield-economy-v65**
    **Validates: Requirements 11.1, 11.2, 11.3**
    
    This dataclass ensures consistent serialization and deserialization
    of RAG fact metadata, preserving all fields including Unicode characters.
    """
    chat_id: int
    user_id: int
    username: str
    topic_id: int  # -1 if not in topic
    message_id: int
    created_at: str  # ISO 8601 format
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize metadata to a dictionary for ChromaDB storage.
        
        All fields are preserved exactly as stored, including Unicode
        characters in username and other string fields.
        
        Returns:
            Dictionary with all metadata fields
        """
        return {
            "chat_id": self.chat_id,
            "user_id": self.user_id,
            "username": self.username,
            "topic_id": self.topic_id,
            "message_id": self.message_id,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RAGFactMetadata":
        """
        Deserialize metadata from a dictionary.
        
        Handles missing fields gracefully with sensible defaults.
        Preserves Unicode characters exactly as stored.
        
        Args:
            data: Dictionary containing metadata fields
            
        Returns:
            RAGFactMetadata instance with all fields populated
        """
        return cls(
            chat_id=data["chat_id"],
            user_id=data["user_id"],
            username=data.get("username", ""),
            topic_id=data.get("topic_id", -1),
            message_id=data.get("message_id", 0),
            created_at=data["created_at"],
        )

# Подавляем ошибки телеметрии chromadb
warnings.filterwarnings("ignore", message=".*telemetry.*")
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)

class VectorDB:
    """Класс для работы с векторной базой данных ChromaDB."""
    
    def __init__(self):
        self.client = None
        self.collections = {}
        self.init_db()
    
    def init_db(self):
        """Инициализирует соединение с ChromaDB."""
        try:
            from app.config import settings
            # Используем PersistentClient для сохранения данных на диск
            self.client = chromadb.PersistentClient(
                path=settings.chromadb_persist_dir,
                settings=Settings(anonymized_telemetry=False)
            )
            logger.info(f"ChromaDB успешно инициализирована (путь: {settings.chromadb_persist_dir})")
        except Exception as e:
            logger.error(f"Ошибка при инициализации ChromaDB: {e}")
            raise
    
    def get_or_create_collection(self, name: str):
        """Получает или создает коллекцию."""
        try:
            # Всегда используем get_or_create для надёжности
            self.collections[name] = self.client.get_or_create_collection(name)
            return self.collections[name]
        except Exception as e:
            logger.error(f"Ошибка при получении коллекции {name}: {e}")
            # Пробуем пересоздать
            try:
                self.collections[name] = self.client.create_collection(name)
                return self.collections[name]
            except Exception as e2:
                logger.error(f"Не удалось создать коллекцию {name}: {e2}")
                raise
    
    def add_fact(self, collection_name: str, fact_text: str, metadata: Dict = None, doc_id: str = None):
        """
        Добавляет факт в коллекцию.
        
        Args:
            collection_name: Название коллекции
            fact_text: Текст факта для хранения
            metadata: Метаданные (чат, пользователь и т.д.)
            doc_id: Уникальный ID документа (если не указан, генерируется автоматически)
        """
        if not self.client:
            raise Exception("ChromaDB не инициализирована")
        
        collection = self.get_or_create_collection(collection_name)
        
        if not doc_id:
            # Генерируем ID на основе текущего времени
            doc_id = f"fact_{int(datetime.now().timestamp() * 1000000)}"
        
        if not metadata:
            metadata = {"created_at": datetime.now().isoformat()}
        
        try:
            collection.add(
                documents=[fact_text],
                metadatas=[metadata],
                ids=[doc_id]
            )
            logger.info(f"Факт добавлен в коллекцию {collection_name}: {fact_text[:100]}...")
        except Exception as e:
            logger.error(f"Ошибка при добавлении факта: {e}")
            raise
    
    def search_facts(self, collection_name: str, query: str, n_results: int = 5, model: str = None, where: Dict = None) -> List[Dict]:
        """
        Ищет релевантные факты в коллекции.
        
        Args:
            collection_name: Название коллекции
            query: Запрос для поиска
            n_results: Количество результатов для возврата
            model: Модель для использования (не используется в ChromaDB, для совместимости)
            where: Фильтр по метаданным (например, {"chat_id": 123})
            
        Returns:
            Список словарей с найденными фактами
        """
        if not self.client:
            raise Exception("ChromaDB не инициализирована")
        
        collection = self.get_or_create_collection(collection_name)
        
        try:
            query_params = {
                "query_texts": [query],
                "n_results": n_results
            }
            if where:
                query_params["where"] = where
            
            results = collection.query(**query_params)
            
            facts = []
            for i in range(len(results['documents'][0])):
                fact = {
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if results['distances'] and len(results['distances'][0]) > i else None
                }
                facts.append(fact)
            
            logger.debug(f"Найдено {len(facts)} фактов по запросу: {query[:50]}...")
            return facts
        except Exception as e:
            logger.error(f"Ошибка при поиске фактов: {e}")
            return []
    
    def search_cross_topic(self, collection_name: str, query: str, chat_id: int, n_results: int = 5) -> List[Dict]:
        """
        Ищет релевантные факты из всех топиков чата (cross-topic retrieval).
        
        Args:
            collection_name: Название коллекции
            query: Запрос для поиска
            chat_id: ID чата для фильтрации
            n_results: Количество результатов для возврата
            
        Returns:
            Список словарей с найденными фактами из всех топиков чата
        """
        # Фильтруем только по chat_id, не по topic_id - это даёт cross-topic retrieval
        return self.search_facts(
            collection_name=collection_name,
            query=query,
            n_results=n_results,
            where={"chat_id": chat_id}
        )
    
    def store_message(self, collection_name: str, text: str, chat_id: int, topic_id: Optional[int], 
                      user_id: int, username: Optional[str], message_id: int) -> None:
        """
        Сохраняет сообщение в RAG с привязкой к chat_id и topic_id.
        
        Args:
            collection_name: Название коллекции
            text: Текст сообщения
            chat_id: ID чата
            topic_id: ID топика (None если не в топике)
            user_id: ID пользователя
            username: Username пользователя
            message_id: ID сообщения в Telegram
        """
        metadata = {
            "chat_id": chat_id,
            "topic_id": topic_id if topic_id is not None else -1,
            "user_id": user_id,
            "username": username or "",
            "message_id": message_id,
            "timestamp": datetime.now().isoformat(),
        }
        
        doc_id = f"msg_{chat_id}_{message_id}"
        
        self.add_fact(
            collection_name=collection_name,
            fact_text=text,
            metadata=metadata,
            doc_id=doc_id
        )
    
    def get_all_facts(self, collection_name: str) -> List[Dict]:
        """
        Получает все факты из коллекции.
        
        Args:
            collection_name: Название коллекции
            
        Returns:
            Список всех фактов
        """
        if not self.client:
            raise Exception("ChromaDB не инициализирована")
        
        collection = self.get_or_create_collection(collection_name)
        
        try:
            results = collection.get()
            
            facts = []
            for i in range(len(results['documents'])):
                fact = {
                    'id': results['ids'][i],
                    'text': results['documents'][i],
                    'metadata': results['metadatas'][i] if results['metadatas'] else {}
                }
                facts.append(fact)
            
            return facts
        except Exception as e:
            logger.error(f"Ошибка при получении всех фактов: {e}")
            return []
    
    def delete_fact(self, collection_name: str, doc_id: str):
        """
        Удаляет факт по ID.
        
        Args:
            collection_name: Название коллекции
            doc_id: ID документа для удаления
        """
        if not self.client:
            raise Exception("ChromaDB не инициализирована")
        
        collection = self.get_or_create_collection(collection_name)
        
        try:
            collection.delete(ids=[doc_id])
            logger.info(f"Факт {doc_id} удален из коллекции {collection_name}")
        except Exception as e:
            logger.error(f"Ошибка при удалении факта {doc_id}: {e}")
    
    # =========================================================================
    # Temporal Memory Methods (Shield & Economy v6.5)
    # =========================================================================
    
    def add_fact_with_timestamp(
        self,
        collection_name: str,
        fact_text: str,
        metadata: Dict,
        created_at: Optional[datetime] = None
    ) -> str:
        """
        Добавляет факт с обязательной временной меткой в ISO 8601.
        
        **Feature: shield-economy-v65**
        **Validates: Requirements 4.1**
        
        Args:
            collection_name: Название коллекции
            fact_text: Текст факта
            metadata: Метаданные (chat_id, user_id, etc.)
            created_at: Время создания (по умолчанию - текущее время)
            
        Returns:
            ID созданного документа
        """
        if created_at is None:
            created_at = datetime.now()
        
        # Ensure created_at is in ISO 8601 format
        metadata["created_at"] = created_at.isoformat()
        
        # Generate unique doc_id
        doc_id = f"fact_{int(datetime.now().timestamp() * 1000000)}"
        
        self.add_fact(
            collection_name=collection_name,
            fact_text=fact_text,
            metadata=metadata,
            doc_id=doc_id
        )
        
        return doc_id
    
    def search_facts_with_age(
        self,
        collection_name: str,
        query: str,
        chat_id: int,
        n_results: int = 5
    ) -> List[Dict]:
        """
        Ищет факты и добавляет информацию о возрасте каждого факта.
        
        **Feature: shield-economy-v65**
        **Validates: Requirements 4.3, 4.4**
        
        Args:
            collection_name: Название коллекции
            query: Запрос для поиска
            chat_id: ID чата для фильтрации
            n_results: Количество результатов
            
        Returns:
            Список фактов с полем age_days
        """
        facts = self.search_facts(
            collection_name=collection_name,
            query=query,
            n_results=n_results,
            where={"chat_id": chat_id}
        )
        
        now = datetime.now()
        
        for fact in facts:
            metadata = fact.get('metadata', {})
            created_at_str = metadata.get('created_at') or metadata.get('timestamp')
            
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str)
                    age_days = (now - created_at).days
                    fact['age_days'] = age_days
                except (ValueError, TypeError):
                    fact['age_days'] = -1  # Unknown age
            else:
                fact['age_days'] = -1
        
        # Sort by recency (newer facts first) for prioritization
        facts.sort(key=lambda f: f.get('age_days', 999))
        
        return facts
    
    # =========================================================================
    # Memory Management Methods (Shield & Economy v6.5)
    # =========================================================================
    
    def delete_all_chat_facts(
        self,
        collection_name: str,
        chat_id: int
    ) -> int:
        """
        Удаляет все факты для указанного чата.
        
        **Feature: shield-economy-v65**
        **Validates: Requirements 5.1, 5.4**
        
        Args:
            collection_name: Название коллекции
            chat_id: ID чата
            
        Returns:
            Количество удаленных фактов
        """
        if not self.client:
            raise Exception("ChromaDB не инициализирована")
        
        collection = self.get_or_create_collection(collection_name)
        
        try:
            # Get all facts for this chat
            results = collection.get(where={"chat_id": chat_id})
            
            if not results['ids']:
                return 0
            
            count = len(results['ids'])
            collection.delete(ids=results['ids'])
            
            logger.info(f"Удалено {count} фактов для чата {chat_id}")
            return count
            
        except Exception as e:
            logger.error(f"Ошибка при удалении фактов чата {chat_id}: {e}")
            return 0
    
    def delete_old_facts(
        self,
        collection_name: str,
        chat_id: int,
        older_than_days: int = 90
    ) -> int:
        """
        Удаляет факты старше указанного количества дней.
        
        **Feature: shield-economy-v65**
        **Validates: Requirements 5.2, 5.4**
        
        Args:
            collection_name: Название коллекции
            chat_id: ID чата
            older_than_days: Удалять факты старше этого количества дней
            
        Returns:
            Количество удаленных фактов
        """
        if not self.client:
            raise Exception("ChromaDB не инициализирована")
        
        collection = self.get_or_create_collection(collection_name)
        
        try:
            # Get all facts for this chat
            results = collection.get(where={"chat_id": chat_id})
            
            if not results['ids']:
                return 0
            
            now = datetime.now()
            ids_to_delete = []
            
            for i, doc_id in enumerate(results['ids']):
                metadata = results['metadatas'][i] if results['metadatas'] else {}
                created_at_str = metadata.get('created_at') or metadata.get('timestamp')
                
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                        age_days = (now - created_at).days
                        
                        if age_days >= older_than_days:
                            ids_to_delete.append(doc_id)
                    except (ValueError, TypeError):
                        pass  # Skip facts with invalid timestamps
            
            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
                logger.info(f"Удалено {len(ids_to_delete)} старых фактов для чата {chat_id}")
            
            return len(ids_to_delete)
            
        except Exception as e:
            logger.error(f"Ошибка при удалении старых фактов чата {chat_id}: {e}")
            return 0
    
    def delete_user_facts(
        self,
        collection_name: str,
        chat_id: int,
        user_id: int
    ) -> int:
        """
        Удаляет все факты указанного пользователя в чате.
        
        **Feature: shield-economy-v65**
        **Validates: Requirements 5.3, 5.4**
        
        Args:
            collection_name: Название коллекции
            chat_id: ID чата
            user_id: ID пользователя
            
        Returns:
            Количество удаленных фактов
        """
        if not self.client:
            raise Exception("ChromaDB не инициализирована")
        
        collection = self.get_or_create_collection(collection_name)
        
        try:
            # ChromaDB supports $and for multiple conditions
            results = collection.get(
                where={
                    "$and": [
                        {"chat_id": chat_id},
                        {"user_id": user_id}
                    ]
                }
            )
            
            if not results['ids']:
                return 0
            
            count = len(results['ids'])
            collection.delete(ids=results['ids'])
            
            logger.info(f"Удалено {count} фактов пользователя {user_id} в чате {chat_id}")
            return count
            
        except Exception as e:
            logger.error(f"Ошибка при удалении фактов пользователя {user_id}: {e}")
            return 0

    def delete_low_importance_facts(
        self,
        collection_name: str,
        chat_id: int,
        max_importance: int = 4
    ) -> int:
        """
        Удаляет факты с низким приоритетом (importance <= max_importance).
        
        Полезно для периодической очистки памяти от малозначимых фактов.
        
        Args:
            collection_name: Название коллекции
            chat_id: ID чата
            max_importance: Максимальный importance для удаления (включительно)
            
        Returns:
            Количество удаленных фактов
        """
        if not self.client:
            raise Exception("ChromaDB не инициализирована")
        
        collection = self.get_or_create_collection(collection_name)
        
        try:
            # Получаем все факты чата
            results = collection.get(where={"chat_id": chat_id})
            
            if not results['ids']:
                return 0
            
            ids_to_delete = []
            
            for i, doc_id in enumerate(results['ids']):
                metadata = results['metadatas'][i] if results['metadatas'] else {}
                importance = metadata.get('importance', 5)
                
                # Удаляем факты с низким приоритетом
                if isinstance(importance, (int, float)) and importance <= max_importance:
                    ids_to_delete.append(doc_id)
            
            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
                logger.info(f"Удалено {len(ids_to_delete)} низкоприоритетных фактов (importance <= {max_importance}) для чата {chat_id}")
            
            return len(ids_to_delete)
            
        except Exception as e:
            logger.error(f"Ошибка при удалении низкоприоритетных фактов чата {chat_id}: {e}")
            return 0

    def cleanup_memory(
        self,
        collection_name: str,
        chat_id: int,
        older_than_days: int = 90,
        low_importance_threshold: int = 4
    ) -> dict:
        """
        Комплексная очистка памяти: удаляет старые и низкоприоритетные факты.
        
        Рекомендуется запускать периодически (например, раз в неделю).
        
        Args:
            collection_name: Название коллекции
            chat_id: ID чата
            older_than_days: Удалять факты старше этого количества дней
            low_importance_threshold: Удалять факты с importance <= этого значения
            
        Returns:
            Словарь с количеством удалённых фактов по категориям
        """
        old_deleted = self.delete_old_facts(collection_name, chat_id, older_than_days)
        low_importance_deleted = self.delete_low_importance_facts(collection_name, chat_id, low_importance_threshold)
        
        total = old_deleted + low_importance_deleted
        if total > 0:
            logger.info(f"Очистка памяти чата {chat_id}: удалено {old_deleted} старых + {low_importance_deleted} низкоприоритетных = {total} фактов")
        
        return {
            "old_facts_deleted": old_deleted,
            "low_importance_deleted": low_importance_deleted,
            "total_deleted": total
        }


# Глобальный экземпляр векторной БД
vector_db = VectorDB()