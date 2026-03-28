from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.booking import Booking
from app.core.deps import get_db, require_parent
from app.models.parent import Learner, ParentProfile
from app.models.payment import Payment
from app.models.teacher import TeacherProfile
from app.schemas.parent import (
    CreateLearnerRequest,
    LearnerResponse,
    ParentPaymentHistoryItemResponse,
    ParentPaymentHistoryResponse,
    ParentPaymentReceiptResponse,
    UpdateLearnerRequest,
)
from app.services.prepaid_series import (
    aggregate_payment_status,
    aggregate_refund_status,
    checkout_amount_cents,
    recurring_weeks_from_metadata,
    series_root_booking_id,
)
from app.services.receipts import build_receipt_reference, net_paid_amount_cents

router = APIRouter()


async def _get_parent_profile(payload: dict, db: AsyncSession) -> ParentProfile:
    profile = await db.scalar(
        select(ParentProfile).where(ParentProfile.user_id == UUID(payload["sub"]))
    )
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent profile not found")
    return profile


def _root_payment_for_group(payments: list[Payment], group_id: UUID) -> Payment:
    return next((payment for payment in payments if payment.booking_id == group_id), payments[0])


def _build_grouped_payment_history(payments: list[Payment]) -> list[ParentPaymentHistoryItemResponse]:
    grouped: dict[UUID, list[Payment]] = defaultdict(list)
    order: list[UUID] = []

    for payment in payments:
        group_id = series_root_booking_id(
            booking_id=payment.booking_id,
            recurring_booking_id=payment.booking.recurring_booking_id,
            is_recurring=payment.booking.is_recurring,
            metadata=payment.gateway_metadata,
        )
        if group_id not in grouped:
            order.append(group_id)
        grouped[group_id].append(payment)

    items: list[ParentPaymentHistoryItemResponse] = []
    for group_id in order:
        series_payments = grouped[group_id]
        root_payment = _root_payment_for_group(series_payments, group_id)
        refund_amount_cents = sum(
            payment.refund.amount_cents
            for payment in series_payments
            if payment.refund
        )
        lessons_in_series = max(
            recurring_weeks_from_metadata(root_payment.gateway_metadata),
            len(series_payments),
        )

        items.append(
            ParentPaymentHistoryItemResponse(
                id=root_payment.id,
                booking_id=root_payment.booking_id,
                gateway=root_payment.gateway,
                gateway_payment_id=root_payment.gateway_payment_id,
                amount_cents=checkout_amount_cents(root_payment.amount_cents, root_payment.gateway_metadata),
                status=aggregate_payment_status(payment.status for payment in series_payments),
                paid_at=root_payment.paid_at,
                created_at=root_payment.created_at,
                booking_status=root_payment.booking.status,
                scheduled_at=root_payment.booking.scheduled_at,
                teacher_name=(
                    f"{root_payment.booking.teacher.user.first_name} {root_payment.booking.teacher.user.last_name}"
                ),
                learner_name=root_payment.booking.learner.full_name,
                subject_name=root_payment.booking.subject.name,
                refund_amount_cents=refund_amount_cents,
                refund_status=aggregate_refund_status(
                    payment.refund.status if payment.refund else None
                    for payment in series_payments
                ),
                refund_requested_at=max(
                    (payment.refund.created_at for payment in series_payments if payment.refund),
                    default=None,
                ),
                refund_processed_at=max(
                    (
                        payment.refund.processed_at
                        for payment in series_payments
                        if payment.refund and payment.refund.processed_at is not None
                    ),
                    default=None,
                ),
                is_series=lessons_in_series > 1,
                series_lessons=lessons_in_series,
            )
        )

    return items


@router.get("/me/learners", response_model=list[LearnerResponse])
async def list_learners(
    payload: dict = Depends(require_parent),
    db: AsyncSession = Depends(get_db),
):
    """List all learner profiles for the authenticated parent."""
    profile = await _get_parent_profile(payload, db)
    result = await db.scalars(
        select(Learner)
        .where(Learner.parent_id == profile.id, Learner.is_active == True)  # noqa: E712
        .order_by(Learner.created_at)
    )
    return result.all()


@router.get("/me/payments", response_model=ParentPaymentHistoryResponse)
async def list_payment_history(
    payload: dict = Depends(require_parent),
    db: AsyncSession = Depends(get_db),
):
    """List payment history for the authenticated parent."""
    profile = await _get_parent_profile(payload, db)
    result = await db.scalars(
        select(Payment)
        .join(Payment.booking)
        .where(Booking.parent_id == profile.id)
        .options(
            selectinload(Payment.refund),
            selectinload(Payment.booking).selectinload(Booking.learner),
            selectinload(Payment.booking).selectinload(Booking.subject),
            selectinload(Payment.booking).selectinload(Booking.teacher).selectinload(TeacherProfile.user),
        )
        .order_by(Payment.created_at.desc())
    )
    payments = result.all()

    history_items = _build_grouped_payment_history(payments)

    completed = sum(
        item.amount_cents
        for item in history_items
        if item.status in {"complete", "partially_refunded", "refunded"}
    )
    pending = sum(item.amount_cents for item in history_items if item.status == "pending")
    refunded = sum(
        payment.refund.amount_cents
        for payment in payments
        if payment.refund and payment.refund.status == "refunded"
    )
    refund_pending = sum(
        payment.refund.amount_cents
        for payment in payments
        if payment.refund and payment.refund.status in {"pending", "processing"}
    )

    return ParentPaymentHistoryResponse(
        completed_payments_cents=completed,
        pending_payments_cents=pending,
        refunded_payments_cents=refunded,
        refund_pending_cents=refund_pending,
        payments=history_items,
    )


@router.get("/me/payments/{payment_id}/receipt", response_model=ParentPaymentReceiptResponse)
async def get_payment_receipt(
    payment_id: UUID,
    payload: dict = Depends(require_parent),
    db: AsyncSession = Depends(get_db),
):
    """Return receipt details for a payment owned by the authenticated parent."""
    profile = await _get_parent_profile(payload, db)
    payment = await db.scalar(
        select(Payment)
        .join(Payment.booking)
        .where(Payment.id == payment_id, Booking.parent_id == profile.id)
        .options(
            selectinload(Payment.refund),
            selectinload(Payment.booking).selectinload(Booking.parent).selectinload(ParentProfile.user),
            selectinload(Payment.booking).selectinload(Booking.learner),
            selectinload(Payment.booking).selectinload(Booking.subject),
            selectinload(Payment.booking).selectinload(Booking.teacher).selectinload(TeacherProfile.user),
        )
    )
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    group_id = series_root_booking_id(
        booking_id=payment.booking_id,
        recurring_booking_id=payment.booking.recurring_booking_id,
        is_recurring=payment.booking.is_recurring,
        metadata=payment.gateway_metadata,
    )
    group_result = await db.scalars(
        select(Payment)
        .join(Payment.booking)
        .where(Booking.parent_id == profile.id)
        .options(
            selectinload(Payment.refund),
            selectinload(Payment.booking).selectinload(Booking.parent).selectinload(ParentProfile.user),
            selectinload(Payment.booking).selectinload(Booking.learner),
            selectinload(Payment.booking).selectinload(Booking.subject),
            selectinload(Payment.booking).selectinload(Booking.teacher).selectinload(TeacherProfile.user),
        )
    )
    grouped_payments = [
        candidate
        for candidate in group_result.all()
        if series_root_booking_id(
            booking_id=candidate.booking_id,
            recurring_booking_id=candidate.booking.recurring_booking_id,
            is_recurring=candidate.booking.is_recurring,
            metadata=candidate.gateway_metadata,
        )
        == group_id
    ]
    root_payment = _root_payment_for_group(grouped_payments, group_id)

    issued_at = root_payment.paid_at or root_payment.created_at
    refund_amount_cents = sum(
        candidate.refund.amount_cents
        for candidate in grouped_payments
        if candidate.refund and candidate.refund.status == "refunded"
    )
    lessons_in_series = max(
        recurring_weeks_from_metadata(root_payment.gateway_metadata),
        len(grouped_payments),
    )
    payment_status = aggregate_payment_status(candidate.status for candidate in grouped_payments)
    charged_amount_cents = checkout_amount_cents(root_payment.amount_cents, root_payment.gateway_metadata)

    return ParentPaymentReceiptResponse(
        payment_id=root_payment.id,
        booking_id=root_payment.booking_id,
        receipt_reference=build_receipt_reference(root_payment.id, issued_at),
        issued_at=issued_at,
        payment_status=payment_status,
        payment_gateway=root_payment.gateway,
        payment_gateway_reference=root_payment.gateway_payment_id,
        amount_cents=charged_amount_cents,
        refund_amount_cents=refund_amount_cents,
        net_paid_cents=net_paid_amount_cents(charged_amount_cents, refund_amount_cents),
        parent_name=f"{root_payment.booking.parent.user.first_name} {root_payment.booking.parent.user.last_name}",
        parent_email=root_payment.booking.parent.user.email,
        teacher_name=f"{root_payment.booking.teacher.user.first_name} {root_payment.booking.teacher.user.last_name}",
        learner_name=root_payment.booking.learner.full_name,
        subject_name=root_payment.booking.subject.name,
        scheduled_at=root_payment.booking.scheduled_at,
        duration_minutes=root_payment.booking.duration_minutes,
        is_trial=root_payment.booking.is_trial,
        is_series=lessons_in_series > 1,
        series_lessons=lessons_in_series,
    )


@router.post("/me/learners", response_model=LearnerResponse, status_code=status.HTTP_201_CREATED)
async def create_learner(
    body: CreateLearnerRequest,
    payload: dict = Depends(require_parent),
    db: AsyncSession = Depends(get_db),
):
    """Add a new learner profile under the parent account."""
    profile = await _get_parent_profile(payload, db)
    learner = Learner(parent_id=profile.id, **body.model_dump())
    db.add(learner)
    await db.flush()
    return learner


@router.patch("/me/learners/{learner_id}", response_model=LearnerResponse)
async def update_learner(
    learner_id: UUID,
    body: UpdateLearnerRequest,
    payload: dict = Depends(require_parent),
    db: AsyncSession = Depends(get_db),
):
    """Update a learner profile."""
    profile = await _get_parent_profile(payload, db)
    learner = await db.get(Learner, learner_id)
    if not learner or learner.parent_id != profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(learner, field, value)

    return learner


@router.delete("/me/learners/{learner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_learner(
    learner_id: UUID,
    payload: dict = Depends(require_parent),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a learner profile."""
    profile = await _get_parent_profile(payload, db)
    learner = await db.get(Learner, learner_id)
    if not learner or learner.parent_id != profile.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learner not found")
    learner.is_active = False
