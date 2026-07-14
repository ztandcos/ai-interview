from pydantic import BaseModel, EmailStr, Field


class VerificationCodeSendRequest(BaseModel):
    email: EmailStr


class VerificationCodeVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class VerificationCodeSendResponse(BaseModel):
    message: str
    expires_in_seconds: int


class VerificationCodeVerifyResponse(BaseModel):
    message: str
