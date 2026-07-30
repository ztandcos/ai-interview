from datetime import datetime, timezone

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    get_password_hash,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import (
    PasswordChangeRequest,
    TokenPairResponse,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserUpdateRequest,
)
from app.services.verification_service import verify_verification_code


async def register_user(db: AsyncSession, user_in: UserRegisterRequest) -> User:
    normalized_email = str(user_in.email).strip().lower()
    existing_user = await db.scalar(select(User).where(User.email == normalized_email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=normalized_email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
    )

    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc

    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, user_in: UserLoginRequest) -> User:
    normalized_email = str(user_in.email).strip().lower()
    user = await db.scalar(select(User).where(User.email == normalized_email))
    if user is None or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def login_user(
    db: AsyncSession,
    redis: Redis,
    user_in: UserLoginRequest,
) -> TokenPairResponse:
    user = await authenticate_user(db, user_in)
    await verify_verification_code(redis, str(user_in.email), user_in.code)

    access_token = create_access_token(subject=str(user.id))
    refresh_token, token_jti, expires_at = create_refresh_token(subject=str(user.id))

    db.add(
        RefreshToken(
            user_id=user.id,
            token_jti=token_jti,
            expires_at=expires_at,
        )
    )
    await db.commit()

    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> TokenResponse:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_refresh_token(refresh_token)
        user_id = int(payload.get("sub", ""))
        token_jti = str(payload["jti"])
    except (ValueError, TypeError):
        raise credentials_exception

    token_record = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_jti == token_jti)
    )
    if (
        token_record is None
        or token_record.user_id != user_id
        or token_record.revoked_at is not None
        or token_record.expires_at <= utc_now_naive()
    ):
        raise credentials_exception

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    return TokenResponse(access_token=create_access_token(subject=str(user.id)))


async def logout_user(db: AsyncSession, refresh_token: str) -> None:
    try:
        payload = decode_refresh_token(refresh_token)
        token_jti = str(payload["jti"])
    except (ValueError, TypeError):
        return

    token_record = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_jti == token_jti)
    )
    if token_record is None or token_record.revoked_at is not None:
        return

    token_record.revoked_at = utc_now_naive()
    await db.commit()


async def update_user_profile(
    db: AsyncSession,
    current_user: User,
    user_in: UserUpdateRequest,
) -> User:
    current_user.full_name = user_in.full_name.strip() if user_in.full_name else None
    await db.commit()
    await db.refresh(current_user)
    return current_user


async def change_user_password(
    db: AsyncSession,
    current_user: User,
    password_in: PasswordChangeRequest,
) -> None:
    if not verify_password(password_in.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if password_in.current_password == password_in.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    current_user.hashed_password = get_password_hash(password_in.new_password)
    active_refresh_tokens = await db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    revoked_at = utc_now_naive()
    for token_record in active_refresh_tokens:
        token_record.revoked_at = revoked_at
    await db.commit()
