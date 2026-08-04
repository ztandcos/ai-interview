from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.db.session import AsyncSessionLocal, engine
from app.models.resume import Resume
from app.models.user import User
from app.services.embedding_provider import RAGUnavailableError
from app.services.resume_chunk_service import build_resume_chunks


async def reindex_all_resumes() -> None:
    async with AsyncSessionLocal() as db:
        resumes = list((await db.scalars(select(Resume).order_by(Resume.id))).all())
        for resume in resumes:
            user = await db.get(User, resume.user_id)
            if user is None:
                continue
            await build_resume_chunks(db, user, resume.id)
            print(f"Indexed resume {resume.id}: {resume.original_filename}")


async def main() -> int:
    try:
        await reindex_all_resumes()
    except RAGUnavailableError as exc:
        print(f"RAG reindex failed: {exc}")
        return 1
    finally:
        await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
