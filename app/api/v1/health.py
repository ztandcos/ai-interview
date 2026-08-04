from fastapi import APIRouter

from app.core.config import settings


router = APIRouter()


@router.get("")
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "project": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/ping")
async def ping() -> dict[str, str]:
    return {"message": "pong"}
