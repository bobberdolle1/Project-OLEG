<p align="center">
  <img src="https://img.shields.io/badge/🤖-ОЛЕГ-red?style=for-the-badge&labelColor=black" alt="Oleg Bot"/>
</p>

<h1 align="center">🔥 ОЛЕГ 5.0 🔥</h1>

<p align="center">
  <strong>Цифровой гигачад. Ветеран кремниевых войн. Местный решала.</strong>
</p>

<p align="center">
  <em>Теперь с единой личностью, PvP-играми и админ-панелью</em>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/></a>
  <a href="https://docs.aiogram.dev/"><img src="https://img.shields.io/badge/aiogram-3.x-2CA5E0?style=flat-square&logo=telegram&logoColor=white" alt="aiogram"/></a>
  <a href="https://ollama.ai/"><img src="https://img.shields.io/badge/Ollama-LLM-FF6F00?style=flat-square&logo=ollama&logoColor=white" alt="Ollama"/></a>
  <a href="https://github.com/openai/whisper"><img src="https://img.shields.io/badge/Whisper-STT-412991?style=flat-square&logo=openai&logoColor=white" alt="Whisper"/></a>
  <a href="https://redis.io/"><img src="https://img.shields.io/badge/Redis-Cache-DC382D?style=flat-square&logo=redis&logoColor=white" alt="Redis"/></a>
  <a href="https://www.trychroma.com/"><img src="https://img.shields.io/badge/ChromaDB-RAG-FF6B6B?style=flat-square" alt="ChromaDB"/></a>
  <a href="https://prometheus.io/"><img src="https://img.shields.io/badge/Prometheus-Metrics-E6522C?style=flat-square&logo=prometheus&logoColor=white" alt="Prometheus"/></a>
</p>

<p align="center">
  <a href="#-быстрый-старт">Быстрый старт</a> •
  <a href="#-возможности">Возможности</a> •
  <a href="#-архитектура">Архитектура</a> •
  <a href="#-roadmap">Roadmap</a>
</p>

---

## 💀 Что это?

**Олег** — это не просто бот. Это полноценный ИИ-ассистент с характером, который:

- 🧠 **Думает** — LLM на базе Ollama (DeepSeek, Qwen, GLM)
- 👁️ **Видит** — 2-step Vision Pipeline для единой личности
- 🎤 **Слышит** — распознаёт голосовые и видеосообщения (Whisper)
- 🧬 **Помнит** — RAG на ChromaDB с меж-топиковым восприятием
- 🎮 **Играет** — PvP с согласием, рулетка, монетка
- ⚔️ **Модерирует** — антиспам, антирейд, токсичность
- 🎛️ **Управляется** — админ-панель на inline-кнопках
- 📊 **Мониторится** — Prometheus + Grafana

---

## 🚀 Что нового в 5.0

```diff
+ 🧠 Think Tag Filter — автоматическое удаление <think>...</think> тегов из ответов LLM
+ �️ и2-Step Vision Pipeline — единая личность Олега для текста и изображений
+ 🌐 Cross-Topic Perception — бот видит сообщения из всех топиков супергруппы
+ 💬 Auto-Reply System — бот сам вклинивается в разговор (1-15% шанс)
+ 🎛️ Owner Dashboard — полная админ-панель на inline-кнопках в ЛС
+ ⚔️ PvP Games — вызовы с согласием, ставки, таймауты
+ 🎰 Russian Roulette — 1/6 шанс "выстрела", очки за выживание
+ 🪙 Coin Flip — ставки на орёл/решка с удвоением
+ 📊 Enhanced /ping — статус всех подсистем (Telegram, Ollama, Vision, RAG)
+ 📹 Video Notes — распознавание речи в кружочках
+ 📥 Media Download — авто-скачивание TikTok, Shorts, Reels
+ 🧪 Property-Based Testing — 46 тестов на Hypothesis
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

# Установи ffmpeg (для голосовых)
# Windows: choco install ffmpeg
# Linux: apt install ffmpeg
# Mac: brew install ffmpeg

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

### 🤖 ИИ и мультимодальность
- **Q&A с личностью** — циничный IT-генералист
- **2-Step Vision** — описание → комментарий в стиле Олега
- **Think Filter** — чистые ответы без внутренних рассуждений
- **Голосовые** — Whisper STT, ответ текстом
- **Видеосообщения** — транскрипция кружочков
- **RAG** — память на ChromaDB
- **Cross-Topic** — видит все топики супергруппы

</td>
<td width="50%">

### 🛡️ Модерация
- **Антиспам** — паттерны + ML
- **Антирейд** — автоматический мьют
- **Токсичность** — анализ и предупреждения
- **Черный список** — глобальный и локальный
- **Режимы** — Light / Normal / Toxic

</td>
</tr>
<tr>
<td>

### 🎮 Игры
- `/challenge @user` — PvP с согласием
- `/roulette` — русская рулетка (1/6)
- `/coinflip` — ставки на монетку
- `/grow` — увеличь пипису
- `/top` — рейтинг
- **Баланс** — очки для ставок

</td>
<td>

### 🎛️ Админ-панель
- `/admin` — меню в ЛС владельца
- **Moderation** — режим, антиспам, бан
- **Behavior** — авто-ответы, топики
- **Actions** — саммари, истории, рестарт
- **Statistics** — графики, токсики, токены

</td>
</tr>
</table>

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                      TELEGRAM API                            │
│         📝 Text  │  🖼️ Images  │  🎤 Voice  │  📹 Video      │
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
│  │  QnA │ Vision │ Voice │ Games │ Admin       │            │
│  └──────────────────────┬──────────────────────┘            │
└─────────────────────────┼───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      SERVICES                                │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐   │
│  │  Think    │ │  Vision   │ │ Auto-Reply│ │   Game    │   │
│  │  Filter   │ │ Pipeline  │ │  System   │ │  Engine   │   │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘   │
│  ┌─────┴─────┐ ┌─────┴─────┐ ┌─────┴─────┐ ┌─────┴─────┐   │
│  │  Ollama   │ │  Whisper  │ │ ChromaDB  │ │   Redis   │   │
│  │   LLM     │ │   STT     │ │   RAG     │ │   Cache   │   │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Стек технологий

| Компонент | Технология | Описание |
|-----------|------------|----------|
| **Runtime** | Python 3.10+ | Async everywhere |
| **Telegram** | aiogram 3.x | Современный async API |
| **LLM** | Ollama | DeepSeek, Qwen, GLM |
| **Vision** | Qwen-VL | 2-step pipeline |
| **STT** | Whisper | Распознавание речи |
| **Database** | PostgreSQL / SQLite | SQLAlchemy async |
| **Cache** | Redis | Rate limiting, sessions |
| **Vector DB** | ChromaDB | RAG память |
| **Metrics** | Prometheus | Мониторинг |
| **Dashboard** | Grafana | Визуализация |
| **Testing** | Hypothesis | Property-based tests |
| **Container** | Docker | Деплой |

---

## ⚙️ Конфигурация

```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_token
OWNER_ID=your_telegram_id

# Ollama — три модели для разных задач
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_BASE_MODEL=deepseek-v3.1:671b-cloud    # Текст
OLLAMA_VISION_MODEL=qwen3-vl:235b-cloud       # Изображения
OLLAMA_MEMORY_MODEL=glm-4.6:cloud             # RAG

# Голосовые сообщения
VOICE_RECOGNITION_ENABLED=true
WHISPER_MODEL=base  # tiny/base/small/medium/large

# Database
DATABASE_URL=sqlite+aiosqlite:///./data/oleg.db

# Redis
REDIS_ENABLED=true
REDIS_HOST=redis
```

Полный список в [.env.example](.env.example)

---

## 📊 Метрики

```bash
# Prometheus метрики
curl http://localhost:9090/metrics

# Health check
curl http://localhost:9090/health
```

**Доступные метрики:**
- `bot_messages_processed_total` — обработанные сообщения
- `bot_ollama_requests_total` — запросы к LLM
- `bot_ollama_request_duration_seconds` — время ответа
- `bot_voice_transcriptions_total` — распознанные голосовые
- `bot_vision_requests_total` — анализ изображений
- `bot_games_played_total` — сыгранные игры

---

## 🧪 Тестирование

```bash
# Все тесты
pytest

# Property-based тесты (46 тестов)
pytest tests/property/ -v

# С покрытием
pytest --cov=app --cov-report=html

# Только unit
pytest tests/unit/
```

---

## 📈 Roadmap

### ✅ Реализовано (v5.0)
- [x] Think Tag Filter — чистые ответы LLM
- [x] 2-Step Vision Pipeline — единая личность
- [x] Cross-Topic Perception — меж-топиковое восприятие
- [x] Auto-Reply System — вклинивание в разговор
- [x] Owner Dashboard — админ-панель на кнопках
- [x] PvP Games с согласием
- [x] Russian Roulette (1/6)
- [x] Coin Flip со ставками
- [x] Enhanced /ping — статус подсистем
- [x] Video Notes — кружочки
- [x] Media Download — TikTok, Shorts, Reels
- [x] Property-Based Testing — 46 тестов

### 🔜 В планах (v6.0)
- [ ] Webhook mode для высоких нагрузок
- [ ] Multi-language (i18n)
- [ ] Plugin system
- [ ] Голосовые ответы (TTS)
- [ ] Турниры и лиги

---

## 📚 Документация

| Документ | Описание |
|----------|----------|
| [QUICKSTART.md](QUICKSTART.md) | Быстрый старт за 5 минут |
| [INSTALLATION.md](INSTALLATION.md) | Подробная установка |
| [TESTING.md](TESTING.md) | Руководство по тестам |
| [CHANGELOG.md](CHANGELOG.md) | История изменений |

---

## 🤖 Личность Олега

```
Ты — Олег. Цифровой гигачад, ветеран кремниевых войн.

ХАРАКТЕР:
• Циничный IT-генералист — знаешь всё, отвечаешь на любые вопросы
• Язык — техжаргон + мат + интернет-сленг
• Адаптивность — не форсишь железо в разговорах о котиках

МУЛЬТИМОДАЛЬНОСТЬ:
• Видит скриншоты и комментирует в своём стиле
• Слышит голосовые и отвечает по делу
• Помнит контекст из всех топиков

Ты живешь в этом чате. Это твоя территория. Ты здесь закон.
```

---

## 🐳 Docker Compose

```yaml
services:
  oleg-bot:
    build: .
    ports:
      - "9090:9090"
    depends_on:
      - redis
      - chromadb
    
  redis:
    image: redis:7-alpine
    
  chromadb:
    image: ghcr.io/chroma-core/chroma:latest
```

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
