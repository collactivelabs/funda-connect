# 09 — Deployment & Infrastructure

> **Status:** Draft  
> **Last Updated:** 2026-03-25

---

## 1. Infrastructure Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    AWS af-south-1 (Cape Town)               │
│                    or Hetzner South Africa                  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   Load Balancer                      │   │
│  │              (ALB / Nginx / Traefik)                 │   │
│  │         SSL termination · Rate limiting              │   │
│  └───────────┬───────────────────┬──────────────────────┘   │
│              │                   │                          │
│  ┌───────────▼──────┐ ┌─────────▼────────┐                  │
│  │  Frontend (Web)  │ │   Backend API    │                  │
│  │  Next.js (SSR)   │ │   FastAPI        │                  │
│  │  Container ×2    │ │   Container ×2-4 │                  │
│  └──────────────────┘ └────┬────────┬────┘                  │
│                            │        │                       │
│              ┌─────────────▼┐ ┌─────▼──────┐                │
│              │ PostgreSQL   │ │   Redis    │                │
│              │ (RDS / VM)   │ │ (ElastiC.  │                │
│              │ Primary +    │ │  or VM)    │                │
│              │ Read Replica │ └────────────┘                │
│              └──────────────┘                               │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐      │
│  │ Celery       │  │ Meilisearch  │  │ S3 / B2       │      │
│  │ Workers ×2   │  │ Container    │  │ (Documents)   │      │
│  └──────────────┘  └──────────────┘  └───────────────┘      │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Monitoring Stack                        │   │
│  │  Sentry · Prometheus · Grafana · CloudWatch / Loki   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Hosting Options

### Option A: AWS Africa (Cape Town, af-south-1)

| Service | Purpose | Estimated Cost |
|---------|---------|----------------|
| EC2 (t3.medium ×2) or ECS Fargate | API + Frontend containers | ~R4,500/month |
| RDS PostgreSQL (db.t3.medium) | Primary database | ~R3,200/month |
| ElastiCache Redis (cache.t3.micro) | Cache + queue broker | ~R1,200/month |
| S3 | Document storage | ~R200/month |
| ALB | Load balancer + SSL | ~R1,500/month |
| SES | Transactional email | ~R100/month |
| CloudWatch | Logging + monitoring | ~R500/month |
| **Total** | | **~R11,200/month** |

**Pros:** Data sovereignty (SA region), managed services, auto-scaling, SLA guarantees  
**Cons:** Higher cost, complexity, vendor lock-in risk

### Option B: Hetzner South Africa

| Service | Purpose | Estimated Cost |
|---------|---------|----------------|
| CX31 VPS (×2) | API + Frontend + Workers | ~R1,600/month |
| CX21 VPS | PostgreSQL + Redis | ~R800/month |
| CX11 VPS | Meilisearch + Monitoring | ~R400/month |
| Backblaze B2 | Document storage | ~R50/month |
| Cloudflare | CDN + SSL + DDoS protection | Free tier |
| **Total** | | **~R2,850/month** |

**Pros:** Significantly cheaper, SA data centre, good peering for SA users  
**Cons:** Self-managed infrastructure, manual scaling, less redundancy

### Recommendation

**Start with Hetzner** for cost efficiency during MVP/early growth. Migrate to AWS when monthly revenue exceeds R200K and the team can invest in managed infrastructure.

---

## 3. Docker Configuration

### 3.1 docker-compose.yml (Production)

```yaml
version: "3.9"

services:
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=postgresql+asyncpg://fc_user:${DB_PASSWORD}@db:5432/fundaconnect
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=${SECRET_KEY}
      - PAYFAST_MERCHANT_ID=${PAYFAST_MERCHANT_ID}
      - PAYFAST_MERCHANT_KEY=${PAYFAST_MERCHANT_KEY}
      - PAYFAST_PASSPHRASE=${PAYFAST_PASSPHRASE}
      - S3_BUCKET=${S3_BUCKET}
      - ENVIRONMENT=production
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 512M
          cpus: "0.5"
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      - NEXT_PUBLIC_API_URL=https://api.fundaconnect.co.za
    ports:
      - "3001:3001"
    deploy:
      replicas: 2
    restart: always

  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.tasks worker -l info -c 4
    environment:
      - DATABASE_URL=postgresql+asyncpg://fc_user:${DB_PASSWORD}@db:5432/fundaconnect
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    deploy:
      replicas: 2
    restart: always

  celery-beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.tasks beat -l info
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
    restart: always

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_DB=fundaconnect
      - POSTGRES_USER=fc_user
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U fc_user -d fundaconnect"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: always

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redisdata:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: always

  meilisearch:
    image: getmeili/meilisearch:v1.11
    environment:
      - MEILI_MASTER_KEY=${MEILI_MASTER_KEY}
      - MEILI_ENV=production
    volumes:
      - meilidata:/meili_data
    ports:
      - "7700:7700"
    restart: always

volumes:
  pgdata:
  redisdata:
  meilidata:
```

### 3.2 Backend Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libmagic1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

---

## 4. CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_pass
        ports: ["5432:5432"]
      redis:
        image: redis:7
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r backend/requirements.txt
      - run: cd backend && pytest --cov=app --cov-report=xml
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: corepack enable && cd frontend && pnpm install --frozen-lockfile && pnpm lint && pnpm typecheck

  build-and-deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker images
        run: |
          docker build -t fundaconnect-api:${{ github.sha }} ./backend
          docker build -t fundaconnect-web:${{ github.sha }} ./frontend
      - name: Push to registry
        run: |
          # Push to container registry (GHCR or ECR)
          echo "Push images..."
      - name: Deploy
        run: |
          # SSH deploy or kubectl apply
          echo "Deploy to production..."
```

---

## 5. Load-Shedding Resilience

South Africa's load-shedding is a key operational risk. Mitigation strategies:

| Layer | Mitigation |
|-------|-----------|
| **Hosting** | Cloud hosting (AWS/Hetzner) not affected by domestic load-shedding |
| **Teachers** | Onboarding guide recommends UPS/inverter + mobile data backup |
| **Platform** | Auto-detection of lesson disruption; auto-reschedule option |
| **Payments** | PayFast/Ozow operate on redundant infrastructure |
| **Communication** | SMS notifications work without internet (teacher can be reached even during outage) |

---

## 6. Monitoring & Alerting

### 6.1 Application Monitoring

| Tool | Purpose |
|------|---------|
| **Sentry** | Error tracking, performance monitoring, release tracking |
| **Prometheus** | Metrics collection (request rates, latency, queue depth) |
| **Grafana** | Dashboards and visualisation |
| **Uptime Robot** | External uptime monitoring (free tier) |

### 6.2 Key Metrics to Monitor

| Metric | Warning | Critical |
|--------|---------|----------|
| API response time (p95) | >500ms | >2000ms |
| Error rate (5xx) | >1% | >5% |
| Database connections | >80% pool | >95% pool |
| Redis memory | >70% | >90% |
| Celery queue depth | >100 tasks | >500 tasks |
| Disk usage | >70% | >85% |
| SSL certificate expiry | <30 days | <7 days |

### 6.3 Alerting Channels
- **Critical:** PagerDuty / SMS to on-call engineer
- **Warning:** Slack #alerts channel
- **Info:** Email digest (daily)

---

## 7. Backup Strategy

| Data | Method | Frequency | Retention |
|------|--------|-----------|-----------|
| PostgreSQL | pg_dump to S3 | Daily (02:00 SAST) | 30 days |
| PostgreSQL WAL | Continuous archival | Real-time | 7 days |
| Redis | RDB snapshot to S3 | Every 6 hours | 7 days |
| S3 documents | S3 versioning + cross-region replication | Real-time | Indefinite |
| Meilisearch | Snapshot to S3 | Daily | 7 days |

### Disaster Recovery
- **RTO (Recovery Time Objective):** 4 hours
- **RPO (Recovery Point Objective):** 1 hour (from WAL archival)
- Restore procedure documented and tested quarterly

---

## 8. Domain & DNS

| Record | Value | Purpose |
|--------|-------|---------|
| `fundaconnect.co.za` | A → Load Balancer IP | Main website |
| `api.fundaconnect.co.za` | A → Load Balancer IP | API endpoint |
| `www.fundaconnect.co.za` | CNAME → fundaconnect.co.za | WWW redirect |
| MX records | Configured for email provider | Transactional email |
| TXT (SPF) | `v=spf1 include:... -all` | Email authentication |
| TXT (DKIM) | DKIM key | Email authentication |
| TXT (DMARC) | `v=DMARC1; p=reject; ...` | Email authentication |
