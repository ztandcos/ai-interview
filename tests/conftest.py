from __future__ import annotations

import math
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.redis import get_redis
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import (  # noqa: F401
    Interview,
    InterviewMessage,
    InterviewReport,
    RefreshToken,
    Resume,
    ResumeChunk,
    User,
)


class FakeRedis:
    def __init__(self) -> None:
        self._values: dict[str, tuple[str, float | None]] = {}

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool | None:
        self._purge_expired(key)
        if nx and key in self._values:
            return None

        expires_at = time.monotonic() + ex if ex is not None else None
        self._values[key] = (value, expires_at)
        return True

    async def ttl(self, key: str) -> int:
        self._purge_expired(key)
        item = self._values.get(key)
        if item is None:
            return -2

        _, expires_at = item
        if expires_at is None:
            return -1
        return max(math.ceil(expires_at - time.monotonic()), 0)

    async def eval(self, _: str, __: int, key: str, expected_value: str) -> int:
        self._purge_expired(key)
        item = self._values.get(key)
        if item is None:
            return 0

        value, _ = item
        if value != expected_value:
            return 0

        del self._values[key]
        return 1

    async def aclose(self) -> None:
        self._values.clear()

    def _purge_expired(self, key: str) -> None:
        item = self._values.get(key)
        if item is None:
            return

        _, expires_at = item
        if expires_at is not None and expires_at <= time.monotonic():
            del self._values[key]


@pytest_asyncio.fixture
async def client(tmp_path: Path, monkeypatch: Any) -> AsyncGenerator[AsyncClient, None]:
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(settings, "LLM_FALLBACK_TO_MOCK", False)
    monkeypatch.setattr(settings, "RESUME_CHUNK_SIZE", 240)
    monkeypatch.setattr(settings, "RESUME_CHUNK_OVERLAP", 40)

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        future=True,
    )
    session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_get_db() -> AsyncGenerator[Any, None]:
        async with session_factory() as session:
            yield session

    fake_redis = FakeRedis()

    async def override_get_redis() -> AsyncGenerator[FakeRedis, None]:
        yield fake_redis

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()
    await fake_redis.aclose()
    await engine.dispose()
