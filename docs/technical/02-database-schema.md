# 02 — Database Schema

> **Status:** Draft  
> **Last Updated:** 2026-03-25  
> **Database:** PostgreSQL 16  
> **ORM:** SQLAlchemy 2.0 (async)  
> **Migrations:** Alembic

---

## 1. Schema Overview

The database is organised into logical domains. All tables use UUIDs as primary keys, store timestamps in UTC, and follow a consistent naming convention (snake_case, plural table names).

```
┌──────────────────────────────────────────────────────────┐
│                     CORE DOMAIN                          │
│  users · teacher_profiles · parent_profiles · learners   │
└──────────────────────┬───────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌──────────────┐ ┌───────────┐ ┌──────────────┐
│  VERIFICATION│ │  BOOKING  │ │  CURRICULUM  │
│  documents   │ │  bookings │ │  subjects    │
│  verification│ │  lessons  │ │  curricula   │
│  _requests   │ │  recurring│ │  grade_levels│
│              │ │  _bookings│ │  topics      │
└──────────────┘ └─────┬─────┘ └──────────────┘
                       │
                ┌──────┼──────┐
                ▼      ▼      ▼
          ┌─────────┐┌─────────┐┌──────────┐
          │PAYMENTS ││ REVIEWS ││ NOTIFS   │
          │payments ││ reviews ││ notifs   │
          │payouts  ││         ││ notif_   │
          │refunds  ││         ││ prefs    │
          └─────────┘└─────────┘└──────────┘
```

---

## 2. Table Definitions

### 2.1 `users`

Central identity table. All roles (parent, teacher, admin) share this table.

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    phone           VARCHAR(20),
    password_hash   VARCHAR(255) NOT NULL,
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    role            VARCHAR(20) NOT NULL CHECK (role IN ('parent', 'teacher', 'admin')),
    avatar_url      TEXT,
    email_verified  BOOLEAN DEFAULT FALSE,
    phone_verified  BOOLEAN DEFAULT FALSE,
    is_active       BOOLEAN DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_role ON users (role);
CREATE INDEX idx_users_active ON users (is_active) WHERE is_active = TRUE;
```

---

### 2.2 `teacher_profiles`

Extended profile information for teacher users.

```sql
CREATE TABLE teacher_profiles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    bio                 TEXT,
    headline            VARCHAR(255),                  -- e.g., "Pure Maths & Physical Sciences Specialist"
    years_experience    INTEGER DEFAULT 0,
    hourly_rate_cents   INTEGER NOT NULL,               -- stored in cents (ZAR)
    trial_lesson_free   BOOLEAN DEFAULT TRUE,
    sace_number         VARCHAR(50),
    nrso_cleared        BOOLEAN DEFAULT FALSE,
    verification_status VARCHAR(30) NOT NULL DEFAULT 'pending'
        CHECK (verification_status IN (
            'pending', 'documents_submitted', 'under_review',
            'verified', 'rejected', 'suspended'
        )),
    verified_at         TIMESTAMPTZ,
    rating_average      NUMERIC(3,2) DEFAULT 0.00,
    rating_count        INTEGER DEFAULT 0,
    total_lessons       INTEGER DEFAULT 0,
    is_featured         BOOLEAN DEFAULT FALSE,
    province            VARCHAR(50),                    -- for analytics; lessons are online
    languages           TEXT[],                         -- e.g., {'English', 'isiZulu', 'Afrikaans'}
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tp_user ON teacher_profiles (user_id);
CREATE INDEX idx_tp_status ON teacher_profiles (verification_status);
CREATE INDEX idx_tp_rating ON teacher_profiles (rating_average DESC);
CREATE INDEX idx_tp_subjects ON teacher_profiles USING GIN (languages);
```

---

### 2.3 `parent_profiles`

Extended profile information for parent users.

```sql
CREATE TABLE parent_profiles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    province            VARCHAR(50),
    home_language       VARCHAR(50),
    subscription_tier   VARCHAR(20) DEFAULT 'free'
        CHECK (subscription_tier IN ('free', 'plus')),
    subscription_expires_at TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### 2.4 `learners`

Children/students managed under a parent account.

```sql
CREATE TABLE learners (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id       UUID NOT NULL REFERENCES parent_profiles(id) ON DELETE CASCADE,
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    date_of_birth   DATE,
    grade_level_id  UUID REFERENCES grade_levels(id),
    curriculum_id   UUID REFERENCES curricula(id),
    notes           TEXT,                              -- parent notes (learning style, needs, etc.)
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_learners_parent ON learners (parent_id);
```

---

### 2.5 Curriculum Reference Tables

```sql
CREATE TABLE curricula (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name    VARCHAR(100) NOT NULL UNIQUE,               -- 'CAPS', 'Cambridge', 'IEB'
    code    VARCHAR(20) NOT NULL UNIQUE
);

CREATE TABLE grade_levels (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name    VARCHAR(50) NOT NULL,                       -- 'Grade 8', 'Grade 12', 'Grade R'
    code    VARCHAR(10) NOT NULL UNIQUE,                -- 'GR08', 'GR12', 'GRR'
    phase   VARCHAR(30) NOT NULL                        -- 'Foundation', 'Intermediate', 'Senior', 'FET'
);

CREATE TABLE subjects (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name    VARCHAR(100) NOT NULL,                      -- 'Mathematics', 'Physical Sciences'
    code    VARCHAR(20) NOT NULL UNIQUE,
    tier    INTEGER DEFAULT 1                           -- launch priority tier (1-4)
);

CREATE TABLE topics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id      UUID NOT NULL REFERENCES subjects(id),
    grade_level_id  UUID NOT NULL REFERENCES grade_levels(id),
    curriculum_id   UUID NOT NULL REFERENCES curricula(id),
    name            VARCHAR(255) NOT NULL,              -- e.g., 'Quadratic Equations'
    caps_reference  VARCHAR(100),                       -- CAPS document reference code
    term            INTEGER CHECK (term BETWEEN 1 AND 4)
);

CREATE INDEX idx_topics_subject ON topics (subject_id);
CREATE INDEX idx_topics_grade ON topics (grade_level_id);
```

---

### 2.6 `teacher_subjects`

Many-to-many: teachers and the subjects/grades they teach.

```sql
CREATE TABLE teacher_subjects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id      UUID NOT NULL REFERENCES teacher_profiles(id) ON DELETE CASCADE,
    subject_id      UUID NOT NULL REFERENCES subjects(id),
    grade_level_id  UUID NOT NULL REFERENCES grade_levels(id),
    curriculum_id   UUID NOT NULL REFERENCES curricula(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (teacher_id, subject_id, grade_level_id, curriculum_id)
);

CREATE INDEX idx_ts_teacher ON teacher_subjects (teacher_id);
CREATE INDEX idx_ts_subject ON teacher_subjects (subject_id);
CREATE INDEX idx_ts_grade ON teacher_subjects (grade_level_id);
```

---

### 2.7 `verification_documents`

Documents uploaded by teachers during verification.

```sql
CREATE TABLE verification_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id      UUID NOT NULL REFERENCES teacher_profiles(id) ON DELETE CASCADE,
    document_type   VARCHAR(50) NOT NULL
        CHECK (document_type IN (
            'id_document', 'qualification', 'sace_certificate',
            'nrso_clearance', 'reference_letter', 'other'
        )),
    file_name       VARCHAR(255) NOT NULL,
    file_url        TEXT NOT NULL,                      -- S3/B2 presigned URL reference
    file_size_bytes INTEGER,
    mime_type       VARCHAR(100),
    status          VARCHAR(20) DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewer_notes  TEXT,
    reviewed_by     UUID REFERENCES users(id),
    reviewed_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_vd_teacher ON verification_documents (teacher_id);
CREATE INDEX idx_vd_status ON verification_documents (status);
```

---

### 2.8 `availability_slots`

Teacher weekly recurring availability.

```sql
CREATE TABLE availability_slots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id      UUID NOT NULL REFERENCES teacher_profiles(id) ON DELETE CASCADE,
    day_of_week     INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6), -- 0=Monday
    start_time      TIME NOT NULL,
    end_time        TIME NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT valid_time_range CHECK (end_time > start_time)
);

CREATE INDEX idx_as_teacher ON availability_slots (teacher_id);
CREATE INDEX idx_as_day ON availability_slots (day_of_week);
```

---

### 2.9 `bookings`

Individual lesson bookings.

```sql
CREATE TABLE bookings (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_number      VARCHAR(20) NOT NULL UNIQUE,    -- human-readable: FC-20260325-A1B2
    parent_id           UUID NOT NULL REFERENCES parent_profiles(id),
    learner_id          UUID NOT NULL REFERENCES learners(id),
    teacher_id          UUID NOT NULL REFERENCES teacher_profiles(id),
    subject_id          UUID NOT NULL REFERENCES subjects(id),
    grade_level_id      UUID NOT NULL REFERENCES grade_levels(id),
    curriculum_id       UUID NOT NULL REFERENCES curricula(id),
    recurring_booking_id UUID REFERENCES recurring_bookings(id),

    scheduled_date      DATE NOT NULL,
    start_time          TIME NOT NULL,
    end_time            TIME NOT NULL,
    duration_minutes    INTEGER NOT NULL DEFAULT 60,

    status              VARCHAR(30) NOT NULL DEFAULT 'pending_payment'
        CHECK (status IN (
            'pending_payment', 'confirmed', 'in_progress',
            'completed', 'cancelled_by_parent', 'cancelled_by_teacher',
            'no_show_parent', 'no_show_teacher', 'disputed'
        )),

    lesson_rate_cents   INTEGER NOT NULL,               -- snapshot of rate at booking time
    platform_fee_cents  INTEGER NOT NULL,               -- commission amount
    teacher_payout_cents INTEGER NOT NULL,              -- rate minus commission

    meeting_link        TEXT,                           -- Google Meet / Jitsi URL
    lesson_notes        TEXT,                           -- teacher post-lesson notes
    topics_covered      UUID[],                        -- references to topics table

    parent_rating       INTEGER CHECK (parent_rating BETWEEN 1 AND 5),
    cancelled_at        TIMESTAMPTZ,
    cancellation_reason TEXT,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_bookings_parent ON bookings (parent_id);
CREATE INDEX idx_bookings_teacher ON bookings (teacher_id);
CREATE INDEX idx_bookings_learner ON bookings (learner_id);
CREATE INDEX idx_bookings_status ON bookings (status);
CREATE INDEX idx_bookings_date ON bookings (scheduled_date);
CREATE INDEX idx_bookings_number ON bookings (booking_number);
```

---

### 2.10 `recurring_bookings`

Weekly recurring lesson series.

```sql
CREATE TABLE recurring_bookings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id       UUID NOT NULL REFERENCES parent_profiles(id),
    learner_id      UUID NOT NULL REFERENCES learners(id),
    teacher_id      UUID NOT NULL REFERENCES teacher_profiles(id),
    subject_id      UUID NOT NULL REFERENCES subjects(id),
    day_of_week     INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    start_time      TIME NOT NULL,
    end_time        TIME NOT NULL,
    start_date      DATE NOT NULL,
    end_date        DATE,                              -- NULL = indefinite
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### 2.11 `payments`

Payment transactions linked to bookings.

```sql
CREATE TABLE payments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id          UUID NOT NULL REFERENCES bookings(id),
    parent_id           UUID NOT NULL REFERENCES parent_profiles(id),
    amount_cents        INTEGER NOT NULL,
    currency            VARCHAR(3) DEFAULT 'ZAR',
    status              VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'refunded', 'partially_refunded')),
    gateway             VARCHAR(20) NOT NULL DEFAULT 'payfast'
        CHECK (gateway IN ('payfast', 'ozow', 'manual')),
    gateway_payment_id  VARCHAR(255),                  -- PayFast m_payment_id
    gateway_reference   VARCHAR(255),                  -- PayFast pf_payment_id
    payment_method      VARCHAR(50),                   -- 'credit_card', 'instant_eft', 'snapscan'
    itn_received_at     TIMESTAMPTZ,                   -- PayFast ITN timestamp
    metadata            JSONB DEFAULT '{}',            -- raw gateway response
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_payments_booking ON payments (booking_id);
CREATE INDEX idx_payments_status ON payments (status);
CREATE INDEX idx_payments_gateway_ref ON payments (gateway_reference);
```

---

### 2.12 `teacher_payouts`

Batch payouts to teachers.

```sql
CREATE TABLE teacher_payouts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id          UUID NOT NULL REFERENCES teacher_profiles(id),
    amount_cents        INTEGER NOT NULL,
    currency            VARCHAR(3) DEFAULT 'ZAR',
    status              VARCHAR(20) DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    payout_method       VARCHAR(30),                   -- 'bank_transfer', 'payfast_split'
    bank_reference      VARCHAR(255),
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    booking_ids         UUID[] NOT NULL,                -- bookings included in this payout
    processed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_payouts_teacher ON teacher_payouts (teacher_id);
CREATE INDEX idx_payouts_status ON teacher_payouts (status);
```

---

### 2.13 `reviews`

```sql
CREATE TABLE reviews (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id      UUID NOT NULL UNIQUE REFERENCES bookings(id),
    parent_id       UUID NOT NULL REFERENCES parent_profiles(id),
    teacher_id      UUID NOT NULL REFERENCES teacher_profiles(id),
    rating          INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment         TEXT,
    teacher_reply   TEXT,
    is_visible      BOOLEAN DEFAULT TRUE,
    flagged         BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reviews_teacher ON reviews (teacher_id);
CREATE INDEX idx_reviews_visible ON reviews (is_visible) WHERE is_visible = TRUE;
```

---

### 2.14 `notifications`

```sql
CREATE TABLE notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type            VARCHAR(50) NOT NULL,              -- 'booking_confirmed', 'lesson_reminder', etc.
    channel         VARCHAR(20) NOT NULL               -- 'email', 'sms', 'push'
        CHECK (channel IN ('email', 'sms', 'push', 'in_app')),
    title           VARCHAR(255),
    body            TEXT,
    metadata        JSONB DEFAULT '{}',
    is_read         BOOLEAN DEFAULT FALSE,
    sent_at         TIMESTAMPTZ,
    read_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notif_user ON notifications (user_id);
CREATE INDEX idx_notif_unread ON notifications (user_id, is_read) WHERE is_read = FALSE;
```

---

### 2.15 `audit_log`

Immutable audit trail for compliance (POPIA).

```sql
CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    action          VARCHAR(100) NOT NULL,             -- 'user.login', 'booking.create', 'document.view'
    resource_type   VARCHAR(50),                       -- 'booking', 'teacher_profile', 'payment'
    resource_id     UUID,
    ip_address      INET,
    user_agent      TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_user ON audit_log (user_id);
CREATE INDEX idx_audit_action ON audit_log (action);
CREATE INDEX idx_audit_created ON audit_log (created_at);

-- Partition by month for performance (optional, add when volume warrants it)
```

---

## 3. Entity Relationship Summary

```
users 1──1 teacher_profiles
users 1──1 parent_profiles
parent_profiles 1──* learners
teacher_profiles 1──* teacher_subjects
teacher_profiles 1──* availability_slots
teacher_profiles 1──* verification_documents
teacher_profiles 1──* teacher_payouts

bookings *──1 parent_profiles
bookings *──1 learners
bookings *──1 teacher_profiles
bookings *──1 subjects
bookings 1──1 payments
bookings 1──1 reviews
bookings *──1 recurring_bookings

teacher_subjects *──1 subjects
teacher_subjects *──1 grade_levels
teacher_subjects *──1 curricula

topics *──1 subjects
topics *──1 grade_levels
topics *──1 curricula
```

---

## 4. Migration Strategy

- **Tool:** Alembic with autogenerate from SQLAlchemy models
- **Naming:** `YYYY_MM_DD_HHMM_description.py` (e.g., `2026_03_25_1400_initial_schema.py`)
- **Rules:**
  - Every migration must be reversible (include `downgrade()`)
  - Data migrations separated from schema migrations
  - Never drop columns in production without a deprecation period
  - Test migrations against a copy of production data before deploying
- **Seed Data:** Reference data (subjects, grade levels, curricula) seeded via a dedicated script

---

## 5. Indexing Strategy

- Primary keys: B-tree (default)
- Foreign keys: Always indexed
- Enum/status columns: Partial indexes where appropriate (e.g., active teachers only)
- Array columns: GIN indexes (e.g., `languages`, `topics_covered`)
- Text search: Meilisearch handles teacher search; no full-text indexes on PostgreSQL
- Date ranges: B-tree on `scheduled_date` for booking queries
- Composite indexes added based on query patterns after launch
