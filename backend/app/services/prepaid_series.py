from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

PREPAID_SERIES_ROOT_BOOKING_ID_KEY = "series_root_booking_id"
PREPAID_SERIES_ROOT_PAYMENT_ID_KEY = "series_root_payment_id"
PREPAID_SERIES_OCCURRENCE_INDEX_KEY = "series_occurrence_index"
PREPAID_SERIES_TOTAL_AMOUNT_CENTS_KEY = "series_total_amount_cents"
PREPAID_SERIES_HIDE_IN_HISTORY_KEY = "hide_in_parent_history"
PREPAID_SERIES_RECURRING_WEEKS_KEY = "recurring_weeks"


def recurring_weeks_from_metadata(metadata: dict | None) -> int:
    if not isinstance(metadata, dict):
        return 1
    try:
        return max(int(metadata.get(PREPAID_SERIES_RECURRING_WEEKS_KEY) or 1), 1)
    except (TypeError, ValueError):
        return 1


def series_total_amount_cents(per_lesson_amount_cents: int, recurring_weeks: int) -> int:
    return per_lesson_amount_cents * max(recurring_weeks, 1)


def checkout_amount_cents(payment_amount_cents: int, metadata: dict | None) -> int:
    if not isinstance(metadata, dict):
        return payment_amount_cents
    if metadata.get(PREPAID_SERIES_HIDE_IN_HISTORY_KEY):
        return payment_amount_cents
    total_amount = metadata.get(PREPAID_SERIES_TOTAL_AMOUNT_CENTS_KEY)
    if isinstance(total_amount, int) and total_amount > 0:
        return total_amount
    weeks = recurring_weeks_from_metadata(metadata)
    if weeks > 1:
        return series_total_amount_cents(payment_amount_cents, weeks)
    return payment_amount_cents


def build_root_series_metadata(root_booking_id: UUID, recurring_weeks: int) -> dict[str, int | str]:
    return {
        PREPAID_SERIES_ROOT_BOOKING_ID_KEY: str(root_booking_id),
        PREPAID_SERIES_OCCURRENCE_INDEX_KEY: 1,
        PREPAID_SERIES_RECURRING_WEEKS_KEY: recurring_weeks,
    }


def build_child_series_metadata(
    *,
    root_booking_id: UUID,
    root_payment_id: UUID,
    recurring_weeks: int,
    occurrence_index: int,
) -> dict[str, int | str | bool]:
    return {
        PREPAID_SERIES_ROOT_BOOKING_ID_KEY: str(root_booking_id),
        PREPAID_SERIES_ROOT_PAYMENT_ID_KEY: str(root_payment_id),
        PREPAID_SERIES_OCCURRENCE_INDEX_KEY: occurrence_index,
        PREPAID_SERIES_RECURRING_WEEKS_KEY: recurring_weeks,
        PREPAID_SERIES_HIDE_IN_HISTORY_KEY: True,
    }


def series_root_booking_id(
    *,
    booking_id: UUID,
    recurring_booking_id: UUID | None,
    is_recurring: bool,
    metadata: dict | None,
) -> UUID:
    if recurring_booking_id is not None:
        return recurring_booking_id
    if not is_recurring:
        return booking_id
    if isinstance(metadata, dict):
        raw_value = metadata.get(PREPAID_SERIES_ROOT_BOOKING_ID_KEY)
        if raw_value:
            try:
                return UUID(str(raw_value))
            except ValueError:
                pass
    return booking_id


def is_hidden_in_parent_history(metadata: dict | None) -> bool:
    return bool(isinstance(metadata, dict) and metadata.get(PREPAID_SERIES_HIDE_IN_HISTORY_KEY))


def aggregate_payment_status(statuses: Iterable[str]) -> str:
    normalized = [status for status in statuses if status]
    if not normalized:
        return "pending"
    if "pending" in normalized:
        return "pending"
    if "failed" in normalized:
        return "failed"
    if "partially_refunded" in normalized:
        return "partially_refunded"
    if all(status == "refunded" for status in normalized):
        return "refunded"
    if "refunded" in normalized:
        return "partially_refunded"
    if all(status == "cancelled" for status in normalized):
        return "cancelled"
    return "complete"


def aggregate_refund_status(statuses: Iterable[str | None]) -> str | None:
    normalized = {status for status in statuses if status}
    if not normalized:
        return None
    for candidate in ("pending", "processing", "failed", "refunded", "cancelled"):
        if candidate in normalized:
            return candidate
    return next(iter(normalized))
