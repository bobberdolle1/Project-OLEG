"""Модуль для работы с векторной базой данных (RAG)."""

import logging
import warnings
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional, Tuple
import json
from datetime import datetime

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
        if name not in self.collections:
            try:
                # Пробуем получить существующую коллекцию
                self.collections[name] = self.client.get_collection(name)
            except:
                # Если коллекции нет, создаем новую
                self.collections[name] = self.client.create_collection(name)
        
        return self.collections[name]
    
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
    
    def search_facts(self, collection_name: str, query: str, n_results: int = 5, model: str = None) -> List[Dict]:
        """
        Ищет релевантные факты в коллекции.
        
        Args:
            collection_name: Название коллекции
            query: Запрос для поиска
            n_results: Количество результатов для возврата
            model: Модель для использования (не используется в ChromaDB, для совместимости)
            
        Returns:
            Список словарей с найденными фактами
        """
        if not self.client:
            raise Exception("ChromaDB не инициализирована")
        
        collection = self.get_or_create_collection(collection_name)
        
        try:
            results = collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
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


# Глобальный экземпляр векторной БД
vector_db = VectorDB()