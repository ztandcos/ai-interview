from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings


class ResumeChunkBuildResponse(BaseModel):
    resume_id: int
    chunks_created: int


class ResumeChunkResponse(BaseModel):
    id: int
    resume_id: int
    chunk_index: int
    content: str
    char_start: int
    char_end: int
    keywords: list[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResumeChunkSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(
        default=settings.RESUME_SEARCH_DEFAULT_TOP_K,
        ge=1,
        le=10,
    )


class ResumeChunkSearchResult(BaseModel):
    id: int
    resume_id: int
    chunk_index: int
    content: str
    score: int
    keywords: list[str]
