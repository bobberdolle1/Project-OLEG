"""Pytest configuration and fixtures."""

import pytest
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database.session import Base


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Create test database."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    
    yield session_maker
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
def mock_telegram_user():
    """Mock Telegram user object."""
    class MockUser:
        id = 12345
        username = "testuser"
        first_name = "Test"
        last_name = "User"
        is_bot = False
    
    return MockUser()


@pytest.fixture
def mock_telegram_message(mock_telegram_user):
    """Mock Telegram message object."""
    class MockMessage:
        message_id = 1
        from_user = mock_telegram_user
        text = "Test message"
        
        class Chat:
            id = 67890
            type = "private"
        
        chat = Chat()
        
        async def reply(self, text, **kwargs):
            return text
        
        async def answer(self, text, **kwargs):
            return text
    
    return MockMessage()
