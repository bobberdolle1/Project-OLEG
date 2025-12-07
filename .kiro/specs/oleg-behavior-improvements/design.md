# Design Document: Oleg Behavior Improvements (v6.6)

## Overview

Улучшение поведения бота Олега для более естественного общения. Три основных направления:
1. Отключение автоматических ответов на изображения (кроме явных вызовов)
2. Улучшение системы авто-ответов с фильтрами по длине и содержанию
3. Переработка промпта для более человечного стиля

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Message Flow                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Incoming Message                                            │
│        │                                                     │
│        ▼                                                     │
│  ┌─────────────┐                                            │
│  │ Is Image?   │──Yes──► ┌──────────────────┐               │
│  └─────────────┘         │ Check Explicit   │               │
│        │                 │ Mention/Reply    │               │
│        No                └────────┬─────────┘               │
│        │                          │                          │
│        ▼                    Yes   │   No                     │
│  ┌─────────────┐            ▼     ▼                         │
│  │ Is Explicit │──Yes──► Process  Skip                      │
│  │ Mention?    │                                            │
│  └─────────────┘                                            │
│        │                                                     │
│        No                                                    │
│        │                                                     │
│        ▼                                                     │
│  ┌─────────────────┐                                        │
│  │ Message Filter  │                                        │
│  │ (length, words) │                                        │
│  └────────┬────────┘                                        │
│           │                                                  │
│     Pass  │  Fail                                           │
│           ▼    ▼                                            │
│     ┌──────┐  Skip                                          │
│     │Random│                                                │
│     │Check │                                                │
│     └──┬───┘                                                │
│        │                                                     │
│   Pass │  Fail                                              │
│        ▼    ▼                                               │
│    Process  Skip                                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Vision Module (app/handlers/vision.py)

**Изменения:**
- Добавить проверку на явный вызов перед обработкой изображения
- Функция `should_process_image(msg: Message) -> bool`

```python
async def should_process_image(msg: Message) -> bool:
    """
    Проверяет, нужно ли обрабатывать изображение.
    
    Returns True если:
    - В caption есть упоминание бота (@username или "олег")
    - Это ответ на сообщение бота
    """
    # Check caption for mentions
    caption = msg.caption or ""
    if _contains_bot_mention(caption, msg.bot):
        return True
    
    # Check if reply to bot
    if msg.reply_to_message and msg.reply_to_message.from_user:
        if msg.reply_to_message.from_user.id == msg.bot.id:
            return True
    
    return False
```

### 2. Auto-Reply System (app/services/auto_reply.py)

**Изменения:**
- Снизить базовую вероятность с 15-25% до 2-5%
- Снизить максимум с 40% до 15%
- Добавить фильтр по длине сообщения (минимум 15 символов)
- Добавить блоклист коротких фраз

```python
# Новые константы
MIN_MESSAGE_LENGTH = 15
BLOCKED_SHORT_PHRASES = {
    "че", "чё", "ок", "да", "нет", "лол", "кек", 
    "ага", "угу", "ну", "хз", "пон", "ясн", "норм",
    "го", "gg", "wp", "лан", "ладно", "окей"
}

# Новые границы вероятности
BASE_PROBABILITY_MIN = 0.02  # 2%
BASE_PROBABILITY_MAX = 0.05  # 5%
MAX_PROBABILITY = 0.15       # 15%
```

### 3. Core Prompt (app/services/ollama_client.py)

**Изменения в CORE_OLEG_PROMPT:**
- Упростить формулировки
- Убрать литературные обороты
- Разделить инструкции и примеры
- Добавить явные ограничения на длину ответов
- Убрать фразы провоцирующие постоянную агрессию

## Data Models

Изменений в моделях данных не требуется.

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Image filtering without explicit mention
*For any* image message without bot mention in caption and not a reply to bot, the Vision_Module should skip processing and return immediately without calling LLM.
**Validates: Requirements 1.1, 1.4**

### Property 2: Image processing with explicit mention
*For any* image message with bot mention ("олег", "@botname") in caption OR as reply to bot message, the Vision_Module should process the image.
**Validates: Requirements 1.2, 1.3**

### Property 3: Short message rejection
*For any* message with fewer than 15 characters OR consisting only of blocked short phrases, the Auto_Reply_System should return False regardless of probability.
**Validates: Requirements 2.2, 2.3**

### Property 4: Probability bounds
*For any* message, the calculated probability should be between 2% and 15% (MIN_PROBABILITY and MAX_PROBABILITY).
**Validates: Requirements 2.1, 2.4**

### Property 5: Explicit mention always triggers response
*For any* message containing "@botname" or "олег" (and variations), the _should_reply function should return True.
**Validates: Requirements 5.1, 5.2**

### Property 6: Private chat always triggers response
*For any* message in private chat (chat.type == "private"), the _should_reply function should return True.
**Validates: Requirements 5.4**

## Error Handling

- Если фильтрация сообщений падает с ошибкой → пропускаем сообщение (не отвечаем)
- Если проверка упоминаний падает → используем fallback на старую логику
- Логируем все ошибки для отладки

## Testing Strategy

### Property-Based Testing

Используем **Hypothesis** (уже установлен в проекте) для property-based тестов.

Каждый property-based тест должен:
- Запускаться минимум 100 итераций
- Быть помечен комментарием с номером property из дизайна
- Использовать генераторы для создания разнообразных входных данных

### Unit Tests

Unit тесты для:
- Конкретных edge cases (пустые строки, граничные длины)
- Интеграции между компонентами
- Проверки что промпт содержит нужные инструкции

### Test Files

- `tests/property/test_vision_filter_props.py` - property тесты для фильтрации изображений
- `tests/property/test_auto_reply_props.py` - обновить существующие тесты с новыми границами
- `tests/unit/test_prompt_structure.py` - проверка структуры промпта
