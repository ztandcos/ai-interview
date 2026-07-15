from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader
from pypdf.errors import PyPdfError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.resume import Resume
from app.models.user import User


ALLOWED_PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}


def clean_filename(filename: str | None) -> str:
    if not filename:
        return "resume.pdf"
    return Path(filename).name


async def read_pdf_upload(file: UploadFile, original_filename: str) -> bytes:
    if not original_filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are supported",
        )
    if file.content_type not in ALLOWED_PDF_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are supported",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )
    if len(file_bytes) > settings.MAX_RESUME_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Resume file is too large",
        )
    return file_bytes


def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(file_bytes))
        if reader.is_encrypted:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Encrypted PDF resumes are not supported",
            )
        page_texts = [page.extract_text() or "" for page in reader.pages]
    except HTTPException:
        raise
    except (PyPdfError, OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not parse PDF resume",
        ) from exc

    extracted_text = "\n\n".join(text.strip() for text in page_texts if text.strip())
    if not extracted_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="PDF does not contain extractable text",
        )
    return extracted_text


def save_resume_file(user_id: int, original_filename: str, file_bytes: bytes) -> Path:
    upload_root = Path(settings.UPLOAD_DIR)
    user_dir = upload_root / str(user_id)

    storage_path = user_dir / f"{uuid4().hex}.pdf"
    try:
        user_dir.mkdir(parents=True, exist_ok=True)
        storage_path.write_bytes(file_bytes)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save uploaded resume file",
        ) from exc
    return storage_path


async def upload_resume(
    db: AsyncSession,
    current_user: User,
    file: UploadFile,
) -> Resume:
    original_filename = clean_filename(file.filename)
    file_bytes = await read_pdf_upload(file, original_filename)
    extracted_text = extract_text_from_pdf(file_bytes)
    storage_path = save_resume_file(current_user.id, original_filename, file_bytes)

    resume = Resume(
        user_id=current_user.id,
        original_filename=original_filename,
        storage_path=str(storage_path),
        content_type=file.content_type or "application/pdf",
        file_size=len(file_bytes),
        extracted_text=extracted_text,
    )
    db.add(resume)
    try:
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        storage_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save resume metadata",
        ) from exc

    await db.refresh(resume)
    return resume


async def list_resumes(db: AsyncSession, current_user: User) -> list[Resume]:
    result = await db.scalars(
        select(Resume)
        .where(Resume.user_id == current_user.id)
        .order_by(Resume.created_at.desc(), Resume.id.desc())
    )
    return list(result)


async def get_resume(
    db: AsyncSession,
    current_user: User,
    resume_id: int,
) -> Resume:
    resume = await db.scalar(
        select(Resume).where(
            Resume.id == resume_id,
            Resume.user_id == current_user.id,
        )
    )
    if resume is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )
    return resume
