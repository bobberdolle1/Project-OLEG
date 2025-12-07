# Requirements Document

## Introduction

Улучшение поведения бота Олега для более естественного общения в чатах. Основные изменения:
1. Удаление автоматических ответов на изображения
2. Улучшение системы автоматических ответов на сообщения (два варианта: рандом с фильтрами или LLM-гейт)
3. Исправление промпта Олега для более человечного стиля общения

## Glossary

- **Oleg_Bot**: Телеграм-бот с личностью "Олега" - циничного IT-эксперта
- **Vision_Module**: Модуль обработки изображений (app/handlers/vision.py)
- **Auto_Reply_System**: Система автоматических ответов на сообщения (app/services/auto_reply.py)
- **LLM_Gate**: Предварительная проверка сообщения через LLM для решения об ответе
- **Core_Prompt**: Основной системный промпт, определяющий личность Олега

## Requirements

### Requirement 1: Удаление ответов на изображения

**User Story:** Как владелец бота, я хочу отключить автоматические ответы на изображения, чтобы бот не спамил комментариями к каждой картинке.

#### Acceptance Criteria

1. WHEN a user sends an image to a chat THEN the Oleg_Bot SHALL NOT automatically respond to that image
2. WHEN a user sends an image with a caption mentioning "олег" or "@botname" THEN the Oleg_Bot SHALL respond to the image
3. WHEN a user replies to the bot's message with an image THEN the Oleg_Bot SHALL respond to that image
4. WHEN the Vision_Module receives an image without explicit mention THEN the Vision_Module SHALL skip processing and return immediately

### Requirement 2: Улучшение системы автоматических ответов (Вариант A - Рандом с фильтрами)

**User Story:** Как владелец бота, я хочу чтобы бот отвечал на сообщения реже и только на содержательные сообщения, чтобы он не выглядел как спам-бот.

#### Acceptance Criteria

1. WHEN the Auto_Reply_System evaluates a message THEN the system SHALL use a base probability of 2-5% instead of current 15-25%
2. WHEN a message has fewer than 15 characters THEN the Auto_Reply_System SHALL NOT trigger an auto-reply
3. WHEN a message consists only of common short phrases (e.g., "че", "ок", "да", "нет", "лол") THEN the Auto_Reply_System SHALL NOT trigger an auto-reply
4. WHEN the Auto_Reply_System calculates probability THEN the system SHALL cap maximum probability at 15% instead of current 40%

### Requirement 3: Улучшение системы автоматических ответов (Вариант B - LLM-гейт)

**User Story:** Как владелец бота, я хочу чтобы отдельная LLM решала, стоит ли отвечать на сообщение, чтобы бот отвечал только в уместных ситуациях.

#### Acceptance Criteria

1. WHEN the Auto_Reply_System evaluates a message for auto-reply THEN the system SHALL first pass the message through LLM_Gate
2. WHEN the LLM_Gate receives a message THEN the LLM_Gate SHALL return exactly "1" (reply) or "0" (skip) with no additional text
3. WHEN the LLM_Gate prompt is configured THEN the prompt SHALL strictly limit reply scenarios to: direct questions about tech, requests for help, interesting discussions worth joining
4. WHEN the LLM_Gate returns "0" THEN the Auto_Reply_System SHALL NOT trigger a response regardless of probability
5. WHEN the LLM_Gate returns "1" THEN the Auto_Reply_System SHALL proceed with normal probability check
6. WHEN the LLM_Gate fails or times out THEN the Auto_Reply_System SHALL fall back to probability-only check

### Requirement 4: Исправление промпта Олега

**User Story:** Как владелец бота, я хочу чтобы Олег отвечал короткими, обрывистыми фразами как живой человек в чате, а не длинными структурированными ответами как типичная LLM.

#### Acceptance Criteria

1. WHEN the Core_Prompt is configured THEN the prompt SHALL instruct the model to use short, fragmented sentences
2. WHEN the Core_Prompt is configured THEN the prompt SHALL instruct the model to split responses into multiple short messages mentally (2-4 words per "message")
3. WHEN the Core_Prompt is configured THEN the prompt SHALL prohibit the model from using bullet points, numbered lists, or structured formatting
4. WHEN the Core_Prompt is configured THEN the prompt SHALL prohibit the model from trying to have the "last word" in a conversation
5. WHEN the Core_Prompt is configured THEN the prompt SHALL instruct the model to ignore punctuation rules and use casual typing style
6. WHEN the Core_Prompt is configured THEN the prompt SHALL limit response length to 1-3 short sentences maximum for most replies
7. WHEN the Core_Prompt is configured THEN the prompt SHALL instruct the model to avoid "helpful assistant" phrases like "Надеюсь помог", "Рад помочь", "Если есть вопросы"
8. WHEN the Core_Prompt mentions specific behaviors (humor, profanity, topics) THEN the prompt SHALL explicitly state these are used "in context, not constantly" to prevent LLM fixation
9. WHEN the Core_Prompt is configured THEN the prompt SHALL use neutral phrasing to prevent the model from overusing any single trait or topic
10. WHEN the Core_Prompt describes profanity usage THEN the prompt SHALL state profanity is an "occasional emphasis tool, not a constant pattern"
11. WHEN the Core_Prompt is configured THEN the prompt SHALL use simple, direct language without literary phrases like "растекаешься мыслью по древу"
12. WHEN the Core_Prompt describes context adaptation THEN the prompt SHALL NOT use phrases like "без форсирования техно-отсылок" - just say "отвечай по теме"
13. WHEN the Core_Prompt describes communication style THEN the prompt SHALL say "как живой человек" without adding "из токсичного чата" to avoid constant aggression
14. WHEN the Core_Prompt provides examples THEN the prompt SHALL place examples in a separate section to not interrupt instruction flow
15. WHEN the Core_Prompt describes entry into dialogue THEN the prompt SHALL NOT provide specific phrase examples that model will copy verbatim

### Requirement 5: Сохранение явных вызовов

**User Story:** Как пользователь, я хочу чтобы бот всегда отвечал когда я его явно вызываю, чтобы я мог получить помощь когда нужно.

#### Acceptance Criteria

1. WHEN a user mentions "@botname" in a message THEN the Oleg_Bot SHALL always respond
2. WHEN a user mentions "олег" (or variations) in a message THEN the Oleg_Bot SHALL always respond
3. WHEN a user replies to the bot's message THEN the Oleg_Bot SHALL always respond
4. WHEN a user sends a private message to the bot THEN the Oleg_Bot SHALL always respond

### Requirement 6: Обновление документации (версия 6.6)

**User Story:** Как разработчик, я хочу чтобы все изменения были задокументированы и закоммичены, чтобы отслеживать историю изменений.

#### Acceptance Criteria

1. WHEN all changes are implemented THEN the CHANGELOG.md SHALL be updated with version 6.6 changes
2. WHEN all changes are implemented THEN the README.md SHALL reflect any new configuration options
3. WHEN documentation is updated THEN a git commit SHALL be created with descriptive message about version 6.6
