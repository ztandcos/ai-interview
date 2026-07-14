import logging
import secrets

from fastapi import HTTPException, status
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings


logger = logging.getLogger(__name__)

VERIFICATION_PURPOSE = "register"
DELETE_CODE_IF_MATCHES = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


def normalize_email(email: str) -> str:
    return email.strip().lower()


def verification_code_key(email: str) -> str:
    return f"verification:{VERIFICATION_PURPOSE}:code:{normalize_email(email)}"


def verification_cooldown_key(email: str) -> str:
    return f"verification:{VERIFICATION_PURPOSE}:cooldown:{normalize_email(email)}"


def generate_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def redis_unavailable_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Verification service is temporarily unavailable",
    )


async def send_verification_code(redis: Redis, email: str) -> int:
    cooldown_key = verification_cooldown_key(email)

    try:
        cooldown_created = await redis.set(
            cooldown_key,
            "1",
            ex=settings.VERIFICATION_SEND_COOLDOWN_SECONDS,
            nx=True,
        )
        if not cooldown_created:
            retry_after = max(await redis.ttl(cooldown_key), 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {retry_after} seconds before requesting another code",
                headers={"Retry-After": str(retry_after)},
            )

        code = generate_verification_code()
        await redis.set(
            verification_code_key(email),
            code,
            ex=settings.VERIFICATION_CODE_TTL_SECONDS,
        )
    except RedisError as exc:
        raise redis_unavailable_exception() from exc

    # First version does not integrate an email provider; code is visible only in server logs.
    logger.info("Verification code generated for %s: %s", normalize_email(email), code)
    print(code)
    return settings.VERIFICATION_CODE_TTL_SECONDS


async def verify_verification_code(redis: Redis, email: str, code: str) -> None:
    try:
        deleted = await redis.eval(
            DELETE_CODE_IF_MATCHES,
            1,
            verification_code_key(email),
            code,
        )
    except RedisError as exc:
        raise redis_unavailable_exception() from exc

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )
