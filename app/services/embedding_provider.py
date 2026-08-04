from __future__ import annotations

from collections.abc import Sequence

import httpx

from app.core.config import settings


class RAGUnavailableError(RuntimeError):
    """Raised when a required RAG dependency cannot serve a request."""


class OllamaEmbeddingProvider:
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embed"
        try:
            async with httpx.AsyncClient(timeout=settings.EMBEDDING_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    url,
                    json={"model": settings.EMBEDDING_MODEL_NAME, "input": list(texts)},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RAGUnavailableError(
                "Embedding service is unavailable. Start Ollama and pull "
                f"{settings.EMBEDDING_MODEL_NAME}."
            ) from exc

        try:
            embeddings = response.json()["embeddings"]
        except (KeyError, TypeError, ValueError) as exc:
            raise RAGUnavailableError("Embedding service returned an invalid response") from exc

        if len(embeddings) != len(texts) or any(
            len(vector) != settings.EMBEDDING_VECTOR_SIZE for vector in embeddings
        ):
            raise RAGUnavailableError(
                "Embedding dimensions do not match EMBEDDING_VECTOR_SIZE"
            )
        return [[float(value) for value in vector] for vector in embeddings]


def get_embedding_provider() -> OllamaEmbeddingProvider:
    return OllamaEmbeddingProvider()
