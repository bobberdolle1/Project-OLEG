import os
import pathlib
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncEngine, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


class Base(DeclarativeBase):
    pass

_engine: AsyncEngine | None = None
_async_session: async_sessionmaker[AsyncSession] | None = None


def _ensure_data_dir():
    if settings.database_url.startswith("sqlite"):
        path = pathlib.Path("data")
        path.mkdir(parents=True, exist_ok=True)


async def init_db():
    global _engine, _async_session
    _ensure_data_dir()
    _engine = create_async_engine(settings.database_url, echo=False, future=True)
    _async_session = async_sessionmaker(_engine, expire_on_commit=False)

    # import models and create tables
    from . import models  # noqa: F401
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_session() -> async_sessionmaker[AsyncSession]:
    assert _async_session is not None, "DB is not initialized"
    return _async_session


def async_session() -> AsyncSession:
    """Контекстный менеджер для получения сессии БД.
    
    Использование:
        async with async_session() as session:
            ...
    """
    assert _async_session is not None, "DB is not initialized"
    return _async_session()
