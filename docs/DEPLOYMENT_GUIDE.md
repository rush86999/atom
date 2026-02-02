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
curl http://localhost:8000/docs | grep "api/users"
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

# 2. Ensure all migrations are applied
cd backend
alembic upgrade head

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

# Verify backend health
curl https://api.atom.com/health
# Expected: {"status": "healthy"}
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
