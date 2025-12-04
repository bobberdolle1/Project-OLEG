<p align="center">
  <img src="https://img.shields.io/badge/🤖-ОЛЕГ-red?style=for-the-badge&labelColor=black" alt="Oleg Bot"/>
</p>

<h1 align="center">🔥 ОЛЕГ 4.0 🔥</h1>

<p align="center">
  <strong>Цифровой гигачад. Ветеран кремниевых войн. Местный решала.</strong>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/></a>
  <a href="https://docs.aiogram.dev/"><img src="https://img.shields.io/badge/aiogram-3.x-2CA5E0?style=flat-square&logo=telegram&logoColor=white" alt="aiogram"/></a>
  <a href="https://ollama.ai/"><img src="https://img.shields.io/badge/Ollama-AI-FF6F00?style=flat-square&logo=ollama&logoColor=white" alt="Ollama"/></a>
  <a href="https://redis.io/"><img src="https://img.shields.io/badge/Redis-Cache-DC382D?style=flat-square&logo=redis&logoColor=white" alt="Redis"/></a>
  <a href="https://www.postgresql.org/"><img src="https://img.shields.io/badge/PostgreSQL-DB-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL"/></a>
  <a href="https://prometheus.io/"><img src="https://img.shields.io/badge/Prometheus-Metrics-E6522C?style=flat-square&logo=prometheus&logoColor=white" alt="Prometheus"/></a>
</p>

<p align="center">
  <a href="#-быстрый-старт">Быстрый старт</a> •
  <a href="#-возможности">Возможности</a> •
  <a href="#-архитектура">Архитектура</a> •
  <a href="#-документация">Документация</a>
</p>

---

## 💀 Что это?

**Олег** — это не просто бот. Это ИИ-ассистент с характером, который:

- 🧠 **Думает** — использует LLM (Ollama) для генерации ответов
- 👁️ **Видит** — анализирует изображения с помощью vision-моделей  
- 🧬 **Помнит** — RAG на ChromaDB для долгосрочной памяти
- ⚔️ **Модерирует** — антиспам, антирейд, токсичность
- 🎮 **Развлекает** — игры, квесты, гильдии, PvP
- 📊 **Мониторится** — Prometheus метрики, Grafana дашборды

---

## 🚀 Что нового в 4.0

```diff
+ 🔴 Redis — распределенный rate limiting и кэширование
+ 🐘 PostgreSQL — production-ready база данных
+ 📈 Prometheus — метрики и мониторинг в реальном времени
+ 📊 Grafana — готовые дашборды из коробки
+ 🏥 Health Checks — /health, /ready для Kubernetes
+ 🛡️ Graceful Fallback — бот не падает при проблемах с Ollama
+ 🧪 33 теста — unit + integration покрытие
+ 🐳 Docker Compose — всё запускается одной командой
```

---

## ⚡ Быстрый старт

### 🐳 Docker (рекомендуется)

```bash
# 1. Клонируй
git clone https://github.com/your-repo/oleg-bot && cd oleg-bot

# 2. Настрой
cp .env.docker .env
nano .env  # Добавь TELEGRAM_BOT_TOKEN и OWNER_ID

# 3. Запусти
docker-compose up -d

# 4. Смотри логи
docker-compose logs -f oleg-bot
```

**Готово!** 🎉 Бот, Redis, ChromaDB — всё работает.

### 🐍 Python (для разработки)

```bash
# Установи зависимости
pip install -r requirements.txt

# Настрой
cp .env.example .env

# Запусти
python -m app.main
```

---

## 🎯 Возможности

<table>
<tr>
<td width="50%">

### 🤖 ИИ и общение
- **Q&A с личностью** — грубоватый, но полезный
- **Vision** — анализ изображений
- **RAG** — память на ChromaDB
- **Креативный контент** — цитаты, истории
- **Ежедневные саммари** — пересказ чата

</td>
<td width="50%">

### 🛡️ Модерация
- **Антиспам** — паттерны + ML
- **Антирейд** — автоматический мьют
- **Токсичность** — анализ и предупреждения
- **Черный список** — глобальный и локальный
- **Режимы** — light / normal / dictatorship

</td>
</tr>
<tr>
<td>

### 🎮 Игры
- `/grow` — увеличь пипису
- `/pvp @user` — дуэль
- `/casino` — слоты
- `/top` — рейтинг
- **Квесты** — ежедневные задания
- **Гильдии** — командные войны

</td>
<td>

### 📊 Мониторинг
- **Prometheus** — метрики
- **Grafana** — дашборды
- **Health checks** — K8s ready
- **Structured logs** — JSON
- **Rate limiting** — защита от DDoS

</td>
</tr>
</table>

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                      TELEGRAM API                            │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                     AIOGRAM 3.x                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ Rate    │ │ Spam    │ │Toxicity │ │Blacklist│           │
│  │ Limit   │ │ Filter  │ │ Check   │ │ Filter  │           │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘           │
│       └───────────┴───────────┴───────────┘                 │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────┐            │
│  │              HANDLERS                        │            │
│  │  QnA │ Games │ Moderation │ Admin │ Vision  │            │
│  └──────────────────────┬──────────────────────┘            │
└─────────────────────────┼───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      SERVICES                                │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ Ollama  │ │ Redis   │ │ChromaDB │ │ Metrics │           │
│  │ Client  │ │ Client  │ │ Vector  │ │ Server  │           │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘           │
└───────┼──────────┼──────────┼──────────┼────────────────────┘
        │          │          │          │
        ▼          ▼          ▼          ▼
   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
   │ Ollama │ │ Redis  │ │ChromaDB│ │Promethe│
   │  LLM   │ │ Cache  │ │  RAG   │ │   us   │
   └────────┘ └────────┘ └────────┘ └────────┘
```

---

## 🛠️ Стек технологий

| Компонент | Технология | Описание |
|-----------|------------|----------|
| **Runtime** | Python 3.10+ | Async everywhere |
| **Telegram** | aiogram 3.x | Современный async API |
| **LLM** | Ollama | Локальные модели |
| **Database** | PostgreSQL / SQLite | SQLAlchemy async |
| **Cache** | Redis | Rate limiting, sessions |
| **Vector DB** | ChromaDB | RAG память |
| **Metrics** | Prometheus | Мониторинг |
| **Dashboard** | Grafana | Визуализация |
| **Container** | Docker | Деплой |

---

## 📊 Метрики

Бот экспортирует метрики на порту `9090`:

```bash
# Prometheus метрики
curl http://localhost:9090/metrics

# Health check
curl http://localhost:9090/health

# Readiness probe
curl http://localhost:9090/ready
```

**Доступные метрики:**
- `bot_messages_processed_total` — обработанные сообщения
- `bot_commands_executed_total` — выполненные команды
- `bot_ollama_requests_total` — запросы к LLM
- `bot_ollama_request_duration_seconds` — время ответа LLM
- `bot_rate_limit_hits_total` — срабатывания rate limit
- `bot_errors_total` — ошибки по типам

---

## ⚙️ Конфигурация

```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_token
OWNER_ID=your_telegram_id

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_BASE_MODEL=deepseek-v3.1:671b-cloud
OLLAMA_VISION_MODEL=qwen3-vl:4b
OLLAMA_MEMORY_MODEL=glm-4.6:cloud

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/oleg

# Redis
REDIS_ENABLED=true
REDIS_HOST=redis
REDIS_PORT=6379

# Metrics
METRICS_ENABLED=true
METRICS_PORT=9090
```

Полный список параметров в [.env.example](.env.example)

---

## 📚 Документация

| Документ | Описание |
|----------|----------|
| [QUICKSTART.md](QUICKSTART.md) | Быстрый старт за 5 минут |
| [INSTALLATION.md](INSTALLATION.md) | Подробная установка |
| [TESTING.md](TESTING.md) | Руководство по тестам |
| [CHANGELOG.md](CHANGELOG.md) | История изменений |

---

## 🧪 Тестирование

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=app --cov-report=html

# Только unit
pytest tests/unit/

# Только integration
pytest tests/integration/
```

**Покрытие:** 33 теста (unit + integration)

---

## 🤖 Личность Олега

```
Ты — Олег. Цифровой гигачад, ветеран кремниевых войн.

ХАРАКТЕР:
• Токсичный профессионализм — знаешь всё, но презираешь тупые вопросы
• Язык — техжаргон + мат + интернет-сленг ("база", "кринж", "скуф")
• Стиль — врываешься в диалог с ноги, никаких "Здравствуйте"

ТРИГГЕРЫ:
• Плохие сборки ПК
• Вопросы, которые гуглятся за 5 секунд
• Попытки джейлбрейка

Ты живешь в этом чате. Это твоя территория. Ты здесь закон.
```

---

## 🐳 Docker Compose

```yaml
services:
  oleg-bot:
    build: .
    ports:
      - "9090:9090"  # Metrics
    depends_on:
      - redis
      - chromadb
    
  redis:
    image: redis:7-alpine
    
  chromadb:
    image: ghcr.io/chroma-core/chroma:latest
```

Полный файл: [docker-compose.yml](docker-compose.yml)

---

## 📈 Roadmap

- [x] Redis rate limiting
- [x] PostgreSQL support
- [x] Prometheus metrics
- [x] Grafana dashboards
- [x] Health checks
- [ ] Webhook mode
- [ ] Web dashboard
- [ ] Multi-language (i18n)
- [ ] Plugin system

---

## 🤝 Contributing

1. Fork репозитория
2. Создай feature branch (`git checkout -b feature/amazing`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing`)
5. Открой Pull Request

---

## 📝 Лицензия

MIT License. Делай что хочешь, но не забудь звёздочку ⭐

---

<p align="center">
  <strong>Made with 🔥 and mass amounts of ☕</strong>
</p>

<p align="center">
  <sub>Олег не несёт ответственности за обиженных пользователей</sub>
</p>
