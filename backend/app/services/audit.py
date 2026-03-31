from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


def _normalize_audit_value(value):
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _normalize_audit_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_normalize_audit_value(item) for item in value]
    return str(value)


def client_ip_from_request(request: Request | None) -> str | None:
    if request is None:
        return None

    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        forwarded_ip = forwarded.split(",")[0].strip()
        if forwarded_ip:
            return forwarded_ip

    return request.client.host if request.client else None


async def create_audit_log(
    db: AsyncSession,
    *,
    action: str,
    resource_type: str,
    resource_id: UUID | str | None = None,
    actor_user_id: UUID | None = None,
    actor_role: str | None = None,
    request: Request | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        ip_address=client_ip_from_request(request),
        user_agent=request.headers.get("user-agent") if request is not None else None,
        metadata_json=_normalize_audit_value(metadata) if metadata is not None else None,
    )
    db.add(audit_log)
    await db.flush()
    return audit_log
