from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.prompts.interview import (
    build_answer_scoring_prompt,
    build_follow_up_prompt,
    build_question_generation_prompt,
)
from app.schemas.interview import (
    AnswerScoringRequest,
    AnswerScoringResponse,
    FollowUpRequest,
    FollowUpResponse,
    InterviewSourceChunk,
    QuestionGenerationRequest,
    QuestionGenerationResponse,
)
from app.services.llm_provider import get_llm_provider
from app.services.resume_chunk_service import list_resume_chunks, search_resume_chunks


async def generate_resume_interview_questions(
    db: AsyncSession,
    current_user: User,
    resume_id: int,
    request: QuestionGenerationRequest,
) -> QuestionGenerationResponse:
    source_chunks = await get_resume_context_chunks(
        db,
        current_user,
        resume_id,
        request.focus,
        request.top_k,
    )
    prompt = build_question_generation_prompt(
        request.focus,
        request.question_count,
        source_chunks,
    )
    provider = get_llm_provider()
    questions = await provider.generate_questions(
        prompt,
        request.focus,
        request.question_count,
        source_chunks,
    )
    return QuestionGenerationResponse(
        provider=provider.name,
        resume_id=resume_id,
        focus=request.focus,
        questions=questions,
        source_chunks=source_chunks,
    )


async def score_resume_interview_answer(
    db: AsyncSession,
    current_user: User,
    resume_id: int,
    request: AnswerScoringRequest,
) -> AnswerScoringResponse:
    query = f"{request.question} {request.answer}"
    source_chunks = await get_resume_context_chunks(
        db,
        current_user,
        resume_id,
        query,
        request.top_k,
    )
    prompt = build_answer_scoring_prompt(
        request.question,
        request.answer,
        source_chunks,
    )
    provider = get_llm_provider()
    score, level, strengths, improvements, reference_points = await provider.score_answer(
        prompt,
        request.question,
        request.answer,
        source_chunks,
    )
    return AnswerScoringResponse(
        provider=provider.name,
        resume_id=resume_id,
        score=score,
        level=level,
        strengths=strengths,
        improvements=improvements,
        reference_points=reference_points,
        source_chunks=source_chunks,
    )


async def generate_resume_interview_follow_up(
    db: AsyncSession,
    current_user: User,
    resume_id: int,
    request: FollowUpRequest,
) -> FollowUpResponse:
    query = f"{request.question} {request.answer}"
    source_chunks = await get_resume_context_chunks(
        db,
        current_user,
        resume_id,
        query,
        request.top_k,
    )
    prompt = build_follow_up_prompt(
        request.question,
        request.answer,
        source_chunks,
    )
    provider = get_llm_provider()
    follow_up, reason = await provider.generate_follow_up(
        prompt,
        request.question,
        request.answer,
        source_chunks,
    )
    return FollowUpResponse(
        provider=provider.name,
        resume_id=resume_id,
        follow_up_question=follow_up,
        reason=reason,
        source_chunks=source_chunks,
    )


async def get_resume_context_chunks(
    db: AsyncSession,
    current_user: User,
    resume_id: int,
    query: str,
    top_k: int,
) -> list[InterviewSourceChunk]:
    all_chunks = await list_resume_chunks(db, current_user, resume_id)
    if not all_chunks:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resume chunks have not been built",
        )

    scored_chunks = await search_resume_chunks(
        db,
        current_user,
        resume_id,
        query,
        top_k,
    )
    if not scored_chunks:
        scored_chunks = [(chunk, 0) for chunk in all_chunks[:top_k]]

    return [
        InterviewSourceChunk(
            id=chunk.id,
            resume_id=chunk.resume_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            score=score,
            keywords=chunk.keywords,
        )
        for chunk, score in scored_chunks
    ]
