import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.interview_session import (
    InterviewAnswerRequest,
    InterviewAnswerResponse,
    InterviewCompleteResponse,
    InterviewCompleteRequest,
    InterviewDetailResponse,
    InterviewStartRequest,
    InterviewStartResponse,
    InterviewSummaryResponse,
)
from app.services.interview_session_service import (
    complete_interview,
    delete_interview,
    get_interview_detail,
    list_interviews,
    start_interview,
    stream_interview_answer,
    submit_interview_answer,
)


router = APIRouter()


@router.post("", response_model=InterviewStartResponse)
async def create_interview(
    request: InterviewStartRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewStartResponse:
    return await start_interview(db, current_user, request)


@router.get("", response_model=list[InterviewSummaryResponse])
async def read_interviews(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[InterviewSummaryResponse]:
    return await list_interviews(db, current_user)


@router.get("/{interview_id}", response_model=InterviewDetailResponse)
async def read_interview_detail(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewDetailResponse:
    return await get_interview_detail(db, current_user, interview_id)


@router.post("/{interview_id}/answers", response_model=InterviewAnswerResponse)
async def answer_interview_question(
    interview_id: int,
    request: InterviewAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewAnswerResponse:
    return await submit_interview_answer(db, current_user, interview_id, request)


@router.post("/{interview_id}/answers/stream")
async def stream_interview_question_answer(
    interview_id: int,
    request: InterviewAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    async def event_stream():
        try:
            async for event in stream_interview_answer(db, current_user, interview_id, request):
                yield f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
        except HTTPException as exc:
            yield f"event: error\ndata: {json.dumps({'detail': exc.detail}, ensure_ascii=False)}\n\n"
        except Exception:
            yield "event: error\ndata: {\"detail\": \"面试官回复生成失败，请稍后重试\"}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{interview_id}/complete", response_model=InterviewCompleteResponse)
async def complete_my_interview(
    interview_id: int,
    request: InterviewCompleteRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterviewCompleteResponse:
    return await complete_interview(
        db,
        current_user,
        interview_id,
        force=request.force if request is not None else False,
    )


@router.delete("/{interview_id}", response_model=MessageResponse)
async def delete_my_interview(
    interview_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await delete_interview(db, current_user, interview_id)
    return MessageResponse(message="Interview deleted")
