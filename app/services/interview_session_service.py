import json
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interview import Interview, InterviewMessage, InterviewReport
from app.models.user import User
from app.schemas.interview import AnswerScoringRequest, FollowUpRequest, QuestionGenerationRequest
from app.schemas.interview_session import (
    InterviewAnswerRequest,
    InterviewAnswerResponse,
    InterviewCompleteResponse,
    InterviewDetailResponse,
    InterviewMessageResponse,
    InterviewReportResponse,
    InterviewStartRequest,
    InterviewStartResponse,
    InterviewSummaryResponse,
)
from app.services.auth_service import utc_now_naive
from app.services.interview_service import (
    generate_resume_interview_follow_up,
    generate_resume_interview_questions,
    score_resume_interview_answer,
)


INTERVIEW_STATUS_ACTIVE = "active"
INTERVIEW_STATUS_COMPLETED = "completed"


async def start_interview(
    db: AsyncSession,
    current_user: User,
    request: InterviewStartRequest,
) -> InterviewStartResponse:
    question_request = QuestionGenerationRequest(
        focus=request.focus,
        question_count=request.question_count,
        top_k=request.top_k,
    )
    generated = await generate_resume_interview_questions(
        db,
        current_user,
        request.resume_id,
        question_request,
    )

    interview = Interview(
        user_id=current_user.id,
        resume_id=request.resume_id,
        title=f"{request.focus} mock interview",
        focus=request.focus,
        status=INTERVIEW_STATUS_ACTIVE,
        question_count=len(generated.questions),
    )
    db.add(interview)
    await db.flush()

    question_messages = [
        InterviewMessage(
            interview_id=interview.id,
            user_id=current_user.id,
            role="assistant",
            message_type="question",
            content=question.question,
            metadata_json=json_dumps(
                {
                    "provider": generated.provider,
                    "question_id": question.question_id,
                    "difficulty": question.difficulty,
                    "expected_points": question.expected_points,
                    "source_chunk_indexes": question.source_chunk_indexes,
                    "source_chunk_ids": [
                        chunk.id
                        for chunk in generated.source_chunks
                        if chunk.chunk_index in question.source_chunk_indexes
                    ],
                }
            ),
        )
        for question in generated.questions
    ]
    db.add_all(question_messages)
    await db.commit()
    await db.refresh(interview)

    messages = await list_interview_messages(db, current_user, interview.id)
    return InterviewStartResponse(
        interview=to_interview_summary(interview),
        questions=generated.questions,
        messages=messages,
    )


async def list_interviews(
    db: AsyncSession,
    current_user: User,
) -> list[InterviewSummaryResponse]:
    result = await db.scalars(
        select(Interview)
        .where(Interview.user_id == current_user.id)
        .order_by(Interview.created_at.desc(), Interview.id.desc())
    )
    return [to_interview_summary(interview) for interview in result]


async def get_interview_detail(
    db: AsyncSession,
    current_user: User,
    interview_id: int,
) -> InterviewDetailResponse:
    interview = await get_owned_interview(db, current_user, interview_id)
    messages = await list_interview_messages(db, current_user, interview.id)
    report = await get_interview_report(db, current_user, interview.id)
    return InterviewDetailResponse(
        interview=to_interview_summary(interview),
        messages=messages,
        report=report,
    )


async def submit_interview_answer(
    db: AsyncSession,
    current_user: User,
    interview_id: int,
    request: InterviewAnswerRequest,
) -> InterviewAnswerResponse:
    interview = await get_owned_interview(db, current_user, interview_id)
    ensure_interview_active(interview)

    question_message = await db.scalar(
        select(InterviewMessage).where(
            InterviewMessage.id == request.question_message_id,
            InterviewMessage.interview_id == interview.id,
            InterviewMessage.user_id == current_user.id,
            InterviewMessage.message_type == "question",
        )
    )
    if question_message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question message not found",
        )

    answer_message = InterviewMessage(
        interview_id=interview.id,
        user_id=current_user.id,
        role="user",
        message_type="answer",
        content=request.answer,
        metadata_json=json_dumps({"question_message_id": question_message.id}),
    )
    db.add(answer_message)
    await db.flush()

    score_result = await score_resume_interview_answer(
        db,
        current_user,
        interview.resume_id,
        AnswerScoringRequest(
            question=question_message.content,
            answer=request.answer,
            top_k=request.top_k,
        ),
    )
    score_message = InterviewMessage(
        interview_id=interview.id,
        user_id=current_user.id,
        role="assistant",
        message_type="score",
        content=build_score_message_content(score_result),
        score=score_result.score,
        metadata_json=json_dumps(
            {
                "provider": score_result.provider,
                "question_message_id": question_message.id,
                "answer_message_id": answer_message.id,
                "level": score_result.level,
                "strengths": score_result.strengths,
                "improvements": score_result.improvements,
                "reference_points": score_result.reference_points,
                "source_chunk_ids": [chunk.id for chunk in score_result.source_chunks],
                "source_chunk_indexes": [
                    chunk.chunk_index for chunk in score_result.source_chunks
                ],
            }
        ),
    )
    db.add(score_message)
    await db.flush()

    follow_up_result = await generate_resume_interview_follow_up(
        db,
        current_user,
        interview.resume_id,
        FollowUpRequest(
            question=question_message.content,
            answer=request.answer,
            top_k=request.top_k,
        ),
    )
    follow_up_message = InterviewMessage(
        interview_id=interview.id,
        user_id=current_user.id,
        role="assistant",
        message_type="follow_up",
        content=follow_up_result.follow_up_question,
        metadata_json=json_dumps(
            {
                "provider": follow_up_result.provider,
                "question_message_id": question_message.id,
                "answer_message_id": answer_message.id,
                "reason": follow_up_result.reason,
                "source_chunk_ids": [chunk.id for chunk in follow_up_result.source_chunks],
                "source_chunk_indexes": [
                    chunk.chunk_index for chunk in follow_up_result.source_chunks
                ],
            }
        ),
    )
    db.add(follow_up_message)
    await db.commit()

    await db.refresh(answer_message)
    await db.refresh(score_message)
    await db.refresh(follow_up_message)
    return InterviewAnswerResponse(
        answer_message=to_message_response(answer_message),
        score_message=to_message_response(score_message),
        follow_up_message=to_message_response(follow_up_message),
    )


async def complete_interview(
    db: AsyncSession,
    current_user: User,
    interview_id: int,
) -> InterviewCompleteResponse:
    interview = await get_owned_interview(db, current_user, interview_id)
    existing_report = await get_interview_report(db, current_user, interview.id)
    if existing_report is not None:
        return InterviewCompleteResponse(
            interview=to_interview_summary(interview),
            report=existing_report,
        )

    score_messages = list(
        await db.scalars(
            select(InterviewMessage)
            .where(
                InterviewMessage.interview_id == interview.id,
                InterviewMessage.user_id == current_user.id,
                InterviewMessage.message_type == "score",
                InterviewMessage.score.is_not(None),
            )
            .order_by(InterviewMessage.created_at, InterviewMessage.id)
        )
    )
    if not score_messages:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Interview has no scored answers",
        )

    overall_score = round(
        sum(message.score or 0 for message in score_messages) / len(score_messages)
    )
    strengths = unique_items(
        item
        for message in score_messages
        for item in json_loads(message.metadata_json).get("strengths", [])
    )
    weaknesses = unique_items(
        item
        for message in score_messages
        for item in json_loads(message.metadata_json).get("improvements", [])
    )
    suggestions = build_report_suggestions(overall_score, weaknesses)
    summary = build_report_summary(overall_score, len(score_messages))

    report = InterviewReport(
        interview_id=interview.id,
        user_id=current_user.id,
        overall_score=overall_score,
        summary=summary,
        strengths_json=json_dumps(strengths),
        weaknesses_json=json_dumps(weaknesses),
        suggestions_json=json_dumps(suggestions),
    )
    interview.status = INTERVIEW_STATUS_COMPLETED
    interview.completed_at = utc_now_naive()
    db.add(report)
    await db.commit()
    await db.refresh(interview)
    await db.refresh(report)

    return InterviewCompleteResponse(
        interview=to_interview_summary(interview),
        report=to_report_response(report),
    )


async def get_owned_interview(
    db: AsyncSession,
    current_user: User,
    interview_id: int,
) -> Interview:
    interview = await db.scalar(
        select(Interview).where(
            Interview.id == interview_id,
            Interview.user_id == current_user.id,
        )
    )
    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found",
        )
    return interview


async def list_interview_messages(
    db: AsyncSession,
    current_user: User,
    interview_id: int,
) -> list[InterviewMessageResponse]:
    result = await db.scalars(
        select(InterviewMessage)
        .where(
            InterviewMessage.interview_id == interview_id,
            InterviewMessage.user_id == current_user.id,
        )
        .order_by(InterviewMessage.created_at, InterviewMessage.id)
    )
    return [to_message_response(message) for message in result]


async def get_interview_report(
    db: AsyncSession,
    current_user: User,
    interview_id: int,
) -> InterviewReportResponse | None:
    report = await db.scalar(
        select(InterviewReport).where(
            InterviewReport.interview_id == interview_id,
            InterviewReport.user_id == current_user.id,
        )
    )
    if report is None:
        return None
    return to_report_response(report)


def ensure_interview_active(interview: Interview) -> None:
    if interview.status != INTERVIEW_STATUS_ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Interview is already completed",
        )


def to_interview_summary(interview: Interview) -> InterviewSummaryResponse:
    return InterviewSummaryResponse.model_validate(interview)


def to_message_response(message: InterviewMessage) -> InterviewMessageResponse:
    return InterviewMessageResponse(
        id=message.id,
        interview_id=message.interview_id,
        role=message.role,  # type: ignore[arg-type]
        message_type=message.message_type,  # type: ignore[arg-type]
        content=message.content,
        score=message.score,
        metadata=json_loads(message.metadata_json),
        created_at=message.created_at,
    )


def to_report_response(report: InterviewReport) -> InterviewReportResponse:
    return InterviewReportResponse(
        id=report.id,
        interview_id=report.interview_id,
        overall_score=report.overall_score,
        summary=report.summary,
        strengths=json_loads(report.strengths_json, default=[]),
        weaknesses=json_loads(report.weaknesses_json, default=[]),
        suggestions=json_loads(report.suggestions_json, default=[]),
        created_at=report.created_at,
    )


def build_score_message_content(score_result: Any) -> str:
    return "\n".join(
        [
            f"评分：{score_result.score}/100（{score_result.level}）",
            f"优势：{'；'.join(score_result.strengths)}",
            f"改进：{'；'.join(score_result.improvements)}",
        ]
    )


def build_report_summary(overall_score: int, scored_answers: int) -> str:
    if overall_score >= 85:
        level = "整体表现很强，回答能较好结合简历证据和工程细节。"
    elif overall_score >= 70:
        level = "整体表现良好，已经能覆盖主要技术点。"
    elif overall_score >= 55:
        level = "整体表现达到基础水平，但细节和结构化表达还需要加强。"
    else:
        level = "整体表现偏弱，需要回到简历项目补充实现细节和验证方法。"
    return f"{level} 本次报告基于 {scored_answers} 条已评分回答生成。"


def build_report_suggestions(overall_score: int, weaknesses: list[str]) -> list[str]:
    suggestions = [
        "回答技术问题时按背景、方案、实现、验证、反思的顺序组织。",
        "主动把回答和简历中的项目关键词、数据表、接口或异常处理联系起来。",
    ]
    if overall_score < 70:
        suggestions.append("优先补齐每个项目的核心链路图和排错案例。")
    if weaknesses:
        suggestions.append(f"下一轮重点改进：{weaknesses[0]}")
    return suggestions


def unique_items(items: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result[:8]


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def json_loads(value: str, default: Any | None = None) -> Any:
    fallback = {} if default is None else default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback
