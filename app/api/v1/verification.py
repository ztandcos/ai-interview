from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from app.core.redis import get_redis
from app.schemas.verification import (
    VerificationCodeSendRequest,
    VerificationCodeSendResponse,
    VerificationCodeVerifyRequest,
    VerificationCodeVerifyResponse,
)
from app.services.verification_service import (
    send_verification_code,
    verify_verification_code,
)


router = APIRouter()


@router.post("/send", response_model=VerificationCodeSendResponse)
async def send_code(
    request: VerificationCodeSendRequest,
    redis: Redis = Depends(get_redis),
) -> VerificationCodeSendResponse:
    expires_in_seconds = await send_verification_code(redis, str(request.email))
    return VerificationCodeSendResponse(
        message="Verification code sent",
        expires_in_seconds=expires_in_seconds,
    )


@router.post("/verify", response_model=VerificationCodeVerifyResponse)
async def verify_code(
    request: VerificationCodeVerifyRequest,
    redis: Redis = Depends(get_redis),
) -> VerificationCodeVerifyResponse:
    await verify_verification_code(redis, str(request.email), request.code)
    return VerificationCodeVerifyResponse(message="Verification code verified")
