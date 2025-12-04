# 🔧 Установка и настройка

## Предварительные требования

- Python 3.10+ (рекомендуется 3.12)
- Git
- Docker и Docker Compose (опционально)
- Ollama с установленными моделями (для локального запуска)

## Шаг 1: Клонирование репозитория

```bash
git clone <repository-url>
cd oleg-bot
```

## Шаг 2: Установка зависимостей

### Вариант A: Использование pip

```bash
# Создать виртуальное окружение
python -m venv venv

# Активировать (Windows)
venv\Scripts\activate

# Активировать (Linux/Mac)
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt
```

### Вариант B: Использование Poetry

```bash
# Установить Poetry
curl -sSL https://install.python-poetry.org | python3 -

# Установить зависимости
poetry install

# Активировать окружение
poetry shell
```

## Шаг 3: Настройка конфигурации

```bash
# Скопировать пример конфигурации
cp .env.example .env

# Отредактировать .env
nano .env  # или любой другой редактор
```

### Минимальная конфигурация .env:

```env
# Обязательные параметры
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
OWNER_ID=123456789

# Ollama (если запускаете локально)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_BASE_MODEL=deepseek-v3.1:671b-cloud
OLLAMA_VISION_MODEL=qwen3-vl:4b
OLLAMA_MEMORY_MODEL=glm-4.6:cloud

# База данных (SQLite по умолчанию)
DATABASE_URL=sqlite+aiosqlite:///./data/oleg.db

# Логирование
LOG_LEVEL=INFO
LOG_FILE=logs/oleg.log
```

## Шаг 4: Установка Ollama моделей

```bash
# Установить Ollama (если еще не установлен)
# https://ollama.ai/download

# Скачать модели
ollama pull deepseek-v3.1:671b-cloud
ollama pull qwen3-vl:4b
ollama pull glm-4.6:cloud

# Проверить установку
ollama list
```

## Шаг 5: Инициализация базы данных

```bash
# Создать директории
mkdir -p data logs

# Инициализировать БД
python -c "import asyncio; from app.database.session import init_db; asyncio.run(init_db())"

# Или использовать Makefile
make db-init
```

## Шаг 6: Запуск бота

### Локальный запуск

```bash
# Запустить бота
python -m app.main

# Или использовать Makefile
make run
```

### Docker запуск

```bash
# Development (SQLite)
docker-compose up -d

# Production (PostgreSQL + Redis + Monitoring)
docker-compose -f docker-compose.prod.yml up -d

# Просмотр логов
docker-compose logs -f oleg-bot
```

## Шаг 7: Проверка работы

1. Откройте Telegram
2. Найдите вашего бота
3. Отправьте команду `/start`
4. Отправьте команду `/help`

Если бот отвечает - установка прошла успешно! 🎉

## Дополнительная настройка

### Pre-commit hooks (для разработки)

```bash
# Установить pre-commit
pip install pre-commit

# Установить hooks
pre-commit install

# Запустить вручную
pre-commit run --all-files
```

### Миграции базы данных

```bash
# Создать миграцию
alembic revision --autogenerate -m "Initial migration"

# Применить миграции
alembic upgrade head

# Откатить миграцию
alembic downgrade -1
```

### Тестирование

```bash
# Запустить все тесты
pytest

# С покрытием
pytest --cov=app --cov-report=html

# Только unit тесты
pytest tests/unit/

# Только integration тесты
pytest tests/integration/
```

## Troubleshooting

### Ошибка: "No module named 'aiogram'"

```bash
# Убедитесь, что зависимости установлены
pip install -r requirements.txt
```

### Ошибка: "TELEGRAM_BOT_TOKEN must be set"

```bash
# Проверьте .env файл
cat .env | grep TELEGRAM_BOT_TOKEN

# Убедитесь, что токен не равен "YOUR_BOT_TOKEN_HERE"
```

### Ошибка: "Ollama connection failed"

```bash
# Проверьте, что Ollama запущена
curl http://localhost:11434/api/tags

# Если не запущена, запустите
ollama serve
```

### Ошибка: "Database locked"

```bash
# Остановите все процессы бота
pkill -f "python -m app.main"

# Удалите lock файл
rm data/oleg.db-journal

# Перезапустите бота
```

### Docker: "Cannot connect to Docker daemon"

```bash
# Запустите Docker Desktop (Windows/Mac)
# Или запустите Docker service (Linux)
sudo systemctl start docker
```

## Полезные команды

```bash
# Показать все доступные команды
make help

# Проверить проект
python check_project.py

# Форматировать код
make format

# Проверить код
make lint

# Запустить все проверки
make check

# Очистить кэш
make clean

# Обновить зависимости
make update-deps
```

## Следующие шаги

1. Прочитайте [QUICKSTART.md](QUICKSTART.md) для быстрого старта
2. Изучите [README.md](README.md) для полной документации
3. Посмотрите [IMPROVEMENTS.md](IMPROVEMENTS.md) для деталей улучшений
4. Проверьте [CHANGELOG.md](CHANGELOG.md) для истории изменений

## Поддержка

Если у вас возникли проблемы:

1. Проверьте логи: `tail -f logs/oleg.log`
2. Проверьте конфигурацию: `python check_project.py`
3. Проверьте документацию выше
4. Создайте issue в репозитории

---

**Удачи с ботом Олег! 🤖**
