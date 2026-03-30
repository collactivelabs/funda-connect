# FundaConnect — Technical Documentation

> **Version:** 1.0  
> **Last Updated:** 2026-03-25  
> **Status:** Pre-Development

---

## Documentation Index

| # | Document | Description |
|---|----------|-------------|
| 1 | [Architecture Overview](./01-architecture-overview.md) | System architecture, component diagram, technology stack decisions, and data flow |
| 2 | [Database Schema](./02-database-schema.md) | Full PostgreSQL schema design with tables, relationships, indexes, and migration strategy |
| 3 | [API Specification](./03-api-specification.md) | RESTful API endpoints, request/response formats, pagination, and error handling |
| 4 | [Authentication & Authorization](./04-authentication-and-authorization.md) | Auth flows, JWT strategy, role-based access control, and OAuth integration |
| 5 | [Payment Integration](./05-payment-integration.md) | PayFast integration today, Ozow planned next, plus refund/dispute handling, commission calculation, and payout cycle |
| 6 | [Teacher Verification Workflow](./06-teacher-verification-workflow.md) | Verification pipeline, document handling, SACE/NRSO checks, and state machine |
| 7 | [Booking & Scheduling Engine](./07-booking-and-scheduling.md) | Availability management, booking flow, conflict resolution, blocked dates, and reminders |
| 8 | [Security & POPIA Compliance](./08-security-and-compliance.md) | Data protection, encryption, POPIA obligations, breach response, and audit logging |
| 9 | [Deployment & Infrastructure](./09-deployment-and-infrastructure.md) | Cloud architecture, Docker setup, CI/CD pipeline, monitoring, and load-shedding resilience |
| 10 | [Development Environment Setup](./10-development-setup.md) | Local dev setup, prerequisites, running the stack, and contribution guidelines |

---

## Project Structure (Planned)

```
funda-connect/
├── docs/
│   ├── technical/          ← You are here
│   └── business/           ← Business documentation (project plan, etc.)
├── backend/                ← FastAPI backend (Python)
│   ├── app/
│   │   ├── api/            ← Route handlers
│   │   ├── core/           ← Config, security, dependencies
│   │   ├── models/         ← SQLAlchemy ORM models
│   │   ├── schemas/        ← Pydantic request/response schemas
│   │   ├── services/       ← Business logic layer
│   │   ├── tasks/          ← Background/async tasks (Celery)
│   │   └── utils/          ← Helpers, constants
│   ├── migrations/         ← Alembic migrations
│   ├── tests/
│   ├── scripts/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               ← Next.js web application
│   ├── src/
│   │   ├── app/            ← App router pages
│   │   ├── components/     ← Reusable UI components
│   │   ├── hooks/          ← Custom React hooks
│   │   ├── lib/            ← API client, utilities
│   │   ├── stores/         ← State management (Zustand)
│   │   └── types/          ← TypeScript type definitions
│   ├── public/
│   ├── Dockerfile
│   └── package.json
├── mobile/                 ← React Native app (Phase 3)
├── infra/                  ← Terraform / Docker Compose
├── docker-compose.yml
├── docker-compose.dev.yml
├── Makefile
└── README.md
```

---

## Quick Links

- **Tech Stack:** FastAPI (Python) · Next.js (TypeScript) · PostgreSQL · Redis · Docker
- **Payments:** PayFast API today · Ozow planned
- **Hosting Target:** AWS Africa (Cape Town, af-south-1) or Hetzner South Africa
- **Primary Market:** South Africa (ZAR only)

---

## Conventions

- **API Versioning:** URL path prefix `/api/v1/`
- **Date/Time:** ISO 8601, stored in UTC, displayed in SAST (UTC+2)
- **Currency:** All monetary values stored as integers in cents (ZAR). Display: `R250.00`
- **IDs:** UUIDs (v4) for all public-facing identifiers
- **Naming:** snake_case for Python/DB, camelCase for TypeScript/JSON responses
