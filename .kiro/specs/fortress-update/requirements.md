# Requirements Document

## Introduction

Project OLEG v6.0 (Fortress Update) — масштабное обновление Telegram-бота Олега, превращающее его в комплексную систему защиты чата с ИИ-модерацией, голосовыми технологиями, улучшенным цитатником, турнирной системой и "живыми" уведомлениями. Цель — создать лучшую систему защиты в Telegram, превосходящую Iris/Combot за счёт ИИ-анализа, при этом развлекая пользователей и создавая собственную экосистему.

## Glossary

- **DEFCON**: Уровень защиты чата (1-3), определяющий строгость модерации
- **Raid Mode**: Режим защиты от массового вступления ботов/спамеров
- **Reputation Score**: Числовой показатель репутации пользователя (начинается с 1000)
- **TTS (Text-to-Speech)**: Технология преобразования текста в голос
- **Golden Fund (Золотой Фонд)**: Коллекция лучших цитат, набравших 5+ реакций
- **ELO**: Рейтинговая система для ранжирования игроков
- **Hard Captcha**: ИИ-загадки для верификации новых пользователей
- **GIF-Патруль**: Система анализа GIF на запрещённый контент
- **Quotly-like**: Стиль рендеринга цитат как у бота Quotly
- **Worker**: Отдельный процесс для тяжёлых задач (Celery/Arq)

## Requirements

### Requirement 1: Система "Цитадель" — Многоуровневая защита (DEFCON)

**User Story:** As a chat administrator, I want to configure different protection levels for my chat, so that I can balance security and user experience based on current threat level.

#### Acceptance Criteria

1. WHEN a new chat is registered THEN the Citadel System SHALL set DEFCON level to 1 (Peaceful) as the default protection level
2. WHEN an administrator sets DEFCON level to 1 (Peaceful) THEN the Citadel System SHALL enable only anti-spam link filtering and basic captcha verification for new members
3. WHEN an administrator sets DEFCON level to 2 (Strict) THEN the Citadel System SHALL enable automatic profanity deletion, sticker flood protection (maximum 3 consecutive stickers), and channel forward blocking
4. WHEN an administrator sets DEFCON level to 3 (Martial Law) THEN the Citadel System SHALL enable full media and link restrictions for new members (less than 24 hours in chat) and activate Hard Captcha verification
5. WHEN 5 or more users join the chat within 60 seconds THEN the Citadel System SHALL automatically activate DEFCON level 3 (Raid Mode) for 15 minutes
6. WHEN Raid Mode is active THEN the Citadel System SHALL restrict all new members from sending any media or links until manually approved by an administrator
7. WHEN an administrator uses the command "олег defcon [1-3]" THEN the Citadel System SHALL change the protection level and confirm the change with a status message

### Requirement 2: Нейро-Модерация — ИИ-анализ токсичности

**User Story:** As a chat moderator, I want the bot to detect toxic messages by context rather than just keywords, so that I can catch sophisticated insults and sarcasm while avoiding false positives on legitimate messages.

#### Acceptance Criteria

1. WHEN a user sends a message THEN the Neuro-Moderation System SHALL analyze the message context using LLM to detect toxicity, distinguishing between sarcastic insults and genuine compliments
2. WHEN the toxicity analysis returns a score above the configured threshold THEN the Neuro-Moderation System SHALL take action based on DEFCON level (warn at level 1, delete at level 2, delete and mute at level 3)
3. WHEN analyzing toxicity THEN the Neuro-Moderation System SHALL return a structured response containing toxicity score (0-100), detected category (insult, hate speech, threat, spam), and confidence level
4. WHEN a message is flagged as toxic THEN the Neuro-Moderation System SHALL log the incident with message text, score, category, and action taken to the toxicity_logs table

### Requirement 3: GIF-Патруль — Анализ анимаций

**User Story:** As a chat administrator, I want the bot to automatically detect and remove inappropriate GIFs, so that I can protect chat members from pornography, screamers, and violent content.

#### Acceptance Criteria

1. WHEN a user sends a GIF THEN the GIF Patrol System SHALL extract 3 frames (beginning, middle, end) for analysis
2. WHEN analyzing GIF frames THEN the GIF Patrol System SHALL detect pornographic content, screamers, and violent imagery using the same vision model as regular image analysis
3. WHEN inappropriate content is detected in a GIF THEN the GIF Patrol System SHALL immediately delete the message and ban the sender
4. WHEN a GIF is analyzed THEN the GIF Patrol System SHALL complete the analysis within 5 seconds to avoid blocking chat flow
5. IF the vision model is unavailable THEN the GIF Patrol System SHALL queue the GIF for later analysis and allow the message temporarily
6. WHEN analyzing GIF content THEN the GIF Patrol System SHALL use the existing vision pipeline infrastructure for consistency with image moderation

### Requirement 4: Репутационная Система (Social Credit)

**User Story:** As a chat member, I want to have a reputation score that reflects my behavior, so that I can see the consequences of my actions and strive to be a better community member.

#### Acceptance Criteria

1. WHEN a new user joins the chat THEN the Reputation System SHALL initialize their reputation score to 1000
2. WHEN a user receives a warning THEN the Reputation System SHALL decrease their reputation by 50 points
3. WHEN a user is muted THEN the Reputation System SHALL decrease their reputation by 100 points
4. WHEN a user's message is deleted by moderation THEN the Reputation System SHALL decrease their reputation by 10 points
5. WHEN a user receives a "thank you" reaction from another user THEN the Reputation System SHALL increase their reputation by 5 points
6. WHEN a user wins a tournament THEN the Reputation System SHALL increase their reputation by 20 points
7. WHEN a user's reputation falls below 200 THEN the Reputation System SHALL automatically restrict the user to read-only mode until reputation recovers above 300
8. WHEN a user requests their profile THEN the Reputation System SHALL display current reputation score and recent reputation changes

### Requirement 5: TTS — Голосовые ответы Олега

**User Story:** As a chat member, I want Oleg to sometimes respond with voice messages, so that I can experience his "brutal" personality in audio form.

#### Acceptance Criteria

1. WHEN a user sends the command "/say <text>" THEN the TTS System SHALL generate a voice message with Oleg's characteristic voice and send it as a voice note
2. WHEN Oleg generates a text response THEN the TTS System SHALL have a 0.1% chance to convert the response to voice instead of text
3. WHEN generating voice THEN the TTS System SHALL use a consistent male voice profile that matches Oleg's personality
4. WHEN the TTS service is unavailable THEN the TTS System SHALL fall back to text response and log the error
5. WHEN generating voice for text longer than 500 characters THEN the TTS System SHALL truncate the text and add "...и так далее" at the end

### Requirement 6: Умный Пересказ (/summarize)

**User Story:** As a chat member, I want to quickly get a summary of long messages or articles, so that I can understand the main points without reading everything.

#### Acceptance Criteria

1. WHEN a user replies to a message with "/tl;dr" or "/summary" THEN the Summarize System SHALL analyze the original message and generate a 2-sentence summary in Oleg's style
2. WHEN summarizing content THEN the Summarize System SHALL preserve the key information while adding Oleg's characteristic commentary
3. WHEN the original message contains a link to an article THEN the Summarize System SHALL attempt to fetch and summarize the article content
4. WHEN summarization is complete THEN the Summarize System SHALL offer to voice the summary using TTS with an inline button
5. IF the content is too short (less than 100 characters) THEN the Summarize System SHALL respond with "Тут и так всё понятно, чё пересказывать?"

### Requirement 7: Генератор Цитат (/q) — Улучшенный рендеринг

**User Story:** As a chat member, I want to create beautiful quote images from messages, so that I can preserve memorable moments in a visually appealing format.

#### Acceptance Criteria

1. WHEN a user replies to a message with "/q" THEN the Quote Generator SHALL render an image with the message text, sender's avatar, username, and timestamp
2. WHEN rendering a quote THEN the Quote Generator SHALL support gradient backgrounds and automatically select dark or light theme based on chat settings
3. WHEN a user replies with "/q [N]" where N is a number THEN the Quote Generator SHALL render a chain of N consecutive messages (maximum 10)
4. WHEN a user replies with "/q *" THEN the Quote Generator SHALL render the quote with an LLM-generated roast comment from Oleg at the bottom
5. WHEN rendering quotes THEN the Quote Generator SHALL produce images in WebP format optimized for Telegram stickers (512x512 max dimension)
6. WHEN a quote image is created THEN the Quote Generator SHALL store the image data and metadata in the quotes table for potential sticker pack inclusion

### Requirement 8: Стикерпаки — Автоматическое управление

**User Story:** As a chat member, I want to add quotes to a shared sticker pack, so that I can use memorable quotes as stickers in conversations.

#### Acceptance Criteria

1. WHEN a user replies to a quote image with "/qs" THEN the Sticker Pack System SHALL add the quote to the current chat's sticker pack
2. WHEN the current sticker pack reaches 120 stickers THEN the Sticker Pack System SHALL automatically create a new pack with incremented version number and switch to it
3. WHEN adding a sticker THEN the Sticker Pack System SHALL validate the image format and resize if necessary to meet Telegram requirements
4. WHEN a sticker is added THEN the Sticker Pack System SHALL update the quote record with the sticker file ID
5. WHEN an administrator replies to a sticker with "/qd" THEN the Sticker Pack System SHALL remove the sticker from the pack and update the database

### Requirement 9: Живые Цитаты (Golden Fund)

**User Story:** As a chat member, I want the best quotes to be automatically collected and occasionally used by Oleg, so that memorable moments are preserved and resurface naturally.

#### Acceptance Criteria

1. WHEN a quote sticker receives 5 or more fire/thumbs-up reactions THEN the Golden Fund System SHALL mark the quote as part of the Golden Fund
2. WHEN Oleg generates a response THEN the Golden Fund System SHALL have a 5% chance to search the Golden Fund for a contextually relevant quote using RAG
3. WHEN a relevant Golden Fund quote is found THEN the Golden Fund System SHALL respond with the quote sticker instead of generating new text
4. WHEN searching for relevant quotes THEN the Golden Fund System SHALL use semantic similarity between the current message and stored quote texts
5. WHEN a quote enters the Golden Fund THEN the Golden Fund System SHALL notify the chat with a celebratory message

### Requirement 10: Турниры — Периодические соревнования

**User Story:** As a chat member, I want to participate in regular tournaments, so that I can compete with others and earn rewards.

#### Acceptance Criteria

1. WHEN a new day begins (00:00 UTC) THEN the Tournament System SHALL start a new Daily tournament tracking /grow gains, /pvp wins, and /roulette survival streaks
2. WHEN a new week begins (Monday 00:00 UTC) THEN the Tournament System SHALL start a new Weekly tournament and finalize the previous week's results
3. WHEN a new month begins THEN the Tournament System SHALL start a Grand Cup tournament and finalize the previous month's results
4. WHEN a tournament ends THEN the Tournament System SHALL announce top 3 winners in each discipline and award reputation points
5. WHEN displaying tournament standings THEN the Tournament System SHALL show current rankings with "/tournament" command
6. WHEN a user wins a tournament THEN the Tournament System SHALL record the achievement in their profile

### Requirement 11: Ранги и Лиги — ELO система

**User Story:** As a competitive player, I want to be ranked in leagues based on my performance, so that I can see my progress and compete with players of similar skill.

#### Acceptance Criteria

1. WHEN a new user starts playing THEN the League System SHALL assign them to Scrap League (🥉) with initial ELO of 1000
2. WHEN a user's ELO reaches 1200 THEN the League System SHALL promote them to Silicon League (🥈)
3. WHEN a user's ELO reaches 1500 THEN the League System SHALL promote them to Quantum League (🥇)
4. WHEN a user reaches top 10 on the server THEN the League System SHALL promote them to Oleg's Elite (💎)
5. WHEN a season ends (monthly) THEN the League System SHALL award unique achievements to top players and apply growth multipliers for the next season
6. WHEN calculating ELO changes THEN the League System SHALL use standard ELO formula with K-factor of 32 for games
7. WHEN displaying user profile THEN the League System SHALL show current league, ELO rating, and progress to next league

### Requirement 12: Живые Системные Уведомления (Alive UI)

**User Story:** As a chat member, I want to see entertaining status messages while waiting for bot responses, so that the waiting time feels engaging rather than boring.

#### Acceptance Criteria

1. WHEN Oleg starts processing a request that takes more than 2 seconds THEN the Alive UI System SHALL send an initial status message with a random phrase from the pool
2. WHILE processing continues THEN the Alive UI System SHALL update the status message every 3 seconds with a new random phrase
3. WHEN analyzing a photo THEN the Alive UI System SHALL use photo-specific phrases like "👀 Разглядываю твои пиксели..."
4. WHEN performing moderation checks THEN the Alive UI System SHALL use moderation-specific phrases like "🔨 Достаю банхаммер..."
5. WHEN processing completes THEN the Alive UI System SHALL delete the status message and send the actual response
6. WHEN an error occurs during processing THEN the Alive UI System SHALL update the status message with an error phrase and explanation

### Requirement 13: Дейлики — Запланированные сообщения

**User Story:** As a chat administrator, I want the bot to send daily summaries and quotes, so that the chat stays active and members are informed about daily events.

#### Acceptance Criteria

1. WHEN the time reaches 09:00 Moscow time THEN the Dailies System SHALL send a #dailysummary message with a digest of yesterday's events (top messages, new members, moderation actions)
2. WHEN the time reaches 21:00 Moscow time THEN the Dailies System SHALL send a #dailyquote message with a wisdom quote (either from Golden Fund or generated)
3. WHEN the time reaches 21:00 Moscow time THEN the Dailies System SHALL send a #dailystats message with game statistics (top growers, top losers, tournament standings)
4. WHEN sending daily messages THEN the Dailies System SHALL respect chat-specific settings for enabled/disabled daily messages
5. WHEN a chat has no activity for the day THEN the Dailies System SHALL skip the summary and send only the quote

### Requirement 14: Архитектура — Worker для тяжёлых задач

**User Story:** As a system administrator, I want heavy tasks to be processed asynchronously, so that the main bot remains responsive.

#### Acceptance Criteria

1. WHEN a TTS generation request is received THEN the Architecture System SHALL queue the task to the Worker process via Redis
2. WHEN a quote rendering request is received THEN the Architecture System SHALL queue the task to the Worker process
3. WHEN a GIF analysis request is received THEN the Architecture System SHALL queue the task to the Worker process
4. WHEN a Worker task completes THEN the Architecture System SHALL notify the main bot process to send the result to the user
5. WHEN a Worker task fails THEN the Architecture System SHALL retry up to 3 times with exponential backoff before reporting failure
6. WHEN the Worker queue exceeds 100 pending tasks THEN the Architecture System SHALL log a warning and notify administrators

### Requirement 15: Уведомления для владельца чата и советы

**User Story:** As a chat owner, I want to automatically receive notifications about important moderation events and get actionable advice, so that I can stay informed and improve chat management without manual checks.

#### Acceptance Criteria

1. WHEN Raid Mode is automatically activated THEN the Notification System SHALL automatically send a private message to the chat owner with details about the raid attempt
2. WHEN a user is banned for inappropriate content THEN the Notification System SHALL automatically notify the chat owner with the reason and evidence
3. WHEN the chat's average toxicity level increases significantly (more than 20% over 24 hours) THEN the Notification System SHALL automatically send a warning to the chat owner with suggested actions
4. WHEN a new DEFCON level is recommended based on chat activity patterns THEN the Notification System SHALL automatically suggest the change to the chat owner with explanation
5. WHEN the bot detects repeated violations from the same user THEN the Notification System SHALL automatically advise the chat owner to consider permanent action
6. WHEN daily statistics are generated THEN the Notification System SHALL automatically include personalized tips for improving chat health based on detected patterns
7. WHEN a chat owner requests advice with "/советы" or "/tips" THEN the Notification System SHALL analyze recent chat activity and provide 3-5 actionable recommendations
8. WHEN a chat is registered THEN the Notification System SHALL enable all automatic notifications by default

### Requirement 16: Админ-панель для владельцев групп (только в ЛС)

**User Story:** As a chat owner, I want an admin panel in private messages with the bot to configure all bot settings, so that I can easily manage moderation, notifications, and features securely without exposing settings in the group chat.

#### Acceptance Criteria

1. WHEN a chat owner sends "/admin" in private messages to the bot THEN the Admin Panel SHALL display a list of chats where the user is owner with inline buttons to select a chat
2. WHEN the owner selects a chat THEN the Admin Panel SHALL display an inline keyboard menu with main configuration categories for that chat
3. WHEN the Admin Panel is opened THEN the Admin Panel SHALL show categories: Protection (DEFCON), Notifications, Games, Dailies, Quotes, and Advanced Settings
4. WHEN the owner selects "Protection" THEN the Admin Panel SHALL display current DEFCON level with buttons to change it and toggle individual features (anti-spam, profanity filter, sticker limit, etc.)
5. WHEN the owner selects "Notifications" THEN the Admin Panel SHALL display toggles for each notification type (raid alerts, ban notifications, toxicity warnings, daily tips) with current status
6. WHEN the owner selects "Games" THEN the Admin Panel SHALL display toggles for enabling/disabling game commands and tournament participation
7. WHEN the owner selects "Dailies" THEN the Admin Panel SHALL display toggles for morning summary, evening quote, and daily stats with time configuration
8. WHEN the owner selects "Quotes" THEN the Admin Panel SHALL display settings for quote themes (dark/light/auto), Golden Fund participation, and sticker pack management
9. WHEN the owner changes any setting THEN the Admin Panel SHALL immediately apply the change and confirm with an updated menu
10. WHEN a user tries to access the Admin Panel for a chat they do not own THEN the Admin Panel SHALL respond with "У вас нет прав на управление этим чатом"
11. WHEN the owner selects "Advanced Settings" THEN the Admin Panel SHALL display toxicity threshold slider, mute durations, and custom banned words management
12. WHEN "/admin" is sent in a group chat THEN the Admin Panel SHALL respond with "Админка доступна только в личных сообщениях. Напиши мне в ЛС: @OlegBot"

### Requirement 17: Безопасность бота

**User Story:** As a system administrator, I want the bot to be protected against common attack vectors and abuse, so that malicious users cannot exploit vulnerabilities or disrupt service.

#### Acceptance Criteria

1. WHEN processing any user input THEN the Security System SHALL sanitize all strings to prevent injection attacks (SQL, command injection, XSS in rendered content)
2. WHEN a user sends more than 30 messages per minute THEN the Security System SHALL temporarily ignore messages from that user for 5 minutes (rate limiting)
3. WHEN a callback query is received THEN the Security System SHALL validate that the callback data matches expected format and the user has permission to perform the action
4. WHEN processing file uploads THEN the Security System SHALL validate file type, size (max 20MB), and scan for malicious content before processing
5. WHEN storing sensitive data THEN the Security System SHALL encrypt user tokens and API keys at rest using environment-configured encryption key
6. WHEN an admin command is received THEN the Security System SHALL verify the user's admin status in real-time from Telegram API, not just from cached database
7. WHEN the bot detects potential abuse patterns (repeated failed auth attempts, mass command spam) THEN the Security System SHALL temporarily blacklist the user and alert system administrators
8. WHEN processing deep links or external URLs THEN the Security System SHALL validate URL format and block known malicious domains
9. WHEN handling errors THEN the Security System SHALL log detailed information internally but return only generic error messages to users to prevent information disclosure
10. WHEN a user attempts to access another user's private data THEN the Security System SHALL deny access and log the attempt as a potential security incident
11. WHEN the bot starts THEN the Security System SHALL validate all environment variables and refuse to start if critical security configurations are missing
12. WHEN processing inline keyboard callbacks THEN the Security System SHALL include HMAC signature in callback data to prevent tampering



### Requirement 18: Документация и README

**User Story:** As a developer or new user, I want comprehensive and up-to-date documentation, so that I can understand, deploy, and use all bot features effectively.

#### Acceptance Criteria

1. WHEN the Fortress Update is complete THEN the Documentation System SHALL update README.md with all new features, commands, and configuration options
2. WHEN updating README THEN the Documentation System SHALL include a visually appealing header with bot logo/banner and feature highlights
3. WHEN documenting features THEN the Documentation System SHALL organize content into clear sections: Features, Installation, Configuration, Commands, Admin Panel, API, and Contributing
4. WHEN documenting commands THEN the Documentation System SHALL provide examples with expected output for each command
5. WHEN documenting the Admin Panel THEN the Documentation System SHALL include screenshots or diagrams of the menu structure
6. WHEN documenting security features THEN the Documentation System SHALL include a dedicated Security section with best practices
7. WHEN the update is complete THEN the Documentation System SHALL update CHANGELOG.md with all changes in v6.0 following Keep a Changelog format
8. WHEN the update is complete THEN the Documentation System SHALL create a git commit with message "feat: OLEG v6.0 Fortress Update" including all changes
9. WHEN documenting DEFCON levels THEN the Documentation System SHALL include a table comparing features enabled at each level
10. WHEN documenting the bot THEN the Documentation System SHALL include badges for Python version, license, and build status in README
