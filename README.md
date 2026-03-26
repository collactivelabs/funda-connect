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
```

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

# PayFast
PAYFAST_MERCHANT_ID=
PAYFAST_MERCHANT_KEY=
PAYFAST_PASSPHRASE=
PAYFAST_SANDBOX=true               # Set false in production

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

---

## Core Features

- **Teacher discovery** — search by subject, curriculum (CAPS / IEB / Cambridge), grade, province, and rate
- **Bookings** — parents book single or recurring weekly lessons; payment via PayFast redirect
- **Video lessons** — daily.co rooms auto-created on payment; join button active 10 min before start
- **Reviews** — parents rate completed lessons; ratings displayed on teacher profiles
- **Document verification** — teachers upload ID and qualifications to S3; admin reviews and approves
- **Automated lifecycle** — Celery Beat marks lessons complete 15 min after end and queues payouts
- **Weekly payouts** — Celery Beat batches teacher payouts every Monday
- **Email notifications** — booking confirmation, verification result, payout processed
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
