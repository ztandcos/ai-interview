import json
import re
from collections.abc import AsyncIterator
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.interview import Interview, InterviewMessage, InterviewReport
from app.models.user import User
from app.schemas.interview import AnswerScoringRequest, InterviewQuestion
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
    generate_live_interview_turn,
    prepare_live_interview_turn,
    score_resume_interview_answer,
)
from app.services.llm_provider import normalize_live_interview_turn, parse_json_object


INTERVIEW_STATUS_ACTIVE = "active"
INTERVIEW_STATUS_COMPLETED = "completed"


async def start_interview(
    db: AsyncSession,
    current_user: User,
    request: InterviewStartRequest,
) -> InterviewStartResponse:
    interview = Interview(
        user_id=current_user.id,
        resume_id=request.resume_id,
        title=f"{request.focus} 模拟面试",
        focus=request.focus,
        difficulty=request.difficulty,
        status=INTERVIEW_STATUS_ACTIVE,
        question_count=request.question_count,
    )
    db.add(interview)
    await db.flush()

    turn, source_chunks, provider_name = await generate_live_interview_turn(
        db,
        current_user,
        interview.resume_id,
        focus=interview.focus,
        difficulty=interview.difficulty,
        turn_number=1,
        history="",
        top_k=request.top_k,
        opening=True,
        ask_next_question=True,
    )
    greeting_message = InterviewMessage(
        interview_id=interview.id,
        user_id=current_user.id,
        role="assistant",
        message_type="greeting",
        content=turn.greeting or "你好，很高兴和你进行这场模拟面试。",
        metadata_json=json_dumps({"provider": provider_name}),
    )
    question_message = InterviewMessage(
        interview_id=interview.id,
        user_id=current_user.id,
        role="assistant",
        message_type="question",
        content=turn.question or "请介绍一下你最有代表性的项目经历。",
        metadata_json=json_dumps(
            question_metadata(
                provider_name,
                interview.difficulty,
                turn.expected_points,
                turn.source_chunk_indexes,
                source_chunks,
            )
        ),
    )
    db.add_all([greeting_message, question_message])
    await db.commit()
    await db.refresh(interview)

    messages = await list_interview_messages(db, current_user, interview.id)
    return InterviewStartResponse(
        interview=to_interview_summary(interview),
        questions=[
            InterviewQuestion(
                question_id=f"live-q-{question_message.id}",
                difficulty=interview.difficulty,  # type: ignore[arg-type]
                question=question_message.content,
                expected_points=turn.expected_points,
                source_chunk_indexes=turn.source_chunk_indexes,
            )
        ],
        messages=messages,
    )


async def list_interviews(
    db: AsyncSession,
    current_user: User,
) -> list[InterviewSummaryResponse]:
    result = await db.execute(
        select(Interview, InterviewReport.overall_score)
        .outerjoin(
            InterviewReport,
            InterviewReport.interview_id == Interview.id,
        )
        .where(Interview.user_id == current_user.id)
        .order_by(Interview.created_at.desc(), Interview.id.desc())
    )
    return [
        to_interview_summary(interview, overall_score)
        for interview, overall_score in result.all()
    ]


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

    answered_question_ids = await get_answered_question_ids(
        db,
        current_user,
        interview.id,
    )
    if question_message.id in answered_question_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Question has already been answered",
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

    answered_count = len(answered_question_ids) + 1
    history = await build_live_history(db, current_user, interview.id)
    turn, source_chunks, provider_name = await generate_live_interview_turn(
        db,
        current_user,
        interview.resume_id,
        focus=interview.focus,
        difficulty=interview.difficulty,
        turn_number=answered_count + 1,
        history=history,
        top_k=request.top_k,
        opening=False,
        ask_next_question=True,
    )
    should_end = turn.should_end or (
        settings.LIVE_INTERVIEW_MAX_TURNS > 0
        and answered_count >= settings.LIVE_INTERVIEW_MAX_TURNS
    )
    coach_message = InterviewMessage(
        interview_id=interview.id,
        user_id=current_user.id,
        role="assistant",
        message_type="feedback",
        content=turn.feedback or "谢谢你的回答，我已经记录了这部分表现。",
        metadata_json=json_dumps(
            {
                "provider": provider_name,
                "question_message_id": question_message.id,
                "answer_message_id": answer_message.id,
                "source_chunk_ids": [chunk.id for chunk in source_chunks],
                "source_chunk_indexes": [chunk.chunk_index for chunk in source_chunks],
            }
        ),
    )
    db.add(coach_message)
    next_question_message: InterviewMessage | None = None
    if not should_end:
        next_question_message = InterviewMessage(
            interview_id=interview.id,
            user_id=current_user.id,
            role="assistant",
            message_type="question",
            content=turn.question or "请继续结合一个具体例子展开说明。",
            metadata_json=json_dumps(
                question_metadata(
                    provider_name,
                    interview.difficulty,
                    turn.expected_points,
                    turn.source_chunk_indexes,
                    source_chunks,
                )
            ),
        )
        db.add(next_question_message)
    await db.commit()

    await db.refresh(answer_message)
    await db.refresh(score_message)
    await db.refresh(coach_message)
    if next_question_message is not None:
        await db.refresh(next_question_message)
    if should_end:
        await complete_interview(db, current_user, interview.id, force=True)

    return InterviewAnswerResponse(
        answer_message=to_message_response(answer_message),
        score_message=to_message_response(score_message),
        coach_message=to_message_response(coach_message),
        next_question=(
            to_message_response(next_question_message)
            if next_question_message is not None
            else None
        ),
        answered_count=answered_count,
        total_questions=interview.question_count,
        is_finished=should_end,
    )


async def stream_interview_answer(
    db: AsyncSession,
    current_user: User,
    interview_id: int,
    request: InterviewAnswerRequest,
) -> AsyncIterator[dict[str, Any]]:
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question message not found")
    answered_question_ids = await get_answered_question_ids(db, current_user, interview.id)
    if question_message.id in answered_question_ids:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Question has already been answered")

    answer_message = InterviewMessage(
        interview_id=interview.id,
        user_id=current_user.id,
        role="user",
        message_type="answer",
        content=request.answer,
        metadata_json=json_dumps({"question_message_id": question_message.id}),
    )
    db.add(answer_message)
    await db.commit()
    await db.refresh(answer_message)
    yield {"event": "answer", "data": {"message": to_message_response(answer_message).model_dump(mode="json")}}

    answered_count = len(answered_question_ids) + 1
    history = await build_live_history(db, current_user, interview.id)
    provider, system_prompt, turn_prompt, source_chunks = await prepare_live_interview_turn(
        db,
        current_user,
        interview.resume_id,
        focus=interview.focus,
        difficulty=interview.difficulty,
        turn_number=answered_count + 1,
        history=history,
        top_k=request.top_k,
        opening=False,
        ask_next_question=True,
    )
    raw_content = ""
    emitted = {"feedback": "", "question": ""}
    async for token in provider.stream_live_interview_turn(
        system_prompt,
        turn_prompt,
        source_chunks,
        opening=False,
        ask_next_question=True,
    ):
        raw_content += token
        for field in emitted:
            value = extract_stream_string(raw_content, field)
            if value is not None and value.startswith(emitted[field]):
                delta = value[len(emitted[field]) :]
                if delta:
                    emitted[field] = value
                    yield {"event": "delta", "data": {"field": field, "content": delta}}

    turn = normalize_live_interview_turn(parse_json_object(raw_content), source_chunks)
    should_end = turn.should_end or (
        settings.LIVE_INTERVIEW_MAX_TURNS > 0
        and answered_count >= settings.LIVE_INTERVIEW_MAX_TURNS
    )
    if not should_end and not turn.question:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM live interview response did not contain a question",
        )

    score_result = await score_resume_interview_answer(
        db,
        current_user,
        interview.resume_id,
        AnswerScoringRequest(question=question_message.content, answer=request.answer, top_k=request.top_k),
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
                "source_chunk_indexes": [chunk.chunk_index for chunk in score_result.source_chunks],
            }
        ),
    )
    coach_message = InterviewMessage(
        interview_id=interview.id,
        user_id=current_user.id,
        role="assistant",
        message_type="feedback",
        content=turn.feedback or "谢谢你的回答，我已经记录了这部分表现。",
        metadata_json=json_dumps(
            {
                "provider": provider.name,
                "question_message_id": question_message.id,
                "answer_message_id": answer_message.id,
                "source_chunk_ids": [chunk.id for chunk in source_chunks],
                "source_chunk_indexes": [chunk.chunk_index for chunk in source_chunks],
            }
        ),
    )
    db.add_all([score_message, coach_message])
    next_question_message: InterviewMessage | None = None
    if not should_end:
        next_question_message = InterviewMessage(
            interview_id=interview.id,
            user_id=current_user.id,
            role="assistant",
            message_type="question",
            content=turn.question or "请继续结合一个具体例子展开说明。",
            metadata_json=json_dumps(
                question_metadata(provider.name, interview.difficulty, turn.expected_points, turn.source_chunk_indexes, source_chunks)
            ),
        )
        db.add(next_question_message)
    await db.commit()
    await db.refresh(score_message)
    await db.refresh(coach_message)
    if next_question_message is not None:
        await db.refresh(next_question_message)
    if should_end:
        await complete_interview(db, current_user, interview.id, force=True)
    yield {
        "event": "complete",
        "data": {
            "coach_message": to_message_response(coach_message).model_dump(mode="json"),
            "next_question": to_message_response(next_question_message).model_dump(mode="json") if next_question_message else None,
            "is_finished": should_end,
        },
    }


async def complete_interview(
    db: AsyncSession,
    current_user: User,
    interview_id: int,
    *,
    force: bool = False,
) -> InterviewCompleteResponse:
    interview = await get_owned_interview(db, current_user, interview_id)
    existing_report = await get_interview_report(db, current_user, interview.id)
    if existing_report is not None:
        return InterviewCompleteResponse(
            interview=to_interview_summary(interview),
            report=existing_report,
        )

    answered_question_ids = await get_answered_question_ids(
        db,
        current_user,
        interview.id,
    )
    if not answered_question_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Interview has no answered question",
        )
    if not force and interview.question_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Let the AI finish the interview or confirm an early finish",
        )
    if not force and len(answered_question_ids) < interview.question_count:
        remaining = interview.question_count - len(answered_question_ids)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Interview has {remaining} unanswered question(s)",
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


async def delete_interview(
    db: AsyncSession,
    current_user: User,
    interview_id: int,
) -> None:
    interview = await get_owned_interview(db, current_user, interview_id)
    await db.execute(
        delete(InterviewReport).where(
            InterviewReport.interview_id == interview.id,
            InterviewReport.user_id == current_user.id,
        )
    )
    await db.execute(
        delete(InterviewMessage).where(
            InterviewMessage.interview_id == interview.id,
            InterviewMessage.user_id == current_user.id,
        )
    )
    await db.delete(interview)
    await db.commit()


async def get_answered_question_ids(
    db: AsyncSession,
    current_user: User,
    interview_id: int,
) -> set[int]:
    answer_messages = await db.scalars(
        select(InterviewMessage).where(
            InterviewMessage.interview_id == interview_id,
            InterviewMessage.user_id == current_user.id,
            InterviewMessage.message_type == "answer",
        )
    )
    return {
        question_message_id
        for message in answer_messages
        if (
            question_message_id := json_loads(message.metadata_json).get(
                "question_message_id"
            )
        )
        is not None
    }


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


async def build_live_history(
    db: AsyncSession,
    current_user: User,
    interview_id: int,
) -> str:
    messages = list(
        await db.scalars(
            select(InterviewMessage)
            .where(
                InterviewMessage.interview_id == interview_id,
                InterviewMessage.user_id == current_user.id,
                InterviewMessage.message_type.in_(["greeting", "question", "answer", "feedback"]),
            )
            .order_by(InterviewMessage.created_at, InterviewMessage.id)
        )
    )
    return "\n".join(
        f"{'Candidate' if message.role == 'user' else 'Interviewer'}: {message.content}"
        for message in messages[-12:]
    )


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


def to_interview_summary(
    interview: Interview,
    overall_score: int | None = None,
) -> InterviewSummaryResponse:
    summary = InterviewSummaryResponse.model_validate(interview)
    summary.overall_score = overall_score
    return summary


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


def question_metadata(
    provider: str,
    difficulty: str,
    expected_points: list[str],
    source_chunk_indexes: list[int],
    source_chunks: list[Any],
) -> dict[str, Any]:
    return {
        "provider": provider,
        "difficulty": difficulty,
        "expected_points": expected_points,
        "source_chunk_indexes": source_chunk_indexes,
        "source_chunk_ids": [
            chunk.id
            for chunk in source_chunks
            if chunk.chunk_index in source_chunk_indexes
        ],
    }


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


def extract_stream_string(content: str, field: str) -> str | None:
    match = re.search(rf'"{re.escape(field)}"\s*:\s*"', content)
    if match is None:
        return None
    chars: list[str] = []
    escaped = False
    for character in content[match.end() :]:
        if escaped:
            chars.append(character)
            escaped = False
            continue
        if character == "\\":
            chars.append(character)
            escaped = True
            continue
        if character == '"':
            break
        chars.append(character)
    value = "".join(chars)
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return value.replace("\\n", "\n")
