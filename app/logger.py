"""Система логирования для бота Олег."""

import logging
import logging.handlers
import pathlib
from app.config import settings


def setup_logging() -> None:
    """Инициализировать систему логирования."""
    # Создать директорию для логов
    log_dir = pathlib.Path(settings.log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # Основной логгер
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, settings.log_level))

    # Формат логов
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler для файла
    file_handler = logging.handlers.RotatingFileHandler(
        settings.log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Handler для консоли
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logging.info(
        f"Логирование инициализировано. "
        f"Уровень: {settings.log_level}, "
        f"Файл: {settings.log_file}"
    )


def get_logger(name: str) -> logging.Logger:
    """Получить логгер с указанным именем."""
    return logging.getLogger(name)
