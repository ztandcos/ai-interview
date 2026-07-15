import re
from collections import Counter

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.resume_chunk import ResumeChunk
from app.models.user import User
from app.services.resume_service import get_resume


WORD_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#.\-]*|[\u4e00-\u9fff]{2,}")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_text_into_chunks(
    text: str,
    chunk_size: int,
    overlap: int,
) -> list[tuple[int, int, str]]:
    normalized_text = normalize_text(text)
    if not normalized_text:
        return []
    if overlap >= chunk_size:
        overlap = max(chunk_size // 5, 0)

    chunks: list[tuple[int, int, str]] = []
    start = 0
    text_length = len(normalized_text)
    while start < text_length:
        end = min(start + chunk_size, text_length)
        content = normalized_text[start:end].strip()
        if content:
            chunks.append((start, end, content))
        if end == text_length:
            break
        start = max(end - overlap, start + 1)
    return chunks


def extract_keywords(text: str, limit: int = 12) -> list[str]:
    words = [word.lower() for word in WORD_PATTERN.findall(text)]
    useful_words = [word for word in words if len(word) > 1 and word not in STOP_WORDS]
    return [word for word, _ in Counter(useful_words).most_common(limit)]


def score_chunk(query: str, chunk: ResumeChunk) -> int:
    query_terms = extract_keywords(query, limit=20)
    if not query_terms:
        query_terms = [query.lower().strip()]

    content = chunk.content.lower()
    chunk_keywords = set(chunk.keywords)
    score = 0
    for term in query_terms:
        if not term:
            continue
        score += content.count(term)
        if term in chunk_keywords:
            score += 2
    return score


async def build_resume_chunks(
    db: AsyncSession,
    current_user: User,
    resume_id: int,
) -> list[ResumeChunk]:
    resume = await get_resume(db, current_user, resume_id)
    chunk_tuples = split_text_into_chunks(
        resume.extracted_text,
        settings.RESUME_CHUNK_SIZE,
        settings.RESUME_CHUNK_OVERLAP,
    )
    if not chunk_tuples:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Resume text cannot be split into chunks",
        )

    await db.execute(
        delete(ResumeChunk).where(
            ResumeChunk.resume_id == resume.id,
            ResumeChunk.user_id == current_user.id,
        )
    )

    chunks = [
        ResumeChunk(
            user_id=current_user.id,
            resume_id=resume.id,
            chunk_index=index,
            content=content,
            char_start=char_start,
            char_end=char_end,
            keywords_text=",".join(extract_keywords(content)),
        )
        for index, (char_start, char_end, content) in enumerate(chunk_tuples)
    ]
    db.add_all(chunks)
    await db.commit()

    result = await db.scalars(
        select(ResumeChunk)
        .where(
            ResumeChunk.resume_id == resume.id,
            ResumeChunk.user_id == current_user.id,
        )
        .order_by(ResumeChunk.chunk_index)
    )
    return list(result)


async def list_resume_chunks(
    db: AsyncSession,
    current_user: User,
    resume_id: int,
) -> list[ResumeChunk]:
    await get_resume(db, current_user, resume_id)
    result = await db.scalars(
        select(ResumeChunk)
        .where(
            ResumeChunk.resume_id == resume_id,
            ResumeChunk.user_id == current_user.id,
        )
        .order_by(ResumeChunk.chunk_index)
    )
    return list(result)


async def search_resume_chunks(
    db: AsyncSession,
    current_user: User,
    resume_id: int,
    query: str,
    top_k: int,
) -> list[tuple[ResumeChunk, int]]:
    chunks = await list_resume_chunks(db, current_user, resume_id)
    scored_chunks = [
        (chunk, score)
        for chunk in chunks
        if (score := score_chunk(query, chunk)) > 0
    ]
    scored_chunks.sort(key=lambda item: (-item[1], item[0].chunk_index))
    return scored_chunks[:top_k]
