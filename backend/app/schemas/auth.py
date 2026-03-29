from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    role: Literal["parent", "teacher"]
    phone: str | None = None
    accept_terms: bool
    accept_privacy_policy: bool
    marketing_email: bool = False
    marketing_sms: bool = False

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("first_name", "last_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    @field_validator("accept_terms")
    @classmethod
    def terms_must_be_accepted(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("Terms of service must be accepted")
        return v

    @field_validator("accept_privacy_policy")
    @classmethod
    def privacy_policy_must_be_accepted(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("Privacy policy must be accepted")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleOAuthStartRequest(BaseModel):
    flow: Literal["login", "register"]
    role: Literal["parent", "teacher"] | None = None
    redirect_path: str | None = None
    accept_terms: bool = False
    accept_privacy_policy: bool = False
    marketing_email: bool = False
    marketing_sms: bool = False

    @field_validator("redirect_path")
    @classmethod
    def redirect_path_must_be_relative(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        path = value.strip()
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Redirect path must be a relative path")
        return path

    @model_validator(mode="after")
    def validate_flow_requirements(self):
        if self.flow == "register":
            if self.role is None:
                raise ValueError("Role is required when registering with Google")
            if self.accept_terms is not True:
                raise ValueError("Terms of service must be accepted")
            if self.accept_privacy_policy is not True:
                raise ValueError("Privacy policy must be accepted")
        return self


class EmailRequest(BaseModel):
    email: EmailStr


class VerifyEmailRequest(BaseModel):
    token: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    role: str
    avatar_url: str | None = None
    email_verified: bool

    model_config = ConfigDict(from_attributes=True)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class GoogleOAuthStartResponse(BaseModel):
    authorization_url: str


class MessageResponse(BaseModel):
    message: str


class SessionResponse(BaseModel):
    id: str
    current: bool
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    user_agent: str | None = None
    ip_address: str | None = None
