# Руководство по тестированию

## 🧪 Запуск тестов

### Все тесты
```bash
pytest
```

### С покрытием кода
```bash
pytest --cov=app --cov-report=html
```

Отчет будет в `htmlcov/index.html`

### Только unit тесты
```bash
pytest tests/unit/
```

### Только integration тесты
```bash
pytest tests/integration/
```

### Конкретный файл
```bash
pytest tests/unit/test_rate_limiter.py
```

### С подробным выводом
```bash
pytest -v
```

### С выводом print()
```bash
pytest -s
```

---

## 📁 Структура тестов

```
tests/
├── conftest.py              # Общие фикстуры
├── unit/                    # Unit тесты (быстрые, изолированные)
│   ├── test_rate_limiter.py
│   ├── test_redis_client.py
│   ├── test_config.py
│   └── test_utils.py
└── integration/             # Integration тесты (медленные, с БД)
    └── test_database.py
```

---

## ✅ Покрытие тестами

### Rate Limiter (`test_rate_limiter.py`)
- ✅ Разрешает запросы в пределах лимита
- ✅ Блокирует запросы сверх лимита
- ✅ Сбрасывается после окна времени
- ✅ Разные пользователи имеют отдельные лимиты
- ✅ Корректно вычисляет оставшееся время

### Redis Client (`test_redis_client.py`)
- ✅ Обрабатывает отсутствие пакета redis
- ✅ Возвращает None при недоступности
- ✅ JSON операции (get_json, set_json)
- ✅ Graceful обработка ошибок подключения

### Config (`test_config.py`)
- ✅ Значения по умолчанию
- ✅ Валидация токена бота
- ✅ Валидация уровня логирования
- ✅ Case-insensitive уровень логирования
- ✅ Конфигурация Redis
- ✅ PostgreSQL URL

### Utils (`test_utils.py`)
- ✅ utc_now() возвращает datetime
- ✅ utc_now() с timezone
- ✅ utc_now() возвращает текущее время

### Database (`test_database.py`)
- ✅ Создание пользователя
- ✅ Связь User-GameStat

---

## 🔧 Настройка окружения для тестов

### 1. Установить зависимости
```bash
pip install -r requirements.txt
```

### 2. Создать тестовую БД (автоматически)
Тесты используют in-memory SQLite, настройка не требуется.

### 3. Запустить тесты
```bash
pytest
```

---

## 📝 Написание новых тестов

### Unit тест (пример)
```python
# tests/unit/test_my_feature.py
import pytest
from app.services.my_feature import my_function


def test_my_function_returns_correct_value():
    """Test that my_function returns expected value."""
    result = my_function(input_value=42)
    assert result == 84
```

### Async unit тест
```python
import pytest


@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await my_async_function()
    assert result is not None
```

### Integration тест с БД
```python
import pytest
from app.database.session import get_session
from app.database.models import User


@pytest.mark.asyncio
async def test_database_operation():
    """Test database operation."""
    async_session = get_session()
    
    async with async_session() as session:
        user = User(tg_user_id=123, username="test")
        session.add(user)
        await session.commit()
        
        # Cleanup
        await session.delete(user)
        await session.commit()
```

---

## 🎯 Best Practices

### 1. Именование тестов
- Используй префикс `test_`
- Описывай что тестируется: `test_rate_limiter_blocks_requests_over_limit`

### 2. Структура теста (AAA)
```python
def test_something():
    # Arrange (подготовка)
    user_id = 12345
    
    # Act (действие)
    result = rate_limiter.is_allowed(user_id)
    
    # Assert (проверка)
    assert result is True
```

### 3. Изоляция тестов
- Каждый тест должен быть независимым
- Используй фикстуры для общей настройки
- Очищай данные после теста

### 4. Моки для внешних зависимостей
```python
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_with_mock():
    with patch('app.services.ollama_client._ollama_chat') as mock:
        mock.return_value = "Mocked response"
        result = await generate_text_reply("test")
        assert result == "Mocked response"
```

---

## 🐛 Отладка тестов

### Запустить один тест
```bash
pytest tests/unit/test_rate_limiter.py::test_rate_limiter_allows_requests_within_limit
```

### С отладчиком
```bash
pytest --pdb
```

### Показать локальные переменные при ошибке
```bash
pytest -l
```

### Остановиться на первой ошибке
```bash
pytest -x
```

---

## 📊 CI/CD Integration

### GitHub Actions (пример)
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: pytest --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v2
```

---

## 🎓 Дополнительные ресурсы

- [pytest документация](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)

---

## ❓ FAQ

**Q: Тесты падают с ошибкой "No module named 'app'"**  
A: Убедись что запускаешь pytest из корня проекта

**Q: Как пропустить медленные тесты?**  
A: Используй маркеры:
```python
@pytest.mark.slow
def test_slow_operation():
    pass
```
Запуск: `pytest -m "not slow"`

**Q: Как тестировать с реальной БД?**  
A: Создай отдельную фикстуру с тестовой БД в `conftest.py`

---

**Последнее обновление**: 2024-12-04
