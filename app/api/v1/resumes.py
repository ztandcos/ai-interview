from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.resume_chunk import (
    ResumeChunkBuildResponse,
    ResumeChunkResponse,
    ResumeChunkSearchRequest,
    ResumeChunkSearchResult,
)
from app.schemas.resume import ResumeDetailResponse, ResumeResponse
from app.services.resume_chunk_service import (
    build_resume_chunks,
    list_resume_chunks,
    search_resume_chunks,
)
from app.services.resume_service import get_resume, list_resumes, upload_resume


router = APIRouter()


@router.post(
    "",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_my_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    return await upload_resume(db, current_user, file)


@router.get("", response_model=list[ResumeResponse])
async def read_my_resumes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ResumeResponse]:
    return await list_resumes(db, current_user)


@router.post("/{resume_id}/chunks", response_model=ResumeChunkBuildResponse)
async def build_my_resume_chunks(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResumeChunkBuildResponse:
    chunks = await build_resume_chunks(db, current_user, resume_id)
    return ResumeChunkBuildResponse(
        resume_id=resume_id,
        chunks_created=len(chunks),
    )


@router.get("/{resume_id}/chunks", response_model=list[ResumeChunkResponse])
async def read_my_resume_chunks(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ResumeChunkResponse]:
    return await list_resume_chunks(db, current_user, resume_id)


@router.post("/{resume_id}/search", response_model=list[ResumeChunkSearchResult])
async def search_my_resume_chunks(
    resume_id: int,
    request: ResumeChunkSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ResumeChunkSearchResult]:
    results = await search_resume_chunks(
        db,
        current_user,
        resume_id,
        request.query,
        request.top_k,
    )
    return [
        ResumeChunkSearchResult(
            id=chunk.id,
            resume_id=chunk.resume_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            score=score,
            keywords=chunk.keywords,
        )
        for chunk, score in results
    ]


@router.get("/{resume_id}", response_model=ResumeDetailResponse)
async def read_my_resume(
    resume_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResumeDetailResponse:
    return await get_resume(db, current_user, resume_id)
