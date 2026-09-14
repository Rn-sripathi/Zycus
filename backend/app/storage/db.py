"""Postgres connection pool.

Targets Neon, which imposes two constraints the defaults get wrong:

- The ``-pooler`` host runs pgbouncer in transaction mode, where asyncpg's
  prepared-statement cache breaks with "prepared statement already exists".
  ``statement_cache_size=0`` disables it.
- The connection string carries ``sslmode``/``channel_binding`` query parameters,
  which are libpq options that asyncpg does not interpret. They are stripped and
  TLS is configured explicitly instead.

Persistence is optional. With no DATABASE_URL configured the pool stays closed and
the application runs exactly as it did before, which keeps the test suite offline.
"""

from __future__ import annotations

import logging
import ssl
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg

from app.config import get_settings

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

_pool: asyncpg.Pool | None = None


def _clean_dsn(dsn: str) -> str:
    """Drop libpq-only query parameters asyncpg would reject."""
    parts = urlsplit(dsn)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


async def connect() -> asyncpg.Pool | None:
    """Open the pool and apply the schema. Returns None when not configured."""
    global _pool

    settings = get_settings()
    if not settings.database_url.strip():
        logger.info("No DATABASE_URL set; running without persistence")
        return None

    if _pool is not None:
        return _pool

    _pool = await asyncpg.create_pool(
        _clean_dsn(settings.database_url),
        ssl=ssl.create_default_context(),
        statement_cache_size=0,  # required behind pgbouncer
        min_size=1,
        max_size=settings.database_pool_size,
        command_timeout=30,
    )

    async with _pool.acquire() as connection:
        await connection.execute(SCHEMA_PATH.read_text(encoding="utf-8"))

    logger.info("Postgres pool ready (%s connections max)", settings.database_pool_size)
    return _pool


async def disconnect() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Postgres pool closed")


def get_pool() -> asyncpg.Pool | None:
    """The live pool, or None when persistence is disabled."""
    return _pool


def is_enabled() -> bool:
    return _pool is not None
