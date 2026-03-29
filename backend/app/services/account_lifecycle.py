from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote, urlparse
from uuid import UUID
from zoneinfo import ZoneInfo

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.redis import get_redis
from app.core.security import hash_password
from app.models.booking import Booking
from app.models.notification import Notification, NotificationPreference
from app.models.parent import Learner, ParentProfile
from app.models.payment import Payment, Refund, VerificationDocument
from app.models.review import Review
from app.models.teacher import TeacherProfile, TeacherSubject
from app.models.user import User
from app.services.audit import create_audit_log
from app.services.auth_tokens import revoke_all_refresh_sessions
from app.services.notifications import create_in_app_notification
from app.services.prepaid_series import recurring_weeks_from_metadata
from app.services.scheduling import booking_occurrence_starts, release_slot_hold, slot_lock_keys
from app.services.video import delete_room

DELETION_GRACE_DAYS = 30
SAST = ZoneInfo("Africa/Johannesburg")


def deletion_status_for_user(user: User) -> str:
    if user.anonymized_at is not None:
        return "anonymized"
    if user.deletion_requested_at is not None:
        return "pending_deletion"
    return "active"


def anonymized_email_for_user(user_id: UUID, current_email: str) -> str:
    digest = hashlib.sha256(f"{user_id}:{current_email}".encode()).hexdigest()[:24]
    return f"deleted-{digest}@deleted.local"


def redact_payment_metadata(value):
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            normalized_key = key.lower()
            if normalized_key in {
                "email",
                "email_address",
                "name_first",
                "name_last",
                "first_name",
                "last_name",
            }:
                redacted[key] = "[deleted]"
            else:
                redacted[key] = redact_payment_metadata(item)
        return redacted
    if isinstance(value, list):
        return [redact_payment_metadata(item) for item in value]
    return value


def _lesson_time_label(value: datetime) -> str:
    return value.astimezone(SAST).strftime("%a, %-d %b %Y at %H:%M SAST")


def _file_key_from_url(file_url: str | None) -> str | None:
    if not file_url:
        return None

    parsed = urlparse(file_url)
    path = unquote(parsed.path.lstrip("/"))
    if not path:
        return None

    bucket = settings.AWS_S3_BUCKET.strip() if settings.AWS_S3_BUCKET else ""
    if bucket and path.startswith(f"{bucket}/"):
        return path.removeprefix(f"{bucket}/")
    return path


def _delete_s3_object(key: str) -> None:
    s3 = boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY or None,
    )
    s3.delete_object(Bucket=settings.AWS_S3_BUCKET, Key=key)


async def _delete_stored_file(file_url: str | None) -> None:
    if not settings.AWS_S3_BUCKET or not settings.AWS_REGION:
        return

    key = _file_key_from_url(file_url)
    if not key:
        return

    try:
        await asyncio.to_thread(_delete_s3_object, key)
    except (BotoCoreError, ClientError):
        return


def _serialize_user(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
        "role": user.role,
        "avatar_url": user.avatar_url,
        "email_verified": user.email_verified,
        "phone_verified": user.phone_verified,
        "is_active": user.is_active,
        "deletion_requested_at": user.deletion_requested_at,
        "deletion_scheduled_for": user.deletion_scheduled_for,
        "anonymized_at": user.anonymized_at,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def _serialize_learner(learner: Learner) -> dict:
    return {
        "id": str(learner.id),
        "first_name": learner.first_name,
        "last_name": learner.last_name,
        "grade": learner.grade,
        "curriculum": learner.curriculum,
        "notes": learner.notes,
        "age": learner.age,
        "is_active": learner.is_active,
        "created_at": learner.created_at,
        "updated_at": learner.updated_at,
    }


def _serialize_parent_profile(profile: ParentProfile | None) -> dict | None:
    if profile is None:
        return None
    return {
        "id": str(profile.id),
        "province": profile.province,
        "is_premium": profile.is_premium,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
        "learners": [_serialize_learner(learner) for learner in profile.learners],
    }


def _serialize_teacher_profile(profile: TeacherProfile | None) -> dict | None:
    if profile is None:
        return None
    return {
        "id": str(profile.id),
        "bio": profile.bio,
        "headline": profile.headline,
        "years_experience": profile.years_experience,
        "hourly_rate_cents": profile.hourly_rate_cents,
        "curricula": profile.curricula or [],
        "verification_status": profile.verification_status,
        "is_listed": profile.is_listed,
        "average_rating": profile.average_rating,
        "total_reviews": profile.total_reviews,
        "total_lessons": profile.total_lessons,
        "is_premium": profile.is_premium,
        "province": profile.province,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
        "subjects": [
            {
                "id": str(subject.id),
                "subject_id": str(subject.subject_id),
                "subject_name": subject.subject.name if subject.subject else None,
                "grade_levels": subject.grade_levels,
                "curriculum": subject.curriculum,
                "created_at": subject.created_at,
                "updated_at": subject.updated_at,
            }
            for subject in profile.subjects
        ],
        "availability_slots": [
            {
                "id": str(slot.id),
                "day_of_week": slot.day_of_week,
                "start_time": slot.start_time,
                "end_time": slot.end_time,
                "is_active": slot.is_active,
                "created_at": slot.created_at,
                "updated_at": slot.updated_at,
            }
            for slot in profile.availability_slots
        ],
        "verification_documents": [
            {
                "id": str(document.id),
                "document_type": document.document_type,
                "file_url": document.file_url,
                "file_name": document.file_name,
                "status": document.status,
                "reviewer_notes": document.reviewer_notes,
                "reviewed_at": document.reviewed_at,
                "created_at": document.created_at,
                "updated_at": document.updated_at,
            }
            for document in profile.documents
        ],
    }


def _serialize_review(review: Review | None) -> dict | None:
    if review is None:
        return None
    return {
        "id": str(review.id),
        "teacher_id": str(review.teacher_id),
        "parent_id": str(review.parent_id),
        "rating": review.rating,
        "comment": review.comment,
        "teacher_reply": review.teacher_reply,
        "status": review.status,
        "created_at": review.created_at,
        "updated_at": review.updated_at,
    }


def _serialize_payment(payment: Payment | None) -> dict | None:
    if payment is None:
        return None
    return {
        "id": str(payment.id),
        "booking_id": str(payment.booking_id),
        "gateway": payment.gateway,
        "gateway_payment_id": payment.gateway_payment_id,
        "amount_cents": payment.amount_cents,
        "status": payment.status,
        "paid_at": payment.paid_at,
        "gateway_metadata": payment.gateway_metadata,
        "created_at": payment.created_at,
        "updated_at": payment.updated_at,
        "refund": (
            {
                "id": str(payment.refund.id),
                "amount_cents": payment.refund.amount_cents,
                "status": payment.refund.status,
                "reason": payment.refund.reason,
                "requested_by_role": payment.refund.requested_by_role,
                "policy_code": payment.refund.policy_code,
                "processed_at": payment.refund.processed_at,
                "gateway_reference": payment.refund.gateway_reference,
                "notes": payment.refund.notes,
                "created_at": payment.refund.created_at,
                "updated_at": payment.refund.updated_at,
            }
            if payment.refund
            else None
        ),
        "payout": (
            {
                "id": str(payment.payout.id),
                "teacher_id": str(payment.payout.teacher_id),
                "amount_cents": payment.payout.amount_cents,
                "status": payment.payout.status,
                "processed_at": payment.payout.processed_at,
                "bank_reference": payment.payout.bank_reference,
                "notes": payment.payout.notes,
                "created_at": payment.payout.created_at,
                "updated_at": payment.payout.updated_at,
            }
            if payment.payout
            else None
        ),
    }


def _serialize_booking(booking: Booking) -> dict:
    return {
        "id": str(booking.id),
        "parent_id": str(booking.parent_id),
        "teacher_id": str(booking.teacher_id),
        "learner_id": str(booking.learner_id),
        "subject_id": str(booking.subject_id),
        "scheduled_at": booking.scheduled_at,
        "duration_minutes": booking.duration_minutes,
        "hold_expires_at": booking.hold_expires_at,
        "status": booking.status,
        "amount_cents": booking.amount_cents,
        "commission_cents": booking.commission_cents,
        "teacher_payout_cents": booking.teacher_payout_cents,
        "video_room_url": booking.video_room_url,
        "is_trial": booking.is_trial,
        "is_recurring": booking.is_recurring,
        "recurring_booking_id": str(booking.recurring_booking_id) if booking.recurring_booking_id else None,
        "parent_notes": booking.parent_notes,
        "cancellation_reason": booking.cancellation_reason,
        "cancelled_at": booking.cancelled_at,
        "cancelled_by_role": booking.cancelled_by_role,
        "created_at": booking.created_at,
        "updated_at": booking.updated_at,
        "learner": (
            {
                "id": str(booking.learner.id),
                "first_name": booking.learner.first_name,
                "last_name": booking.learner.last_name,
                "grade": booking.learner.grade,
                "curriculum": booking.learner.curriculum,
            }
            if booking.learner
            else None
        ),
        "subject": (
            {
                "id": str(booking.subject.id),
                "name": booking.subject.name,
                "slug": booking.subject.slug,
            }
            if booking.subject
            else None
        ),
        "payment": _serialize_payment(booking.payment),
        "dispute": (
            {
                "id": str(booking.dispute.id),
                "raised_by_role": booking.dispute.raised_by_role,
                "reason": booking.dispute.reason,
                "status": booking.dispute.status,
                "resolution": booking.dispute.resolution,
                "original_booking_status": booking.dispute.original_booking_status,
                "admin_notes": booking.dispute.admin_notes,
                "resolved_at": booking.dispute.resolved_at,
                "created_at": booking.dispute.created_at,
                "updated_at": booking.dispute.updated_at,
            }
            if booking.dispute
            else None
        ),
        "review": _serialize_review(booking.review),
    }


def _serialize_notification(notification: Notification) -> dict:
    return {
        "id": str(notification.id),
        "type": notification.type,
        "channel": notification.channel,
        "title": notification.title,
        "body": notification.body,
        "metadata": notification.metadata_json,
        "is_read": notification.is_read,
        "sent_at": notification.sent_at,
        "read_at": notification.read_at,
        "created_at": notification.created_at,
        "updated_at": notification.updated_at,
    }


def _serialize_notification_preferences(preferences: NotificationPreference | None) -> dict | None:
    if preferences is None:
        return None
    return {
        "in_app_enabled": preferences.in_app_enabled,
        "email_enabled": preferences.email_enabled,
        "sms_enabled": preferences.sms_enabled,
        "push_enabled": preferences.push_enabled,
        "created_at": preferences.created_at,
        "updated_at": preferences.updated_at,
    }


async def _load_user_for_export(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.parent_profile).selectinload(ParentProfile.learners),
            selectinload(User.teacher_profile)
            .selectinload(TeacherProfile.subjects)
            .selectinload(TeacherSubject.subject),
            selectinload(User.teacher_profile).selectinload(TeacherProfile.documents),
            selectinload(User.teacher_profile).selectinload(TeacherProfile.availability_slots),
            selectinload(User.notifications),
            selectinload(User.notification_preferences),
        )
    )


async def _bookings_for_user(db: AsyncSession, user: User) -> list[Booking]:
    statement = (
        select(Booking)
        .options(
            selectinload(Booking.learner),
            selectinload(Booking.subject),
            selectinload(Booking.payment).selectinload(Payment.refund),
            selectinload(Booking.payment).selectinload(Payment.payout),
            selectinload(Booking.dispute),
            selectinload(Booking.review),
            selectinload(Booking.parent).selectinload(ParentProfile.user),
            selectinload(Booking.teacher).selectinload(TeacherProfile.user),
        )
        .order_by(Booking.created_at.desc())
    )

    if user.role == "parent" and user.parent_profile:
        result = await db.scalars(statement.where(Booking.parent_id == user.parent_profile.id))
        return result.all()
    if user.role == "teacher" and user.teacher_profile:
        result = await db.scalars(statement.where(Booking.teacher_id == user.teacher_profile.id))
        return result.all()
    return []


async def export_account_data(db: AsyncSession, user_id: UUID) -> dict[str, object]:
    user = await _load_user_for_export(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    bookings = await _bookings_for_user(db, user)

    return {
        "user": _serialize_user(user),
        "deletion": {
            "status": deletion_status_for_user(user),
            "deletion_requested_at": user.deletion_requested_at,
            "deletion_scheduled_for": user.deletion_scheduled_for,
            "anonymized_at": user.anonymized_at,
        },
        "parent_profile": _serialize_parent_profile(user.parent_profile),
        "teacher_profile": _serialize_teacher_profile(user.teacher_profile),
        "bookings": [_serialize_booking(booking) for booking in bookings],
        "notifications": [_serialize_notification(notification) for notification in user.notifications],
        "notification_preferences": _serialize_notification_preferences(user.notification_preferences),
    }


def _deletion_response(user: User, *, cancelled_future_bookings: int = 0) -> dict[str, object]:
    return {
        "status": deletion_status_for_user(user),
        "is_active": user.is_active,
        "deletion_requested_at": user.deletion_requested_at,
        "deletion_scheduled_for": user.deletion_scheduled_for,
        "anonymized_at": user.anonymized_at,
        "cancelled_future_bookings": cancelled_future_bookings,
        "grace_period_days": DELETION_GRACE_DAYS,
    }


async def get_account_deletion_status(db: AsyncSession, user_id: UUID) -> dict[str, object]:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _deletion_response(user)


async def _future_bookings_owned_by_user(db: AsyncSession, user: User, now_utc: datetime) -> list[Booking]:
    statement = (
        select(Booking)
        .where(
            Booking.status.in_(["pending_payment", "confirmed"]),
            Booking.scheduled_at > now_utc,
        )
        .options(
            selectinload(Booking.payment).selectinload(Payment.refund),
            selectinload(Booking.payment).selectinload(Payment.payout),
            selectinload(Booking.parent).selectinload(ParentProfile.user),
            selectinload(Booking.teacher).selectinload(TeacherProfile.user),
        )
    )
    if user.role == "parent" and user.parent_profile:
        result = await db.scalars(statement.where(Booking.parent_id == user.parent_profile.id))
        return result.all()
    if user.role == "teacher" and user.teacher_profile:
        result = await db.scalars(statement.where(Booking.teacher_id == user.teacher_profile.id))
        return result.all()
    return []


async def request_account_deletion(
    db: AsyncSession,
    *,
    user_id: UUID,
    request: Request,
) -> dict[str, object]:
    user = await db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.parent_profile),
            selectinload(User.teacher_profile),
        )
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.anonymized_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account has already been anonymized",
        )
    if user.deletion_requested_at is not None:
        return _deletion_response(user)

    now_utc = datetime.now(UTC)
    user.is_active = False
    user.deletion_requested_at = now_utc
    user.deletion_scheduled_for = now_utc + timedelta(days=DELETION_GRACE_DAYS)

    if user.teacher_profile is not None:
        user.teacher_profile.is_listed = False

    future_bookings = await _future_bookings_owned_by_user(db, user, now_utc)
    hold_keys: list[str] = []
    room_names: list[str] = []

    for booking in future_bookings:
        previous_status = booking.status
        payment = booking.payment
        booking.status = "cancelled"
        booking.cancellation_reason = "Account deletion requested"
        booking.cancelled_at = now_utc
        booking.cancelled_by_role = user.role
        booking.hold_expires_at = None

        if booking.video_room_url:
            room_names.append(booking.video_room_url.rstrip("/").split("/")[-1])
            booking.video_room_url = None

        if previous_status == "pending_payment" and payment is not None:
            recurring_weeks = recurring_weeks_from_metadata(payment.gateway_metadata)
            payment.status = "cancelled"
            hold_keys.extend(
                slot_lock_keys(
                    booking.teacher_id,
                    booking_occurrence_starts(booking.scheduled_at, recurring_weeks),
                    booking.duration_minutes,
                )
            )

        if previous_status == "confirmed" and payment is not None:
            booking.teacher_payout_cents = 0
            booking.commission_cents = 0

            if payment.payout and payment.payout.status != "paid":
                payment.payout.status = "failed"
                payment.payout.notes = "Cancelled because an account deletion was requested."

            refund = payment.refund
            if refund is None:
                refund = Refund(
                    payment_id=payment.id,
                    amount_cents=payment.amount_cents,
                    status="pending",
                    reason="Account deletion requested",
                    requested_by_role=user.role,
                    policy_code="account_deletion",
                    notes="Created from account deletion. Process manually in PayFast and then mark refunded.",
                )
                db.add(refund)
            else:
                refund.amount_cents = payment.amount_cents
                refund.status = "pending"
                refund.reason = "Account deletion requested"
                refund.requested_by_role = user.role
                refund.policy_code = "account_deletion"
                refund.notes = "Created from account deletion. Process manually in PayFast and then mark refunded."

        if user.role == "parent" and booking.teacher and booking.teacher.user:
            await create_in_app_notification(
                db,
                user_id=booking.teacher.user_id,
                notification_type="booking_cancelled",
                title="Lesson cancelled",
                body=(
                    f"A lesson on {_lesson_time_label(booking.scheduled_at)} was cancelled because the parent account is being closed."
                ),
                metadata={"booking_id": str(booking.id), "cancelled_by_role": user.role},
            )
        elif user.role == "teacher" and booking.parent and booking.parent.user:
            await create_in_app_notification(
                db,
                user_id=booking.parent.user_id,
                notification_type="booking_cancelled",
                title="Lesson cancelled",
                body=(
                    f"A lesson on {_lesson_time_label(booking.scheduled_at)} was cancelled because the teacher account is being closed."
                ),
                metadata={"booking_id": str(booking.id), "cancelled_by_role": user.role},
            )

    await revoke_all_refresh_sessions(user.id)
    await create_audit_log(
        db,
        action="account.delete_request",
        resource_type="user",
        resource_id=user.id,
        actor_user_id=user.id,
        actor_role=user.role,
        request=request,
        metadata={
            "deletion_scheduled_for": user.deletion_scheduled_for,
            "cancelled_future_bookings": len(future_bookings),
        },
    )
    await db.commit()

    if hold_keys:
        redis = await get_redis()
        await release_slot_hold(redis, list(dict.fromkeys(hold_keys)))

    for room_name in room_names:
        asyncio.create_task(delete_room(room_name))

    return _deletion_response(user, cancelled_future_bookings=len(future_bookings))


async def anonymize_user_account(db: AsyncSession, user: User) -> bool:
    now_utc = datetime.now(UTC)
    if user.anonymized_at is not None:
        return False
    if user.deletion_scheduled_for is None or user.deletion_scheduled_for > now_utc:
        return False

    old_email = user.email

    if user.parent_profile is not None:
        user.parent_profile.province = None
        user.parent_profile.is_premium = False
        learners_result = await db.scalars(
            select(Learner).where(Learner.parent_id == user.parent_profile.id)
        )
        for index, learner in enumerate(learners_result.all(), start=1):
            learner.first_name = "Deleted"
            learner.last_name = f"Learner {index}"
            learner.notes = None
            learner.age = None

        reviews_result = await db.scalars(
            select(Review).where(Review.parent_id == user.parent_profile.id)
        )
        for review in reviews_result.all():
            review.comment = None

        bookings_result = await db.scalars(
            select(Booking)
            .where(Booking.parent_id == user.parent_profile.id)
            .options(selectinload(Booking.payment))
        )
        for booking in bookings_result.all():
            booking.parent_notes = None
            if booking.payment and booking.payment.gateway_metadata:
                booking.payment.gateway_metadata = redact_payment_metadata(booking.payment.gateway_metadata)

    if user.teacher_profile is not None:
        user.teacher_profile.bio = None
        user.teacher_profile.headline = None
        user.teacher_profile.years_experience = None
        user.teacher_profile.hourly_rate_cents = None
        user.teacher_profile.curricula = []
        user.teacher_profile.verification_status = "suspended"
        user.teacher_profile.is_listed = False
        user.teacher_profile.average_rating = None
        user.teacher_profile.total_reviews = 0
        user.teacher_profile.total_lessons = 0
        user.teacher_profile.is_premium = False
        user.teacher_profile.province = None

        availability_result = await db.scalars(
            select(Booking).where(Booking.teacher_id == user.teacher_profile.id).options(selectinload(Booking.payment))
        )
        for booking in availability_result.all():
            if booking.payment and booking.payment.gateway_metadata:
                booking.payment.gateway_metadata = redact_payment_metadata(booking.payment.gateway_metadata)

        reviews_result = await db.scalars(
            select(Review).where(Review.teacher_id == user.teacher_profile.id)
        )
        for review in reviews_result.all():
            review.teacher_reply = None

        teacher_subjects_result = await db.scalars(
            select(TeacherSubject).where(TeacherSubject.teacher_id == user.teacher_profile.id)
        )
        for subject in teacher_subjects_result.all():
            subject.grade_levels = []

        for slot in user.teacher_profile.availability_slots:
            slot.is_active = False

        for document in user.teacher_profile.documents:
            await _delete_stored_file(document.file_url)
            document.file_url = f"deleted://verification-document/{document.id}"
            document.file_name = "deleted"
            document.reviewer_notes = None

    await _delete_stored_file(user.avatar_url)
    await db.execute(delete(Notification).where(Notification.user_id == user.id))
    await db.execute(delete(NotificationPreference).where(NotificationPreference.user_id == user.id))

    user.email = anonymized_email_for_user(user.id, old_email)
    user.first_name = "Deleted"
    user.last_name = "User"
    user.phone = None
    user.avatar_url = None
    user.password_hash = hash_password(hashlib.sha256(f"{user.id}:{old_email}:{now_utc.isoformat()}".encode()).hexdigest())
    user.email_verified = False
    user.phone_verified = False
    user.is_active = False
    user.anonymized_at = now_utc
    user.deletion_scheduled_for = None

    await revoke_all_refresh_sessions(user.id)
    await create_audit_log(
        db,
        action="account.anonymize",
        resource_type="user",
        resource_id=user.id,
        actor_role="system",
        metadata={"role": user.role},
    )
    return True


async def anonymize_due_accounts(db: AsyncSession, *, limit: int = 100) -> list[UUID]:
    result = await db.scalars(
        select(User)
        .where(
            User.is_active == False,  # noqa: E712
            User.deletion_scheduled_for.is_not(None),
            User.deletion_scheduled_for <= datetime.now(UTC),
            User.anonymized_at.is_(None),
        )
        .options(
            selectinload(User.parent_profile),
            selectinload(User.teacher_profile).selectinload(TeacherProfile.documents),
            selectinload(User.teacher_profile).selectinload(TeacherProfile.availability_slots),
        )
        .limit(limit)
    )
    users = result.all()
    anonymized_ids: list[UUID] = []

    for user in users:
        if await anonymize_user_account(db, user):
            anonymized_ids.append(user.id)

    if anonymized_ids:
        await db.commit()

    return anonymized_ids
