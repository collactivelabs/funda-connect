from datetime import UTC, datetime
from uuid import UUID

from app.services.reports import build_learner_report_reference


def test_build_learner_report_reference_uses_date_and_learner_prefix() -> None:
    learner_id = UUID("87654321-1234-5678-1234-567812345678")
    generated_at = datetime(2026, 3, 29, 8, 15, tzinfo=UTC)

    assert build_learner_report_reference(learner_id, generated_at) == "FC-LRP-20260329-87654321"
