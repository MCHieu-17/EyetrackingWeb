from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models.registry  # noqa: F401 - load all models before mapper configuration
from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_min,
    max_overflow=max(0, settings.db_pool_max - settings.db_pool_min),
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=1800,
    pool_use_lifo=True,
    connect_args={
        "prepared_statement_cache_size": settings.db_prepared_statement_cache_size,
        "statement_cache_size": settings.db_prepared_statement_cache_size,
        "server_settings": {
            "application_name": "eyelearning-backend",
            "statement_timeout": str(settings.db_statement_timeout_ms),
            "lock_timeout": "5000",
        },
    },
)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
