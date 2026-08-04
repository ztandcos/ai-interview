from __future__ import annotations

import math
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, Sequence

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
from app.services import resume_chunk_service, resume_service
from app.services.embedding_provider import RAGUnavailableError
from app.services.vector_store import VectorSearchHit


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

    async def get(self, key: str) -> str | None:
        self._purge_expired(key)
        item = self._values.get(key)
        return item[0] if item is not None else None

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


class FakeEmbeddingProvider:
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * 16
            for character in text.lower():
                if not character.isspace():
                    vector[ord(character) % len(vector)] += 1
            norm = math.sqrt(sum(value * value for value in vector))
            vectors.append([value / norm if norm else 0.0 for value in vector])
        return vectors


class FakeVectorStore:
    def __init__(self) -> None:
        self._vectors: dict[tuple[int, int], dict[int, list[float]]] = {}

    async def replace_resume_vectors(self, chunks: Sequence[Any], vectors: Sequence[Sequence[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Chunks and vectors must have the same length")
        if not chunks:
            return
        key = (chunks[0].user_id, chunks[0].resume_id)
        self._vectors[key] = {
            chunk.id: list(vector) for chunk, vector in zip(chunks, vectors, strict=True)
        }

    async def search(
        self,
        user_id: int,
        resume_id: int,
        vector: Sequence[float],
        top_k: int,
    ) -> list[VectorSearchHit]:
        hits = [
            VectorSearchHit(
                chunk_id=chunk_id,
                score=sum(a * b for a, b in zip(vector, stored_vector, strict=True)),
            )
            for chunk_id, stored_vector in self._vectors.get((user_id, resume_id), {}).items()
        ]
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:top_k]

    async def delete_resume_vectors(self, user_id: int, resume_id: int) -> None:
        self._vectors.pop((user_id, resume_id), None)


class UnavailableEmbeddingProvider:
    async def embed(self, _: Sequence[str]) -> list[list[float]]:
        raise RAGUnavailableError("Embedding service is unavailable")


@pytest_asyncio.fixture
async def client(tmp_path: Path, monkeypatch: Any) -> AsyncGenerator[AsyncClient, None]:
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(settings, "LLM_FALLBACK_TO_MOCK", False)
    monkeypatch.setattr(settings, "EXPOSE_VERIFICATION_CODE", True)
    monkeypatch.setattr(settings, "VERIFICATION_SEND_COOLDOWN_SECONDS", 1)
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
    fake_vector_store = FakeVectorStore()
    monkeypatch.setattr(
        resume_chunk_service,
        "get_embedding_provider",
        lambda: FakeEmbeddingProvider(),
    )
    monkeypatch.setattr(resume_chunk_service, "get_vector_store", lambda: fake_vector_store)
    monkeypatch.setattr(resume_service, "get_vector_store", lambda: fake_vector_store)

    async def override_get_redis() -> AsyncGenerator[FakeRedis, None]:
        yield fake_redis

    app = create_app()
    app.state.fake_vector_store = fake_vector_store
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        test_client._fake_vector_store = fake_vector_store  # type: ignore[attr-defined]
        yield test_client

    app.dependency_overrides.clear()
    await fake_redis.aclose()
    await engine.dispose()
