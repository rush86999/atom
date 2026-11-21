# Atom Platform - Production Deployment Guide

This guide covers deploying the Atom platform to production using Docker Compose.

## Prerequisites

- Docker 24+ and Docker Compose V2
- A server with 4GB+ RAM
- Domain name with SSL certificate (recommended)

## Quick Start

> **Run production Compose commands from the repository root.** The production
> Compose file is `infra/docker-compose.prod.yml`; there is no
> `docker-compose.prod.yml` at the repository root. Pass
> `--project-directory .` so Compose resolves the `backend/`,
> `frontend-nextjs/`, and `backend/piece-engine/` build contexts against the
> repository. Without it, Compose resolves those paths under `infra/`, where
> the application trees do not exist.

1. **Clone the repository**:
   ```bash
   git clone git@github.com:rush86999/atom.git
   cd atom
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env and fill in required values:
   # - POSTGRES_PASSWORD (use a strong password)
   # - SECRET_KEY (openssl rand -hex 32; backend authentication/session signing)
   #   JWT_SECRET_KEY remains a documented compatibility fallback when SECRET_KEY is unset.
   # - BYOK_ENCRYPTION_KEY (openssl rand -hex 32)
   # - NEXTAUTH_SECRET (openssl rand -hex 32; runtime web auth secret)
   # - AI provider keys (optional — LLM features disabled without; add via Settings > AI or .env)
   ```

   The example Compose setup exposes the backend on public port `8001` and
   uses `NEXT_PUBLIC_API_URL=http://localhost:8001` for browser requests.
   Loopback is never accepted by default in production:
   `NEXT_PUBLIC_ALLOW_LOOPBACK` resolves to `0`, so the production build refuses
   a loopback origin unless the operator opts in. Set
   `NEXT_PUBLIC_ALLOW_LOOPBACK=1` only for a same-host deployment
   where the browser runs on the deployment host, for example with
   `NEXT_PUBLIC_API_URL=http://localhost:8001`. For a remote browser, leave it at
   `0` and set `NEXT_PUBLIC_API_URL` to the operator's public backend origin
   (for example an HTTPS origin). Both values are passed as frontend build args
   so the production build compiles the browser origin without embedding
   secrets. Inside the frontend container, server rewrites and web auth use the
   separate `BACKEND_URL=http://atom-backend:8000` service DNS over the Compose
   network.

3. **Prepare the database before starting the application**:

   Run production Compose commands from the repository root with the existing
   `--project-directory . -f infra/docker-compose.prod.yml` spelling. Start only
   PostgreSQL first. The backend and frontend must not start until the schema
   setup below succeeds.

   ```bash
   # Start only PostgreSQL. The backend and frontend are not started yet.
   docker compose --project-directory . -f infra/docker-compose.prod.yml up -d postgres
   ```

   **Fresh production installation:** Do not run `alembic upgrade heads` against
   an empty database. Raw Alembic still cannot bootstrap an empty database: on
   an empty PostgreSQL 16 schema it fails at revision `b78e9c2f1a3d`, which
   alters `agent_registry` before the migration history creates it. The
   application's startup bootstrap does not record Alembic history. Confirm
   `SHOW server_encoding;` returns `UTF8`, then run the transactional
   initializer in a one-off `atom-backend` container. Use the same
   `DATABASE_URL` as the application; do not override it for these commands.

   ```bash
   # Bootstrap the empty UTF-8 target transactionally.
   docker compose --project-directory . -f infra/docker-compose.prod.yml run --rm atom-backend python -m scripts.initialize_postgres

   # Verify all migration heads with ordinary Alembic.
   docker compose --project-directory . -f infra/docker-compose.prod.yml run --rm -e PYTHONPATH= atom-backend alembic heads
   docker compose --project-directory . -f infra/docker-compose.prod.yml run --rm -e PYTHONPATH= atom-backend alembic current
   ```

   `alembic current` must report every revision returned by `alembic heads`.
   If the initializer fails, do not start the application and do not fall back
   to raw `alembic upgrade heads` on the empty database. After PostgreSQL and
   the application are running, complete the signed starter-template read and
   restart check in [Health Checks](#health-checks).

   **Existing Alembic-managed database:** the commands below apply to an
   existing schema whose `server_encoding` is `UTF8`. Take a backup and rehearse
   the upgrade against a staging copy before applying it to production. Run the
   read-only compatibility check first, then the ordinary Alembic upgrade:

   ```bash
   # Read-only: verify the target's exact Alembic history and upgrade path.
   docker compose --project-directory . -f infra/docker-compose.prod.yml run --rm atom-backend python -m scripts.initialize_postgres --check-upgrade

   # Review the heads, then apply them in a one-off backend container.
   docker compose --project-directory . -f infra/docker-compose.prod.yml run --rm -e PYTHONPATH= atom-backend alembic heads
   docker compose --project-directory . -f infra/docker-compose.prod.yml run --rm -e PYTHONPATH= atom-backend alembic upgrade heads

   # Confirm the applied revisions match the migration heads.
   docker compose --project-directory . -f infra/docker-compose.prod.yml run --rm -e PYTHONPATH= atom-backend alembic current
   ```

   The `--check-upgrade` check is read-only. An existing target with exact legacy
   Alembic history needs no fresh bootstrap marker; proceed with `alembic upgrade
   heads`. If the target history is unknown, stop. Do not bootstrap, stamp, or
   upgrade an unknown target; follow the current release guidance and resolve
   the history before retrying.

   The initializer has been verified in PostgreSQL 15 (PG15) and PostgreSQL 16
   (PG16) core database rehearsals. These rehearsals cover core database
   bootstrap only; they are not a claim that a full Docker Compose deployment
   has been verified. See the [deployment runbook's migration
   step](../deployment/DEPLOYMENT_RUNBOOK.md#step-2-run-database-migrations)
   for the full fresh-install and existing-target procedures.

4. **Start the application after the schema setup succeeds**:
   ```bash
   docker compose --project-directory . -f infra/docker-compose.prod.yml up -d
   ```

5. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8001/api/v1/docs

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `POSTGRES_PASSWORD` | ✅ | Database password |
| `SECRET_KEY` | ✅ | Backend authentication/session signing secret. Generate with `openssl rand -hex 32`; the production Compose file passes it to the backend at container start |
| `JWT_SECRET_KEY` | — | Documented compatibility fallback for `SECRET_KEY`. When `SECRET_KEY` is unset, the production Compose file passes `JWT_SECRET_KEY` as the backend's `SECRET_KEY`; prefer setting `SECRET_KEY` directly |
| `BYOK_ENCRYPTION_KEY` | ✅ | AI key encryption |
| `NEXTAUTH_SECRET` | ✅ | Web auth runtime secret; passed to the frontend at container start, never baked into the image |
| `NEXT_PUBLIC_API_URL` | — | Browser-facing backend origin compiled into the frontend. Defaults to `http://localhost:8001` for the Compose example |
| `NEXT_PUBLIC_ALLOW_LOOPBACK` | — | Defaults to `0`; set to `1` only for a same-host browser (for example with `NEXT_PUBLIC_API_URL=http://localhost:8001`). Leave `0` for a remote public origin |
| `NEXTAUTH_URL` | — | Public frontend origin for web auth callbacks. Defaults to `http://localhost:3000`; set to the operator's public frontend origin for remote deployments |
| `OPENAI_API_KEY` | — | OpenAI API access (optional — LLM features disabled without) |
| `ANTHROPIC_API_KEY` | — | Anthropic Claude access (optional) |
| `TAVILY_API_KEY` | Optional | Web search capability |

The backend signing secret is `SECRET_KEY`. At container start, the production
Compose file resolves it from `SECRET_KEY` when provided, otherwise from the
documented `JWT_SECRET_KEY` compatibility name; `SECRET_KEY` wins when both are
set. Keep the same secret across restarts and backend replicas.

`BACKEND_URL` is fixed to `http://atom-backend:8000` by the production Compose
file for container-to-container server requests; it is not the browser-facing
URL. Remote deployments should configure the public frontend and backend
origins through a reverse proxy and set the operator's public origins, for
example:

```bash
NEXT_PUBLIC_API_URL=https://api.example.invalid
NEXT_PUBLIC_ALLOW_LOOPBACK=0
NEXTAUTH_URL=https://app.example.invalid
NEXTAUTH_SECRET=<the same configured runtime secret>
```

Rebuild the frontend after changing a `NEXT_PUBLIC_*` value because those values
are compiled into the browser bundle.

## Health Checks

- Backend reachability: `curl -fsS http://localhost:8001/alive`

  A successful `/alive` response only means the API is reachable. It does not
  prove that startup seed data was written.

- Seed data: sign in as the bootstrap user, then request `GET /api/user/templates`
  with the session token:

  ```bash
  curl -fsS -H "Authorization: Bearer $TOKEN" http://localhost:8001/api/user/templates
  ```

  Confirm the bundled starter templates are present, repeat the read after an
  orderly restart, and compare the template IDs. A failed seed write can still
  leave `/alive` returning success; see the [deployment
  runbook](../deployment/DEPLOYMENT_RUNBOOK.md#step-2-run-database-migrations)
  for the full fresh-install rehearsal.

- Frontend: `curl -fsS http://localhost:3000/api/health`

  `/api/health` is public and reports this frontend HTTP service directly; it
  does not require a session or call the backend.

## Scaling

For high availability, consider:
- Using an external managed PostgreSQL (RDS, Cloud SQL)
- Deploying multiple backend replicas behind a load balancer
- Adding Redis for session and cache (not included in `infra/docker-compose.prod.yml`)

## Monitoring

`infra/docker-compose.prod.yml` does not include Prometheus or Grafana. Deploy
them separately if you need dashboards; see the [deployment
runbook](../deployment/DEPLOYMENT_RUNBOOK.md) for monitoring and verification
steps.
# Frontend to Backend Migration - Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the frontend-to-backend database migration across environments (staging and production).

**Migration Date**: February 2, 2026
**Feature Flag**: `NEXT_PUBLIC_USE_BACKEND_API`
**Rollout Strategy**: Gradual (10% → 50% → 100%)

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Pre-Deployment Checklist](#pre-deployment-checklist)
- [Staging Deployment](#staging-deployment)
- [Production Deployment](#production-deployment)
- [Gradual Rollout Process](#gradual-rollout-process)
- [Post-Deployment Verification](#post-deployment-verification)
- [Emergency Rollback](#emergency-rollback)

---

## Prerequisites

### Backend Requirements

- Python 3.11+
- FastAPI 0.104.0+
- SQLAlchemy 2.0+
- PostgreSQL 14+ (or SQLite for development)
- Alembic for database migrations

### Frontend Requirements

- Node.js 18+
- Next.js 15.5.0+
- Environment variables configured

### Access Requirements

- Backend server access (port 8000)
- Frontend server access (port 3000)
- Database access for migrations
- Monitoring tools access (Sentry, logs, metrics)

---

## Pre-Deployment Checklist

### 1. Backend Verification

```bash
# Run all backend tests
cd backend
pytest tests/test_user_management_api.py -v

# Verify database models
python -c "from core.models import User, EmailVerificationToken, Tenant; print('Models OK')"

# Check API endpoints
curl -fsS http://localhost:8001/api/v1/openapi.json | jq -e '.paths | keys | any(startswith("/api/users"))'
```

**Expected Results**:
- ✅ All 40+ tests pass
- ✅ All models import successfully
- ✅ All endpoints visible in Swagger UI

### 2. Frontend Verification

```bash
# Check TypeScript compilation
cd frontend-nextjs
npm run build

# Verify feature flag
grep NEXT_PUBLIC_USE_BACKEND_API .env.local

# Test API client
npm run test -- lib/__tests__/api-client.test.ts
```

**Expected Results**:
- ✅ No TypeScript errors
- ✅ Feature flag set to `false` (initial state)
- ✅ API client tests pass

### 3. Database Migration Verification

```bash
cd backend

# Check current migration version
alembic current

# Verify all migrations applied
alembic history | grep "Add user management models"

# Check tables exist
python -c "
from core.database import engine
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print('Tables:', tables)
assert 'email_verification_tokens' in tables
assert 'tenants' in tables
assert 'admin_users' in tables
assert 'meeting_attendance_status' in tables
assert 'financial_accounts' in tables
assert 'net_worth_snapshots' in tables
print('✅ All tables exist')
"
```

**Expected Results**:
- ✅ Migration "Add user management models" applied
- ✅ All 6 new tables exist

---

## Staging Deployment

### Step 1: Deploy Backend to Staging

```bash
# 1. Create staging branch
git checkout -b release/backend-migration-staging

# 2. For an existing PostgreSQL staging database, verify its history and migrate it.
cd backend
python -m scripts.initialize_postgres --check-upgrade
alembic upgrade heads

# 3. Deploy backend to staging
./deploy-backend.sh staging

# 4. Verify backend is running
curl https://staging-api.atom.com/api/users/me
# Expected: 401 Unauthorized (requires auth token)
```

**Verification**:
- [ ] Backend responds on staging URL
- [ ] All 6 route groups loaded in logs
- [ ] Database migrations successful
- [ ] No errors in backend logs

### Step 2: Deploy Frontend to Staging

```bash
# 1. Build frontend with feature flag DISABLED (initial state)
cd frontend-nextjs
echo "NEXT_PUBLIC_USE_BACKEND_API=false" >> .env.staging
npm run build

# 2. Deploy to staging
./deploy-frontend.sh staging

# 3. Verify frontend is running
curl https://staging.atom.com
# Expected: 200 OK
```

### Step 3: Test with Feature Flag Enabled

```bash
# Update staging environment to enable backend API
ssh staging-server
cd /var/www/frontend-nextjs
echo "NEXT_PUBLIC_USE_BACKEND_API=true" >> .env.local
pm2 restart frontend
```

### Step 4: Staging Testing Suite

Run comprehensive tests:
- User registration
- Email verification
- User login
- Password reset
- Session management

---

## Production Deployment

### Step 1: Deploy Backend to Production

```bash
# Deploy backend (zero-downtime deployment)
./deploy-backend.sh production

# Verify the API is reachable
curl -fsS https://api.atom.com/alive
# Expected: HTTP 200. Reachability only; this does not confirm seed data.

# Verify signed seed data after signing in as the bootstrap user
curl -fsS -H "Authorization: Bearer $TOKEN" https://api.atom.com/api/user/templates
# Expected: the bundled starter templates are listed.
```

### Step 2: Deploy Frontend to Production (Feature Flag Disabled)

```bash
# IMPORTANT: Start with feature flag DISABLED
cd frontend-nextjs
echo "NEXT_PUBLIC_USE_BACKEND_API=false" > .env.production
npm run build

# Deploy frontend
./deploy-frontend.sh production
```

---

## Gradual Rollout Process

### Week 1: 10% Rollout

**Objective**: Validate stability with small user segment

**Monitoring Dashboard**:
- API response time (p50, p95, p99)
- Error rate by endpoint
- Database connection pool usage
- Frontend error rate (Sentry)

**Alerting Thresholds**:
- API p95 latency > 1s → WARNING
- API p95 latency > 2s → CRITICAL
- Error rate > 0.5% → WARNING
- Error rate > 1% → CRITICAL

**Success Criteria**:
- ✅ 24 hours stable
- ✅ Error rate < 0.1%
- ✅ API p95 < 500ms
- ✅ No user complaints

### Week 2: 50% Rollout

**Success Criteria**:
- ✅ 24 hours stable
- ✅ Error rate < 0.1%
- ✅ API p95 < 500ms

### Week 3: 100% Rollout

**Success Criteria**:
- ✅ 7 days stable
- ✅ Error rate < 0.05%
- ✅ All metrics improved vs baseline

---

## Emergency Rollback

### Immediate Rollback (< 5 minutes)

```bash
# Disable backend API feature flag
ssh production-frontend-server
cd /var/www/frontend-nextjs
sed -i 's/NEXT_PUBLIC_USE_BACKEND_API=true/NEXT_PUBLIC_USE_BACKEND_API=false/' .env.local
pm2 restart frontend
```

### Verification After Rollback

```bash
# Verify direct DB queries resume
tail -f /var/log/postgresql/postgresql.log

# Verify frontend works
curl -X POST https://atom.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'
```

---

## Rollback Decision Matrix

| Severity | Symptoms | Action | Timeline |
|----------|----------|--------|----------|
| **CRITICAL** | 5xx errors > 5%, API down | Immediate rollback to 0% | < 5 min |
| **HIGH** | 5xx errors > 1%, API p95 > 2s | Rollback to previous level | < 15 min |
| **MEDIUM** | Error rate > 0.5% | Pause rollout, investigate | < 1 hour |
| **LOW** | Error rate > 0.1% | Monitor, continue | Continue |

---

**Last Updated**: February 2, 2026
**Version**: 1.0.0
