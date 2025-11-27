import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.logger import setup_logging
from app.database.session import init_db
from app.handlers import qna, games, moderation, achievements, trading, auctions, quests, guilds, team_wars, duos, statistics, quotes, vision, random_responses
from app.handlers.private_admin import router as private_admin_router
from app.handlers.chat_join import router as chat_join_router
from app.handlers.admin_commands import router as admin_commands_router
from app.services.content_downloader import router as content_downloader_router
from app.handlers.quotes import reactions_router
from app.handlers import antiraid
from app.handlers.private_admin import router as private_admin_router
from app.handlers.chat_join import router as chat_join_router
from app.services.content_downloader import router as content_downloader_router
from app.middleware.logging import MessageLoggerMiddleware
from app.middleware.spam_filter import SpamFilterMiddleware, load_spam_patterns
from app.middleware.spam_control import SpamControlMiddleware
from app.middleware.mode_filter import ModeFilterMiddleware
from app.middleware.toxicity_analysis import ToxicityAnalysisMiddleware
from app.middleware.blacklist_filter import BlacklistMiddleware
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
    from app.middleware.spam_filter import load_spam_patterns, load_moderation_configs
    await load_spam_patterns()
    logger.info("Спам-паттерны загружены")

    logger.info("Загрузка конфигураций модерации...")
    await load_moderation_configs()
    logger.info("Конфигурации модерации загружены")

    logger.info("Запуск фоновой задачи для случайных сообщений...")
    from app.handlers.random_responses import schedule_random_messages
    # Создаем задачу для периодических случайных сообщений
    random_task = asyncio.create_task(schedule_random_messages(bot))
    # Храним задачу в dispatcher, чтобы можно было корректно завершить при выключении
    if not hasattr(dp, 'tasks'):
        dp.tasks = []
    dp.tasks.append(random_task)
    logger.info("Фоновая задача для случайных сообщений запущена")

    logger.info("Запуск воркеров загрузки контента...")
    from app.services.content_downloader import downloader
    await downloader.start_workers()
    logger.info("Воркеры загрузки контента запущены")


def build_dp() -> Dispatcher:
    """Построить диспетчер с обработчиками."""
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(MessageLoggerMiddleware())
    dp.message.middleware(BlacklistMiddleware())  # Middleware для проверки черного списка
    dp.message.middleware(ModeFilterMiddleware())  # Middleware для режимов модерации
    dp.message.middleware(SpamFilterMiddleware())
    dp.message.middleware(SpamControlMiddleware())  # Middleware для защиты от "дрючки"
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
        quotes.router,
        vision.router,  # Роутер для обработки изображений
        random_responses.router,  # Роутер для рандомных ответов
        admin_commands_router,  # Роутер для команд администратора
        reactions_router,  # Роутер для обработки реакций
        content_downloader_router,  # Роутер для скачивания контента
        private_admin_router,  # Роутер для админ-панели в ЛС
        chat_join_router,  # Роутер для обработки событий добавления в чат
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
        logger.info("Остановка фоновых задач...")
        # Отменяем все задачи, которые мы сохранили в dp
        if hasattr(dp, 'tasks'):
            for task in dp.tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass  # Ожидаемое поведение при отмене

        logger.info("Фоновые задачи остановлены")

        logger.info("Остановка воркеров загрузки контента...")
        from app.services.content_downloader import downloader
        await downloader.stop_workers()
        logger.info("Воркеры загрузки контента остановлены")

        await bot.session.close()
        logger.info("Сессия бота закрыта")


if __name__ == "__main__":
    asyncio.run(main())
