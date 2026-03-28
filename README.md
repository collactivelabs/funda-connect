# FundaConnect

A marketplace connecting South African homeschooling families with qualified tutors. Parents discover verified teachers, book lessons, and pay securely via PayFast. Teachers manage their availability, receive payouts, and track their lesson history.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | FastAPI (Python 3.12), SQLAlchemy 2.0 (async), Alembic |
| Database | PostgreSQL 16 |
| Cache / Queue broker | Redis 7 |
| Task queue | Celery 5 + Celery Beat |
| Search | Meilisearch |
| Payments | PayFast (sandbox + live) |
| Video | daily.co |
| Storage | AWS S3 (teacher documents) |
| Email | SMTP (stdlib) |

---

## Project Structure

```
funda-connect/
├── backend/            # FastAPI application
│   ├── app/
│   │   ├── api/        # Route handlers (auth, bookings, teachers, parents, reviews, admin)
│   │   ├── core/       # Config, security, dependencies
│   │   ├── models/     # SQLAlchemy ORM models
│   │   ├── schemas/    # Pydantic request/response schemas
│   │   ├── services/   # Email, video room helpers
│   │   └── tasks/      # Celery tasks (notifications, lessons, payouts)
│   ├── migrations/     # Alembic migration files
│   └── tests/
├── frontend/           # Next.js application
│   └── src/
│       ├── app/        # App Router pages (auth, dashboard, teachers, admin)
│       ├── components/ # UI components (booking, parent, teacher, shared)
│       ├── lib/        # API client, utilities
│       ├── stores/     # Zustand auth store
│       └── types/      # TypeScript types
├── docs/               # Business and technical documentation
├── docker-compose.yml
├── Makefile
└── .env.example
```

---

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Make

### First-time setup

```bash
# Clone the repo
git clone <repo-url>
cd funda-connect

# Copy env file and fill in your values
cp .env.example .env

# Build images, start services, and run migrations
make setup
```

Once complete:

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3001 |
| Backend API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Celery Flower | http://localhost:5555 |

### Common commands

```bash
make up              # Start all services
make down            # Stop all services
make logs            # Tail all logs
make logs-backend    # Tail backend logs only

make migrate                        # Run pending migrations
make migrate-create MSG="add table" # Generate a new migration

make lint            # Lint backend + frontend
make test            # Run all tests
make db-shell        # Open psql shell
make promote-admin EMAIL=you@example.com  # Promote an existing user to admin
make payfast-tunnel  # Start an ngrok tunnel for PayFast webhooks
make payfast-webhook-path  # Show the public ITN path to use in PAYFAST_NOTIFY_URL
```

Frontend tooling uses `pnpm`. The current `pnpm test` script is a lightweight smoke check based on TypeScript validation until dedicated frontend tests are added.

---

## Environment Variables

Copy `.env.example` to `.env` and set the following:

```bash
# Database
POSTGRES_DB=fundaconnect
POSTGRES_USER=fundaconnect
POSTGRES_PASSWORD=

# JWT
SECRET_KEY=                        # Long random string
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS=24
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=60
APP_BASE_URL=http://localhost:3001

# PayFast
PAYFAST_MERCHANT_ID=
PAYFAST_MERCHANT_KEY=
PAYFAST_PASSPHRASE=
PAYFAST_SANDBOX=true               # Set false in production
PAYFAST_RETURN_URL=http://localhost:3001/parent
PAYFAST_CANCEL_URL=http://localhost:3001/parent
PAYFAST_NOTIFY_URL=               # e.g. https://<your-ngrok-domain>/api/v1/bookings/payfast/itn

# daily.co (video rooms)
DAILY_API_KEY=

# AWS S3 (teacher document uploads)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_S3_BUCKET=
AWS_REGION=af-south-1

# Email (SMTP)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
EMAIL_FROM=noreply@fundaconnect.co.za

# Meilisearch
MEILISEARCH_MASTER_KEY=

# Platform
PLATFORM_COMMISSION_RATE=0.175     # 17.5%
ALLOWED_ORIGINS=http://localhost:3001
```

### Local PayFast Webhooks

PayFast cannot send ITN webhooks to `localhost`, so local payment testing needs a public tunnel.

```bash
# 1. Start the backend if it is not running
make up

# 2. Start an ngrok tunnel to the backend
make payfast-tunnel

# 3. Copy the HTTPS ngrok URL and set it in .env
PAYFAST_NOTIFY_URL=https://<your-ngrok-domain>/api/v1/bookings/payfast/itn

# 4. Restart the backend so the new env var is loaded
docker compose restart backend
```

`PAYFAST_RETURN_URL` and `PAYFAST_CANCEL_URL` can stay on `http://localhost:3001/parent` for local browser testing.

---

## Core Features

- **Teacher discovery** — search by subject, curriculum (CAPS / IEB / Cambridge), grade, province, and rate
- **Bookings** — parents book single or recurring weekly lessons; payment via PayFast redirect
- **Video lessons** — daily.co rooms auto-created on payment; join button active 10 min before start
- **Reviews** — parents rate completed lessons; ratings displayed on teacher profiles
- **Document verification** — teachers upload ID and qualifications to S3; admin reviews and approves
- **Automated lifecycle** — Celery Beat marks lessons complete 15 min after end and queues payouts
- **Weekly payouts** — Celery Beat batches teacher payouts every Monday
- **Notification center** — in-app inbox with unread state, mark-read actions, and notification preferences
- **Email notifications** — booking confirmation, verification result, payout processed, refund updates
- **Admin dashboard** — teacher verification workflow, payout status management, platform stats

---

## API Overview

All endpoints are under `/api/v1/`. Interactive docs at `http://localhost:8000/docs`.

| Prefix | Description |
|--------|-------------|
| `/auth` | Register, login, refresh token, logout, me |
| `/teachers` | Profile, availability, subjects, documents, search |
| `/parents` | Profile, learners |
| `/bookings` | Create, list, get, cancel; PayFast ITN webhook |
| `/curricula` | Supported curricula reference data |
| `/grade-levels` | Grade level reference data grouped by phase |
| `/notifications` | Inbox, unread state, and notification preferences |
| `/reviews` | Submit review, list by teacher |
| `/subjects` | Subject catalogue |
| `/admin` | Stats, teacher verification, payout management |

---

## Booking State Machine

```
pending_payment → confirmed → completed → reviewed
                ↘ cancelled
```

Recurring bookings: the root booking goes through PayFast. On payment confirmation, N−1 child bookings are created as `confirmed` at weekly intervals, all referencing the root via `recurring_booking_id`.

## Auth Flows

- Email verification links are sent on registration and can be resent from the dashboard while an account is still unverified.
- Password reset links can be requested from `/forgot-password`, with resets completed on `/reset-password`.
- Refresh tokens now rotate with reuse detection, and signed-in users can review or revoke active sessions from the dashboard.
- Password reset is available via `/forgot-password` and `/reset-password`.
- Refresh tokens now rotate on `/auth/refresh` and are revoked on logout or password reset.
