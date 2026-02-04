# Frontend to Backend Migration - Rollback Procedure

## Overview

This document provides detailed rollback procedures for the frontend-to-backend database migration, including instant rollback via feature flag and troubleshooting steps.

**Migration Date**: February 2, 2026
**Feature Flag**: `NEXT_PUBLIC_USE_BACKEND_API`
**Rollback Time**: < 5 minutes (instant)

---

## Table of Contents

- [Rollback Overview](#rollback-overview)
- [Instant Rollback Procedure](#instant-rollback-procedure)
- [Rollback Scenarios](#rollback-scenarios)
- [Verification Steps](#verification-steps)
- [Troubleshooting Rollback Issues](#troubleshooting-rollback-issues)
- [Post-Rollback Analysis](#post-rollback-analysis)

---

## Rollback Overview

### Rollback Levels

| Level | Scope | Time to Rollback | When to Use |
|-------|-------|------------------|-------------|
| **Level 1: Single Endpoint** | One API endpoint | 1 minute | One endpoint failing |
| **Level 2: Partial Rollback** | Feature flag (10%/50%/100%) | 2 minutes | Multiple endpoints failing |
| **Level 3: Full Rollback** | Entire migration | 5 minutes | Critical system failure |

### Rollback Decision Matrix

| Severity | Symptoms | Action | Timeline |
|----------|----------|--------|----------|
| **CRITICAL** | - 5xx errors > 5%<br>- API completely down<br>- Data loss risk<br>- Security breach | **Immediate full rollback** | < 5 min |
| **HIGH** | - 5xx errors > 1%<br>- API p95 > 2s<br>- DB pool > 90%<br>- 50%+ users affected | **Rollback to previous level** | < 15 min |
| **MEDIUM** | - Error rate > 0.5%<br>- API p95 > 1s<br>- User complaints > 5/hr | **Pause rollout, investigate** | < 1 hour |
| **LOW** | - Error rate > 0.1%<br>- API p95 > 500ms | **Monitor, continue** | Continue |

---

## Instant Rollback Procedure

### Level 3: Full Rollback (Critical)

**Time**: < 5 minutes
**Impact**: All users revert to direct DB access

#### Step 1: Identify the Issue (30 seconds)

```bash
# Check error rate
curl -s http://localhost:9090/api/v1/query?query=rate(api_errors_total[5m]) | jq '.data.result[0].value[1]'
# If > 0.01 (1%), initiate rollback

# Check API latency
curl -s http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,api_request_latency_seconds) | jq '.data.result[0].value[1]'
# If > 2, initiate rollback

# Check database pool
curl -s http://localhost:9090/api/v1/query?query=db_connection_pool_usage | jq '.data.result[0].value[1]'
# If > 0.9, initiate rollback
```

#### Step 2: Disable Feature Flag (1 minute)

```bash
# SSH to frontend server
ssh production-frontend-server

# Navigate to app directory
cd /var/www/frontend-nextjs

# Disable backend API (sed or manual edit)
sed -i 's/NEXT_PUBLIC_USE_BACKEND_API=true/NEXT_PUBLIC_USE_BACKEND_API=false/' .env.local

# Verify change
grep USE_BACKEND_API .env.local
# Should show: NEXT_PUBLIC_USE_BACKEND_API=false

# Restart frontend service
pm2 restart frontend

# Or if using systemd:
sudo systemctl restart frontend
```

**Alternative: If using deployment dashboard**

1. Log in to deployment dashboard (e.g., Vercel, Netlify, AWS)
2. Navigate to Environment Variables
3. Find `NEXT_PUBLIC_USE_BACKEND_API`
4. Change value from `true` to `false`
5. Trigger redeploy
6. Wait for deployment to complete (~2 minutes)

#### Step 3: Verify Rollback (2 minutes)

```bash
# 1. Check frontend is serving new flag
curl https://atom.com | grep -o "USE_BACKEND_API.*false"
# Or in browser console:
# process.env.NEXT_PUBLIC_USE_BACKEND_API
# Should return: "false"

# 2. Verify direct DB queries resume
tail -f /var/log/postgresql/postgresql.log
# Should see SQL queries from frontend IP

# 3. Test API endpoints still work
curl -X POST https://atom.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'
# Expected: 200 OK (via direct DB)

# 4. Check error rate decreases
curl -s http://localhost:9090/api/v1/query?query=rate(api_errors_total[5m])
# Should decrease to baseline
```

#### Step 4: Communicate (1 minute)

```bash
# Send Slack message
slack-send "#incident-response" "🚨 ROLLBACK COMPLETE: Frontend reverted to direct DB access. Investigating root cause."

# Page on-call if critical
pagerduty-notify --severity critical "Migration rollback complete"
```

---

### Level 2: Partial Rollback

**Time**: < 15 minutes
**Impact**: Reduce rollout percentage (100% → 50% → 10% → 0%)

#### Scenario: Currently at 50% Rollout, Need to Rollback to 10%

```bash
# Option 1: If using feature flag service (LaunchDarkly, Optimizely, etc.)
# Update via dashboard or API
curl -X POST https://app.launchdarkly.com/api/v2/flags/backend-migration \
  -H "Authorization: api-key-xxx" \
  -d '{
    "variations": [
      {"value": true, "weight": 10},
      {"value": false, "weight": 90}
    ]
  }'

# Option 2: If using environment variable (requires redeploy)
# Update deployment to reduce percentage
# This is slower, so prefer Option 1 for gradual rollback
```

#### Verification Steps

```bash
# Monitor metrics for 10 minutes
# Check if error rate decreases
# Check if user complaints stop

# If stable, continue at reduced level
# If still unstable, proceed to full rollback
```

---

### Level 1: Single Endpoint Rollback

**Time**: < 1 minute
**Impact**: Only one endpoint uses direct DB

#### Scenario: `/api/email-verification/verify` Endpoint Failing

**File**: `frontend-nextjs/lib/api.ts`

```typescript
// Add endpoint-specific fallback
export const emailVerificationAPI = {
  verifyEmail: async (email: string, code: string) => {
    try {
      return await apiClient.post("/api/email-verification/verify", { email, code });
    } catch (error) {
      // Fallback to direct DB for this endpoint only
      console.warn('Backend API failed for email verification, falling back to direct DB');
      return fallbackVerifyEmail(email, code);
    }
  },
};
```

**Implementation**:
1. Add try-catch around specific endpoint call
2. Implement fallback function using direct DB
3. No need to disable entire feature flag

---

## Rollback Scenarios

### Scenario 1: Backend API Down

**Symptoms**:
- All API requests failing with 5xx errors
- Backend server not responding
- Network timeout errors

**Root Causes**:
- Backend server crashed
- Network issue between frontend and backend
- Backend deployment failed

**Rollback Steps**:

```bash
# 1. Check backend status
curl https://api.atom.com/health
# If fails, backend is down

# 2. Check backend logs
ssh backend-server
tail -100 /var/log/atom/backend.log

# 3. Restart backend (if safe)
pm2 restart backend

# 4. If backend cannot be restarted quickly, rollback frontend
ssh frontend-server
cd /var/www/frontend-nextjs
sed -i 's/NEXT_PUBLIC_USE_BACKEND_API=true/NEXT_PUBLIC_USE_BACKEND_API=false/' .env.local
pm2 restart frontend

# 5. Verify
curl -X POST https://atom.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'
```

**Time**: 3-5 minutes

---

### Scenario 2: Database Connection Pool Exhausted

**Symptoms**:
- API errors: "Connection pool exhausted"
- High database connection count
- Slow API responses

**Root Causes**:
- Connection leak (not closing connections)
- Too many concurrent requests
- Long-running queries

**Rollback Steps**:

```bash
# 1. Check database connections
psql -U postgres -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# 2. Check long-running queries
psql -U postgres -c "SELECT pid, query, state FROM pg_stat_activity WHERE state != 'idle' ORDER BY query_start;"

# 3. Kill long-running queries (if safe)
psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE query_start < now() - interval '5 minutes';"

# 4. If issue persists, rollback frontend to reduce load
ssh frontend-server
cd /var/www/frontend-nextjs
sed -i 's/NEXT_PUBLIC_USE_BACKEND_API=true/NEXT_PUBLIC_USE_BACKEND_API=false/' .env.local
pm2 restart frontend

# 5. Monitor database
watch -n 5 "psql -U postgres -c 'SELECT count(*) FROM pg_stat_activity;'"
```

**Time**: 5-10 minutes

---

### Scenario 3: Authentication Failure

**Symptoms**:
- Users unable to login
- 401 Unauthorized errors
- JWT validation failing

**Root Causes**:
- JWT secret mismatch
- Authentication service down
- Token expired

**Rollback Steps**:

```bash
# 1. Check authentication logs
tail -100 /var/log/atom/backend.log | grep -i auth

# 2. Test authentication manually
curl -X POST https://api.atom.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'

# 3. If auth completely broken, rollback frontend
ssh frontend-server
cd /var/www/frontend-nextjs
sed -i 's/NEXT_PUBLIC_USE_BACKEND_API=true/NEXT_PUBLIC_USE_BACKEND_API=false/' .env.local
pm2 restart frontend

# 4. Verify login works
curl -X POST https://atom.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'
```

**Time**: 5 minutes

---

### Scenario 4: Performance Degradation

**Symptoms**:
- API p95 latency > 2s
- Slow page loads
- User complaints

**Root Causes**:
- Slow database queries
- N+1 query problem
- Network latency
- Insufficient backend resources

**Rollback Steps**:

```bash
# 1. Check API latency
curl -s http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,api_request_latency_seconds)

# 2. Check slow queries
psql -U postgres -c "SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# 3. If latency > 2s for > 5 minutes, rollback
ssh frontend-server
cd /var/www/frontend-nextjs
sed -i 's/NEXT_PUBLIC_USE_BACKEND_API=true/NEXT_PUBLIC_USE_BACKEND_API=false/' .env.local
pm2 restart frontend

# 4. Verify performance improves
# Page load time should return to baseline
```

**Time**: 5-10 minutes

---

### Scenario 5: Data Corruption

**Symptoms**:
- Incorrect data returned from API
- Data integrity errors
- User reports of wrong data

**Root Causes**:
- Bug in data transformation
- Incorrect database query
- Race condition

**Rollback Steps**:

```bash
# 1. IMMEDIATE ROLLBACK (data corruption is critical)
ssh frontend-server
cd /var/www/frontend-nextjs
sed -i 's/NEXT_PUBLIC_USE_BACKEND_API=true/NEXT_PUBLIC_USE_BACKEND_API=false/' .env.local
pm2 restart frontend

# 2. Verify data integrity
# Check sample records in database
psql -U postgres -c "SELECT * FROM users LIMIT 10;"

# 3. Check recent changes
# Did a deployment introduce a bug?
git log --since="2 hours ago"

# 4. Fix bug in backend
# Test thoroughly on staging
# Re-deploy backend fix
# Re-enable feature flag
```

**Time**: < 5 minutes (rollback), then fix time varies

---

## Verification Steps

After any rollback, verify the following:

### 1. Feature Flag Status

```bash
# Check environment variable
ssh frontend-server
cat /var/www/frontend-nextjs/.env.local | grep USE_BACKEND_API
# Expected: NEXT_PUBLIC_USE_BACKEND_API=false

# Check in browser console
# Open https://atom.com
# Press F12, go to Console tab
# Type: process.env.NEXT_PUBLIC_USE_BACKEND_API
# Expected: "false"
```

### 2. Direct DB Queries Active

```bash
# Monitor PostgreSQL logs
tail -f /var/log/postgresql/postgresql.log
# Should see SQL queries from frontend IP

# Check query pattern
tail -100 /var/log/postgresql/postgresql.log | grep "SELECT"
```

### 3. API Endpoints Working

```bash
# Test user registration
curl -X POST https://atom.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test-rollback@example.com","password":"SecurePass123!"}'
# Expected: 200 OK

# Test user login
curl -X POST https://atom.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'
# Expected: 200 OK with session

# Test email verification
curl -X POST https://atom.com/api/auth/send-verification-email \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com"}'
# Expected: 200 OK
```

### 4. Metrics Improved

```bash
# Check error rate decreased
curl -s http://localhost:9090/api/v1/query?query=rate(api_errors_total[5m])
# Should return to baseline (< 0.1%)

# Check API latency decreased
curl -s http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,api_request_latency_seconds)
# Should return to baseline (< 500ms)

# Check database pool
curl -s http://localhost:9090/api/v1/query?query=db_connection_pool_usage
# Should decrease (< 50%)
```

### 5. User Experience Restored

- [ ] Page load times normal
- [ ] User registration works
- [ ] User login works
- [ ] No console errors
- [ ] User complaints stopped

---

## Troubleshooting Rollback Issues

### Issue: Feature Flag Not Changing

**Symptoms**:
- Changed `.env.local` but flag still reads `true`
- Frontend still calling backend API

**Solutions**:

```bash
# 1. Restart frontend service
pm2 restart frontend
# Or
sudo systemctl restart frontend

# 2. Clear build cache
cd /var/www/frontend-nextjs
rm -rf .next
npm run build
pm2 restart frontend

# 3. Check multiple environment files
cat .env.local .env.production .env | grep USE_BACKEND_API
# Make sure all are set to false

# 4. Browser cache
# Users may need to hard refresh (Ctrl+Shift+R)
```

---

### Issue: Direct DB Queries Not Working

**Symptoms**:
- Rollback completed but errors persist
- Direct DB queries failing

**Solutions**:

```bash
# 1. Check database connection
psql -U postgres -c "SELECT 1;"
# Should return "1"

# 2. Check database credentials
cat /var/www/frontend-nextjs/.env.local | grep DATABASE_URL
# Verify credentials are correct

# 3. Check `lib/db.ts` still exists
ls -la /var/www/frontend-nextjs/lib/db.ts
# If missing, restore from git:
git checkout HEAD -- lib/db.ts

# 4. Restart frontend
pm2 restart frontend
```

---

### Issue: Error Rate Still High After Rollback

**Symptoms**:
- Rollback completed but error rate still high
- Both backend and direct DB failing

**Solutions**:

```bash
# 1. Check if issue is with database itself
psql -U postgres -c "SELECT 1;"
# If this fails, database is down

# 2. Restart database
sudo systemctl restart postgresql

# 3. Check database disk space
df -h /var/lib/postgresql
# If > 90%, need to clean up

# 4. Check database logs
tail -100 /var/log/postgresql/postgresql.log

# 5. May need to rollback backend deployment too
cd backend
git revert HEAD
pm2 restart backend
```

---

### Issue: Users Still Experiencing Problems

**Symptoms**:
- Rollback completed, metrics good, but users complaining

**Solutions**:

```bash
# 1. Check if users have cached responses
# Ask users to hard refresh (Ctrl+Shift+R)

# 2. Check if CDN is caching old responses
# Purge CDN cache
curl -X POST https://api.cdn.com/purge \
  -H "Authorization: Bearer xxx" \
  -d '{"urls": ["https://atom.com/*"]}'

# 3. Check specific user reports
# Look up user in database
psql -U postgres -c "SELECT * FROM users WHERE email = 'complaining-user@example.com';"

# 4. Check browser console for specific errors
# Ask user to send screenshot of console
```

---

## Post-Rollback Analysis

### Immediate Actions (First Hour)

1. **Stabilize System**
   - Ensure all metrics return to baseline
   - Verify all user flows working
   - Monitor for additional issues

2. **Communicate**
   - Update incident channel
   - Notify stakeholders
   - Post status page update

3. **Collect Data**
   - Save logs from incident period
   - Export metrics during incident
   - Record timeline of events

### Investigation (First 24 Hours)

1. **Root Cause Analysis**
   ```bash
   # Review backend logs
   grep ERROR /var/log/atom/backend.log > incident-errors.log
   
   # Review database logs
   grep ERROR /var/log/postgresql/postgresql.log > incident-db-errors.log
   
   # Review metrics during incident
   # Export Prometheus data for incident period
   ```

2. **Identify Trigger**
   - What deployment/change caused issue?
   - Was it load-related?
   - Was it a specific user/action?

3. **Reproduce Issue**
   - Can you reproduce on staging?
   - What exact steps trigger the issue?

### Resolution (Next 1-7 Days)

1. **Fix Bug**
   - Write test case for bug
   - Implement fix
   - Test on staging
   - Get code review

2. **Prevent Recurrence**
   - Add monitoring/alarm for this condition
   - Improve error handling
   - Add circuit breaker
   - Increase test coverage

3. **Re-Deploy**
   - Deploy fix to staging
   - Run full test suite
   - Deploy to production (with monitoring)
   - Gradual re-enable feature flag (10% → 50% → 100%)

### Post-Mortem (Within 1 Week)

Create post-mortem document with:

1. **Timeline**
   - When did issue start?
   - When was it detected?
   - When was rollback initiated?
   - When was system restored?

2. **Impact**
   - How many users affected?
   - How long was system degraded?
   - What was the business impact?

3. **Root Cause**
   - What was the technical root cause?
   - Were there process issues?
   - Were there communication issues?

4. **Lessons Learned**
   - What went well?
   - What could be improved?
   - What changes need to be made?

5. **Action Items**
   - Technical improvements
   - Process improvements
   - Monitoring improvements
   - Documentation updates

---

## Rollback Test Procedure

### Pre-Deployment Rollback Test

**Before every deployment, test rollback:**

```bash
# 1. Enable feature flag on staging
echo "NEXT_PUBLIC_USE_BACKEND_API=true" > .env.staging
npm run build
pm2 restart frontend-staging

# 2. Verify working
curl https://staging.atom.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'

# 3. Practice rollback
echo "NEXT_PUBLIC_USE_BACKEND_API=false" > .env.staging
npm run build
pm2 restart frontend-staging

# 4. Verify rollback worked
curl https://staging.atom.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'

# 5. Document rollback time
# Should be < 5 minutes
```

### Rollback Time Target

| Environment | Target Rollback Time | Actual Time |
|-------------|---------------------|-------------|
| Staging | < 5 minutes | ___ |
| Production | < 5 minutes | ___ |

---

## Rollback Checklist

### Pre-Rollback Checklist

- [ ] Identified severity level (Critical/High/Medium/Low)
- [ ] Confirmed rollback decision with team
- [ ] Notified stakeholders (Slack, email)
- [ ] Prepared to execute rollback
- [ ] Have rollback steps ready
- [ ] Have verification steps ready

### During Rollback Checklist

- [ ] Executed rollback command
- [ ] Restarted frontend service
- [ ] Waited for service to start
- [ ] Verified feature flag changed
- [ ] Tested API endpoints
- [ ] Monitored metrics improving
- [ ] Communicated rollback complete

### Post-Rollback Checklist

- [ ] All metrics at baseline
- [ ] All user flows working
- [ ] No new errors in logs
- [ ] Users notified of resolution
- [ ] Incident investigation started
- [ ] Root cause analysis scheduled
- [ ] Post-mortem planned

---

## Emergency Contacts

| Role | Name | Phone | Slack |
|------|------|-------|-------|
| On-Call Engineer | - | - | @oncall |
| Engineering Lead | - | - | @eng-lead |
| Product Manager | - | - | @pm |
| Support Lead | - | - | @support |

---

**Last Updated**: February 2, 2026
**Version**: 1.0.0
**Tested**: Rollback procedure tested on staging
