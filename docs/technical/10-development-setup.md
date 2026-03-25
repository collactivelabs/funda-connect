# 10 — Development Environment Setup

> **Status:** Draft  
> **Last Updated:** 2026-03-25

---

## 1. Prerequisites

| Tool | Version | Installation |
|------|---------|-------------|
| Python | 3.12+ | `brew install python@3.12` |
| Node.js | 20+ LTS | `brew install node@20` or via `nvm` |
| Docker Desktop | Latest | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) |
| Docker Compose | v2+ | Bundled with Docker Desktop |
| Git | Latest | `brew install git` |
| PostgreSQL client | 16 | `brew install postgresql@16` (for `psql` CLI) |
| Redis CLI | 7 | `brew install redis` (for `redis-cli`) |

### Optional but Recommended

| Tool | Purpose |
|------|---------|
| `direnv` | Automatic `.env` loading per directory |
| `just` or `make` | Task runner for common commands |
| `httpie` or `curl` | API testing from terminal |
| VS Code | IDE with Python + TypeScript extensions |
| pgAdmin or DBeaver | Database GUI |

---

## 2. Project Setup

### 2.1 Clone the Repository

```bash
cd ~/My-Projects
git clone git@github.com:your-org/funda-connect.git
cd funda-connect
```

### 2.2 Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

```env
# ─── Database ───
DATABASE_URL=postgresql+asyncpg://fc_user:fc_password@localhost:5432/fundaconnect
DB_PASSWORD=fc_password

# ─── Redis ───
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=fc_redis_password

# ─── Auth ───
SECRET_KEY=your-super-secret-key-change-this-in-production
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ─── PayFast (Sandbox) ───
PAYFAST_MERCHANT_ID=10000100
PAYFAST_MERCHANT_KEY=46f0cd694581a
PAYFAST_PASSPHRASE=jt7NOE43FZPn
PAYFAST_SANDBOX=true
PAYFAST_RETURN_URL=http://localhost:3001/booking/success
PAYFAST_CANCEL_URL=http://localhost:3001/booking/cancelled
PAYFAST_NOTIFY_URL=http://localhost:8000/api/v1/webhooks/payfast

# ─── File Storage (Local dev) ───
STORAGE_BACKEND=local
LOCAL_STORAGE_PATH=./uploads
# For S3: STORAGE_BACKEND=s3, S3_BUCKET=..., AWS_ACCESS_KEY_ID=..., etc.

# ─── Email (dev: console backend) ───
EMAIL_BACKEND=console
# For real email: EMAIL_BACKEND=smtp, SMTP_HOST=..., etc.

# ─── SMS (dev: disabled) ───
SMS_ENABLED=false

# ─── Meilisearch ───
MEILI_URL=http://localhost:7700
MEILI_MASTER_KEY=dev_master_key_change_in_prod

# ─── App ───
ENVIRONMENT=development
DEBUG=true
ALLOWED_ORIGINS=http://localhost:3001,http://localhost:3001
```

---

## 3. Running with Docker Compose (Recommended)

The easiest way to run the full stack locally:

```bash
# Start all services
docker compose -f docker-compose.dev.yml up -d

# View logs
docker compose -f docker-compose.dev.yml logs -f api

# Stop all services
docker compose -f docker-compose.dev.yml down

# Reset database (destructive!)
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d
```

### docker-compose.dev.yml

```yaml
version: "3.9"

services:
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    volumes:
      - ./backend:/app            # Hot reload
      - ./uploads:/app/uploads     # Local file uploads
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://fc_user:fc_password@db:5432/fundaconnect
      - REDIS_URL=redis://redis:6379/0
      - ENVIRONMENT=development
      - DEBUG=true
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    volumes:
      - ./frontend:/app
      - /app/node_modules          # Avoid overwriting container node_modules
    ports:
      - "3001:3001
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    command: npm run dev

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_DB=fundaconnect
      - POSTGRES_USER=fc_user
      - POSTGRES_PASSWORD=fc_password
    volumes:
      - pgdata_dev:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U fc_user -d fundaconnect"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  meilisearch:
    image: getmeili/meilisearch:v1.11
    environment:
      - MEILI_MASTER_KEY=dev_master_key_change_in_prod
      - MEILI_ENV=development
    ports:
      - "7700:7700"
    volumes:
      - meilidata_dev:/meili_data

  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    command: celery -A app.tasks worker -l debug -c 2
    volumes:
      - ./backend:/app
    environment:
      - DATABASE_URL=postgresql+asyncpg://fc_user:fc_password@db:5432/fundaconnect
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  mailhog:
    image: mailhog/mailhog
    ports:
      - "1025:1025"      # SMTP
      - "8025:8025"       # Web UI for viewing emails

volumes:
  pgdata_dev:
  meilidata_dev:
```

---

## 4. Running Without Docker

### 4.1 Backend

```bash
cd backend

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run database migrations
alembic upgrade head

# Seed reference data
python -m scripts.seed_data

# Start the API server (with hot reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4.2 Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
# → http://localhost:3001
```

### 4.3 Celery Worker

```bash
cd backend
source .venv/bin/activate
celery -A app.tasks worker -l debug -c 2
```

### 4.4 Celery Beat (Scheduler)

```bash
cd backend
source .venv/bin/activate
celery -A app.tasks beat -l info
```

---

## 5. Database Operations

```bash
# Connect to local database
psql -h localhost -U fc_user -d fundaconnect

# Create a new migration
cd backend
alembic revision --autogenerate -m "description_of_change"

# Apply migrations
alembic upgrade head

# Rollback last migration
alembic downgrade -1

# View migration history
alembic history

# Seed reference data (subjects, grades, curricula)
python -m scripts.seed_data

# Seed test data (fake teachers, parents, bookings)
python -m scripts.seed_test_data
```

---

## 6. Testing

### 6.1 Backend Tests

```bash
cd backend
source .venv/bin/activate

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_bookings.py

# Run specific test
pytest tests/test_bookings.py::test_create_booking_success

# Run with verbose output
pytest -v -s
```

### 6.2 Frontend Tests

```bash
cd frontend

# Run unit tests
npm test

# Run with coverage
npm run test:coverage

# Run E2E tests (requires running dev server)
npm run test:e2e
```

### 6.3 API Testing

```bash
# The API auto-generates OpenAPI docs:
# Swagger UI: http://localhost:8000/docs
# ReDoc:      http://localhost:8000/redoc

# Example API calls with httpie:
http POST localhost:8000/api/v1/auth/register \
  email=test@example.co.za \
  password=Test@1234 \
  first_name=Test \
  last_name=User \
  role=parent

http POST localhost:8000/api/v1/auth/login \
  email=test@example.co.za \
  password=Test@1234
```

---

## 7. Useful Commands (Makefile)

```makefile
.PHONY: dev stop logs test lint migrate seed

dev:                    ## Start all services
	docker compose -f docker-compose.dev.yml up -d

stop:                   ## Stop all services
	docker compose -f docker-compose.dev.yml down

logs:                   ## Tail all logs
	docker compose -f docker-compose.dev.yml logs -f

test:                   ## Run all tests
	cd backend && pytest --cov=app
	cd frontend && npm test

lint:                   ## Run linters
	cd backend && ruff check . && mypy app/
	cd frontend && npm run lint && npm run type-check

migrate:                ## Run database migrations
	cd backend && alembic upgrade head

seed:                   ## Seed reference + test data
	cd backend && python -m scripts.seed_data && python -m scripts.seed_test_data

reset-db:               ## Reset database (DESTRUCTIVE)
	docker compose -f docker-compose.dev.yml down -v
	docker compose -f docker-compose.dev.yml up -d db redis
	sleep 3
	cd backend && alembic upgrade head && python -m scripts.seed_data

format:                 ## Auto-format code
	cd backend && ruff format .
	cd frontend && npm run format
```

---

## 8. IDE Configuration

### VS Code (Recommended Extensions)
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Ruff (charliermarsh.ruff)
- ES7+ React/Redux/React-Native snippets
- Tailwind CSS IntelliSense
- Prettier
- GitLens
- Docker
- Thunder Client (API testing)

### VS Code Settings (`.vscode/settings.json`)
```json
{
  "python.defaultInterpreterPath": "./backend/.venv/bin/python",
  "python.analysis.typeCheckingMode": "basic",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "editor.tabSize": 2,
  "files.exclude": {
    "**/__pycache__": true,
    "**/.pytest_cache": true
  }
}
```

---

## 9. Git Workflow

### Branch Naming
- `main` — production-ready code
- `develop` — integration branch
- `feature/FC-123-add-booking-flow` — feature branches (with ticket number)
- `fix/FC-456-payment-timeout` — bug fixes
- `hotfix/critical-security-patch` — production hotfixes

### Commit Messages
Follow [Conventional Commits](https://www.conventionalcommits.org/):
```
feat(bookings): add recurring booking support
fix(payments): handle PayFast timeout gracefully
docs(api): update booking endpoint documentation
test(auth): add password reset flow tests
chore(deps): upgrade FastAPI to 0.115.0
```

### Pull Request Process
1. Create feature branch from `develop`
2. Implement changes with tests
3. Push and open PR against `develop`
4. CI pipeline must pass (tests, lint, type-check)
5. At least 1 code review approval required
6. Squash merge into `develop`
7. Release: merge `develop` into `main` via PR
