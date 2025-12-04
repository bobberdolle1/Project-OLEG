# ⚡ Быстрый старт — Олег 4.0

> Запусти бота за 2 минуты

---

## 🐳 Docker (рекомендуется)

```bash
# 1. Клонируй
git clone https://github.com/your-repo/oleg-bot && cd oleg-bot

# 2. Настрой
cp .env.docker .env
nano .env  # Добавь TELEGRAM_BOT_TOKEN и OWNER_ID

# 3. Запусти
docker-compose up -d

# 4. Проверь
docker-compose logs -f oleg-bot
```

**Готово!** 🎉

---

## 🐍 Python (для разработки)

```bash
# 1. Установи зависимости
pip install -r requirements.txt

# 2. Настрой
cp .env.example .env
nano .env

# 3. Запусти
python -m app.main
```

---

## ⚙️ Минимальная конфигурация

```bash
# .env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...  # От @BotFather
OWNER_ID=123456789                     # Твой Telegram ID
```

---

## ✅ Проверка

Отправь боту в Telegram:
```
/start
/help
```

---

## 📊 Метрики (опционально)

```bash
# Включи в .env
METRICS_ENABLED=true

# Проверь
curl http://localhost:9090/health
curl http://localhost:9090/metrics
```

---

## 🔧 Полезные команды

```bash
# Логи
docker-compose logs -f oleg-bot

# Перезапуск
docker-compose restart oleg-bot

# Остановка
docker-compose down

# Обновление
git pull && docker-compose up -d --build
```

---

## 🧪 Тесты

```bash
pytest                    # Все тесты
pytest tests/unit/        # Только unit
pytest --cov=app          # С покрытием
```

---

## 🐛 Проблемы?

### Бот не запускается
```bash
docker-compose logs oleg-bot
```

### Ollama не отвечает
```bash
curl http://localhost:11434/api/tags
ollama pull deepseek-v3.1:671b-cloud
```

### Ошибки БД
```bash
docker-compose down -v
docker-compose up -d
```

---

## 📚 Документация

| Документ | Описание |
|----------|----------|
| [README.md](README.md) | Полная документация |
| [WHATS_NEW_V4.md](WHATS_NEW_V4.md) | Что нового в 4.0 |
| [TESTING.md](TESTING.md) | Руководство по тестам |
| [CHANGELOG.md](CHANGELOG.md) | История изменений |

---

## 🏗️ Структура проекта

```
oleg-bot/
├── app/
│   ├── handlers/      # Команды бота
│   ├── services/      # Бизнес-логика
│   ├── middleware/    # Rate limit, spam filter
│   ├── database/      # Модели SQLAlchemy
│   └── main.py        # Точка входа
├── tests/             # Тесты
├── monitoring/        # Prometheus, Grafana
├── docker-compose.yml # Docker конфиг
└── .env.example       # Пример конфигурации
```

---

**Вопросы?** Создай issue в репозитории.
