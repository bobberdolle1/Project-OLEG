# Requirements Document

## Introduction

Project OLEG v6.5 (Shield & Economy) — обновление Telegram-бота Олега, направленное на экономию токенов LLM через систему rate limiting и усиление защиты чатов от рейдов и спама. Обновление включает систему cooldown для пользователей, временную память RAG, умную защиту от рейдов (Citadel 2.0) и профили защиты в админке.

## Glossary

- **OLEG_Bot**: Telegram-бот Олег, основная система обработки сообщений и модерации
- **LLM**: Large Language Model — языковая модель для генерации ответов
- **Cooldown**: Период ожидания между запросами пользователя к боту
- **Energy**: Виртуальный ресурс пользователя для общения с ботом
- **RAG**: Retrieval-Augmented Generation — система памяти на основе ChromaDB
- **ChromaDB**: Векторная база данных для хранения фактов
- **Panic_Mode**: Режим автоматической защиты при обнаружении рейда
- **RO**: Read Only — режим только чтения (мут)
- **Silent_Ban**: Скрытый бан, при котором сообщения пользователя удаляются без уведомления
- **Protection_Profile**: Предустановленный набор настроек защиты чата
- **Newreg**: Новозарегистрированный пользователь Telegram

## Requirements

### Requirement 1: Personal Cooldown System

**User Story:** As a chat administrator, I want users to have limited free requests to the bot, so that LLM tokens are not wasted on spam.

#### Acceptance Criteria

1. WHEN a user sends a message to OLEG_Bot within 10 seconds of their previous message THEN OLEG_Bot SHALL decrement the user's energy counter by 1
2. WHEN a user's energy counter reaches 0 THEN OLEG_Bot SHALL respond with a cooldown message containing the user's mention and a 60-second wait instruction
3. WHEN a user sends a message after 60 seconds of inactivity THEN OLEG_Bot SHALL reset the user's energy counter to 3
4. WHEN a user has energy remaining THEN OLEG_Bot SHALL process the request normally through the LLM pipeline

### Requirement 2: Global Chat Rate Limiting

**User Story:** As a system administrator, I want to limit total LLM requests per chat, so that the bot remains responsive and cost-effective.

#### Acceptance Criteria

1. WHILE the chat's LLM request count exceeds the configured limit (default: 20 per minute) THEN OLEG_Bot SHALL ignore new LLM requests from that chat
2. WHEN the global limit is exceeded THEN OLEG_Bot SHALL respond with a cached short message "Занят." instead of generating a new response
3. WHEN an administrator configures a custom rate limit via the admin panel THEN OLEG_Bot SHALL apply the new limit within 5 seconds
4. WHEN the rate limit window (1 minute) expires THEN OLEG_Bot SHALL reset the request counter to 0

### Requirement 3: Status Notification Anti-Flood

**User Story:** As a chat member, I want the bot to not spam status messages, so that the chat remains clean during high activity.

#### Acceptance Criteria

1. WHILE OLEG_Bot is processing a request in a chat THEN OLEG_Bot SHALL add a reaction (⏳) to new incoming messages instead of sending status notifications
2. WHEN OLEG_Bot starts processing the first request in a chat THEN OLEG_Bot SHALL send a single status notification
3. WHEN OLEG_Bot completes all pending requests in a chat THEN OLEG_Bot SHALL remove the processing reaction from messages

### Requirement 4: RAG Timestamping

**User Story:** As a user, I want the bot to understand when facts were learned, so that it can prioritize recent information.

#### Acceptance Criteria

1. WHEN OLEG_Bot saves a fact to ChromaDB THEN OLEG_Bot SHALL include a created_at metadata field in ISO 8601 format
2. WHEN OLEG_Bot generates a response using RAG THEN OLEG_Bot SHALL include the current date and time in the prompt in format "СЕГОДНЯ: YYYY-MM-DD HH:MM"
3. WHEN OLEG_Bot retrieves facts with conflicting information THEN OLEG_Bot SHALL prioritize the fact with the most recent created_at timestamp
4. WHEN displaying retrieved facts in context THEN OLEG_Bot SHALL include the age of each fact for LLM consideration

### Requirement 5: RAG Memory Management

**User Story:** As a chat administrator, I want to manage the bot's memory, so that I can clear outdated or unwanted information.

#### Acceptance Criteria

1. WHEN an administrator selects "🗑 Забыть всё" in the Memory settings THEN OLEG_Bot SHALL delete all facts associated with that chat from ChromaDB
2. WHEN an administrator selects "🗓 Забыть старое" in the Memory settings THEN OLEG_Bot SHALL delete all facts older than 3 months from that chat
3. WHEN an administrator selects "👤 Забыть юзера" and provides a user ID or username THEN OLEG_Bot SHALL delete all facts associated with that user in the chat
4. WHEN a memory deletion operation completes THEN OLEG_Bot SHALL confirm the action with the count of deleted facts

### Requirement 6: Panic Mode Auto-Activation

**User Story:** As a chat administrator, I want the bot to automatically defend against raids, so that the chat is protected even when I'm offline.

#### Acceptance Criteria

1. WHEN more than 10 new users join within 10 seconds THEN OLEG_Bot SHALL activate Panic_Mode automatically
2. WHEN more than 20 messages per second are received from different users THEN OLEG_Bot SHALL activate Panic_Mode automatically
3. WHILE Panic_Mode is active THEN OLEG_Bot SHALL stop sending welcome messages to new users
4. WHILE Panic_Mode is active THEN OLEG_Bot SHALL apply RO status for 30 minutes to all users who joined within the last 24 hours
5. WHILE Panic_Mode is active THEN OLEG_Bot SHALL require hard captcha (math problem) in private messages for users to remove RO status

### Requirement 7: Bot Permission Self-Check

**User Story:** As a chat administrator, I want the bot to be aware of its permissions, so that it doesn't make empty threats or fail silently.

#### Acceptance Criteria

1. WHEN OLEG_Bot attempts a moderation action (mute/ban/delete) THEN OLEG_Bot SHALL first verify its permissions via get_chat_member API
2. WHEN OLEG_Bot lacks required permissions for an action THEN OLEG_Bot SHALL silently report to administrators "У меня нет прав на [action], сделайте что-нибудь!"
3. WHEN OLEG_Bot lacks permissions THEN OLEG_Bot SHALL NOT send threatening messages to violators
4. WHEN OLEG_Bot's permissions change THEN OLEG_Bot SHALL update its cached permissions within 60 seconds

### Requirement 8: Neural Spam Filter

**User Story:** As a chat administrator, I want automatic detection and removal of spam messages, so that the chat stays clean without manual intervention.

#### Acceptance Criteria

1. WHEN a message matches spam patterns (selling accounts, crypto schemes, job offers, collaboration requests) THEN OLEG_Bot SHALL delete the message immediately
2. WHEN a spam message is detected THEN OLEG_Bot SHALL ban the sender without warning
3. WHEN the spam filter processes a message THEN OLEG_Bot SHALL use a combination of regex, keywords, and classification model
4. WHEN a message is classified as spam THEN OLEG_Bot SHALL log the detection with message content hash and classification confidence

### Requirement 9: New User Scanning

**User Story:** As a chat administrator, I want new users to be automatically screened, so that bot accounts are detected early.

#### Acceptance Criteria

1. WHEN a new user joins THEN OLEG_Bot SHALL check for presence of profile photo
2. WHEN a new user joins THEN OLEG_Bot SHALL analyze the username for suspicious patterns (RTL characters, hieroglyphics, spam words)
3. WHEN a new user joins THEN OLEG_Bot SHALL check Premium status as a trust signal
4. WHEN a user's suspicion score exceeds threshold (no avatar + suspicious name) THEN OLEG_Bot SHALL apply Silent_Ban until captcha is passed
5. WHILE Silent_Ban is active THEN OLEG_Bot SHALL delete all messages from the user without notification

### Requirement 10: Protection Profiles

**User Story:** As a chat administrator, I want preset protection configurations, so that I can quickly apply appropriate security levels.

#### Acceptance Criteria

1. WHEN an administrator selects "🟢 Стандарт" profile THEN OLEG_Bot SHALL enable link anti-spam, button captcha, and allow profanity
2. WHEN an administrator selects "🟡 Строгий" profile THEN OLEG_Bot SHALL enable neural ad filter, block forwards, and limit stickers
3. WHEN an administrator selects "🔴 Бункер" profile THEN OLEG_Bot SHALL mute all newcomers until captcha, block all media from non-admins, and enable aggressive profanity filter
4. WHEN an administrator selects "⚙️ Кастомный" profile THEN OLEG_Bot SHALL display toggles for each protection feature
5. WHEN a protection profile is applied THEN OLEG_Bot SHALL activate all associated settings within 5 seconds

### Requirement 11: Serialization Round-Trip for RAG Facts

**User Story:** As a developer, I want RAG facts to serialize and deserialize correctly, so that no data is lost during storage operations.

#### Acceptance Criteria

1. WHEN a RAG fact is serialized to JSON for ChromaDB storage THEN OLEG_Bot SHALL preserve all metadata fields including created_at, user_id, and chat_id
2. WHEN a serialized RAG fact is deserialized THEN OLEG_Bot SHALL produce an equivalent fact object with identical field values
3. WHEN facts contain Unicode characters THEN OLEG_Bot SHALL preserve character encoding through serialization round-trip
