from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResumeChunk(Base):
    __tablename__ = "resume_chunks"
    __table_args__ = (
        UniqueConstraint("resume_id", "chunk_index", name="uq_resume_chunks_resume_index"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id"),
        index=True,
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    keywords_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    @property
    def keywords(self) -> list[str]:
        if not self.keywords_text:
            return []
        return [keyword for keyword in self.keywords_text.split(",") if keyword]
