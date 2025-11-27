"""Модуль бота Олег (Версия 3.0)."""

__version__ = "3.0.0"
__author__ = "Oleg Bot Development Team"
__maintainer__ = "Oleg"
__email__ = "oleg@example.com"
__status__ = "production"

# Импорты для удобства использования
from .main import main
from .config import settings
from .database.session import get_session
from .handlers import qna, games, moderation, achievements, trading, auctions, quests, guilds, team_wars, duos, statistics, quotes, vision, random_responses
from .handlers.private_admin import router as private_admin_router
from .handlers.chat_join import router as chat_join_router
from .handlers.admin_commands import router as admin_commands_router
from .services.content_downloader import router as content_downloader_router
from .handlers.quotes import reactions_router
from .handlers import antiraid