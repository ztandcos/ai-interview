from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import settings


class InterviewSourceChunk(BaseModel):
    id: int
    resume_id: int
    chunk_index: int
    content: str
    score: float
    keywords: list[str]


class QuestionGenerationRequest(BaseModel):
    focus: str = Field(default="backend engineering", min_length=1, max_length=100)
    question_count: int = Field(default=3, ge=1, le=10)
    top_k: int = Field(
        default=settings.RESUME_SEARCH_DEFAULT_TOP_K,
        ge=1,
        le=10,
    )


class InterviewQuestion(BaseModel):
    question_id: str
    difficulty: Literal["easy", "medium", "hard"]
    question: str
    expected_points: list[str]
    source_chunk_indexes: list[int]


class LiveInterviewTurn(BaseModel):
    greeting: str | None = None
    feedback: str | None = None
    question: str | None = None
    expected_points: list[str] = Field(default_factory=list)
    source_chunk_indexes: list[int] = Field(default_factory=list)
    should_end: bool = False


class QuestionGenerationResponse(BaseModel):
    provider: str
    resume_id: int
    focus: str
    questions: list[InterviewQuestion]
    source_chunks: list[InterviewSourceChunk]


class AnswerScoringRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=5000)
    top_k: int = Field(
        default=settings.RESUME_SEARCH_DEFAULT_TOP_K,
        ge=1,
        le=10,
    )


class AnswerScoringResponse(BaseModel):
    provider: str
    resume_id: int
    score: int = Field(ge=0, le=100)
    level: Literal["weak", "basic", "good", "strong"]
    strengths: list[str]
    improvements: list[str]
    reference_points: list[str]
    source_chunks: list[InterviewSourceChunk]


class FollowUpRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=5000)
    top_k: int = Field(
        default=settings.RESUME_SEARCH_DEFAULT_TOP_K,
        ge=1,
        le=10,
    )


class FollowUpResponse(BaseModel):
    provider: str
    resume_id: int
    follow_up_question: str
    reason: str
    source_chunks: list[InterviewSourceChunk]
