from uuid import uuid4

from app.services.prepaid_series import (
    aggregate_payment_status,
    aggregate_refund_status,
    build_child_series_metadata,
    build_root_series_metadata,
    checkout_amount_cents,
    is_hidden_in_parent_history,
    recurring_weeks_from_metadata,
    series_root_booking_id,
    series_total_amount_cents,
)


def test_series_total_amount_cents_multiplies_per_lesson_amount() -> None:
    assert series_total_amount_cents(35000, 4) == 140000


def test_checkout_amount_uses_series_total_for_root_payment() -> None:
    metadata = build_root_series_metadata(uuid4(), 4)
    metadata["series_total_amount_cents"] = 140000

    assert checkout_amount_cents(35000, metadata) == 140000


def test_checkout_amount_keeps_child_payment_allocations_per_lesson() -> None:
    metadata = build_child_series_metadata(
        root_booking_id=uuid4(),
        root_payment_id=uuid4(),
        recurring_weeks=4,
        occurrence_index=2,
    )

    assert checkout_amount_cents(35000, metadata) == 35000
    assert is_hidden_in_parent_history(metadata) is True


def test_series_root_booking_id_prefers_parent_link_when_present() -> None:
    root_booking_id = uuid4()

    assert (
        series_root_booking_id(
            booking_id=uuid4(),
            recurring_booking_id=root_booking_id,
            is_recurring=True,
            metadata=None,
        )
        == root_booking_id
    )


def test_series_root_booking_id_reads_root_from_metadata_for_root_bookings() -> None:
    root_booking_id = uuid4()
    metadata = build_root_series_metadata(root_booking_id, 6)

    assert (
        series_root_booking_id(
            booking_id=root_booking_id,
            recurring_booking_id=None,
            is_recurring=True,
            metadata=metadata,
        )
        == root_booking_id
    )
    assert recurring_weeks_from_metadata(metadata) == 6


def test_aggregate_payment_status_handles_partial_refunds() -> None:
    assert aggregate_payment_status(["complete", "refunded"]) == "partially_refunded"


def test_aggregate_refund_status_prefers_pending_work() -> None:
    assert aggregate_refund_status(["refunded", "pending"]) == "pending"
