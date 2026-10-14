from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    if url.startswith("sqlite:///") and not url.startswith("sqlite+aiosqlite:///"):
        return "sqlite+aiosqlite:///" + url.removeprefix("sqlite:///")
    return url


settings = get_settings()
database_url = _normalize_database_url(settings.database_url)
engine = create_async_engine(database_url, echo=settings.debug, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
