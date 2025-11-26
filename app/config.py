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
    ollama_model: str = os.getenv(
        "OLLAMA_MODEL", "deepseek-v3.1:671b-cloud"
    )
    ollama_timeout: int = int(
        os.getenv("OLLAMA_TIMEOUT", "90")
    )

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
