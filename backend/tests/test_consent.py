from datetime import UTC, datetime
from uuid import uuid4

import pytest
from starlette.requests import Request

from app.models.consent import ConsentRecord
from app.schemas.auth import RegisterRequest
from app.services.consent import (
    MARKETING_EMAIL,
    PRIVACY_POLICY,
    TERMS_OF_SERVICE,
    current_consent_versions,
    get_current_consents,
    record_consent,
)


class FakeScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class FakeSession:
    def __init__(self, current: ConsentRecord | None = None, records: list[ConsentRecord] | None = None):
        self.current = current
        self.records = records or []

    async def scalar(self, statement):
        return self.current

    async def scalars(self, statement):
        return FakeScalarResult(self.records)

    def add(self, instance):
        if isinstance(instance, ConsentRecord):
            self.records.append(instance)
            self.current = instance

    async def flush(self):
        return None


def build_request() -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/register",
        "headers": [(b"user-agent", b"pytest-agent")],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


def test_register_request_requires_terms_and_privacy_acceptance():
    with pytest.raises(Exception):
        RegisterRequest(
            email="user@example.com",
            password="password123",
            first_name="Hope",
            last_name="Tester",
            role="parent",
            accept_terms=False,
            accept_privacy_policy=True,
        )


@pytest.mark.asyncio
async def test_record_consent_revokes_previous_active_record():
    user_id = uuid4()
    existing = ConsentRecord(
        user_id=user_id,
        consent_type=MARKETING_EMAIL,
        granted=False,
        version="2026-03-01",
        granted_at=datetime(2026, 3, 1, tzinfo=UTC),
    )
    session = FakeSession(current=existing, records=[existing])

    created = await record_consent(
        session,
        user_id=user_id,
        consent_type=MARKETING_EMAIL,
        granted=True,
        version="2026-03-29",
        request=build_request(),
    )

    assert created is not None
    assert existing.revoked_at is not None
    assert created.granted is True
    assert created.version == "2026-03-29"


@pytest.mark.asyncio
async def test_get_current_consents_defaults_missing_values_to_false():
    session = FakeSession(
        records=[
            ConsentRecord(
                user_id=uuid4(),
                consent_type=TERMS_OF_SERVICE,
                granted=True,
                version="2026-03-29",
                granted_at=datetime(2026, 3, 29, tzinfo=UTC),
            ),
            ConsentRecord(
                user_id=uuid4(),
                consent_type=PRIVACY_POLICY,
                granted=True,
                version="2026-03-29",
                granted_at=datetime(2026, 3, 29, tzinfo=UTC),
            ),
        ]
    )

    consents = await get_current_consents(session, uuid4())

    assert consents[TERMS_OF_SERVICE]["granted"] is True
    assert consents[PRIVACY_POLICY]["granted"] is True
    assert consents[MARKETING_EMAIL]["granted"] is False
    assert consents[MARKETING_EMAIL]["version"] == current_consent_versions()[MARKETING_EMAIL]
