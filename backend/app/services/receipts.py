from datetime import datetime
from uuid import UUID


def build_receipt_reference(payment_id: UUID, issued_at: datetime) -> str:
    return f"FC-REC-{issued_at.strftime('%Y%m%d')}-{str(payment_id).split('-')[0].upper()}"


def net_paid_amount_cents(amount_cents: int, refund_amount_cents: int) -> int:
    return max(amount_cents - refund_amount_cents, 0)
