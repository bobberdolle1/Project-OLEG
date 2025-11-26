# Gemini Project File: Oleg Telegram Bot

This document provides a comprehensive overview of the "Oleg" Telegram bot project, intended to be used as instructional context for Gemini.

## Project Overview

"Oleg" is a multifunctional AI-powered Telegram bot with a unique personality, extensive moderation tools, and a rich set of interactive game mechanics. The bot is designed to be a helpful and entertaining assistant for Telegram chats, particularly those focused on technology, computer hardware, and gaming.

### Core Technologies

*   **Backend:** Python 3.10+
*   **Telegram Bot Framework:** `aiogram` v3
*   **Database:** SQLAlchemy (async) with support for SQLite and PostgreSQL.
*   **AI Integration:** Ollama for local language model inference.
*   **Scheduling:** `APScheduler` for running periodic tasks like daily summaries and content generation.
*   **Containerization:** Docker and Docker Compose for easy deployment and service management.

### Architecture

The project follows a modular and well-structured architecture:

*   **`app/main.py`:** The main entry point of the application, responsible for initializing the bot, dispatcher, middleware, and routers.
*   **`app/config.py`:** Manages all application settings loaded from environment variables (`.env` file).
*   **`app/database/`:** Contains all database-related code, including SQLAlchemy ORM models (`models.py`) and session management (`session.py`).
*   **`app/handlers/`:** A directory containing multiple handler modules, each responsible for a specific set of commands (e.g., `qna.py`, `games.py`, `moderation.py`). This promotes separation of concerns.
*   **`app/middleware/`:** Contains custom `aiogram` middleware for tasks like logging all incoming messages and filtering spam.
*   **`app/services/`:** Houses the business logic, such as the Ollama API client, profile data aggregation, and game mechanic calculations (e.g., ELO rating).
*   **`app/jobs/`:** Manages scheduled tasks, such as generating daily chat summaries, creating content, and managing the lifecycle of in-game events like auctions and wars.

## Building and Running

### Docker Compose (Recommended)

1.  **Copy Environment File:**
    ```bash
    cp .env.docker .env
    ```
2.  **Edit Configuration:** Add your `TELEGRAM_BOT_TOKEN` and `PRIMARY_CHAT_ID` to the `.env` file.
3.  **Run Services:**
    ```bash
    docker-compose up -d
    ```
4.  **View Logs:**
    ```bash
    docker-compose logs -f oleg-bot
    ```

### Local Development (Poetry)

1.  **Install Dependencies:**
    ```bash
    poetry install
    ```
2.  **Activate Virtual Environment:**
    ```bash
    poetry shell
    ```
3.  **Copy and Edit Configuration:**
    ```bash
    cp .env.example .env
    nano .env
    ```
4.  **Run the Bot:**
    ```bash
    poetry run python -m app.main
    ```

## Development Conventions

*   **Modularity:** The codebase is organized into distinct modules for handlers, services, middleware, and database models. This pattern should be followed when adding new features.
*   **Asynchronous:** The entire application is built on `asyncio`, and all I/O operations (database, API calls) are asynchronous.
*   **Configuration:** All configuration is managed through the `Settings` dataclass in `app/config.py`, which loads values from environment variables. No hardcoded secrets or settings should be added.
*   **Database:** Database interactions are performed using the SQLAlchemy ORM. Handlers and services are responsible for acquiring their own async session from `app.database.session.get_session()`.
*   **Error Handling:** The Ollama client includes a retry mechanism and proper exception handling. This pattern should be replicated for any other external API integrations.
*   **Testing:** While not yet implemented, the project structure is amenable to unit and integration tests. The `pytest` framework and its async extension are included in the development dependencies.
