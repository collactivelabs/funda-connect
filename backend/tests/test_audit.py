from datetime import UTC, datetime
from uuid import uuid4

import pytest
from starlette.requests import Request

from app.models.audit import AuditLog
from app.services.audit import client_ip_from_request, create_audit_log


class FakeSession:
    def __init__(self):
        self.audit_logs: list[AuditLog] = []

    def add(self, instance):
        if isinstance(instance, AuditLog):
            self.audit_logs.append(instance)

    async def flush(self):
        return None


def build_request(*, forwarded_for: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = [(b"user-agent", b"pytest-agent")]
    if forwarded_for:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/admin/teachers/example/verify",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


def test_client_ip_prefers_forwarded_header():
    request = build_request(forwarded_for="203.0.113.5, 127.0.0.1")

    assert client_ip_from_request(request) == "203.0.113.5"


@pytest.mark.asyncio
async def test_create_audit_log_normalizes_metadata_and_request_details():
    session = FakeSession()
    actor_user_id = uuid4()
    booking_id = uuid4()
    request = build_request(forwarded_for="198.51.100.10")

    log = await create_audit_log(
        session,
        action="booking.reschedule",
        resource_type="booking",
        resource_id=booking_id,
        actor_user_id=actor_user_id,
        actor_role="parent",
        request=request,
        metadata={
            "booking_id": booking_id,
            "scheduled_at": datetime(2026, 3, 29, 8, 30, tzinfo=UTC),
            "tags": ["reschedule", "ui"],
        },
    )

    assert session.audit_logs == [log]
    assert log.actor_user_id == actor_user_id
    assert log.actor_role == "parent"
    assert log.resource_id == str(booking_id)
    assert log.ip_address == "198.51.100.10"
    assert log.user_agent == "pytest-agent"
    assert log.metadata_json == {
        "booking_id": str(booking_id),
        "scheduled_at": "2026-03-29T08:30:00+00:00",
        "tags": ["reschedule", "ui"],
    }
