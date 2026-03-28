from datetime import UTC, datetime
from uuid import UUID

from app.services.receipts import build_receipt_reference, net_paid_amount_cents


def test_build_receipt_reference_uses_date_and_payment_prefix() -> None:
    payment_id = UUID("12345678-1234-5678-1234-567812345678")
    issued_at = datetime(2026, 3, 28, 18, 45, tzinfo=UTC)

    assert build_receipt_reference(payment_id, issued_at) == "FC-REC-20260328-12345678"


def test_net_paid_amount_cents_clamps_at_zero() -> None:
    assert net_paid_amount_cents(35_000, 0) == 35_000
    assert net_paid_amount_cents(35_000, 17_500) == 17_500
    assert net_paid_amount_cents(35_000, 40_000) == 0
