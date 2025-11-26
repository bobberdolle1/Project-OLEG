# Docker & Docker Compose для Олега

Полное руководство по запуску бота в Docker контейнере.

## 📋 Требования

- **Docker** 20.10+ ([установить](https://www.docker.com/products/docker-desktop))
- **Docker Compose** 1.29+ (обычно идет с Docker Desktop)
- **Telegram Bot Token** ([получить в @BotFather](https://t.me/BotFather))

### Проверка установки

```bash
docker --version
docker-compose --version
```

---

## 🚀 Быстрый старт с Docker Compose

### Шаг 1: Подготовка

```bash
# Клонируй репозиторий
git clone <repo-url> oleg-bot
cd oleg-bot

# Скопируй конфиг для Docker
cp .env.docker .env
```

### Шаг 2: Конфигурация

Отредактируй `.env`:

```env
TELEGRAM_BOT_TOKEN=YOUR_TOKEN_HERE
PRIMARY_CHAT_ID=YOUR_CHAT_ID
OLLAMA_BASE_URL=http://ollama:11434  # Важно: используй имя сервиса
```

### Шаг 3: Запуск

```bash
# Запуск сервисов (бот + Ollama)
docker-compose up -d

# Просмотр логов
docker-compose logs -f oleg-bot

# Проверка статуса
docker-compose ps

# Остановка
docker-compose down
```

---

## 🐋 Отдельный Docker образ

### Сборка образа

```bash
docker build -t oleg-bot:latest .
```

### Запуск контейнера

#### С SQLite (простой вариант)

```bash
docker run -d \
  --name oleg \
  --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN=YOUR_TOKEN \
  -e PRIMARY_CHAT_ID=YOUR_CHAT_ID \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -v oleg-data:/app/data \
  -v oleg-logs:/app/logs \
  oleg-bot:latest
```

#### Со внешним Ollama

```bash
docker run -d \
  --name oleg \
  --restart unless-stopped \
  --env-file .env \
  -v oleg-data:/app/data \
  -v oleg-logs:/app/logs \
  --network host \
  oleg-bot:latest
```

#### С PostgreSQL

```bash
docker run -d \
  --name oleg \
  --restart unless-stopped \
  -e DATABASE_URL=postgresql+asyncpg://user:pass@postgres-host:5432/oleg_db \
  -e TELEGRAM_BOT_TOKEN=YOUR_TOKEN \
  -e OLLAMA_BASE_URL=http://ollama-host:11434 \
  -v oleg-logs:/app/logs \
  oleg-bot:latest
```

### Просмотр логов

```bash
# Все логи
docker logs oleg

# Последние логи с автообновлением
docker logs -f oleg

# Последние 100 строк
docker logs --tail 100 oleg
```

### Управление контейнером

```bash
# Остановка
docker stop oleg

# Запуск
docker start oleg

# Перезагрузка
docker restart oleg

# Удаление
docker rm oleg

# Удаление образа
docker rmi oleg-bot:latest
```

---

## 🔧 Docker Compose детально

### Структура `docker-compose.yml`

```yaml
services:
  oleg-bot:        # Основной сервис бота
  ollama:          # Локальный ИИ сервис
  # postgres:      # PostgreSQL (опционально)
```

### Запуск конкретных сервисов

```bash
# Только бот и Ollama
docker-compose up -d oleg-bot ollama

# Добавить PostgreSQL (если раскомментировать в .yml)
docker-compose up -d

# Только Ollama
docker-compose up -d ollama

# Без Ollama (если ИИ на отдельном сервере)
docker-compose up -d oleg-bot
```

### Параметры контейнеров

#### oleg-bot

| Параметр | Значение | Описание |
|----------|---------|---------|
| `restart` | `unless-stopped` | Перезагружается при падении, но не при `docker-compose down` |
| `volumes` | `/app/data`, `/app/logs` | Сохранение БД и логов |
| `networks` | `oleg-network` | Приватная сеть для контейнеров |
| `depends_on` | `ollama` | Запускается после Ollama |

#### ollama

| Параметр | Значение | Описание |
|----------|---------|---------|
| `image` | `ollama/ollama:latest` | Официальный образ Ollama |
| `ports` | `11434:11434` | Порт для API (только внутренняя сеть) |
| `volumes` | `/root/.ollama` | Кэш моделей (персистентный) |

### Сетевое подключение

Контейнеры в `docker-compose.yml` находятся в приватной сети `oleg-network`:

```yaml
networks:
  oleg-network:
    driver: bridge
```

**Значит:**
- Бот подключается к Ollama как `http://ollama:11434` ✅
- Внешний доступ к Ollama ограничен ✅
- Контейнеры видят друг друга по имени сервиса ✅

---

## 🛠️ Production конфигурация

### Использование PostgreSQL

Раскомментируй в `docker-compose.yml`:

```yaml
postgres:
  image: postgres:15-alpine
  environment:
    POSTGRES_DB: oleg_db
    POSTGRES_USER: oleg
    POSTGRES_PASSWORD: SECURE_PASSWORD_HERE
  volumes:
    - postgres-data:/var/lib/postgresql/data
```

И установи в `.env`:

```env
DATABASE_URL=postgresql+asyncpg://oleg:SECURE_PASSWORD_HERE@postgres:5432/oleg_db
```

### Резервное копирование

```bash
# Экспорт БД SQLite
docker-compose exec oleg-bot cp /app/data/oleg.db /app/data/backup.db
docker cp oleg-bot:/app/data/backup.db ./backup.db

# Экспорт БД PostgreSQL
docker-compose exec postgres pg_dump -U oleg oleg_db > backup.sql

# Экспорт логов
docker cp oleg-bot:/app/logs/ ./logs-backup/
```

### Масштабирование

```bash
# Ограничение памяти контейнера
docker-compose.yml:
  services:
    oleg-bot:
      deploy:
        resources:
          limits:
            cpus: '1'
            memory: 512M
          reservations:
            cpus: '0.5'
            memory: 256M

# Применить
docker-compose up -d --force-recreate
```

### Мониторинг

```bash
# Просмотр использования ресурсов
docker stats oleg-bot

# Проверка здоровья контейнера
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.State}}"

# Детальная информация о контейнере
docker inspect oleg-bot
```

---

## 📊 Volume и Data Persistence

### Диагностика volume

```bash
# Просмотр всех volume
docker volume ls

# Информация о volume
docker volume inspect oleg-data

# Удаление volume (⚠️ удалит данные!)
docker volume rm oleg-data
```

### Доступ к данным

```bash
# Посмотреть содержимое volume
docker run --rm -v oleg-data:/data alpine ls -la /data

# Экспортировать файлы
docker run --rm -v oleg-data:/data -v $(pwd):/backup \
  alpine cp -r /data /backup/data-export

# Импортировать файлы
docker run --rm -v oleg-data:/data -v $(pwd):/backup \
  alpine cp -r /backup/restore-data/* /data/
```

---

## 🐛 Решение проблем

### Проблема: "Connection refused" при подключении к Ollama

```
error: Failed to generate reply: HTTPConnectionPool(host='localhost', port=11434)
```

**Решение:**

❌ Неправильно (в docker-compose):
```env
OLLAMA_BASE_URL=http://localhost:11434
```

✅ Правильно:
```env
OLLAMA_BASE_URL=http://ollama:11434
```

### Проблема: Контейнер постоянно перезагружается

```bash
# Просмотр полных логов
docker logs --tail 100 oleg-bot

# Проверка exit code
docker ps -a  # Ищи exit code в STATUS

# Запуск в режиме отладки
docker run -it --rm --env-file .env oleg-bot python -m app.main
```

### Проблема: Нет места на диске (Ollama модели кэшируются)

```bash
# Очистить неиспользуемые volume
docker volume prune

# Очистить все Docker данные (⚠️ удалит все!)
docker system prune -a --volumes
```

### Проблема: Медленная загрузка моделей

Убедись что:
1. Интернет соединение хорошее
2. У Ollama достаточно памяти: `docker stats ollama`
3. Диск не полный: `docker system df`

---

## 🔐 Безопасность

### Секреты и .env

❌ Никогда не коммитьте `.env`:

```bash
# Проверить .gitignore
cat .gitignore | grep "^\.env"
```

✅ Используй `.env.example` как шаблон:

```bash
# Создать пример
cp .env .env.example
# Отредактировать, оставив только переменные без значений
```

### Сетевая безопасность

По умолчанию:
- ✅ Ollama доступен только из приватной сети контейнеров
- ✅ Бот использует переменные окружения
- ✅ Логи сохраняются локально

Для production:
- Используй SSL/TLS для внешних подключений
- Ограничь доступ к портам на firewall уровне
- Храни secrets в Docker Secrets или external vault

---

## 📦 Build без Compose

### Кастомный build с аргументами

```dockerfile
# Dockerfile.custom
ARG PYTHON_VERSION=3.11
ARG BASE_IMAGE=python:${PYTHON_VERSION}-slim

FROM ${BASE_IMAGE} as builder
# ...
```

```bash
# Сборка с параметрами
docker build \
  --build-arg PYTHON_VERSION=3.12 \
  -t oleg-bot:py312 .
```

### Multi-stage optimization

Текущий Dockerfile использует multi-stage для оптимизации:

1. **builder** — полная установка зависимостей
2. **final** — только runtime

Размер образа: ~500MB (vs ~1.5GB если без оптимизации)

---

## 🌐 Дополнительные ссылки

- [Docker Документация](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [Ollama Docker Hub](https://hub.docker.com/r/ollama/ollama)
- [Python Docker Best Practices](https://docs.docker.com/language/python/build-images/)

---

## 📝 Примеры развертывания

### На VPS (Linux)

```bash
# 1. Установить Docker
curl -sSL https://get.docker.com | sh

# 2. Клонировать проект
git clone <url> && cd oleg-bot

# 3. Настроить .env
nano .env  # или vim .env

# 4. Запустить
docker-compose up -d

# 5. Проверить
docker-compose logs -f oleg-bot
```

### На машине с ограниченными ресурсами

```yaml
# docker-compose.yml - добавить в oleg-bot:
services:
  oleg-bot:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
```

### С внешним Ollama сервером

```env
OLLAMA_BASE_URL=http://ollama.example.com:11434
```

```bash
# docker-compose.yml - удалить сервис ollama и зависимость
services:
  oleg-bot:
    # ... убрать depends_on: ollama
```

---

**Готово!** 🎉 Твой бот Олег теперь работает в Docker!
