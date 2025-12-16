# Multi-stage build для уменьшения размера
FROM python:3.13-slim as builder

WORKDIR /app

# Российское зеркало apt для ускорения
RUN sed -i 's|deb.debian.org|mirror.yandex.ru|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|deb.debian.org|mirror.yandex.ru|g' /etc/apt/sources.list 2>/dev/null || true

# Минимальные зависимости для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.prod.txt .

# Используем Яндекс зеркало PyPI + CPU-only torch
RUN pip install --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /wheels \
    --index-url https://pypi.yandex.ru/simple \
    --trusted-host pypi.yandex.ru \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    --extra-index-url https://pypi.org/simple \
    -r requirements.prod.txt

# Финальный образ
FROM python:3.13-slim

WORKDIR /app

# Российское зеркало apt
RUN sed -i 's|deb.debian.org|mirror.yandex.ru|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|deb.debian.org|mirror.yandex.ru|g' /etc/apt/sources.list 2>/dev/null || true

# Runtime зависимости (ffmpeg для аудио, espeak для офлайн TTS, шрифты для цитат)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Копируем wheels и устанавливаем
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Копируем код
COPY . .

RUN mkdir -p /app/data

CMD ["python", "-m", "app.main"]
