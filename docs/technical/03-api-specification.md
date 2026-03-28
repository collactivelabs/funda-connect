# 03 — API Specification

> **Status:** Draft  
> **Last Updated:** 2026-03-25  
> **Base URL:** `https://api.fundaconnect.co.za/api/v1`  
> **Format:** JSON  
> **Auth:** Bearer JWT

---

## 1. General Conventions

### Request Format
- Content-Type: `application/json`
- Authentication: `Authorization: Bearer <access_token>`
- All dates: ISO 8601 (`2026-03-25T14:30:00Z`)
- All monetary values: integer cents (`25000` = R250.00)

### Response Envelope
```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

### Error Response
```json
{
  "success": false,
  "error": {
    "code": "BOOKING_SLOT_UNAVAILABLE",
    "message": "The selected time slot is no longer available.",
    "details": { ... }
  }
}
```

### HTTP Status Codes
| Code | Usage |
|------|-------|
| 200  | Success |
| 201  | Created |
| 204  | No Content (successful delete) |
| 400  | Bad Request (validation error) |
| 401  | Unauthorized (missing/invalid token) |
| 403  | Forbidden (insufficient permissions) |
| 404  | Not Found |
| 409  | Conflict (duplicate, booking clash) |
| 422  | Unprocessable Entity (business rule violation) |
| 429  | Too Many Requests |
| 500  | Internal Server Error |

### Pagination
- Query params: `?page=1&per_page=20`
- Default: `page=1`, `per_page=20`, max `per_page=100`

### Filtering & Sorting
- Filters: `?subject=mathematics&grade=GR12&curriculum=CAPS&min_rate=15000&max_rate=40000`
- Sorting: `?sort_by=rating_average&sort_order=desc`

---

## 2. Authentication Endpoints

### `POST /auth/register`
Register a new user (parent or teacher).

**Request:**
```json
{
  "email": "sipho@example.co.za",
  "password": "SecureP@ss123",
  "first_name": "Sipho",
  "last_name": "Ndlovu",
  "phone": "+27821234567",
  "role": "parent"
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "a1b2c3d4-...",
      "email": "sipho@example.co.za",
      "first_name": "Sipho",
      "last_name": "Ndlovu",
      "role": "parent",
      "email_verified": false
    },
    "message": "Verification email sent. Please check your inbox."
  }
}
```

### `POST /auth/login`
**Request:**
```json
{
  "email": "sipho@example.co.za",
  "password": "SecureP@ss123"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ...",
    "refresh_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

### `POST /auth/refresh`
Exchange a valid refresh token for a new access token.

### `POST /auth/forgot-password`
Initiate password reset. Sends email with reset link.

### `POST /auth/reset-password`
Complete password reset with token.

### `POST /auth/verify-email`
Verify email address with token from verification email.

### `POST /auth/google`
Google OAuth 2.0 social login.

---

## 3. Teacher Endpoints

### `GET /teachers`
Browse and search teachers. **Public endpoint** (no auth required).

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `subject` | string | Filter by subject code (e.g., `MATHS`) |
| `grade` | string | Filter by grade code (e.g., `GR12`) |
| `curriculum` | string | Filter by curriculum code (`CAPS`, `CAMB`, `IEB`) |
| `min_rate` | int | Minimum hourly rate in cents |
| `max_rate` | int | Maximum hourly rate in cents |
| `language` | string | Filter by teaching language |
| `province` | string | Filter by province |
| `min_rating` | float | Minimum average rating |
| `trial_free` | bool | Only teachers offering free trials |
| `q` | string | Full-text search (name, bio, subjects) |
| `sort_by` | string | `rating_average`, `hourly_rate_cents`, `total_lessons`, `created_at` |
| `sort_order` | string | `asc` or `desc` |

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "t1-uuid",
      "user": {
        "first_name": "Nomvula",
        "last_name": "M.",
        "avatar_url": "https://..."
      },
      "headline": "Pure Maths & Physical Sciences — 8 years experience",
      "bio": "Former high school teacher specialising in...",
      "hourly_rate_cents": 25000,
      "trial_lesson_free": true,
      "rating_average": 4.8,
      "rating_count": 47,
      "total_lessons": 312,
      "verification_status": "verified",
      "languages": ["English", "isiZulu"],
      "subjects": [
        { "subject": "Mathematics", "grades": ["Grade 10", "Grade 11", "Grade 12"], "curriculum": "CAPS" }
      ]
    }
  ],
  "meta": { "page": 1, "per_page": 20, "total": 85, "total_pages": 5 }
}
```

### `GET /teachers/{id}`
Full teacher profile with reviews.

### `GET /teachers/{id}/availability`
Teacher's available time slots for a given date range.

**Query Parameters:** `start_date`, `end_date`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "teacher_id": "t1-uuid",
    "slots": [
      { "date": "2026-03-27", "day_of_week": 2, "start_time": "09:00", "end_time": "10:00", "is_booked": false },
      { "date": "2026-03-27", "day_of_week": 2, "start_time": "10:00", "end_time": "11:00", "is_booked": true },
      { "date": "2026-03-27", "day_of_week": 2, "start_time": "14:00", "end_time": "15:00", "is_booked": false }
    ]
  }
}
```

### `GET /teachers/{id}/reviews`
Paginated reviews for a teacher.

### `PUT /teachers/me/profile` 🔒 Teacher
Update own teacher profile.

### `PUT /teachers/me/availability` 🔒 Teacher
Set/update weekly availability slots.

### `POST /teachers/me/subjects` 🔒 Teacher
Add a subject-grade-curriculum combination.

### `DELETE /teachers/me/subjects/{id}` 🔒 Teacher
Remove a subject offering.

---

## 4. Verification Endpoints

### `POST /verification/documents` 🔒 Teacher
Upload a verification document.

**Request:** `multipart/form-data`
| Field | Type | Required |
|-------|------|----------|
| `file` | File | Yes |
| `document_type` | string | Yes (`id_document`, `qualification`, `sace_certificate`, `nrso_clearance`, `reference_letter`) |

### `GET /verification/status` 🔒 Teacher
Get current verification status and document statuses.

### `PUT /verification/documents/{id}/review` 🔒 Admin
Approve or reject a verification document.

---

## 5. Learner Endpoints

### `GET /learners` 🔒 Parent
List all learners under the authenticated parent.

### `POST /learners` 🔒 Parent
Add a new learner profile.

**Request:**
```json
{
  "first_name": "Thabo",
  "last_name": "Ndlovu",
  "date_of_birth": "2013-05-15",
  "grade_level_id": "grade-uuid",
  "curriculum_id": "caps-uuid",
  "notes": "Prefers visual learning. Needs extra support with algebra."
}
```

### `PUT /learners/{id}` 🔒 Parent
Update learner details.

### `GET /learners/{id}/progress` 🔒 Parent
Get learner progress summary (lessons completed, subjects, topics covered).

### `GET /learners/{id}/report` 🔒 Parent
Generate a downloadable progress report (PDF).

---

## 6. Booking Endpoints

### `POST /bookings` 🔒 Parent
Create a new booking (initiates payment flow).

**Request:**
```json
{
  "teacher_id": "t1-uuid",
  "learner_id": "l1-uuid",
  "subject_id": "subj-uuid",
  "grade_level_id": "grade-uuid",
  "curriculum_id": "curr-uuid",
  "scheduled_date": "2026-03-27",
  "start_time": "09:00",
  "end_time": "10:00"
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "booking": {
      "id": "b1-uuid",
      "booking_number": "FC-20260327-X7K9",
      "status": "pending_payment",
      "lesson_rate_cents": 25000,
      "platform_fee_cents": 4375,
      "teacher_payout_cents": 20625
    },
    "payment": {
      "gateway": "payfast",
      "redirect_url": "https://www.payfast.co.za/eng/process?..."
    }
  }
}
```

### `GET /bookings` 🔒 Parent | Teacher
List bookings (filtered by role). Parents see their bookings; teachers see theirs.

**Query Parameters:** `status`, `from_date`, `to_date`, `learner_id`

### `GET /bookings/{id}` 🔒 Parent | Teacher
Booking details including meeting link (available after confirmation).

### `POST /bookings/{id}/cancel` 🔒 Parent | Teacher
Cancel a booking.

**Request:**
```json
{
  "reason": "Schedule conflict — need to reschedule"
}
```

### `POST /bookings/{id}/complete` 🔒 Teacher
Mark a lesson as completed and add notes.

**Request:**
```json
{
  "lesson_notes": "Covered quadratic formula and discriminant. Thabo grasped the concepts well.",
  "topics_covered": ["topic-uuid-1", "topic-uuid-2"]
}
```

### `POST /bookings/{id}/reschedule` 🔒 Parent | Teacher
Reschedule to a new slot.

### `POST /bookings/recurring` 🔒 Parent
Create a recurring weekly booking series.

---

## 7. Payment Endpoints

### `POST /bookings/payfast/itn`
PayFast ITN (Instant Transaction Notification) webhook. **No auth** — validated by PayFast signature.

### `GET /payments/history` 🔒 Parent | Teacher
Transaction history.

### `GET /teachers/me/payouts` 🔒 Teacher
Payout history.

### `GET /teachers/me/earnings` 🔒 Teacher
Earnings summary (this week, this month, total).

---

## 8. Review Endpoints

### `POST /bookings/{id}/review` 🔒 Parent
Submit a review for a completed lesson.

**Request:**
```json
{
  "rating": 5,
  "comment": "Excellent lesson! Nomvula explained quadratics clearly and Thabo finally understands."
}
```

### `POST /reviews/{id}/reply` 🔒 Teacher
Teacher replies to a review.

---

## 9. Notification Endpoints

### `GET /notifications` 🔒 Authenticated
List notifications for the current user.

### `PUT /notifications/{id}/read` 🔒 Authenticated
Mark a notification as read.

### `PUT /notifications/read-all` 🔒 Authenticated
Mark all notifications as read.

### `PUT /notifications/preferences` 🔒 Authenticated
Update notification preferences (email, SMS, push toggles).

### `GET /notifications/preferences` 🔒 Authenticated
Fetch the current notification preference values for the signed-in user.

---

## 10. Reference Data Endpoints

### `GET /subjects`
List all subjects (with tier/priority info).

### `GET /grade-levels`
List all grade levels grouped by phase.

### `GET /curricula`
List supported curricula.

### `GET /topics`
List topics filtered by subject, grade, curriculum, and term.

---

## 11. Admin Endpoints (🔒 Admin Role)

### `GET /admin/users`
List/search all users with filtering.

### `GET /admin/teachers/pending-verification`
Teachers awaiting verification review.

### `PUT /admin/teachers/{id}/verification`
Update teacher verification status.

### `GET /admin/bookings`
All bookings with advanced filters.

### `GET /admin/payments`
Payment and revenue reporting.

### `GET /admin/dashboard`
Platform metrics (active teachers, bookings this month, revenue, etc.).

---

## 12. Webhook Endpoints

### `POST /bookings/payfast/itn`
PayFast ITN handler. See [Payment Integration](./05-payment-integration.md) for full specification.

---

## 13. Rate Limits

| Endpoint Group | Rate Limit | Window |
|---------------|-----------|--------|
| Auth (login, register) | 5 requests | 1 minute |
| Auth (password reset) | 3 requests | 15 minutes |
| Teacher search | 30 requests | 1 minute |
| Booking creation | 10 requests | 1 minute |
| File upload | 5 requests | 1 minute |
| General API | 60 requests | 1 minute |
| Admin endpoints | 120 requests | 1 minute |
