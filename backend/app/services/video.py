"""
daily.co video room management.

Docs: https://docs.daily.co/reference/rest-api/rooms
"""
from datetime import UTC, datetime, timedelta

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()

_DAILY_API_BASE = "https://api.daily.co/v1"


async def create_room(booking_id: str, scheduled_at: datetime, duration_minutes: int) -> str | None:
    """
    Create a daily.co video room for a booking and return its URL.
    Returns None if DAILY_API_KEY is not configured (dev fallback).
    """
    if not settings.DAILY_API_KEY:
        logger.info("video.daily_skip", booking_id=booking_id, reason="no API key configured")
        return None

    # Room expires 30 minutes after the lesson ends
    exp = scheduled_at + timedelta(minutes=duration_minutes + 30)
    exp_ts = int(exp.replace(tzinfo=UTC).timestamp()) if exp.tzinfo is None else int(exp.timestamp())

    # Room names must be URL-safe; use first 8 chars of booking UUID
    room_name = f"fc-{booking_id.replace('-', '')[:16]}"

    payload = {
        "name": room_name,
        "privacy": "private",  # token required to join
        "properties": {
            "exp": exp_ts,
            "max_participants": 2,
            "enable_chat": True,
            "enable_screenshare": False,
            "start_video_off": False,
            "start_audio_off": False,
            "lang": "en",
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{_DAILY_API_BASE}/rooms",
                json=payload,
                headers={"Authorization": f"Bearer {settings.DAILY_API_KEY}"},
            )
            resp.raise_for_status()
            data = resp.json()
            url = data.get("url")
            logger.info("video.room_created", booking_id=booking_id, room=room_name, url=url)
            return url
    except httpx.HTTPStatusError as exc:
        logger.error(
            "video.create_room_failed",
            booking_id=booking_id,
            status=exc.response.status_code,
            body=exc.response.text,
        )
        return None
    except Exception as exc:
        logger.error("video.create_room_error", booking_id=booking_id, error=str(exc))
        return None


async def delete_room(room_name: str) -> None:
    """Delete a daily.co room (called on booking cancellation)."""
    if not settings.DAILY_API_KEY:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(
                f"{_DAILY_API_BASE}/rooms/{room_name}",
                headers={"Authorization": f"Bearer {settings.DAILY_API_KEY}"},
            )
            if resp.status_code not in (200, 404):
                resp.raise_for_status()
        logger.info("video.room_deleted", room=room_name)
    except Exception as exc:
        logger.warning("video.delete_room_error", room=room_name, error=str(exc))
