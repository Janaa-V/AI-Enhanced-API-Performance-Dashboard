"""Application-owned asynchronous PostgreSQL connections and request sessions."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings


def build_database_url(settings: Settings) -> URL:
    """Build the connection URL; shared by the application and Alembic migrations."""
    if not settings.db_password.get_secret_value():
        raise ValueError("Set DB_PASSWORD in backend/.env before starting the backend.")
    return URL.create(
        "postgresql+psycopg",
        username=settings.db_user,
        password=settings.db_password.get_secret_value(),
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
    )


class Database:
    def __init__(self, settings: Settings) -> None:
        self.engine = create_async_engine(
            build_database_url(settings), pool_pre_ping=True, connect_args={"connect_timeout": 5}
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def check_connection(self) -> None:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self.engine.dispose()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Provide an isolated session; callers explicitly commit successful writes."""
    async with request.app.state.database.sessions() as session:
        yield session
