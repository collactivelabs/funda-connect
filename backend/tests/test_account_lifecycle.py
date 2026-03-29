from types import SimpleNamespace
from uuid import uuid4

from app.services.account_lifecycle import (
    anonymized_email_for_user,
    deletion_status_for_user,
    redact_payment_metadata,
)


def test_anonymized_email_is_stable_and_uses_deleted_domain():
    user_id = uuid4()

    first = anonymized_email_for_user(user_id, "person@example.com")
    second = anonymized_email_for_user(user_id, "person@example.com")

    assert first == second
    assert first.endswith("@deleted.local")
    assert "person@example.com" not in first


def test_redact_payment_metadata_removes_email_fields_recursively():
    metadata = {
        "email_address": "parent@example.com",
        "custom": {
            "first_name": "Hope",
            "nested": {"email": "guardian@example.com"},
        },
        "item_name": "Lesson",
    }

    redacted = redact_payment_metadata(metadata)

    assert redacted == {
        "email_address": "[deleted]",
        "custom": {
            "first_name": "[deleted]",
            "nested": {"email": "[deleted]"},
        },
        "item_name": "Lesson",
    }


def test_deletion_status_for_user_reports_pending_and_anonymized_states():
    pending_user = SimpleNamespace(deletion_requested_at=object(), anonymized_at=None)
    anonymized_user = SimpleNamespace(deletion_requested_at=object(), anonymized_at=object())
    active_user = SimpleNamespace(deletion_requested_at=None, anonymized_at=None)

    assert deletion_status_for_user(active_user) == "active"
    assert deletion_status_for_user(pending_user) == "pending_deletion"
    assert deletion_status_for_user(anonymized_user) == "anonymized"
