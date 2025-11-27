import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """Конфигурация приложения из переменных окружения."""

    # Telegram
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    primary_chat_id: int | None = (
        int(os.getenv("PRIMARY_CHAT_ID"))
        if os.getenv("PRIMARY_CHAT_ID")
        else None
    )
    summary_topic_id: int = int(
        os.getenv("SUMMARY_TOPIC_ID", "1")
    )
    creative_topic_id: int = int(
        os.getenv("CREATIVE_TOPIC_ID", "1121")
    )

    # Ollama
    ollama_base_url: str = os.getenv(
        "OLLAMA_BASE_URL", "http://localhost:11434"
    )
    # Модель для основных задач (чтение/генерация текста)
    ollama_base_model: str = os.getenv(
        "OLLAMA_BASE_MODEL", "deepseek-v3.1:671b-cloud"
    )

    # Модель для визуального анализа (обработка изображений)
    ollama_vision_model: str = os.getenv(
        "OLLAMA_VISION_MODEL", "qwen3-vl:4b"
    )

    # Модель для работы с памятью и поиском (RAG)
    ollama_memory_model: str = os.getenv(
        "OLLAMA_MEMORY_MODEL", "glm-4.6:cloud"
    )

    # Модель по умолчанию (для обратной совместимости)
    @property
    def ollama_model(self) -> str:
        return self.ollama_base_model
    ollama_timeout: int = int(
        os.getenv("OLLAMA_TIMEOUT", "90")
    )
    ollama_cache_enabled: bool = os.getenv("OLLAMA_CACHE_ENABLED", "true").lower() == "true"
    ollama_cache_ttl: int = int(os.getenv("OLLAMA_CACHE_TTL", "3600")) # seconds
    ollama_cache_max_size: int = int(os.getenv("OLLAMA_CACHE_MAX_SIZE", "128"))
    toxicity_analysis_enabled: bool = os.getenv("TOXICITY_ANALYSIS_ENABLED", "true").lower() == "true"
    toxicity_threshold: int = int(os.getenv("TOXICITY_THRESHOLD", "75"))

    # ChromaDB (для RAG - "Мозг Олега")
    chromadb_persist_dir: str = os.getenv("CHROMADB_PERSIST_DIR", "./data/chroma")  # Директория сохранения ChromaDB
    chromadb_collection_name: str = os.getenv("CHROMADB_COLLECTION_NAME", "oleg_kb")  # Название коллекции для знаний

    # Векторное хранилище
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")  # Модель для эмбеддингов
    similarity_threshold: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))  # Порог схожести для RAG

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL", "sqlite+aiosqlite:///./data/oleg.db"
    )

    # Timezone
    timezone: str = os.getenv("TIMEZONE", "Europe/Moscow")

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: str = os.getenv("LOG_FILE", "logs/oleg.log")


settings = Settings()
