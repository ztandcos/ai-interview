from fastapi import APIRouter, Depends, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.redis import get_redis
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    MessageResponse,
    RefreshTokenRequest,
    TokenPairResponse,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth_service import (
    login_user,
    logout_user,
    refresh_access_token,
    register_user,
)


router = APIRouter()


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    user_in: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    return await register_user(db, user_in)


@router.post("/login", response_model=TokenPairResponse)
async def login(
    user_in: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TokenPairResponse:
    return await login_user(db, redis, user_in)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    token_in: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    return await refresh_access_token(db, token_in.refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    token_in: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await logout_user(db, token_in.refresh_token)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserResponse)
async def read_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return current_user
