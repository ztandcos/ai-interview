import re
from collections import Counter

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.resume_chunk import ResumeChunk
from app.models.user import User
from app.services.embedding_provider import get_embedding_provider
from app.services.resume_service import get_resume
from app.services.vector_store import get_vector_store


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

    chunk_drafts = [
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
    vectors = await get_embedding_provider().embed([chunk.content for chunk in chunk_drafts])
    vector_store = get_vector_store()

    try:
        await db.execute(
            delete(ResumeChunk).where(
                ResumeChunk.resume_id == resume.id,
                ResumeChunk.user_id == current_user.id,
            )
        )
        db.add_all(chunk_drafts)
        await db.flush()
        await vector_store.replace_resume_vectors(chunk_drafts, vectors)
        await db.commit()
    except Exception:
        await db.rollback()
        try:
            await vector_store.delete_resume_vectors(current_user.id, resume.id)
        except Exception:
            pass
        raise

    return chunk_drafts


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
) -> list[tuple[ResumeChunk, float]]:
    query_vector = (await get_embedding_provider().embed([query]))[0]
    hits = await get_vector_store().search(
        current_user.id,
        resume_id,
        query_vector,
        top_k,
    )
    if not hits:
        return []

    chunks_result = await db.scalars(
        select(ResumeChunk).where(
            ResumeChunk.id.in_([hit.chunk_id for hit in hits]),
            ResumeChunk.resume_id == resume_id,
            ResumeChunk.user_id == current_user.id,
        )
    )
    chunks_by_id = {chunk.id: chunk for chunk in chunks_result}
    return [
        (chunks_by_id[hit.chunk_id], hit.score)
        for hit in hits
        if hit.chunk_id in chunks_by_id
    ]
