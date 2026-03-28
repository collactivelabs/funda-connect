"""
Email sending service using the `emails` package + stdlib smtplib.
All sends are synchronous so they can be called from Celery workers.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

from app.core.config import settings

logger = structlog.get_logger()


def _send(to: str, subject: str, html_body: str) -> None:
    """Send a single HTML email via configured SMTP server."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if not settings.SMTP_HOST:
        # Dev fallback: just log
        logger.info("email.dev_skip", to=to, subject=subject)
        return

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.sendmail(settings.EMAIL_FROM, [to], msg.as_string())
        logger.info("email.sent", to=to, subject=subject)
    except Exception as exc:
        logger.error("email.failed", to=to, subject=subject, error=str(exc))
        raise


# ── Template helpers ──────────────────────────────────────────

def _base(content: str) -> str:
    """Minimal HTML wrapper so emails render cleanly in all clients."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background:#f9f9f9; margin:0; padding:0; }}
  .wrap {{ max-width:560px; margin:40px auto; background:#fff;
           border-radius:8px; border:1px solid #e5e7eb; overflow:hidden; }}
  .hdr  {{ background:#1a1a1a; padding:24px 32px; }}
  .hdr a{{ color:#fff; font-size:18px; font-weight:700; text-decoration:none; }}
  .hdr span {{ color:#10b981; }}
  .bdy  {{ padding:32px; color:#374151; font-size:15px; line-height:1.6; }}
  .bdy h2 {{ margin-top:0; font-size:20px; color:#111827; }}
  .box  {{ background:#f3f4f6; border-radius:6px; padding:16px 20px;
           margin:20px 0; font-size:14px; }}
  .box p {{ margin:4px 0; }}
  .btn  {{ display:inline-block; background:#10b981; color:#fff; padding:12px 24px;
           border-radius:6px; text-decoration:none; font-weight:600; margin-top:16px; }}
  .ftr  {{ padding:20px 32px; font-size:12px; color:#9ca3af; border-top:1px solid #f3f4f6; }}
</style>
</head>
<body>
  <div class="wrap">
    <div class="hdr"><a href="https://fundaconnect.co.za">Funda<span>Connect</span></a></div>
    <div class="bdy">{content}</div>
    <div class="ftr">© FundaConnect · South Africa · <a href="https://fundaconnect.co.za">fundaconnect.co.za</a></div>
  </div>
</body>
</html>"""


# ── Email builders ────────────────────────────────────────────

def booking_confirmation_parent(
    to: str,
    parent_name: str,
    teacher_name: str,
    subject_name: str,
    scheduled_at: str,
    duration_minutes: int,
    amount_cents: int,
    booking_id: str,
) -> None:
    amount = f"R{amount_cents / 100:.2f}"
    content = f"""
<h2>Booking confirmed!</h2>
<p>Hi {parent_name}, your lesson has been booked and payment received.</p>
<div class="box">
  <p><strong>Teacher:</strong> {teacher_name}</p>
  <p><strong>Subject:</strong> {subject_name}</p>
  <p><strong>When:</strong> {scheduled_at}</p>
  <p><strong>Duration:</strong> {duration_minutes} minutes</p>
  <p><strong>Amount paid:</strong> {amount}</p>
</div>
<a class="btn" href="https://fundaconnect.co.za/parent">View my lessons</a>
<p style="margin-top:24px;font-size:13px;color:#6b7280;">Booking reference: {booking_id[:8].upper()}</p>
"""
    _send(to, "Your FundaConnect lesson is confirmed", _base(content))


def booking_confirmation_teacher(
    to: str,
    teacher_name: str,
    parent_name: str,
    subject_name: str,
    scheduled_at: str,
    duration_minutes: int,
    payout_cents: int,
) -> None:
    payout = f"R{payout_cents / 100:.2f}"
    content = f"""
<h2>New lesson booked!</h2>
<p>Hi {teacher_name}, a parent has just booked a lesson with you.</p>
<div class="box">
  <p><strong>Parent:</strong> {parent_name}</p>
  <p><strong>Subject:</strong> {subject_name}</p>
  <p><strong>When:</strong> {scheduled_at}</p>
  <p><strong>Duration:</strong> {duration_minutes} minutes</p>
  <p><strong>Your payout:</strong> {payout}</p>
</div>
<a class="btn" href="https://fundaconnect.co.za/teacher">View my lessons</a>
"""
    _send(to, "You have a new lesson booking", _base(content))


def verification_approved(to: str, teacher_name: str) -> None:
    content = f"""
<h2>You're verified! 🎉</h2>
<p>Hi {teacher_name}, your FundaConnect account has been verified.</p>
<p>Your profile is now listed and parents can start booking lessons with you.</p>
<a class="btn" href="https://fundaconnect.co.za/teacher">Go to my dashboard</a>
"""
    _send(to, "Your FundaConnect account is now verified", _base(content))


def verification_rejected(to: str, teacher_name: str, notes: str | None) -> None:
    notes_html = f"<div class='box'><p><strong>Reviewer notes:</strong> {notes}</p></div>" if notes else ""
    content = f"""
<h2>Verification update</h2>
<p>Hi {teacher_name}, unfortunately your verification was not approved at this time.</p>
{notes_html}
<p>Please review the requirements and re-upload your documents.</p>
<a class="btn" href="https://fundaconnect.co.za/teacher">Update my documents</a>
"""
    _send(to, "FundaConnect verification update", _base(content))


def verification_submitted_admin(teacher_name: str, teacher_id: str, document_count: int) -> None:
    """Internal alert to admin when a teacher uploads documents."""
    if not settings.EMAIL_FROM:
        return
    content = f"""
<h2>New verification submission</h2>
<div class="box">
  <p><strong>Teacher:</strong> {teacher_name}</p>
  <p><strong>ID:</strong> {teacher_id}</p>
  <p><strong>Documents:</strong> {document_count}</p>
</div>
<a class="btn" href="https://fundaconnect.co.za/admin">Review in admin panel</a>
"""
    _send(settings.EMAIL_FROM, "Teacher verification submission — action required", _base(content))


def payout_processed(to: str, teacher_name: str, amount_cents: int, bank_reference: str | None) -> None:
    amount = f"R{amount_cents / 100:.2f}"
    ref_html = f"<p><strong>Bank reference:</strong> {bank_reference}</p>" if bank_reference else ""
    content = f"""
<h2>Payout processed</h2>
<p>Hi {teacher_name}, your FundaConnect earnings have been paid out.</p>
<div class="box">
  <p><strong>Amount:</strong> {amount}</p>
  {ref_html}
</div>
<p>Funds typically arrive within 1–2 business days.</p>
<a class="btn" href="https://fundaconnect.co.za/teacher">View my account</a>
"""
    _send(to, f"FundaConnect payout of {amount} processed", _base(content))


def email_verification_link(to: str, first_name: str, verify_url: str) -> None:
    content = f"""
<h2>Verify your email</h2>
<p>Hi {first_name}, welcome to FundaConnect.</p>
<p>Please verify your email address to secure your account.</p>
<a class="btn" href="{verify_url}">Verify my email</a>
<p style="margin-top:24px;font-size:13px;color:#6b7280;">If the button does not work, copy and paste this link into your browser:</p>
<p style="font-size:13px;word-break:break-all;color:#6b7280;">{verify_url}</p>
"""
    _send(to, "Verify your FundaConnect email address", _base(content))


def password_reset_link(to: str, first_name: str, reset_url: str) -> None:
    content = f"""
<h2>Reset your password</h2>
<p>Hi {first_name}, we received a request to reset your FundaConnect password.</p>
<a class="btn" href="{reset_url}">Choose a new password</a>
<p style="margin-top:24px;font-size:13px;color:#6b7280;">If you did not request this, you can ignore this email.</p>
<p style="font-size:13px;word-break:break-all;color:#6b7280;">{reset_url}</p>
"""
    _send(to, "Reset your FundaConnect password", _base(content))
