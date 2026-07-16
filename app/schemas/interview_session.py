from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.schemas.interview import InterviewQuestion


InterviewStatus = Literal["active", "completed"]
InterviewRole = Literal["assistant", "user", "system"]
InterviewMessageType = Literal["question", "answer", "score", "follow_up"]


class InterviewStartRequest(BaseModel):
    resume_id: int = Field(ge=1)
    focus: str = Field(default="backend engineering", min_length=1, max_length=100)
    question_count: int = Field(default=3, ge=1, le=5)
    top_k: int = Field(
        default=settings.RESUME_SEARCH_DEFAULT_TOP_K,
        ge=1,
        le=10,
    )


class InterviewSummaryResponse(BaseModel):
    id: int
    resume_id: int
    title: str
    focus: str
    status: InterviewStatus
    question_count: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class InterviewMessageResponse(BaseModel):
    id: int
    interview_id: int
    role: InterviewRole
    message_type: InterviewMessageType
    content: str
    score: int | None
    metadata: dict[str, Any]
    created_at: datetime


class InterviewReportResponse(BaseModel):
    id: int
    interview_id: int
    overall_score: int = Field(ge=0, le=100)
    summary: str
    strengths: list[str]
    weaknesses: list[str]
    suggestions: list[str]
    created_at: datetime


class InterviewStartResponse(BaseModel):
    interview: InterviewSummaryResponse
    questions: list[InterviewQuestion]
    messages: list[InterviewMessageResponse]


class InterviewDetailResponse(BaseModel):
    interview: InterviewSummaryResponse
    messages: list[InterviewMessageResponse]
    report: InterviewReportResponse | None


class InterviewAnswerRequest(BaseModel):
    question_message_id: int = Field(ge=1)
    answer: str = Field(min_length=1, max_length=5000)
    top_k: int = Field(
        default=settings.RESUME_SEARCH_DEFAULT_TOP_K,
        ge=1,
        le=10,
    )


class InterviewAnswerResponse(BaseModel):
    answer_message: InterviewMessageResponse
    score_message: InterviewMessageResponse
    follow_up_message: InterviewMessageResponse


class InterviewCompleteResponse(BaseModel):
    interview: InterviewSummaryResponse
    report: InterviewReportResponse
