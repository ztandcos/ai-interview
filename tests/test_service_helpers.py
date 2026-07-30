from __future__ import annotations

import pytest

from app.schemas.interview import InterviewSourceChunk
from app.services.llm_provider import (
    MockLLMProvider,
    normalize_follow_up,
    normalize_score,
    parse_json_object,
)
from app.services.resume_chunk_service import extract_keywords, split_text_into_chunks


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
