# 🔧 Установка — Олег 4.0

> Подробное руководство по установке и настройке

---

## 📋 Требования

| Компонент | Версия | Обязательно |
|-----------|--------|-------------|
| Python | 3.10 - 3.13 | ✅ |
| Docker | 20.10+ | Рекомендуется |
| Ollama | Latest | ✅ |
| Redis | 7.x | Для продакшена |
| PostgreSQL | 15+ | Для продакшена |

---

## 🐳 Вариант 1: Docker (рекомендуется)

### 1. Клонирование

```bash
git clone https://github.com/your-repo/oleg-bot
cd oleg-bot
```

### 2. Конфигурация

```bash
cp .env.docker .env
nano .env
```

**Минимум:**
```bash
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
OWNER_ID=123456789
```

### 3. Запуск

```bash
# Development
docker-compose up -d

# Production (с PostgreSQL + мониторинг)
docker-compose -f docker-compose.prod.yml up -d
```

### 4. Проверка

```bash
docker-compose logs -f oleg-bot
```

---

## 🐍 Вариант 2: Python

### 1. Виртуальное окружение

```bash
# Создать
python -m venv venv

# Активировать (Windows)
venv\Scripts\activate

# Активировать (Linux/Mac)
source venv/bin/activate
```

### 2. Зависимости

```bash
pip install -r requirements.txt
```

### 3. Конфигурация

```bash
cp .env.example .env
nano .env
```

### 4. Ollama модели

```bash
ollama pull deepseek-v3.1:671b-cloud
ollama pull qwen3-vl:4b
ollama pull glm-4.6:cloud
```

### 5. Запуск

```bash
python -m app.main
```

---

## ⚙️ Конфигурация

### Development (.env)

```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_token
OWNER_ID=your_id

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_BASE_MODEL=deepseek-v3.1:671b-cloud

# Database (SQLite)
DATABASE_URL=sqlite+aiosqlite:///./data/oleg.db

# Redis (отключен)
REDIS_ENABLED=false

# Metrics (отключены)
METRICS_ENABLED=false

# Logging
LOG_LEVEL=DEBUG
```

### Production (.env)

```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_production_token
OWNER_ID=your_id

# Ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_BASE_MODEL=deepseek-v3.1:671b-cloud

# Database (PostgreSQL)
DATABASE_URL=postgresql+asyncpg://oleg:password@postgres:5432/oleg_db

# Redis (включен)
REDIS_ENABLED=true
REDIS_HOST=redis
REDIS_PORT=6379

# Metrics (включены)
METRICS_ENABLED=true
METRICS_PORT=9090

# Logging
LOG_LEVEL=INFO
```

---

## 🗄️ База данных

### SQLite (development)

```bash
# Автоматически создается при запуске
mkdir -p data
python -m app.main
```

### PostgreSQL (production)

```bash
# 1. Раскомментируй в docker-compose.yml
# 2. Обнови DATABASE_URL в .env
# 3. Запусти миграции
alembic upgrade head
```

### Миграции

```bash
# Создать миграцию
alembic revision --autogenerate -m "Add feature"

# Применить
alembic upgrade head

# Откатить
alembic downgrade -1
```

---

## 📊 Мониторинг

### Метрики

```bash
# Включи в .env
METRICS_ENABLED=true
METRICS_PORT=9090

# Проверь
curl http://localhost:9090/metrics
curl http://localhost:9090/health
```

### Grafana

```bash
# Раскомментируй в docker-compose.yml
# grafana:
#   image: grafana/grafana:latest
#   ports:
#     - "3000:3000"

# Открой http://localhost:3000
# Login: admin / admin
```

---

## 🧪 Тестирование

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=app --cov-report=html

# Только unit
pytest tests/unit/
```

---

## 🔧 Разработка

### Pre-commit hooks

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

### Форматирование

```bash
black app/
isort app/
```

### Линтинг

```bash
flake8 app/
mypy app/
```

---

## 🐛 Troubleshooting

### "No module named 'aiogram'"

```bash
pip install -r requirements.txt
```

### "TELEGRAM_BOT_TOKEN must be set"

```bash
# Проверь .env
cat .env | grep TELEGRAM_BOT_TOKEN
```

### "Ollama connection failed"

```bash
# Проверь Ollama
curl http://localhost:11434/api/tags

# Запусти если не работает
ollama serve
```

### "Database locked"

```bash
# Останови бота
pkill -f "python -m app.main"

# Удали lock
rm data/oleg.db-journal
```

### Docker: "Cannot connect"

```bash
# Linux
sudo systemctl start docker

# Windows/Mac
# Запусти Docker Desktop
```

---

## 📁 Структура проекта

```
oleg-bot/
├── app/
│   ├── handlers/          # Команды
│   ├── services/          # Бизнес-логика
│   │   ├── redis_client.py
│   │   ├── metrics.py
│   │   └── ollama_client.py
│   ├── middleware/        # Rate limit, spam
│   ├── database/          # Модели
│   └── main.py
├── tests/
│   ├── unit/
│   └── integration/
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/
├── migrations/            # Alembic
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## 📚 Следующие шаги

1. [QUICKSTART.md](QUICKSTART.md) — Быстрый старт
2. [WHATS_NEW_V4.md](WHATS_NEW_V4.md) — Что нового в 4.0
3. [TESTING.md](TESTING.md) — Тестирование
4. [CHANGELOG.md](CHANGELOG.md) — История изменений

---

## 💬 Поддержка

1. Проверь логи: `docker-compose logs -f`
2. Проверь `.env`
3. Создай issue в репозитории

---

**Удачи с Олегом! 🤖**
