# 01 — Architecture Overview

> **Status:** Draft  
> **Last Updated:** 2026-03-25

---

## 1. High-Level Architecture

FundaConnect follows a **three-tier architecture** with a clear separation between presentation, business logic, and data layers. The system is designed as a monolithic backend with a decoupled frontend, transitioning to microservices only if scale demands it.

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENTS                              │
│  ┌──────────┐   ┌──────────┐  ┌──────────────────────┐  │
│  │ Web App  │   │ Mobile   │  │ Admin Dashboard      │  │
│  │ (Next.js)│   │ (React   │  │ (Next.js /admin)     │  │
│  │          │   │  Native) │  │                      │  │
│  └────┬─────┘   └────┬─────┘  └──────────┬───────────┘  │
└───────┼──────────────┼───────────────────┼──────────────┘
        │              │                   │
        ▼              ▼                   ▼
┌─────────────────────────────────────────────────────────┐
│                 API GATEWAY / REVERSE PROXY             │
│                    (Nginx / Traefik)                    │
│               Rate Limiting · SSL Termination           │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  BACKEND API (FastAPI)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐   │
│  │ Auth     │ │ Teachers │ │ Bookings │ │ Payments  │   │
│  │ Module   │ │ Module   │ │ Module   │ │ Module    │   │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐   │
│  │ Learners │ │ Lessons  │ │ Reviews  │ │ Notif.    │   │
│  │ Module   │ │ Module   │ │ Module   │ │ Module    │   │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘   │
└────────┬───────────────┬──────────────┬─────────────────┘
         │               │              │
    ┌────▼──────┐   ┌────▼────┐   ┌─────▼─────┐
    │PostgreSQL │   │  Redis  │   │  Celery   │
    │  (Data)   │   │ (Cache/ │   │ (Workers) │
    │           │   │  Queue) │   │           │
    └───────────┘   └─────────┘   └─────┬─────┘
                                        │
                                ┌───────▼────────┐
                                │ External APIs  │
                                │ ┌────────────┐ │
                                │ │ PayFast    │ │
                                │ │ Ozow*      │ │
                                │ │ BulkSMS    │ │
                                │ │ Google Meet│ │
                                │ │ S3/B2      │ │
                                │ └────────────┘ │
                                └────────────────┘
```

`*` Ozow remains in planned scope; PayFast is the currently implemented payment gateway.

---

## 2. Technology Stack

### 2.1 Backend

| Component | Technology | Version | Rationale |
|-----------|-----------|---------|-----------|
| Framework | FastAPI | 0.115+ | Async-first, auto-generated OpenAPI docs, Pydantic validation, high performance |
| Language | Python | 3.12+ | Team familiarity, rich ecosystem, strong for data processing |
| ORM | SQLAlchemy | 2.0+ | Mature, async support, excellent migration tooling (Alembic) |
| Migrations | Alembic | 1.13+ | Schema versioning, auto-generation from models |
| Task Queue | Celery + Redis | 5.4+ | Background jobs (verification, notifications, payouts) |
| Validation | Pydantic | 2.0+ | Request/response validation, settings management |
| ASGI Server | Uvicorn | 0.30+ | High-performance async server |

### 2.2 Frontend

| Component | Technology | Version | Rationale |
|-----------|-----------|---------|-----------|
| Framework | Next.js | 15+ | App Router, SSR/SSG, excellent SEO, React Server Components |
| Language | TypeScript | 5.5+ | Type safety, better developer experience |
| Styling | Tailwind CSS | 4.0+ | Utility-first, rapid prototyping, small bundle |
| State | Zustand | 5.0+ | Lightweight, simple API, no boilerplate |
| Forms | React Hook Form + Zod | — | Performant form handling with schema validation |
| HTTP Client | Axios / ky | — | Request interceptors, retry logic |
| Date/Time | date-fns | — | Lightweight, tree-shakeable |
| UI Components | shadcn/ui | — | Accessible, customisable, Tailwind-native |

### 2.3 Infrastructure

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Database | PostgreSQL 16 | ACID compliance, JSONB support, strong for relational data |
| Cache/Broker | Redis 7 | Session store, Celery broker, rate limiting, caching |
| Search | Meilisearch | Typo-tolerant, fast, easy to self-host, good for teacher search |
| Object Storage | AWS S3 (af-south-1) or Backblaze B2 | Document uploads (IDs, certs, portfolio files) |
| Email | Amazon SES or Postmark | Transactional emails (confirmations, receipts) |
| SMS | BulkSMS or Africa's Talking | SA-focused, cost-effective, reliable delivery |
| Containerisation | Docker + Docker Compose | Reproducible environments, simplified deployment |
| CI/CD | GitHub Actions | Automated testing, building, and deployment |
| Hosting | AWS (af-south-1) or Hetzner SA | Low latency for SA users, data sovereignty |
| Monitoring | Sentry + Prometheus + Grafana | Error tracking, metrics, dashboards |
| Logging | Structured JSON → CloudWatch / Loki | Centralised, searchable logs |

---

## 3. Data Flow — Lesson Booking (Core Flow)

```
Parent                FundaConnect API          Teacher          PayFast
  │                        │                       │                │
  │  1. Browse teachers    │                       │                │
  │ ─────────────────────► │                       │                │
  │  2. Teacher list       │                       │                │
  │ ◄───────────────────── │                       │                │
  │                        │                       │                │
  │  3. Select slot        │                       │                │
  │ ─────────────────────► │                       │                │
  │                        │  4. Hold slot         │                │
  │                        │ ────────────────────► │                │
  │  5. Redirect to pay    │                       │                │
  │ ◄───────────────────── │                       │                │
  │                        │                       │                │
  │  6. Complete payment   │                       │                │
  │ ──────────────────────────────────────────────────────────────► │
  │                        │                       │                │
  │                        │  7. Payment webhook (ITN)              │
  │                        │ ◄───────────────────────────────────── │
  │                        │                       │                │
  │                        │  8. Confirm booking   │                │
  │                        │ ────────────────────► │                │
  │  9. Booking confirmed  │                       │                │
  │ ◄───────────────────── │                       │                │
  │                        │  10. SMS + Email      │                │
  │ ◄───────────────────── │ ────────────────────► │                │
```

---

## 4. Module Responsibilities

### 4.1 Auth Module
- User registration (parent, teacher, admin roles)
- Email/password login with JWT (access + refresh tokens)
- Google OAuth 2.0 social login
- Password reset flow
- Email verification
- Session management via Redis

### 4.2 Teachers Module
- Profile CRUD (bio, subjects, qualifications, rates)
- Verification state management
- Document upload and retrieval
- Availability calendar management
- Search and filtering (by subject, grade, curriculum, price range, rating)
- Subject-curriculum tagging (CAPS / Cambridge / IEB)

### 4.3 Bookings Module
- Slot availability checking with conflict detection
- Booking creation with payment initiation
- Booking state machine: `pending_payment → confirmed → in_progress → completed → reviewed`
- Cancellation with configurable refund policies
- Prepaid weekly series support (root payment upfront, child bookings created after confirmation)
- Rescheduling logic

### 4.4 Payments Module
- PayFast payment initiation and ITN (Instant Transaction Notification) handling
- Escrow logic: funds held until lesson completion confirmed
- Commission calculation and deduction
- Weekly teacher payout processing
- Refund processing
- Transaction history and reporting
- Invoice generation

### 4.5 Lessons Module
- Lesson session management
- Video room link generation (Google Meet API or Jitsi)
- Lesson content logging (topic, CAPS outcomes covered)
- Attendance tracking
- Session recording metadata (if opted in)
- Post-lesson feedback prompts

### 4.6 Learners Module
- Learner profile management (under parent account)
- Multi-learner support per family
- Progress tracking per learner per subject
- Portfolio-of-evidence generation
- Report card / progress report export

### 4.7 Reviews Module
- Post-lesson rating (1–5 stars) and written review
- Review moderation (flagging, admin approval)
- Aggregate rating calculation
- Review response by teachers

### 4.8 Notifications Module
- Multi-channel: email, SMS, in-app push
- Event-driven via Celery tasks
- Notification preferences per user
- Template management
- Delivery tracking and retry logic

---

## 5. Cross-Cutting Concerns

### 5.1 Error Handling
- Consistent error response format across all endpoints
- Structured error codes (e.g., `BOOKING_SLOT_UNAVAILABLE`, `PAYMENT_FAILED`)
- Sentry integration for unhandled exceptions
- Request ID tracking for debugging

### 5.2 Logging
- Structured JSON logging via `structlog`
- Request/response logging (sanitised — no PII in logs)
- Correlation IDs across async tasks
- Log levels: DEBUG (dev), INFO (prod), WARNING, ERROR, CRITICAL

### 5.3 Rate Limiting
- Redis-backed sliding window rate limiter
- Per-endpoint limits (e.g., auth endpoints: 5 req/min, search: 30 req/min)
- Per-user and per-IP strategies
- 429 Too Many Requests response with `Retry-After` header

### 5.4 Caching Strategy
- Redis cache for frequently accessed, slowly changing data:
  - Teacher search results (TTL: 5 min)
  - Teacher public profiles (TTL: 15 min)
  - Subject/curriculum reference data (TTL: 1 hour)
- Cache invalidation on write operations
- No caching of user-specific or sensitive data

---

## 6. Key Design Decisions

| Decision | Choice | Alternatives Considered | Reasoning |
|----------|--------|------------------------|-----------|
| Monolith vs Microservices | Modular Monolith | Microservices | Simpler to develop, deploy, and debug for a small team; can extract services later |
| API Style | REST | GraphQL | Simpler for CRUD-heavy operations; OpenAPI tooling; team familiarity |
| Database | PostgreSQL | MongoDB | Relational data (users, bookings, payments) fits SQL; ACID guarantees for financial data |
| Task Queue | Celery + Redis | RQ, Dramatiq | Mature ecosystem; periodic tasks; monitoring (Flower) |
| Search | Meilisearch | Elasticsearch, Algolia | Lightweight, easy to self-host, excellent relevance, lower resource usage |
| Frontend Framework | Next.js | Remix, Nuxt | SSR/SSG capabilities, large ecosystem, strong community, App Router |
| Auth Strategy | JWT (access + refresh) | Session cookies | Stateless API; mobile app compatibility; refresh token rotation |
| File Storage | S3 / B2 | Local disk, GCS | Scalable, durable, pre-signed URL support for secure access |
