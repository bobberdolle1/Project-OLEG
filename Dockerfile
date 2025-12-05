# Multi-stage build для оптимизации размера образа
FROM python:3.12-slim AS builder

WORKDIR /build

# Установка системных зависимостей для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Установка зависимостей Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt

# Финальный образ
FROM python:3.12-slim

LABEL maintainer="Oleg Bot Team"
LABEL description="Telegram bot with AI, moderation and game mechanics"

WORKDIR /app

# Установка runtime зависимостей
# ffmpeg - для Whisper (распознавание голоса) и yt-dlp (конвертация медиа)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Создание пользователя без привилегий
RUN useradd -m -u 1000 oleg && \
    mkdir -p /app/data /app/logs /app/data/chroma && \
    chown -R oleg:oleg /app

# Копирование установленных пакетов из builder
COPY --from=builder --chown=oleg:oleg /root/.local /home/oleg/.local

# Копирование кода приложения
COPY --chown=oleg:oleg app ./app
COPY --chown=oleg:oleg alembic.ini migrations ./

# Переключение на непривилегированного пользователя
USER oleg

# Настройка PATH для пользовательских пакетов
ENV PATH="/home/oleg/.local/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Запуск приложения
CMD ["python", "app/main.py"]
