from fastapi import APIRouter

from app.api.v1 import auth
from app.api.v1 import health
from app.api.v1 import resumes
from app.api.v1 import verification


api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
api_router.include_router(
    verification.router,
    prefix="/verification",
    tags=["verification"],
)
