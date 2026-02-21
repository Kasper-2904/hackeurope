"""Shared test fixtures."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.storage.database import Base

# In-memory SQLite for tests
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session() -> AsyncSession:
    """Provide a clean async DB session backed by an in-memory SQLite database."""
    engine = create_async_engine(TEST_DB_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()
