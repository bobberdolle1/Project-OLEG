# 🧪 Тестирование — Олег 4.0

> 33 теста для уверенности в коде

---

## ⚡ Быстрый запуск

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=app --cov-report=html

# Подробный вывод
pytest -v
```

---

## 📁 Структура тестов

```
tests/
├── conftest.py              # Фикстуры
├── unit/                    # Unit тесты (быстрые)
│   ├── test_rate_limiter.py # Rate limiting
│   ├── test_redis_client.py # Redis операции
│   ├── test_config.py       # Конфигурация
│   ├── test_utils.py        # Утилиты
│   ├── test_metrics.py      # Метрики
│   └── test_ollama_fallback.py # Fallback
└── integration/             # Integration тесты
    └── test_database.py     # Операции с БД
```

---

## 📊 Покрытие

| Модуль | Тесты | Описание |
|--------|-------|----------|
| `rate_limiter` | 5 | Лимиты, окна, пользователи |
| `redis_client` | 5 | Подключение, операции, fallback |
| `config` | 6 | Валидация, defaults, Redis/PG |
| `utils` | 3 | utc_now, timezone |
| `metrics` | 7 | Counters, gauges, histograms |
| `ollama_fallback` | 5 | Timeout, HTTP, connection errors |
| `database` | 2 | User, GameStat |

**Всего: 33 теста**

---

## 🎯 Запуск по категориям

```bash
# Только unit
pytest tests/unit/

# Только integration
pytest tests/integration/

# Конкретный файл
pytest tests/unit/test_rate_limiter.py

# Конкретный тест
pytest tests/unit/test_rate_limiter.py::test_rate_limiter_blocks_requests_over_limit
```

---

## 🔧 Полезные флаги

```bash
pytest -v              # Подробный вывод
pytest -s              # Показать print()
pytest -x              # Остановиться на первой ошибке
pytest -l              # Показать локальные переменные
pytest --pdb           # Отладчик при ошибке
pytest -k "redis"      # Тесты с "redis" в имени
pytest -m "not slow"   # Пропустить медленные
```

---

## 📈 Покрытие кода

```bash
# HTML отчет
pytest --cov=app --cov-report=html
open htmlcov/index.html

# Terminal отчет
pytest --cov=app --cov-report=term-missing

# XML для CI
pytest --cov=app --cov-report=xml
```

---

## ✍️ Написание тестов

### Unit тест

```python
import pytest

def test_my_function():
    # Arrange
    input_value = 42
    
    # Act
    result = my_function(input_value)
    
    # Assert
    assert result == 84
```

### Async тест

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await my_async_function()
    assert result is not None
```

### С моками

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_with_mock():
    with patch('app.services.ollama_client._ollama_chat') as mock:
        mock.return_value = "Mocked"
        result = await generate_reply("test")
        assert result == "Mocked"
```

### С фикстурами

```python
@pytest.fixture
def rate_limiter():
    return RateLimiter(max_requests=3, window_seconds=10)

@pytest.mark.asyncio
async def test_rate_limiter(rate_limiter):
    assert await rate_limiter.is_allowed(123) is True
```

---

## 🐛 Отладка

```bash
# Запустить с отладчиком
pytest --pdb

# Показать полный traceback
pytest --tb=long

# Остановиться на первой ошибке
pytest -x --pdb
```

---

## 🔄 CI/CD

### GitHub Actions

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: pytest --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v4
```

---

## 📝 Best Practices

1. **Именование**: `test_<что>_<ожидание>`
   ```python
   def test_rate_limiter_blocks_requests_over_limit():
   ```

2. **AAA паттерн**: Arrange → Act → Assert

3. **Изоляция**: Каждый тест независим

4. **Моки**: Для внешних зависимостей (Redis, Ollama)

5. **Фикстуры**: Для общей настройки

---

## ❓ FAQ

**Q: Тесты падают с "No module named 'app'"**
```bash
# Запускай из корня проекта
cd oleg-bot && pytest
```

**Q: Как пропустить медленные тесты?**
```python
@pytest.mark.slow
def test_slow():
    pass
```
```bash
pytest -m "not slow"
```

**Q: Как тестировать с реальной БД?**
```python
# В conftest.py уже есть фикстура test_db
async def test_with_db(test_db):
    async with test_db() as session:
        # ...
```

---

## 📚 Ресурсы

- [pytest docs](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)

---

**Версия:** 4.0.0  
**Тестов:** 33
