import json
from typing import Annotated

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "change-me"
    DEBUG: bool = True
    APP_BASE_URL: str = Field(
        default="http://localhost:3001",
        validation_alias=AliasChoices("APP_BASE_URL", "NEXT_PUBLIC_APP_URL"),
    )
    API_BASE_URL: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("API_BASE_URL", "NEXT_PUBLIC_API_URL"),
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://fundaconnect:fundaconnect@localhost:5432/fundaconnect"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Meilisearch
    MEILISEARCH_URL: str = "http://localhost:7700"
    MEILISEARCH_MASTER_KEY: str = "masterKey"

    # Observability
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = ""
    SENTRY_RELEASE: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0
    SENTRY_PROFILES_SAMPLE_RATE: float = 0.0
    SENTRY_SEND_DEFAULT_PII: bool = False

    # Web push
    WEB_PUSH_PUBLIC_KEY: str = ""
    WEB_PUSH_PRIVATE_KEY: str = ""
    WEB_PUSH_SUBJECT: str = "mailto:noreply@fundaconnect.co.za"

    # JWT
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 60

    # Legal / consent
    TERMS_OF_SERVICE_VERSION: str = "2026-03-29"
    PRIVACY_POLICY_VERSION: str = "2026-03-29"
    MARKETING_CONSENT_VERSION: str = "2026-03-29"

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_OAUTH_STATE_EXPIRE_MINUTES: int = 15

    # PayFast
    PAYFAST_MERCHANT_ID: str = ""
    PAYFAST_MERCHANT_KEY: str = ""
    PAYFAST_PASSPHRASE: str = ""
    PAYFAST_SANDBOX: bool = True
    PAYFAST_RETURN_URL: str = ""
    PAYFAST_CANCEL_URL: str = ""
    PAYFAST_NOTIFY_URL: str = ""

    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "af-south-1"
    AWS_S3_BUCKET: str = "fundaconnect-documents"
    MALWARE_SCAN_MODE: str = "off"
    CLAMSCAN_PATH: str = "clamscan"

    # Email
    EMAIL_FROM: str = "noreply@fundaconnect.co.za"
    EMAIL_FROM_NAME: str = "FundaConnect"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # SMS
    BULKSMS_USERNAME: str = ""
    BULKSMS_PASSWORD: str = ""
    AT_API_KEY: str = ""
    AT_USERNAME: str = ""

    # Video
    DAILY_API_KEY: str = ""

    # CORS
    ALLOWED_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:3001",
        "http://localhost:8000",
    ]

    # Commission
    PLATFORM_COMMISSION_RATE: float = 0.175  # 17.5%

    # Booking / scheduling
    BOOKING_HOLD_MINUTES: int = 15
    BOOKING_MIN_LEAD_MINUTES: int = 60
    BOOKING_NO_SHOW_GRACE_MINUTES: int = 15
    BOOKABLE_SLOT_DAYS: int = 21

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        if isinstance(value, tuple):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                parsed = json.loads(raw)
                if not isinstance(parsed, list):
                    raise ValueError("ALLOWED_ORIGINS JSON value must be an array")
                return [str(origin).strip() for origin in parsed if str(origin).strip()]
            return [origin.strip() for origin in raw.split(",") if origin.strip()]
        raise TypeError("ALLOWED_ORIGINS must be a list or comma-separated string")


settings = Settings()
