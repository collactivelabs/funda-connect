from datetime import UTC, datetime
from uuid import UUID

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.consent import ConsentRecord

TERMS_OF_SERVICE = "terms_of_service"
PRIVACY_POLICY = "privacy_policy"
MARKETING_EMAIL = "marketing_email"
MARKETING_SMS = "marketing_sms"

CONSENT_LABELS = (
    TERMS_OF_SERVICE,
    PRIVACY_POLICY,
    MARKETING_EMAIL,
    MARKETING_SMS,
)


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


def _user_agent(request: Request | None) -> str | None:
    return request.headers.get("user-agent") if request is not None else None


def current_consent_versions() -> dict[str, str]:
    return {
        TERMS_OF_SERVICE: settings.TERMS_OF_SERVICE_VERSION,
        PRIVACY_POLICY: settings.PRIVACY_POLICY_VERSION,
        MARKETING_EMAIL: settings.MARKETING_CONSENT_VERSION,
        MARKETING_SMS: settings.MARKETING_CONSENT_VERSION,
    }


async def record_consent(
    db: AsyncSession,
    *,
    user_id: UUID,
    consent_type: str,
    granted: bool,
    version: str,
    request: Request | None = None,
) -> ConsentRecord | None:
    current = await db.scalar(
        select(ConsentRecord)
        .where(
            ConsentRecord.user_id == user_id,
            ConsentRecord.consent_type == consent_type,
            ConsentRecord.revoked_at.is_(None),
        )
        .order_by(ConsentRecord.granted_at.desc())
    )

    if current and current.granted == granted and current.version == version:
        return None

    now_utc = datetime.now(UTC)
    if current:
        current.revoked_at = now_utc

    consent = ConsentRecord(
        user_id=user_id,
        consent_type=consent_type,
        granted=granted,
        version=version,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
        granted_at=now_utc,
    )
    db.add(consent)
    await db.flush()
    return consent


async def record_registration_consents(
    db: AsyncSession,
    *,
    user_id: UUID,
    request: Request,
    marketing_email: bool,
    marketing_sms: bool,
) -> None:
    versions = current_consent_versions()
    await record_consent(
        db,
        user_id=user_id,
        consent_type=TERMS_OF_SERVICE,
        granted=True,
        version=versions[TERMS_OF_SERVICE],
        request=request,
    )
    await record_consent(
        db,
        user_id=user_id,
        consent_type=PRIVACY_POLICY,
        granted=True,
        version=versions[PRIVACY_POLICY],
        request=request,
    )
    await record_consent(
        db,
        user_id=user_id,
        consent_type=MARKETING_EMAIL,
        granted=marketing_email,
        version=versions[MARKETING_EMAIL],
        request=request,
    )
    await record_consent(
        db,
        user_id=user_id,
        consent_type=MARKETING_SMS,
        granted=marketing_sms,
        version=versions[MARKETING_SMS],
        request=request,
    )


async def get_current_consents(db: AsyncSession, user_id: UUID) -> dict[str, dict[str, object]]:
    result = await db.scalars(
        select(ConsentRecord)
        .where(
            ConsentRecord.user_id == user_id,
            ConsentRecord.revoked_at.is_(None),
        )
        .order_by(ConsentRecord.granted_at.desc())
    )
    records = result.all()
    current: dict[str, dict[str, object]] = {}

    for consent_type in CONSENT_LABELS:
        record = next((item for item in records if item.consent_type == consent_type), None)
        current[consent_type] = {
            "granted": record.granted if record is not None else False,
            "version": record.version
            if record is not None
            else current_consent_versions()[consent_type],
            "granted_at": record.granted_at if record is not None else None,
            "revoked_at": record.revoked_at if record is not None else None,
        }
    return current


async def update_marketing_consents(
    db: AsyncSession,
    *,
    user_id: UUID,
    request: Request,
    marketing_email: bool,
    marketing_sms: bool,
) -> dict[str, dict[str, object]]:
    versions = current_consent_versions()
    await record_consent(
        db,
        user_id=user_id,
        consent_type=MARKETING_EMAIL,
        granted=marketing_email,
        version=versions[MARKETING_EMAIL],
        request=request,
    )
    await record_consent(
        db,
        user_id=user_id,
        consent_type=MARKETING_SMS,
        granted=marketing_sms,
        version=versions[MARKETING_SMS],
        request=request,
    )
    return await get_current_consents(db, user_id)
