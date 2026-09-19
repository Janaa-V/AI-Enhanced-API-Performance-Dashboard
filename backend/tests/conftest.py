"""Shared fixtures.

Integration tests use a dedicated PostgreSQL database that is created on demand,
migrated once per test session, and emptied before every test. It is never the
development database.
"""

from collections.abc import AsyncIterator

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy import text

from app.config import BACKEND_ROOT, Settings
from app.database import Database, build_database_url


def _ensure_database_exists(settings: Settings) -> None:
    try:
        with psycopg.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password.get_secret_value(),
            dbname="postgres",
            autocommit=True,
            connect_timeout=5,
        ) as connection:
            exists = connection.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (settings.db_name,)
            ).fetchone()
            if not exists:
                connection.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(settings.db_name))
                )
    except psycopg.OperationalError as error:
        pytest.exit(
            f"PostgreSQL is not reachable at {settings.db_host}:{settings.db_port}; "
            f"start it and check DB_PASSWORD. ({error})",
            returncode=1,
        )


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    settings = Settings()
    # Safety guard: these tests empty tables, so only accept a clearly named test database.
    if not settings.test_db_name.endswith("_test"):
        pytest.exit(
            f"TEST_DB_NAME must end with '_test', got {settings.test_db_name!r}.", returncode=1
        )
    return settings.model_copy(update={"db_name": settings.test_db_name})


@pytest.fixture(scope="session")
def alembic_cfg(test_settings: Settings) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.attributes["database_url"] = build_database_url(test_settings)
    return config


@pytest.fixture(scope="session")
def migrated_database(test_settings: Settings, alembic_cfg: Config) -> Settings:
    """Create the test database if needed and bring its schema up to date once."""
    _ensure_database_exists(test_settings)
    command.upgrade(alembic_cfg, "head")
    return test_settings


@pytest.fixture
async def db(migrated_database: Settings) -> AsyncIterator[Database]:
    """A database handle whose tables are empty at the start of each test."""
    database = Database(migrated_database)
    async with database.engine.begin() as connection:
        await connection.execute(text("TRUNCATE request_logs RESTART IDENTITY"))
    try:
        yield database
    finally:
        await database.close()
