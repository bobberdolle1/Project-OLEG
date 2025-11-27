# Qwen Project Context: Олег Telegram Bot

## Project Overview

"Олег" is a multifunctional Telegram bot with AI capabilities, moderation tools, and game mechanics. The bot features a distinctive personality based on a gruff but helpful character named Oleg. It's designed for tech-focused chats, particularly those centered around hardware, overclocking, Steam Deck, and gaming.

### Core Features

1. **AI-Powered Q&A**: Responds to questions in Oleg's distinctive gruff, direct personality using local Ollama models
2. **Daily Summaries**: Automatically generates daily chat summaries (#dailysummary) at 08:00 MSK
3. **Creative Content**: Generates random creative content (stories, quotes, jokes, poems) at 20:00 MSK
4. **Game Mechanics**: 
   - `/grow` command to grow a virtual "penis" (random 1-20cm)
   - `/top` to show leaderboards
   - `/pvp` for duels between users
   - `/casino` for slot games
5. **Moderation Tools**: Ban, mute, kick commands for admins
6. **Anti-Raid Protection**: Detects and mitigates raid attempts
7. **Advanced Game Systems**: Achievements, trading, auctions, guilds, team wars, quests, and duo systems

### Tech Stack

- **Backend**: Python 3.10+ with asyncio
- **Telegram Framework**: aiogram v3
- **Database**: SQLAlchemy async with SQLite (with PostgreSQL support)
- **AI**: Ollama with local language model inference
- **Scheduling**: APScheduler for periodic tasks
- **Containerization**: Docker and Docker Compose
- **Caching**: TTL cache for Ollama responses
- **Logging**: Custom rotating file logger with console output

## Architecture

The application follows a modular, well-structured architecture:

### Core Components

- **`app/main.py`**: Main entry point, initializes bot, dispatcher, middleware, and routers
- **`app/config.py`**: Configuration management via environment variables
- **`app/logger.py`**: Rotating file logging with console output
- **`app/database/`**: SQLAlchemy models and session management
- **`app/handlers/`**: Message handlers separated by functionality
- **`app/middleware/`**: Custom aiogram middleware for logging, spam filtering, toxicity analysis
- **`app/services/`**: Business logic including Ollama client, content generation
- **`app/jobs/`**: Scheduled tasks for daily summaries, content generation, game mechanics

### Database Models

The application uses a comprehensive set of SQLAlchemy models:
- **User Management**: Users, profiles, status tracking
- **Game Systems**: Stats, wallet, achievements, quests
- **Social Features**: Guilds, teams, duos, wars
- **Economy System**: Trading, auctions, currency
- **Content**: Message logs, question history
- **Moderation**: Spam patterns, warnings, toxicity analysis

### Key Features Implementation

#### Q&A System
The Q&A system uses the Ollama API to generate responses in Oleg's distinctive personality. It includes retry logic, caching, and toxicity analysis. The bot responds when mentioned or when replying to its messages.

#### Content Generation
The bot automatically generates daily summaries and creative content using AI. Summaries identify trending topics and links, while creative content includes random stories, quotes, jokes, and poems featuring active chat participants.

#### Game Mechanics
The game system is extensive, featuring:
- Personal stats (size, reputation, wins)
- Economy system with virtual currency
- Social elements (guilds, duos, team wars)
- Achievement and quest systems
- Trading and auction systems

## Building and Running

### Docker Compose (Recommended)

```bash
# Copy environment file
cp .env.docker .env

# Edit configuration (TELEGRAM_BOT_TOKEN, PRIMARY_CHAT_ID)
nano .env

# Run services
docker-compose up -d

# View logs
docker-compose logs -f oleg-bot
```

### Poetry (Development)

```bash
# Install dependencies
poetry install

# Activate virtual environment
poetry shell

# Copy and configure environment
cp .env.example .env
nano .env

# Run the bot
poetry run python -m app.main
```

### Pip (Alternative)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
nano .env

# Run
python -m app.main
```

## Development Conventions

1. **Modularity**: Code is organized into distinct modules for handlers, services, middleware, and database models
2. **Async/Await**: All I/O operations are asynchronous
3. **Configuration**: All settings loaded from environment variables via the Settings dataclass
4. **Database**: Async SQLAlchemy sessions with proper error handling
5. **Error Handling**: Retry mechanisms for external API calls
6. **Code Quality**: Type hints, documentation, and organized imports

## Environment Variables

Key configuration variables include:
- `TELEGRAM_BOT_TOKEN`: Bot token from @BotFather
- `PRIMARY_CHAT_ID`: Target chat ID
- `SUMMARY_TOPIC_ID`: Topic for daily summaries
- `OLLAMA_BASE_URL`: Ollama server URL
- `OLLAMA_MODEL`: AI model name
- `DATABASE_URL`: Database connection string
- `LOG_LEVEL`: Logging level (DEBUG/INFO/WARNING/ERROR)

## Deployment and Production

The project includes Docker and systemd service configurations for production deployment. The architecture supports PostgreSQL for scaling and includes health checks for containerized deployment.

## Current Status

The bot is an active project with extensive features already implemented, including AI integration, games, moderation, and social systems. The technical specification outlines additional features to be implemented including the Quote module, enhanced admin panel, content downloader, and adaptive personality based on chat toxicity.