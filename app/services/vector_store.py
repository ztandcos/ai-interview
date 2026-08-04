from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.core.config import settings
from app.models.resume_chunk import ResumeChunk
from app.services.embedding_provider import RAGUnavailableError


@dataclass(frozen=True)
class VectorSearchHit:
    chunk_id: int
    score: float


class QdrantVectorStore:
    def __init__(self) -> None:
        self.client = AsyncQdrantClient(url=settings.QDRANT_URL)

    async def ensure_collection(self) -> None:
        try:
            exists = await self.client.collection_exists(settings.QDRANT_COLLECTION_NAME)
            if not exists:
                await self.client.create_collection(
                    collection_name=settings.QDRANT_COLLECTION_NAME,
                    vectors_config=models.VectorParams(
                        size=settings.EMBEDDING_VECTOR_SIZE,
                        distance=models.Distance.COSINE,
                    ),
                )
        except (ResponseHandlingException, UnexpectedResponse, OSError, RuntimeError) as exc:
            raise RAGUnavailableError("Qdrant is unavailable") from exc

    async def replace_resume_vectors(
        self,
        chunks: Sequence[ResumeChunk],
        vectors: Sequence[Sequence[float]],
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Chunks and vectors must have the same length")
        if not chunks:
            return

        await self.ensure_collection()
        first_chunk = chunks[0]
        try:
            await self.delete_resume_vectors(first_chunk.user_id, first_chunk.resume_id)
            await self.client.upsert(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                wait=True,
                points=[
                    models.PointStruct(
                        id=chunk.id,
                        vector=list(vector),
                        payload={
                            "user_id": chunk.user_id,
                            "resume_id": chunk.resume_id,
                            "chunk_id": chunk.id,
                            "chunk_index": chunk.chunk_index,
                        },
                    )
                    for chunk, vector in zip(chunks, vectors, strict=True)
                ],
            )
        except (ResponseHandlingException, UnexpectedResponse, OSError, RuntimeError) as exc:
            raise RAGUnavailableError("Could not write resume vectors to Qdrant") from exc

    async def search(
        self,
        user_id: int,
        resume_id: int,
        vector: Sequence[float],
        top_k: int,
    ) -> list[VectorSearchHit]:
        await self.ensure_collection()
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="user_id",
                    match=models.MatchValue(value=user_id),
                ),
                models.FieldCondition(
                    key="resume_id",
                    match=models.MatchValue(value=resume_id),
                ),
            ]
        )
        try:
            result = await self.client.query_points(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                query=list(vector),
                query_filter=query_filter,
                limit=top_k,
                with_payload=False,
            )
        except (ResponseHandlingException, UnexpectedResponse, OSError, RuntimeError) as exc:
            raise RAGUnavailableError("Could not search resume vectors in Qdrant") from exc
        return [VectorSearchHit(chunk_id=int(point.id), score=float(point.score)) for point in result.points]

    async def delete_resume_vectors(self, user_id: int, resume_id: int) -> None:
        try:
            exists = await self.client.collection_exists(settings.QDRANT_COLLECTION_NAME)
            if not exists:
                return
            await self.client.delete(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                wait=True,
                points_selector=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="user_id",
                            match=models.MatchValue(value=user_id),
                        ),
                        models.FieldCondition(
                            key="resume_id",
                            match=models.MatchValue(value=resume_id),
                        ),
                    ]
                ),
            )
        except (ResponseHandlingException, UnexpectedResponse, OSError, RuntimeError) as exc:
            raise RAGUnavailableError("Could not delete resume vectors from Qdrant") from exc


def get_vector_store() -> QdrantVectorStore:
    return QdrantVectorStore()
