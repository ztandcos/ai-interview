from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.interview import (
    AnswerScoringRequest,
    AnswerScoringResponse,
    FollowUpRequest,
    FollowUpResponse,
    QuestionGenerationRequest,
    QuestionGenerationResponse,
)
from app.services.interview_service import (
    generate_resume_interview_follow_up,
    generate_resume_interview_questions,
    score_resume_interview_answer,
)


router = APIRouter()


@router.post(
    "/{resume_id}/interview/questions",
    response_model=QuestionGenerationResponse,
)
async def generate_questions(
    resume_id: int,
    request: QuestionGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuestionGenerationResponse:
    return await generate_resume_interview_questions(
        db,
        current_user,
        resume_id,
        request,
    )


@router.post(
    "/{resume_id}/interview/score",
    response_model=AnswerScoringResponse,
)
async def score_answer(
    resume_id: int,
    request: AnswerScoringRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnswerScoringResponse:
    return await score_resume_interview_answer(db, current_user, resume_id, request)


@router.post(
    "/{resume_id}/interview/follow-up",
    response_model=FollowUpResponse,
)
async def generate_follow_up(
    resume_id: int,
    request: FollowUpRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FollowUpResponse:
    return await generate_resume_interview_follow_up(
        db,
        current_user,
        resume_id,
        request,
    )
