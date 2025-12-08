import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.logger import setup_logging
from app.database.session import init_db
from app.handlers import qna, games, moderation, achievements, trading, auctions, quests, guilds, team_wars, duos, statistics, quotes, vision, random_responses, help
from app.handlers.game_hub import router as game_hub_router
from app.handlers.gif_patrol import router as gif_patrol_router
from app.handlers.tournaments import router as tournaments_router
from app.handlers.health import router as health_router
from app.handlers.private_admin import router as private_admin_router
from app.handlers.admin_dashboard import router as admin_dashboard_router
from app.handlers.chat_join import router as chat_join_router
from app.handlers.voice import router as voice_router
from app.handlers.summarizer import router as summarizer_router
from app.handlers.topic_listener import router as topic_listener_router
from app.handlers.challenges import router as challenges_router
from app.handlers.tips import router as tips_router
from app.handlers.blackjack import router as blackjack_router
from app.handlers.broadcast import router as broadcast_router
from app.services.content_downloader import router as content_downloader_router
from app.handlers.quotes import reactions_router
from app.handlers import antiraid
from app.middleware.logging import MessageLoggerMiddleware
from app.middleware.spam_filter import SpamFilterMiddleware, load_spam_patterns
from app.middleware.spam_control import SpamControlMiddleware
from app.middleware.mode_filter import ModeFilterMiddleware
from app.middleware.toxicity_analysis import ToxicityAnalysisMiddleware
from app.middleware.blacklist_filter import BlacklistMiddleware
from app.middleware.anti_click import AntiClickMiddleware
from app.jobs.scheduler import setup_scheduler

# Логгер будет инициализирован в main()
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot, dp: Dispatcher):
    """Действия при запуске бота."""
    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("База данных инициализирована")
    
    # Register command scopes for different chat types
    logger.info("Регистрация команд для разных типов чатов...")
    from app.services.command_scope import setup_commands
    if await setup_commands(bot):
        logger.info("Команды зарегистрированы для групп и ЛС")
    else:
        logger.warning("Не удалось зарегистрировать команды, используются значения по умолчанию")
    
    # Initialize Redis
    if settings.redis_enabled:
        logger.info("Подключение к Redis...")
        from app.services.redis_client import redis_client
        await redis_client.connect()
        
        # Configure rate limiter to use Redis
        from app.middleware.rate_limit import rate_limiter
        rate_limiter.set_redis_client(redis_client)
        logger.info("Redis подключен и настроен для rate limiting")
        
        # Configure StateManager to use Redis for game sessions (Requirements 2.x)
        from app.services.state_manager import state_manager
        state_manager.set_redis_client(redis_client)
        logger.info("StateManager настроен для использования Redis")

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

    # Инициализация Whisper для распознавания голосовых
    if settings.voice_recognition_enabled:
        logger.info("Инициализация Whisper для распознавания голосовых...")
        from app.services.voice_recognition import init_whisper
        if await init_whisper():
            logger.info("Whisper инициализирован")
        else:
            logger.warning("Whisper не удалось инициализировать, распознавание голосовых недоступно")

    # Preload Silero TTS model for /say command (works offline in Russia)
    logger.info("Предзагрузка Silero TTS модели...")
    try:
        from app.services.tts_silero import silero_tts_service
        # Trigger async model load
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: silero_tts_service._preload_model())
        if silero_tts_service.is_available:
            logger.info("Silero TTS модель загружена")
        else:
            logger.warning("Silero TTS недоступен, /say будет возвращать текст")
    except Exception as e:
        logger.warning(f"Не удалось загрузить Silero TTS: {e}")

    # Initialize Arq worker pool for heavy tasks
    if settings.worker_enabled and settings.redis_enabled:
        logger.info("Инициализация Arq worker pool...")
        try:
            from app.worker import get_arq_pool
            pool = await get_arq_pool()
            if pool:
                logger.info("Arq worker pool инициализирован")
            else:
                logger.warning("Не удалось инициализировать Arq worker pool")
        except Exception as e:
            logger.warning(f"Ошибка инициализации Arq worker pool: {e}")

    # Start metrics server
    if settings.metrics_enabled:
        logger.info("Запуск сервера метрик...")
        from app.services.metrics_server import metrics_server
        await metrics_server.start()
        logger.info(f"Сервер метрик запущен на порту {settings.metrics_port}")


def build_dp() -> Dispatcher:
    """Построить диспетчер с обработчиками."""
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(MessageLoggerMiddleware())
    dp.message.middleware(BlacklistMiddleware())  # Middleware для проверки черного списка
    dp.message.middleware(ModeFilterMiddleware())  # Middleware для режимов модерации
    dp.message.middleware(SpamFilterMiddleware())
    dp.message.middleware(SpamControlMiddleware())  # Middleware для защиты от "дрючки"
    dp.message.middleware(ToxicityAnalysisMiddleware())
    
    # Rate limiting (should be one of the first middlewares)
    from app.middleware.rate_limit import RateLimitMiddleware
    dp.message.outer_middleware(RateLimitMiddleware())
    
    # Anti-click protection for game buttons (Requirements 3.x)
    dp.callback_query.middleware(AntiClickMiddleware())

    # Routers
    dp.include_routers(
        health_router,  # Health check должен быть первым для быстрого ответа
        help.router,  # Help должен быть вторым для приоритета
        game_hub_router,  # Game Hub UI (Requirements 1.x) - before games for /games priority
        challenges_router,  # PvP challenges with consent (Requirements 8.x)
        blackjack_router,  # Blackjack game (Requirements 9.x)
        tournaments_router,  # Tournament standings (Requirements 10.5)
        games.router,
        moderation.router,
        antiraid.router,
        voice_router,  # Роутер для голосовых сообщений (до qna, чтобы перехватить voice)
        summarizer_router,  # Роутер для пересказа контента (/tldr, /summary)
        tips_router,  # Роутер для советов владельцам чатов (/советы, /tips)
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
        gif_patrol_router,  # GIF Patrol - анализ GIF на запрещённый контент (до vision)
        vision.router,  # Роутер для обработки изображений
        random_responses.router,  # Роутер для рандомных ответов
        reactions_router,  # Роутер для обработки реакций
        content_downloader_router,  # Роутер для скачивания контента
        private_admin_router,  # Роутер для админ-панели в ЛС
        admin_dashboard_router,  # Роутер для расширенной админ-панели владельца (Requirements 7.x)
        broadcast_router,  # Broadcast wizard for admin announcements (Requirements 13.x)
        chat_join_router,  # Роутер для обработки событий добавления в чат
        topic_listener_router,  # Роутер для глобального слушателя топиков (RAG) - должен быть последним
    )
    return dp


async def main():
    """Главная функция бота."""
    logger.info(f"Начало запуска бота. Модель: {settings.ollama_model}")

    if not settings.bot_token:
        logger.error("TELEGRAM_BOT_TOKEN не установлен!")
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dp()

    await on_startup(bot, dp)

    logger.info("Бот начинает polling...")
    try:
        # Удаляем webhook и очищаем все накопившиеся обновления перед запуском
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook удален, pending updates очищены")
        
        # skip_updates=True - игнорируем старые сообщения при запуске
        await dp.start_polling(bot, skip_updates=True)
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
        
        # Stop metrics server
        if settings.metrics_enabled:
            logger.info("Остановка сервера метрик...")
            from app.services.metrics_server import metrics_server
            await metrics_server.stop()
            logger.info("Сервер метрик остановлен")

        # Close Arq worker pool
        if settings.worker_enabled and settings.redis_enabled:
            logger.info("Закрытие Arq worker pool...")
            try:
                from app.worker import close_arq_pool
                await close_arq_pool()
                logger.info("Arq worker pool закрыт")
            except Exception as e:
                logger.warning(f"Ошибка закрытия Arq worker pool: {e}")

        # Close Redis connection
        if settings.redis_enabled:
            logger.info("Закрытие соединения с Redis...")
            from app.services.redis_client import redis_client
            await redis_client.close()
            logger.info("Redis соединение закрыто")

        await bot.session.close()
        logger.info("Сессия бота закрыта")


if __name__ == "__main__":
    # Инициализировать логирование только при прямом запуске
    setup_logging()
    asyncio.run(main())
