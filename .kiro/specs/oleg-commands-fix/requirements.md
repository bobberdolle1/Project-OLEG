# Requirements Document

## Introduction

Исправление и улучшение функциональности бота Олег: починка админ-панели в ЛС, реализация TTS голосовых ответов, настройка отображения команд в меню "/" для групп и ЛС, а также разделение /help для разных контекстов.

## Glossary

- **Oleg_Bot**: Telegram бот с персонажем "Олег" - цифровой гигачад
- **TTS (Text-to-Speech)**: Сервис преобразования текста в голосовое сообщение
- **Admin_Panel**: Интерфейс управления настройками чата для владельцев
- **Command_Menu**: Меню команд Telegram, отображаемое при вводе "/"
- **Private_Chat**: Личные сообщения с ботом (ЛС)
- **Group_Chat**: Групповой чат, где бот является участником
- **Chat_Owner**: Создатель/владелец группового чата

## Requirements

### Requirement 1

**User Story:** As a chat owner, I want to access the admin panel via /admin in private messages, so that I can manage my chat settings conveniently.

#### Acceptance Criteria

1. WHEN a chat owner sends "/admin" in private messages to the bot THEN the Oleg_Bot SHALL display a list of chats where the user is owner with inline buttons to select a chat
2. WHEN "/admin" is sent in a group chat THEN the Oleg_Bot SHALL respond with a message directing the user to use the command in private messages
3. WHEN a non-owner user sends "/admin" in private messages THEN the Oleg_Bot SHALL display a message indicating no chats are available for management

### Requirement 2

**User Story:** As a user, I want to hear Oleg's voice responses via /say command, so that I can experience the bot's personality through audio.

#### Acceptance Criteria

1. WHEN a user sends "/say <text>" command THEN the Oleg_Bot SHALL generate a voice message using TTS and send it as a voice note
2. WHEN TTS service is unavailable THEN the Oleg_Bot SHALL fall back to text response with "🔊 (голосом Олега)" prefix
3. WHEN text exceeds 500 characters THEN the Oleg_Bot SHALL truncate the text and append "...и так далее" suffix
4. WHEN "/say" is sent without text THEN the Oleg_Bot SHALL respond with usage instructions

### Requirement 3

**User Story:** As a user, I want to see relevant commands in the "/" menu based on my context, so that I can easily discover available functionality.

#### Acceptance Criteria

1. WHEN a user opens the command menu in a group chat THEN the Oleg_Bot SHALL display group-relevant commands (games, moderation, quotes, etc.)
2. WHEN a user opens the command menu in private messages THEN the Oleg_Bot SHALL display private-relevant commands (admin, reset, help, etc.)
3. WHEN bot starts THEN the Oleg_Bot SHALL register separate command scopes for private and group chats

### Requirement 4

**User Story:** As a user, I want /help to show context-appropriate information, so that I see only relevant commands for my current chat type.

#### Acceptance Criteria

1. WHEN a user sends "/help" in a group chat THEN the Oleg_Bot SHALL display group-specific commands and features
2. WHEN a user sends "/help" in private messages THEN the Oleg_Bot SHALL display private-specific commands including admin panel access
3. WHEN displaying help THEN the Oleg_Bot SHALL format the response with clear categories and descriptions

### Requirement 5

**User Story:** As a developer, I want TTS to use a real voice synthesis service, so that users can hear actual voice responses.

#### Acceptance Criteria

1. WHEN TTS is requested THEN the Oleg_Bot SHALL use Silero TTS model for Russian voice synthesis
2. WHEN generating voice THEN the Oleg_Bot SHALL produce OGG format audio compatible with Telegram voice messages
3. WHEN TTS model is not loaded THEN the Oleg_Bot SHALL attempt to load it on first use with graceful fallback on failure
