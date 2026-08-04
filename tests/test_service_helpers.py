from __future__ import annotations

import pytest

from app.core.config import settings
from app.schemas.interview import InterviewSourceChunk
from app.services.embedding_provider import OllamaEmbeddingProvider, RAGUnavailableError
from app.services.llm_provider import (
    MockLLMProvider,
    normalize_follow_up,
    normalize_score,
    parse_json_object,
)
from app.services.resume_chunk_service import extract_keywords, split_text_into_chunks
from app.services.vector_store import QdrantVectorStore


def source_chunk() -> InterviewSourceChunk:
    return InterviewSourceChunk(
        id=1,
        resume_id=1,
        chunk_index=0,
        content="FastAPI Redis MySQL RAG 项目实现与接口测试",
        score=6,
        keywords=["fastapi", "redis", "mysql", "rag"],
    )


def test_text_chunking_preserves_configured_overlap() -> None:
    chunks = split_text_into_chunks(
        "0123456789ABCDEFGHIJ",
        chunk_size=10,
        overlap=3,
    )

    assert [item[:2] for item in chunks] == [(0, 10), (7, 17), (14, 20)]
    assert chunks[0][2][-3:] == chunks[1][2][:3]
    assert chunks[1][2][-3:] == chunks[2][2][:3]


def test_keyword_extraction_is_ranked_and_case_insensitive() -> None:
    keywords = extract_keywords("FastAPI Redis fastapi MySQL Redis FastAPI")

    assert keywords[:3] == ["fastapi", "redis", "mysql"]


def test_llm_json_parser_accepts_markdown_and_surrounding_text() -> None:
    markdown = '```json\n{"score": 88, "level": "strong"}\n```'
    surrounding = '模型结果如下：{"follow_up_question": "为什么？"} 完毕'

    assert parse_json_object(markdown)["score"] == 88
    assert parse_json_object(surrounding)["follow_up_question"] == "为什么？"


def test_llm_normalizers_apply_safe_defaults_and_bounds() -> None:
    score, level, strengths, improvements, references = normalize_score(
        {"score": 120, "strengths": [], "improvements": "invalid"},
        [source_chunk()],
    )
    follow_up, reason = normalize_follow_up({}, [source_chunk()])

    assert score == 100
    assert level == "strong"
    assert strengths
    assert improvements
    assert references
    assert "fastapi" in follow_up
    assert reason


@pytest.mark.asyncio
async def test_mock_provider_generates_requested_questions_and_score() -> None:
    provider = MockLLMProvider()
    chunks = [source_chunk()]

    questions = await provider.generate_questions(
        "prompt",
        "AI application intern",
        3,
        chunks,
    )
    score_result = await provider.score_answer(
        "prompt",
        questions[0].question,
        "我使用 FastAPI、Redis、MySQL 和 RAG 完成实现，并通过测试验证。",
        chunks,
    )

    assert len(questions) == 3
    assert questions[0].source_chunk_indexes == [0]
    assert 0 <= score_result[0] <= 100
    assert score_result[1] in {"weak", "basic", "good", "strong"}


@pytest.mark.asyncio
async def test_ollama_embedding_provider_parses_batch_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, list[list[float]]]:
            return {"embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]}

    class FakeClient:
        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(self, _: str, json: dict[str, object]) -> FakeResponse:
            assert json["input"] == ["first", "second"]
            return FakeResponse()

    monkeypatch.setattr(settings, "EMBEDDING_VECTOR_SIZE", 3)
    monkeypatch.setattr("app.services.embedding_provider.httpx.AsyncClient", lambda **_: FakeClient())

    embeddings = await OllamaEmbeddingProvider().embed(["first", "second"])

    assert embeddings == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


@pytest.mark.asyncio
async def test_ollama_embedding_provider_rejects_wrong_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, list[list[float]]]:
            return {"embeddings": [[0.1, 0.2]]}

    class FakeClient:
        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(self, _: str, json: dict[str, object]) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(settings, "EMBEDDING_VECTOR_SIZE", 3)
    monkeypatch.setattr("app.services.embedding_provider.httpx.AsyncClient", lambda **_: FakeClient())

    with pytest.raises(RAGUnavailableError, match="dimensions"):
        await OllamaEmbeddingProvider().embed(["first"])


@pytest.mark.asyncio
async def test_qdrant_store_writes_and_queries_with_user_and_resume_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClient:
        def __init__(self, **_: object) -> None:
            self.created = None
            self.deleted = None
            self.upserted = None
            self.query_filter = None

        async def collection_exists(self, _: str) -> bool:
            return self.created is not None

        async def create_collection(self, **kwargs: object) -> None:
            self.created = kwargs

        async def delete(self, **kwargs: object) -> None:
            self.deleted = kwargs

        async def upsert(self, **kwargs: object) -> None:
            self.upserted = kwargs

        async def query_points(self, **kwargs: object) -> object:
            self.query_filter = kwargs["query_filter"]
            return type(
                "QueryResult",
                (),
                {
                    "points": [
                        type("Point", (), {"id": 22, "score": 0.87})(),
                        type("Point", (), {"id": 23, "score": 0.62})(),
                    ]
                },
            )()

    monkeypatch.setattr("app.services.vector_store.AsyncQdrantClient", FakeClient)
    monkeypatch.setattr(settings, "EMBEDDING_VECTOR_SIZE", 3)
    store = QdrantVectorStore()
    chunks = [
        type(
            "Chunk",
            (),
            {"id": 22, "user_id": 7, "resume_id": 11, "chunk_index": 2},
        )()
    ]

    await store.replace_resume_vectors(chunks, [[0.1, 0.2, 0.3]])
    hits = await store.search(7, 11, [0.1, 0.2, 0.3], 3)

    assert store.client.upserted is not None
    point = store.client.upserted["points"][0]
    assert point.id == 22
    assert point.payload == {
        "user_id": 7,
        "resume_id": 11,
        "chunk_id": 22,
        "chunk_index": 2,
    }
    assert store.client.deleted is not None
    delete_conditions = store.client.deleted["points_selector"].must
    assert [condition.match.value for condition in delete_conditions] == [7, 11]
    assert [condition.match.value for condition in store.client.query_filter.must] == [7, 11]
    assert [hit.chunk_id for hit in hits] == [22, 23]
    assert [hit.score for hit in hits] == pytest.approx([0.87, 0.62])
