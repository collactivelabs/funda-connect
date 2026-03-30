# 07 — Booking & Scheduling Engine

> **Status:** Draft  
> **Last Updated:** 2026-03-25

---

## 1. Overview

The booking engine manages the full lifecycle from availability definition through lesson completion. It handles slot conflicts, prepaid weekly series, cancellations, rescheduling, and enforces business rules around timing and refunds.

---

## 2. Time & Timezone Handling

- **Storage:** All times stored in UTC
- **Display:** Converted to SAST (UTC+2) for all SA users
- **Lesson slots:** Defined in 30-minute increments (e.g., 09:00, 09:30, 10:00)
- **Default lesson duration:** 60 minutes (configurable per booking: 30, 60, 90, 120 min)
- **DST:** South Africa does not observe daylight saving time — SAST is fixed UTC+2

---

## 3. Availability Management

### 3.1 Weekly Recurring Slots

Teachers define their weekly availability as recurring time blocks:

```json
{
  "availability": [
    { "day_of_week": 0, "start_time": "09:00", "end_time": "12:00" },
    { "day_of_week": 0, "start_time": "14:00", "end_time": "16:00" },
    { "day_of_week": 2, "start_time": "09:00", "end_time": "15:00" },
    { "day_of_week": 4, "start_time": "10:00", "end_time": "13:00" }
  ]
}
```

`day_of_week`: 0 = Monday, 6 = Sunday

### 3.2 Blocked Dates

Teachers can block specific dates (holidays, personal):

```json
{
  "blocked_dates": [
    { "date": "2026-04-18", "reason": "Good Friday" },
    { "date": "2026-04-21", "reason": "Family Day" }
  ]
}
```

Blocked dates are applied on top of weekly availability when generating concrete bookable slots.

### 3.3 Available Slot Computation

When a parent requests available slots for a teacher on a given date:

```python
async def get_available_slots(teacher_id: UUID, date: date, duration_minutes: int = 60):
    day_of_week = date.weekday()
    
    # 1. Get recurring availability for this day
    availability = await get_availability(teacher_id, day_of_week)
    if not availability:
        return []
    
    # 2. Check for blocked dates
    if await is_date_blocked(teacher_id, date):
        return []
    
    # 3. Get existing bookings for this date
    existing_bookings = await get_bookings_for_date(teacher_id, date)
    booked_ranges = [(b.start_time, b.end_time) for b in existing_bookings
                     if b.status not in ('cancelled_by_parent', 'cancelled_by_teacher')]
    
    # 4. Generate available slots
    slots = []
    for avail in availability:
        current = avail.start_time
        while add_minutes(current, duration_minutes) <= avail.end_time:
            slot_end = add_minutes(current, duration_minutes)
            is_booked = any(
                times_overlap(current, slot_end, br_start, br_end)
                for br_start, br_end in booked_ranges
            )
            slots.append({
                "start_time": current,
                "end_time": slot_end,
                "is_booked": is_booked
            })
            current = add_minutes(current, 30)  # 30-min step
    
    return slots
```

---

## 4. Booking Flow

### 4.1 Single Lesson Booking

```
1. Parent selects teacher, subject, learner, date, and time slot
2. API validates:
   a. Teacher is verified and active
   b. Slot falls within teacher's availability
   c. Slot is not already booked (optimistic locking)
   d. Parent's learner matches the subject/grade
3. Booking created with status = "pending_payment"
4. Slot temporarily held for 15 minutes (Redis lock)
5. PayFast payment URL generated and returned
6. Parent redirected to PayFast
7. On payment success (ITN received):
   a. Booking status → "confirmed"
   b. Meeting link generated
   c. Confirmation SMS + email sent to both parties
8. If payment not received within 15 minutes:
   a. Slot lock released
   b. Booking status → "expired"
```

### 4.2 Slot Locking (Race Condition Prevention)

```python
SLOT_LOCK_TTL = 900  # 15 minutes

async def acquire_slot_lock(teacher_id: UUID, date: str, start_time: str) -> bool:
    """Attempt to lock a slot using Redis SETNX."""
    lock_key = f"slot_lock:{teacher_id}:{date}:{start_time}"
    acquired = await redis.set(lock_key, "locked", nx=True, ex=SLOT_LOCK_TTL)
    return acquired

async def release_slot_lock(teacher_id: UUID, date: str, start_time: str):
    lock_key = f"slot_lock:{teacher_id}:{date}:{start_time}"
    await redis.delete(lock_key)
```

### 4.3 Booking Number Generation

Human-readable, unique: `FC-YYYYMMDD-XXXX`

```python
import secrets
import string

def generate_booking_number(date: date) -> str:
    date_str = date.strftime("%Y%m%d")
    random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    return f"FC-{date_str}-{random_part}"
```

---

## 5. Booking State Machine

```
                    ┌─────────────────┐
                    │ pending_payment │
                    └──┬─────────┬────┘
                       │         │
               Payment │         │ Timeout (15min)
               success │         │
                       ▼         ▼
              ┌──────────┐  ┌─────────┐
              │confirmed │  │ expired │
              └──┬───────┘  └─────────┘
                 │
         Lesson  │ start_time reached
                 ▼
           ┌────────────┐
           │ in_progress │
           └──┬──────────┘
              │
    Teacher   │ marks complete
              ▼
          ┌───────────┐
          │ completed │
          └───────────┘

    ─── Cancellation (from confirmed or in_progress) ───

    ┌─────────────────────┐    ┌──────────────────────┐
    │cancelled_by_parent  │    │cancelled_by_teacher  │
    └─────────────────────┘    └──────────────────────┘

    ─── No-show (reported after 15min grace window) ───

    ┌────────────────┐    ┌──────────────────┐
    │no_show_parent  │    │no_show_teacher   │
    └────────────────┘    └──────────────────┘

    ─── Dispute (from any active state) ───

    ┌───────────┐
    │ disputed  │  → resolved by admin → completed OR refunded
    └───────────┘
```

---

## 6. Cancellation & Refund Policy

| Scenario | Timing | Refund | Teacher |
|----------|--------|--------|---------|
| Parent cancels | >24hrs before lesson | 100% refund | No payout |
| Parent cancels | <24hrs before lesson | 50% refund | 50% payout |
| Parent cancels | <2hrs before lesson | No refund | Full payout |
| Teacher cancels | Any time | 100% refund | No payout; strike logged |
| Parent no-show | — | No refund | Full payout |
| Teacher no-show | — | 100% refund | No payout; strike logged |

---

## 7. Weekly Series

### 7.1 Creation

A parent can request a prepaid weekly lesson series:

```json
{
  "teacher_id": "t1-uuid",
  "learner_id": "l1-uuid",
  "subject_id": "subj-uuid",
  "day_of_week": 2,
  "start_time": "10:00",
  "end_time": "11:00",
  "start_date": "2026-04-01",
  "end_date": "2026-06-30"
}
```

### 7.2 Processing

```
1. Validate that the selected weekly slot is available across the requested number of weeks
2. Create one root booking in `pending_payment`
3. Generate a single PayFast checkout for the **full series amount**
4. On successful payment:
   - Root booking moves to `confirmed`
   - The API creates the later weekly child bookings as `confirmed`
   - Each child booking points back to the root via `recurring_booking_id`
5. Skip blocked dates by rejecting series creation if any occurrence lands on an unavailable week
6. Either party can cancel the remaining future lessons in the series
```

### 7.3 Current Product Decision

FundaConnect currently supports **prepaid weekly series**, not auto-rebilling subscriptions.

- This keeps booking, dispute, refund, and payout behavior predictable
- Parent receipts and payment history show one series payment
- If the product later needs true subscription rebilling, it should be treated as a separate payment-system project rather than an incremental copy tweak

---

## 8. Reminders & Notifications

| Trigger | Timing | Channel | Recipient |
|---------|--------|---------|-----------|
| Booking confirmed | Immediately | Email + SMS | Both |
| Lesson reminder | 24 hours before | Email | Both |
| Lesson reminder | 1 hour before | SMS + push | Both |
| Meeting link | 15 min before | SMS | Both |
| Lesson completed | Immediately | Email | Parent |
| Review prompt | 2 hours after | Email + push | Parent |
| Cancellation | Immediately | Email + SMS | Both |
| Payout processed | On payout day | Email | Teacher |

---

## 9. Calendar Integration (Deferred Scope)

Current product decision as of March 30, 2026:

- FundaConnect does **not** currently implement Google Calendar sync, Outlook sync, or `.ics` export
- The supported scheduling model is in-app availability, blocked dates, reminders, rescheduling, and no-show handling
- External calendar integrations should only be added if they become a validated delivery requirement, because they introduce OAuth, sync-conflict, and support complexity that the current product does not need
