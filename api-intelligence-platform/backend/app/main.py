"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import router as api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.security import get_password_hash
from app.db.database import AsyncSessionLocal, init_db
from app.db.neo4j import init_neo4j_schema, neo4j_driver
from app.models.user import Organization, User

logger = get_logger(__name__)


async def _ensure_dev_seed_data(db: AsyncSession) -> None:
    """Create default organization and users for local development."""
    result = await db.execute(
        select(Organization).where(Organization.slug == "demo-org")
    )
    org = result.scalar_one_or_none()
    if org is None:
        org = Organization(name="Demo Organization", slug="demo-org", plan="free")
        db.add(org)
        await db.flush()

    users_to_seed = [
        ("admin@demo.com", "demo1234", "Demo Admin"),
        ("admin@example.com", "Admin@123", "Platform Admin"),
    ]
    for email, password, full_name in users_to_seed:
        existing_user = await db.execute(select(User).where(User.email == email))
        if existing_user.scalar_one_or_none() is None:
            db.add(
                User(
                    email=email,
                    hashed_password=get_password_hash(password),
                    full_name=full_name,
                    role="admin",
                    org_id=org.id,
                    is_active=True,
                )
            )
    await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    configure_logging()
    logger.info("Starting API Intelligence backend")

    await init_db()
    async with AsyncSessionLocal() as db:
        await _ensure_dev_seed_data(db)

    try:
        await neo4j_driver.connect()
        await init_neo4j_schema()
    except Exception as exc:
        logger.warning("Neo4j startup skipped", error=str(exc))

    yield

    try:
        await neo4j_driver.close()
    except Exception as exc:
        logger.warning("Neo4j shutdown warning", error=str(exc))


app = FastAPI(
    title="API Intelligence Platform Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health")
async def api_health() -> dict[str, str]:
    return {"status": "ok"}


# Frontend currently calls /api/*. Keep /api/v1/* compatibility too.
app.include_router(api_router, prefix="/api", tags=["api"])
app.include_router(api_router, prefix="/api/v1", tags=["api-v1"])
