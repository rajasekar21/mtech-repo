"""Async SQLAlchemy database engine and session factory."""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
async_engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.is_development,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# --------------------------------------------------------------------------- #
# Declarative base
# --------------------------------------------------------------------------- #
class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# --------------------------------------------------------------------------- #
# FastAPI dependency
# --------------------------------------------------------------------------- #
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session and close it when the request is done."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# --------------------------------------------------------------------------- #
# Initialisation
# --------------------------------------------------------------------------- #
async def init_db() -> None:
    """Create all tables that are registered with Base.metadata.

    This is called once at application startup. In production, prefer using
    Alembic migrations instead.
    """
    # Import all models so metadata is populated before create_all
    import app.models.user  # noqa: F401
    import app.models.api_spec  # noqa: F401
    import app.models.knowledge  # noqa: F401

    # Try to enable pgvector separately so a missing extension does not poison
    # the metadata creation transaction on developer machines.
    try:
        async with async_engine.connect() as conn:
            autocommit_conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
            await autocommit_conn.execute(
                __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector")
            )
            logger.info("pgvector extension ensured")
    except Exception as exc:
        logger.warning("Could not create pgvector extension", error=str(exc))

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialised")
