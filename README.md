<p align="center">
  <img src="https://img.shields.io/badge/🤖-ОЛЕГ-red?style=for-the-badge&labelColor=black" alt="Oleg Bot"/>
</p>

<h1 align="center">🛡️ ОЛЕГ 6.5 — Shield & Economy Update 🛡️</h1>

<p align="center">
  <strong>Цифровой гигачад. Ветеран кремниевых войн. Местный решала.</strong>
</p>

<p align="center">
  <em>Теперь с системой экономии токенов, умной защитой от рейдов и профилями защиты</em>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/></a>
  <a href="https://docs.aiogram.dev/"><img src="https://img.shields.io/badge/aiogram-3.x-2CA5E0?style=flat-square&logo=telegram&logoColor=white" alt="aiogram"/></a>
  <a href="https://ollama.ai/"><img src="https://img.shields.io/badge/Ollama-LLM-FF6F00?style=flat-square&logo=ollama&logoColor=white" alt="Ollama"/></a>
  <a href="https://github.com/openai/whisper"><img src="https://img.shields.io/badge/Whisper-STT-412991?style=flat-square&logo=openai&logoColor=white" alt="Whisper"/></a>
  <a href="https://redis.io/"><img src="https://img.shields.io/badge/Redis-Cache-DC382D?style=flat-square&logo=redis&logoColor=white" alt="Redis"/></a>
  <a href="https://www.trychroma.com/"><img src="https://img.shields.io/badge/ChromaDB-RAG-FF6B6B?style=flat-square" alt="ChromaDB"/></a>
  <a href="https://prometheus.io/"><img src="https://img.shields.io/badge/Prometheus-Metrics-E6522C?style=flat-square&logo=prometheus&logoColor=white" alt="Prometheus"/></a>
  <a href="https://arq-docs.helpmanual.io/"><img src="https://img.shields.io/badge/Arq-Worker-00ADD8?style=flat-square" alt="Arq"/></a>
</p>

<p align="center">
  <a href="#-быстрый-старт">Быстрый старт</a> •
  <a href="#-возможности">Возможности</a> •
  <a href="#-что-нового-в-60">Что нового</a> •
  <a href="#-архитектура">Архитектура</a> •
  <a href="#-безопасность">Безопасность</a> •
  <a href="#-админ-панель">Админ-панель</a>
</p>

---

## 💀 Что это?

**Олег** — это не просто бот. Это полноценный ИИ-ассистент с характером, который:

- 🧠 **Думает** — LLM на базе Ollama (DeepSeek, Qwen, GLM)
- 👁️ **Видит** — 2-step Vision Pipeline для единой личности
- 🎤 **Слышит** — распознаёт голосовые и видеосообщения (Whisper)
- 🔊 **Говорит** — TTS голосовые ответы в стиле Олега
- 🧬 **Помнит** — RAG на ChromaDB с меж-топиковым восприятием
- 🎮 **Играет** — PvP с согласием, рулетка, турниры, лиги
- 🏰 **Защищает** — система "Цитадель" с DEFCON уровнями
- ⚔️ **Модерирует** — нейро-модерация с ИИ-анализом токсичности
- 🎛️ **Управляется** — админ-панель для владельцев чатов в ЛС
- 📊 **Мониторится** — Prometheus + Grafana

---

## 🚀 Что нового в 6.5

### 🛡️ Shield & Economy Update — Главные фичи

```diff
+ ⚡ Система энергии — персональный cooldown для экономии токенов LLM
+ 🌐 Глобальный rate limit — лимит запросов на чат (20/мин по умолчанию)
+ ⏳ Статус-менеджер — реакции вместо спама уведомлений
+ 🧠 RAG с временной памятью — приоритет свежих фактов
+ 🗑️ Управление памятью — забыть всё/старое/юзера
+ 🚨 Panic Mode — автозащита при 10+ вступлениях за 10 сек
+ 🔐 Проверка прав — бот не угрожает без полномочий
+ 🕵️ Нейро-спам фильтр — детекция продаж, крипты, вакансий
+ 👤 Сканер новичков — проверка аватара, имени, Premium
+ 🔇 Silent Ban — тихое удаление сообщений подозрительных
+ 🛡️ Профили защиты — Стандарт/Строгий/Бункер/Кастом
+ 📊 30 property-based тестов — полное покрытие новых фич
```

### 🏰 Fortress Update (v6.0) — Предыдущие фичи

```diff
+ 🏰 Система "Цитадель" — многоуровневая защита с DEFCON 1/2/3
+ 🧠 Нейро-Модерация — ИИ-анализ токсичности вместо ключевых слов
+ 🎬 GIF-Патруль — автоматический анализ GIF на запрещённый контент
+ ⭐ Репутационная система — Social Credit с автоматическими санкциями
+ 🔊 TTS — голосовые ответы Олега (/say, авто-озвучка 0.1%)
+ 📝 Умный пересказ — /tl;dr и /summary с озвучкой
+ 🖼️ Улучшенный цитатник — градиенты, цепочки, roast-режим
+ 📦 Стикерпаки — автоматическое управление и ротация
+ 🏆 Золотой Фонд — лучшие цитаты с RAG-поиском
+ 🎖️ Турниры — ежедневные, еженедельные, Grand Cup
+ 🏅 Лиги и ELO — ранговая система для игроков
+ 💬 Живые уведомления — анимированные статусы обработки
+ 📅 Дейлики — утренние саммари и вечерние цитаты
+ 🔔 Уведомления владельцу — рейды, баны, токсичность
+ 🎛️ Админ-панель в ЛС — полное управление чатом
+ ⚙️ Worker Process — Arq для тяжёлых задач
+ 🔒 Усиленная безопасность — HMAC, rate limiting, санитизация
```

---

## 🏰 Система DEFCON

Многоуровневая защита чата с автоматической активацией при угрозах.

| Уровень | Название | Защита |
|---------|----------|--------|
| 🟢 **DEFCON 1** | Мирное время | Антиспам ссылок, базовая капча |
| 🟡 **DEFCON 2** | Строгий режим | + Фильтр мата, лимит стикеров (3), блок форвардов |
| 🔴 **DEFCON 3** | Военное положение | + Полные ограничения для новичков, Hard Captcha |

**Автоматическая активация:** При 5+ вступлениях за 60 секунд включается Raid Mode (DEFCON 3 на 15 минут).

**Команда:** `олег defcon [1-3]` — изменить уровень защиты (только админы)

---

## 📋 Новые команды

| Команда | Описание |
|---------|----------|
| `олег defcon [1-3]` | Изменить уровень защиты чата |
| `/say <текст>` | Озвучить текст голосом Олега |
| `/tl;dr` | Краткий пересказ сообщения (ответом) |
| `/summary` | Пересказ сообщения или статьи по ссылке |
| `/q` | Создать цитату из сообщения |
| `/q [N]` | Создать цепочку из N сообщений (макс. 10) |
| `/q *` | Цитата с roast-комментарием от Олега |
| `/qs` | Добавить цитату в стикерпак чата |
| `/qd` | Удалить стикер из пака (админ) |
| `/tournament` | Показать текущие турнирные таблицы |
| `/советы` или `/tips` | Получить советы по управлению чатом |
| `/admin` | Админ-панель (только в ЛС бота) |

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

**Готово!** 🎉 Бот, Redis, ChromaDB, Worker — всё работает.

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

# Запусти бота
python -m app.main

# Запусти worker (в отдельном терминале)
python -m app.worker
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
- **TTS** — голосовые ответы Олега
- **Видеосообщения** — транскрипция кружочков
- **RAG** — память на ChromaDB
- **Cross-Topic** — видит все топики супергруппы

</td>
<td width="50%">

### 🏰 Защита "Цитадель"
- **DEFCON 1/2/3** — уровни защиты
- **Нейро-модерация** — ИИ-анализ токсичности
- **GIF-Патруль** — анализ анимаций
- **Raid Mode** — автозащита от набегов
- **Репутация** — Social Credit система
- **Hard Captcha** — ИИ-загадки для новичков
- **Rate Limiting** — защита от спама

</td>
</tr>
<tr>
<td>

### 🎮 Игры и турниры
- `/challenge @user` — PvP с согласием
- `/roulette` — русская рулетка (1/6)
- `/coinflip` — ставки на монетку
- `/grow` — увеличь пипису
- `/top` — рейтинг
- `/tournament` — турнирные таблицы
- **Лиги** — Scrap → Silicon → Quantum → Elite
- **ELO** — рейтинговая система

</td>
<td>

### 🎛️ Админ-панель (в ЛС)
- `/admin` — меню в ЛС владельца
- **Protection** — DEFCON, антиспам, фильтры
- **Notifications** — рейды, баны, токсичность
- **Games** — включение/выключение игр
- **Dailies** — утренние/вечерние сообщения
- **Quotes** — темы, Золотой Фонд, стикеры
- **Advanced** — пороги, длительности, слова

</td>
</tr>
<tr>
<td>

### 🖼️ Цитатник
- `/q` — создать цитату
- `/q [N]` — цепочка сообщений
- `/q *` — с roast-комментарием
- `/qs` — добавить в стикерпак
- **Градиенты** — красивые фоны
- **Золотой Фонд** — лучшие цитаты
- **RAG-поиск** — релевантные цитаты

</td>
<td>

### 📅 Дейлики и уведомления
- **09:00** — утренний дайджест
- **21:00** — цитата дня + статистика
- **Raid Alert** — уведомление о набеге
- **Ban Notification** — уведомление о бане
- **Toxicity Warning** — рост токсичности
- `/советы` — советы по управлению

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
│  │ Rate    │ │ DEFCON  │ │Toxicity │ │Blacklist│           │
│  │ Limit   │ │ Filter  │ │ Filter  │ │ Filter  │           │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘           │
│       └───────────┴───────────┴───────────┘                 │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────┐            │
│  │              HANDLERS                        │            │
│  │  QnA │ Vision │ Voice │ Games │ Admin │ ... │            │
│  └──────────────────────┬──────────────────────┘            │
└─────────────────────────┼───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      SERVICES                                │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐   │
│  │ Citadel   │ │ Reputation│ │   TTS     │ │ Tournaments│   │
│  │ (DEFCON)  │ │  System   │ │  Service  │ │  & Leagues │   │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘   │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐   │
│  │  Quote    │ │  Golden   │ │  Alive    │ │  Dailies  │   │
│  │ Generator │ │   Fund    │ │    UI     │ │  Service  │   │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘   │
└─────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   WORKER PROCESS (Arq)                       │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐   │
│  │    TTS    │ │   Quote   │ │    GIF    │ │ Summarizer│   │
│  │   Task    │ │  Render   │ │  Analysis │ │   Task    │   │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘   │
└─────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      DATA LAYER                              │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐                 │
│  │PostgreSQL │ │   Redis   │ │ ChromaDB  │                 │
│  │  / SQLite │ │   Queue   │ │    RAG    │                 │
│  └───────────┘ └───────────┘ └───────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎛️ Админ-панель для владельцев чатов

Полное управление ботом через личные сообщения. Отправьте `/admin` боту в ЛС.

### Структура меню

```
📋 Выберите чат для настройки
    └── [Список ваших чатов]
        │
        ├── 🛡️ Protection (Защита)
        │   ├── DEFCON Level [1] [2] [3]
        │   ├── Anti-Spam [ON/OFF]
        │   ├── Profanity Filter [ON/OFF]
        │   ├── Sticker Limit [ON/OFF]
        │   └── Forward Block [ON/OFF]
        │
        ├── 🔔 Notifications (Уведомления)
        │   ├── Raid Alerts [ON/OFF]
        │   ├── Ban Notifications [ON/OFF]
        │   ├── Toxicity Warnings [ON/OFF]
        │   └── Daily Tips [ON/OFF]
        │
        ├── 🎮 Games (Игры)
        │   ├── /grow [ON/OFF]
        │   ├── /pvp [ON/OFF]
        │   ├── /roulette [ON/OFF]
        │   └── Tournaments [ON/OFF]
        │
        ├── 📅 Dailies (Ежедневные)
        │   ├── Morning Summary [ON/OFF]
        │   ├── Evening Quote [ON/OFF]
        │   └── Daily Stats [ON/OFF]
        │
        ├── 🖼️ Quotes (Цитаты)
        │   ├── Theme [Dark/Light/Auto]
        │   ├── Golden Fund [ON/OFF]
        │   └── Sticker Pack [Manage]
        │
        └── ⚙️ Advanced (Расширенные)
            ├── Toxicity Threshold [0-100]
            ├── Mute Duration [minutes]
            └── Custom Banned Words [Edit]
```

**Важно:** Админ-панель доступна только в личных сообщениях с ботом. При использовании `/admin` в группе бот ответит: "Админка доступна только в личных сообщениях. Напиши мне в ЛС."

---


## 🔒 Безопасность

### Встроенные механизмы защиты

| Механизм | Описание |
|----------|----------|
| **Input Sanitization** | Очистка всех входных данных от SQL-инъекций, XSS, command injection |
| **Rate Limiting** | Ограничение 30 сообщений/минуту, блокировка на 5 минут при превышении |
| **HMAC Callbacks** | Подпись callback-данных для предотвращения подделки |
| **File Validation** | Проверка типа и размера файлов (макс. 20MB) |
| **Real-time Admin Check** | Проверка прав админа через Telegram API в реальном времени |
| **Error Sanitization** | Скрытие внутренних деталей ошибок от пользователей |
| **Abuse Detection** | Автоматическое обнаружение паттернов злоупотребления |
| **Security Blacklist** | Временная блокировка подозрительных пользователей |

### Рекомендации по деплою

1. **Используйте переменные окружения** для всех секретов (токены, ключи)
2. **Включите DEFCON 2** по умолчанию для новых чатов
3. **Настройте уведомления** владельцу о рейдах и банах
4. **Регулярно проверяйте** логи на подозрительную активность
5. **Используйте Docker** для изоляции
6. **Настройте firewall** — откройте только необходимые порты

### Система DEFCON для защиты чата

Система "Цитадель" предоставляет три уровня защиты:

- **DEFCON 1** — для спокойных чатов с доверенными участниками
- **DEFCON 2** — рекомендуется для большинства публичных чатов
- **DEFCON 3** — для чатов под атакой или с высоким риском

При обнаружении массового вступления (5+ за 60 сек) автоматически активируется Raid Mode.

---

## 🛠️ Стек технологий

| Компонент | Технология | Описание |
|-----------|------------|----------|
| **Runtime** | Python 3.10+ | Async everywhere |
| **Telegram** | aiogram 3.x | Современный async API |
| **LLM** | Ollama | DeepSeek, Qwen, GLM |
| **Vision** | Qwen-VL | 2-step pipeline |
| **STT** | Whisper | Распознавание речи |
| **TTS** | Edge-TTS / Silero | Синтез речи |
| **Database** | PostgreSQL / SQLite | SQLAlchemy async |
| **Cache** | Redis | Rate limiting, sessions, queue |
| **Vector DB** | ChromaDB | RAG память |
| **Worker** | Arq | Async task queue |
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

# TTS
TTS_ENABLED=true
TTS_VOICE=ru-RU-DmitryNeural

# Database
DATABASE_URL=sqlite+aiosqlite:///./data/oleg.db

# Redis (обязательно для Worker)
REDIS_ENABLED=true
REDIS_HOST=redis
REDIS_PORT=6379

# Security
HMAC_SECRET_KEY=your_secret_key_here
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
- `bot_tts_generations_total` — сгенерированные голосовые
- `bot_vision_requests_total` — анализ изображений
- `bot_games_played_total` — сыгранные игры
- `bot_toxicity_incidents_total` — инциденты токсичности
- `bot_raid_activations_total` — активации Raid Mode

---

## 🧪 Тестирование

```bash
# Все тесты
pytest

# Property-based тесты
pytest tests/property/ -v

# С покрытием
pytest --cov=app --cov-report=html

# Только unit
pytest tests/unit/

# Только integration
pytest tests/integration/
```

---

## 📈 Roadmap

### ✅ Реализовано (v6.5 Shield & Economy)
- [x] Система энергии — персональный cooldown (3 запроса, 60 сек восстановление)
- [x] Глобальный rate limit — лимит на чат с настройкой через админку
- [x] Статус-менеджер — ⏳ реакции вместо спама уведомлений
- [x] RAG с временной памятью — ISO 8601 timestamps, приоритет свежих фактов
- [x] Управление памятью — забыть всё/старое (90 дней)/юзера
- [x] Panic Mode — автозащита при массовых вступлениях/флуде
- [x] Проверка прав бота — тихий репорт админам при отсутствии прав
- [x] Нейро-спам фильтр — детекция продаж, крипты, вакансий, коллабов
- [x] Сканер новичков — проверка аватара, имени, Premium статуса
- [x] Silent Ban — тихое удаление сообщений с captcha для разбана
- [x] Профили защиты — Стандарт/Строгий/Бункер/Кастом
- [x] 30 property-based тестов — полное покрытие Hypothesis

### ✅ Реализовано (v6.0 Fortress Update)
- [x] Система "Цитадель" — DEFCON 1/2/3
- [x] Нейро-модерация — ИИ-анализ токсичности
- [x] GIF-Патруль — анализ анимаций
- [x] Репутационная система — Social Credit
- [x] TTS — голосовые ответы
- [x] Умный пересказ — /tl;dr, /summary
- [x] Улучшенный цитатник — градиенты, цепочки
- [x] Стикерпаки — автоуправление
- [x] Золотой Фонд — лучшие цитаты
- [x] Турниры — daily/weekly/Grand Cup
- [x] Лиги и ELO — ранговая система
- [x] Живые уведомления — Alive UI
- [x] Дейлики — утренние/вечерние сообщения
- [x] Уведомления владельцу — рейды, баны
- [x] Админ-панель в ЛС — полное управление
- [x] Worker Process — Arq для тяжёлых задач
- [x] Усиленная безопасность — HMAC, rate limiting

### 🔜 В планах (v7.0)
- [ ] Webhook mode для высоких нагрузок
- [ ] Multi-language (i18n)
- [ ] Plugin system
- [ ] Web dashboard
- [ ] API для интеграций

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
• Говорит голосом — TTS в своём стиле
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
    
  oleg-worker:
    build: .
    command: python -m app.worker
    depends_on:
      - redis
    
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
