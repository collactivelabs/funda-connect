from __future__ import annotations

import re
from decimal import Decimal

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class SMSConfigurationError(RuntimeError):
    pass


def configured_sms_provider() -> str | None:
    if settings.BULKSMS_USERNAME and settings.BULKSMS_PASSWORD:
        return "bulksms"
    if settings.AT_API_KEY and settings.AT_USERNAME:
        return "africastalking"
    return None


def sms_provider_configured() -> bool:
    return configured_sms_provider() is not None


def normalize_phone_number(phone: str) -> str:
    raw = phone.strip()
    if not raw:
        raise ValueError("Phone number cannot be empty")

    if raw.startswith("+"):
        normalized = f"+{re.sub(r'\D', '', raw)}".replace("++", "+", 1)
    else:
        digits = re.sub(r"\D", "", raw)
        if digits.startswith("00"):
            normalized = f"+{digits[2:]}"
        elif digits.startswith("0") and len(digits) == 10:
            normalized = f"+27{digits[1:]}"
        elif digits.startswith("27"):
            normalized = f"+{digits}"
        elif 10 <= len(digits) <= 15:
            normalized = f"+{digits}"
        else:
            raise ValueError("Phone number must be a valid local or international number")

    digit_count = len(re.sub(r"\D", "", normalized))
    if not normalized.startswith("+") or digit_count < 10 or digit_count > 15:
        raise ValueError("Phone number must be a valid E.164-compatible number")
    return normalized


async def send_sms_message(*, to: str, message: str) -> dict[str, str]:
    provider = configured_sms_provider()
    if provider is None:
        raise SMSConfigurationError("SMS delivery is not configured")

    normalized_to = normalize_phone_number(to)
    body = message.strip()
    if not body:
        raise ValueError("SMS message cannot be empty")

    async with httpx.AsyncClient(timeout=15.0) as client:
        if provider == "bulksms":
            response = await client.post(
                "https://api.bulksms.com/v1/messages",
                auth=(settings.BULKSMS_USERNAME, settings.BULKSMS_PASSWORD),
                json={"to": normalized_to, "body": body},
                headers={"Accept": "application/json"},
            )
        else:
            response = await client.post(
                "https://api.africastalking.com/version1/messaging",
                headers={"apiKey": settings.AT_API_KEY, "Accept": "application/json"},
                data={
                    "username": settings.AT_USERNAME,
                    "to": normalized_to,
                    "message": body,
                },
            )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error(
            "sms.send.failed",
            provider=provider,
            recipient=normalized_to,
            status_code=response.status_code,
            response_text=response.text,
        )
        raise RuntimeError(f"SMS provider rejected the request: {response.text}") from exc

    logger.info("sms.send.success", provider=provider, recipient=normalized_to)
    return {"provider": provider, "recipient": normalized_to}


def format_rand(cents: int) -> str:
    amount = Decimal(cents) / Decimal("100")
    return f"R{amount:.2f}"


def build_booking_confirmation_parent_sms(
    *,
    teacher_name: str,
    subject_name: str,
    scheduled_at: str,
    booking_id: str,
) -> str:
    return (
        f"FundaConnect: Your {subject_name} lesson with {teacher_name} is confirmed for "
        f"{scheduled_at}. Ref {booking_id[:8].upper()}."
    )


def build_booking_confirmation_teacher_sms(
    *,
    parent_name: str,
    subject_name: str,
    scheduled_at: str,
) -> str:
    return (
        f"FundaConnect: New {subject_name} lesson with {parent_name} confirmed for {scheduled_at}."
    )


def build_verification_result_sms(*, status_label: str, notes: str | None = None) -> str:
    if notes:
        trimmed_notes = notes.strip()
        return f"FundaConnect: Your verification status is {status_label}. Notes: {trimmed_notes}"
    return f"FundaConnect: Your verification status is {status_label}."


def build_payout_processed_sms(*, amount_cents: int, bank_reference: str | None = None) -> str:
    reference_suffix = f" Ref {bank_reference}." if bank_reference else "."
    return f"FundaConnect: Your payout of {format_rand(amount_cents)} has been marked paid{reference_suffix}"


def build_refund_processed_sms(*, amount_cents: int, lesson_reference: str) -> str:
    return (
        f"FundaConnect: Your refund of {format_rand(amount_cents)} for lesson "
        f"{lesson_reference} has been processed."
    )
