# Multi-stage build для оптимизации размера образа
FROM python:3.11-slim as builder

WORKDIR /build

# Установка Poetry
RUN pip install --no-cache-dir poetry==1.7.1

# Копирование зависимостей
COPY pyproject.toml poetry.lock* ./

# Создание виртуального окружения и установка зависимостей
RUN python -m venv /opt/venv && \
    . /opt/venv/bin/activate && \
    poetry install --no-root --only main

# Финальный образ
FROM python:3.11-slim

WORKDIR /app

# Создание пользователя без привилегий
RUN useradd -m -u 1000 oleg

# Копирование виртуального окружения из builder
COPY --from=builder --chown=oleg:oleg /opt/venv /opt/venv

# Копирование кода приложения
COPY --chown=oleg:oleg . .

# Создание директории для логов
RUN mkdir -p logs && chown oleg:oleg logs

# Переключение на непривилегированного пользователя
USER oleg

# Активация виртуального окружения
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Запуск приложения
CMD ["python", "-m", "app.main"]
