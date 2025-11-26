import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.logger import setup_logging
from app.database.session import init_db
from app.handlers import qna, games, moderation, achievements, trading, auctions, quests, guilds, team_wars, duos, statistics
from app.handlers import antiraid
from app.middleware.logging import MessageLoggerMiddleware
from app.middleware.spam_filter import SpamFilterMiddleware, load_spam_patterns
from app.middleware.toxicity_analysis import ToxicityAnalysisMiddleware
from app.jobs.scheduler import setup_scheduler

# Инициализировать логирование
setup_logging()
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot, dp: Dispatcher):
    """Действия при запуске бота."""
    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("База данных инициализирована")

    logger.info("Настройка планировщика задач...")
    await setup_scheduler(bot)
    logger.info("Планировщик запущен")

    logger.info("Загрузка спам-паттернов...")
    await load_spam_patterns()
    logger.info("Спам-паттерны загружены")


def build_dp() -> Dispatcher:
    """Построить диспетчер с обработчиками."""
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(MessageLoggerMiddleware())
    dp.message.middleware(SpamFilterMiddleware())
    dp.message.middleware(ToxicityAnalysisMiddleware())

    # Routers
    dp.include_routers(
        games.router,
        moderation.router,
        antiraid.router,
        qna.router,
        achievements.router,
        trading.router,
        auctions.router,
        quests.router,
        guilds.router,
        team_wars.router,
        duos.router,
        statistics.router,
    )
    return dp


async def main():
    """Главная функция бота."""
    logger.info(f"Начало запуска бота. Модель: {settings.ollama_model}")

    if not settings.bot_token:
        logger.error("TELEGRAM_BOT_TOKEN не установлен!")
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    bot = Bot(token=settings.bot_token, parse_mode=ParseMode.HTML)
    dp = build_dp()

    await on_startup(bot, dp)

    logger.info("Бот начинает polling...")
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    finally:
        await bot.session.close()
        logger.info("Сессия бота закрыта")


if __name__ == "__main__":
    asyncio.run(main())
