# Frontend to Backend Migration - Monitoring Guide

## Overview

This guide describes the monitoring setup for the frontend-to-backend database migration, including key metrics, alerting thresholds, and dashboard configurations.

**Migration Date**: February 2, 2026
**Monitoring Tools**: Sentry, Prometheus, Grafana, ELK Stack

---

## Table of Contents

- [Key Metrics](#key-metrics)
- [Monitoring Setup](#monitoring-setup)
- [Alerting Configuration](#alerting-configuration)
- [Dashboard Configuration](#dashboard-configuration)
- [Log Aggregation](#log-aggregation)
- [Troubleshooting Guide](#troubleshooting-guide)

---

## Key Metrics

### Backend API Metrics

#### API Performance

| Metric | Type | Target | Warning | Critical |
|--------|------|--------|---------|----------|
| API Request Latency (p50) | Histogram | < 200ms | > 300ms | > 500ms |
| API Request Latency (p95) | Histogram | < 500ms | > 1s | > 2s |
| API Request Latency (p99) | Histogram | < 1000ms | > 2s | > 5s |
| Request Rate | Gauge | > 100 req/s | - | < 10 req/s |
| Error Rate | Counter | < 0.1% | > 0.5% | > 1% |

#### Endpoint-Specific Metrics

Monitor each of the 12 endpoints separately:

```
GET /api/users/me
GET /api/users/sessions
DELETE /api/users/sessions/{id}
DELETE /api/users/sessions
POST /api/email-verification/verify
POST /api/email-verification/send
GET /api/tenants/by-subdomain/{subdomain}
GET /api/tenants/context
GET /api/admin/users
PATCH /api/admin/users/{id}/last-login
GET /api/meetings/attendance/{task_id}
GET /api/financial/net-worth/summary
GET /api/financial/accounts
```

For each endpoint, track:
- Request count per minute
- Average latency
- Error rate (4xx, 5xx)
- Timeout rate

#### Database Metrics

| Metric | Type | Target | Warning | Critical |
|--------|------|--------|---------|----------|
| Connection Pool Usage | Gauge | < 50% | > 70% | > 90% |
| Query Latency (p95) | Histogram | < 100ms | > 200ms | > 500ms |
| Slow Queries (> 1s) | Counter | 0 | > 10/min | > 100/min |
| Deadlocks | Counter | 0 | - | > 0 |
| Transaction Time | Histogram | < 50ms | > 100ms | > 200ms |

#### System Metrics

| Metric | Type | Target | Warning | Critical |
|--------|------|--------|---------|----------|
| CPU Usage | Gauge | < 50% | > 70% | > 90% |
| Memory Usage | Gauge | < 70% | > 80% | > 90% |
| Disk I/O | Gauge | < 50% | > 70% | > 90% |
| Network I/O | Gauge | < 50% | > 70% | > 90% |

---

### Frontend Metrics

#### API Client Metrics

| Metric | Type | Target | Warning | Critical |
|--------|------|--------|---------|----------|
| API Request Success Rate | Gauge | > 99% | < 98% | < 95% |
| API Request Latency (p95) | Histogram | < 500ms | > 1s | > 2s |
| API Timeout Rate | Counter | 0% | > 1% | > 5% |
| Fallback to Direct DB | Counter | 0/min | - | > 0/min |

#### Browser Metrics

| Metric | Type | Target | Warning | Critical |
|--------|------|--------|---------|----------|
| Page Load Time | Histogram | < 2s | > 3s | > 5s |
| Time to Interactive | Histogram | < 3s | > 5s | > 8s |
| First Contentful Paint | Histogram | < 1s | > 2s | > 3s |
| Console Error Rate | Counter | 0 | > 10/min | > 100/min |
| JavaScript Error Rate | Counter | < 0.1% | > 0.5% | > 1% |

#### User Experience Metrics

| Metric | Type | Target | Warning | Critical |
|--------|------|--------|---------|----------|
| Registration Success Rate | Gauge | > 95% | < 90% | < 80% |
| Login Success Rate | Gauge | > 99% | < 95% | < 90% |
| Email Verification Rate | Gauge | > 80% | < 70% | < 50% |
| Password Reset Success Rate | Gauge | > 90% | < 80% | < 70% |

---

### Business Metrics

| Metric | Type | Target | Warning | Critical |
|--------|------|--------|---------|----------|
| Daily Active Users | Counter | Baseline | < 95% | < 90% |
| Registration Rate | Counter | Baseline | < 90% | < 80% |
| User Complaints | Counter | 0/day | > 5/day | > 20/day |
| Support Tickets | Counter | Baseline | > 110% | > 125% |

---

## Monitoring Setup

### Backend Monitoring

#### Prometheus Metrics Export

**File**: `backend/core/metrics.py`

```python
from prometheus_client import Counter, Histogram, Gauge
import time

# Request metrics
api_requests_total = Counter(
    'api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status']
)

api_request_latency = Histogram(
    'api_request_latency_seconds',
    'API request latency',
    ['method', 'endpoint']
)

api_errors_total = Counter(
    'api_errors_total',
    'Total API errors',
    ['method', 'endpoint', 'error_type']
)

# Database metrics
db_query_latency = Histogram(
    'db_query_latency_seconds',
    'Database query latency'
)

db_connection_pool_usage = Gauge(
    'db_connection_pool_usage',
    'Database connection pool usage'
)

# Middleware to track requests
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    
    response = await call_next(request)
    
    latency = time.time() - start_time
    endpoint = request.url.path
    
    api_requests_total.labels(
        method=request.method,
        endpoint=endpoint,
        status=response.status_code
    ).inc()
    
    api_request_latency.labels(
        method=request.method,
        endpoint=endpoint
    ).observe(latency)
    
    if response.status_code >= 400:
        api_errors_total.labels(
            method=request.method,
            endpoint=endpoint,
            error_type=str(response.status_code)
        ).inc()
    
    return response
```

#### Sentry Integration

**File**: `backend/core/sentry.py`

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[
        FastApiIntegration(),
        SqlalchemyIntegration()
    ],
    traces_sample_rate=0.1,  # 10% of transactions
    profiles_sample_rate=0.1,  # 10% of profiles
    environment=os.getenv("ENVIRONMENT", "development")
)
```

#### Health Check Endpoint

**File**: `backend/api/health_routes.py`

```python
from fastapi import APIRouter
from sqlalchemy import text
from core.database import engine
import psutil
import time

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/")
async def health_check():
    """Comprehensive health check"""
    
    # Check database
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # Check system resources
    cpu_percent = psutil.cpu_percent(interval=1)
    memory_percent = psutil.virtual_memory().percent
    disk_percent = psutil.disk_usage('/').percent
    
    overall_status = "healthy"
    if cpu_percent > 90 or memory_percent > 90 or disk_percent > 90:
        overall_status = "degraded"
    
    return {
        "status": overall_status,
        "timestamp": time.time(),
        "checks": {
            "database": db_status,
            "cpu": f"{cpu_percent}%",
            "memory": f"{memory_percent}%",
            "disk": f"{disk_percent}%"
        }
    }
```

---

### Frontend Monitoring

#### Sentry Integration

**File**: `frontend-nextjs/lib/sentry.ts`

```typescript
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: 0.1,  // 10% of transactions
  
  // Feature flag tracking
  initialScope: {
    tags: {
      use_backend_api: process.env.NEXT_PUBLIC_USE_BACKEND_API === 'true',
    },
  },
  
  // Custom breadcrumbs
  beforeBreadcrumb(breadcrumb) {
    if (breadcrumb.category === 'fetch') {
      const url = breadcrumb.data?.url || '';
      if (url.includes('/api/')) {
        breadcrumb.tags = { ...breadcrumb.tags, api_call: true };
      }
    }
    return breadcrumb;
  },
  
  // Track API errors
  integrations: [
    new Sentry.BrowserTracing({
      tracingOrigins: ['localhost', 'api.atom.com', /^\//],
    }),
  ],
});

// Track API call errors
export function trackApiError(endpoint: string, error: any) {
  Sentry.captureException(error, {
    tags: {
      api_endpoint: endpoint,
      use_backend_api: process.env.NEXT_PUBLIC_USE_BACKEND_API === 'true',
    },
    extra: {
      endpoint,
      error_message: error.message,
      stack_trace: error.stack,
    },
  });
}

// Track fallback to direct DB
export function trackDbFallback(endpoint: string) {
  Sentry.captureMessage('Fell back to direct DB access', {
    level: 'warning',
    tags: {
      endpoint,
      use_backend_api: process.env.NEXT_PUBLIC_USE_BACKEND_API === 'true',
    },
  });
}
```

#### API Client Instrumentation

**File**: `frontend-nextjs/lib/api.ts`

```typescript
import { trackApiError, trackDbFallback } from './sentry';

// In apiClient class:
private async request(endpoint: string, options: RequestInit = {}) {
  const startTime = performance.now();
  
  try {
    const response = await fetch(url, options);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    // Track success metrics
    const duration = performance.now() - startTime;
    if (typeof window !== 'undefined' && (window as any).gtag) {
      (window as any).gtag('event', 'api_request_success', {
        endpoint,
        duration,
        use_backend_api: USE_BACKEND_API,
      });
    }
    
    return response.json();
  } catch (error) {
    // Track error
    trackApiError(endpoint, error);
    
    // Fallback to direct DB if enabled
    if (USE_BACKEND_API && FALLBACK_ENABLED) {
      trackDbFallback(endpoint);
      return this.fallbackToDirectDB(endpoint, options);
    }
    
    throw error;
  }
}
```

---

## Alerting Configuration

### Alert Rules

#### Critical Alerts (Page On-Call Immediately)

1. **API Error Rate Critical**
```yaml
- alert: HighAPIErrorRate
  expr: rate(api_errors_total[5m]) > 0.01  # 1% error rate
  for: 2m
  annotations:
    summary: "API error rate above 1%"
    description: "Error rate is {{ $value }} errors/sec"
  labels:
    severity: critical
```

2. **API Latency Critical**
```yaml
- alert: HighAPILatency
  expr: histogram_quantile(0.95, api_request_latency_seconds) > 2
  for: 5m
  annotations:
    summary: "API p95 latency above 2s"
    description: "p95 latency is {{ $value }}s"
  labels:
    severity: critical
```

3. **Database Connection Pool Critical**
```yaml
- alert: DatabasePoolExhausted
  expr: db_connection_pool_usage > 0.9
  for: 2m
  annotations:
    summary: "Database connection pool above 90%"
    description: "Pool usage is {{ $value }}"
  labels:
    severity: critical
```

4. **Service Down**
```yaml
- alert: ServiceDown
  expr: up{job="atom-backend"} == 0
  for: 1m
  annotations:
    summary: "Backend service is down"
  labels:
    severity: critical
```

#### Warning Alerts (Email/Slack)

1. **API Error Rate Warning**
```yaml
- alert: ElevatedAPIErrorRate
  expr: rate(api_errors_total[5m]) > 0.005  # 0.5% error rate
  for: 5m
  annotations:
    summary: "API error rate elevated"
    description: "Error rate is {{ $value }} errors/sec"
  labels:
    severity: warning
```

2. **API Latency Warning**
```yaml
- alert: ElevatedAPILatency
  expr: histogram_quantile(0.95, api_request_latency_seconds) > 1
  for: 10m
  annotations:
    summary: "API p95 latency elevated"
    description: "p95 latency is {{ $value }}s"
  labels:
    severity: warning
```

3. **Database Pool Warning**
```yaml
- alert: DatabasePoolHigh
  expr: db_connection_pool_usage > 0.7
  for: 10m
  annotations:
    summary: "Database connection pool high"
    description: "Pool usage is {{ $value }}"
  labels:
    severity: warning
```

#### Info Alerts (Dashboard Notification)

1. **Deployment Detected**
```yaml
- alert: NewDeployment
  expr: changes(api_requests_total[1h]) > 0
  annotations:
    summary: "New deployment detected"
    description: "Request count changed, possible new deployment"
  labels:
    severity: info
```

---

### Alert Notification Channels

#### Critical Alerts
- **PagerDuty**: Page on-call engineer immediately
- **Slack**: Post to #incident-response
- **Email**: Send to on-call@atom.com

#### Warning Alerts
- **Slack**: Post to #engineering
- **Email**: Send to eng@atom.com

#### Info Alerts
- **Slack**: Post to #deployments

---

## Dashboard Configuration

### Grafana Dashboard

#### Panel 1: Overview

**Metrics**:
- API Request Rate (requests/sec)
- API Error Rate (%)
- API p95 Latency (ms)
- Database Pool Usage (%)

**Queries**:
```promql
# Request Rate
sum(rate(api_requests_total[5m]))

# Error Rate
sum(rate(api_errors_total[5m])) / sum(rate(api_requests_total[5m])) * 100

# p95 Latency
histogram_quantile(0.95, sum(rate(api_request_latency_seconds_bucket[5m])) by (le))

# DB Pool
db_connection_pool_usage * 100
```

#### Panel 2: Endpoint Performance

**Metrics**: Table showing each endpoint's performance

**Columns**:
- Endpoint
- Request Rate
- p50 Latency
- p95 Latency
- p99 Latency
- Error Rate
- Timeout Rate

**Query**:
```promql
sum(rate(api_requests_total{endpoint=~"/api/.*"}[5m])) by (endpoint)
```

#### Panel 3: Database Performance

**Metrics**:
- Connection Pool Usage (%)
- Query p95 Latency (ms)
- Slow Queries per Minute
- Active Transactions

**Queries**:
```promql
# Pool Usage
db_connection_pool_usage * 100

# Query Latency
histogram_quantile(0.95, db_query_latency_seconds)

# Slow Queries
rate(db_slow_queries_total[5m])
```

#### Panel 4: System Resources

**Metrics**:
- CPU Usage (%)
- Memory Usage (%)
- Disk I/O (%)
- Network I/O (%)

#### Panel 5: Feature Flag Usage

**Metrics**:
- Backend API Requests (%)
- Direct DB Requests (%)
- Fallback Rate (%)

**Query**:
```promql
# Backend API %
sum(rate(api_requests_total{use_backend="true"}[5m])) / sum(rate(api_requests_total[5m])) * 100
```

---

### Sentry Dashboard

#### Error Tracking

- **Errors by Endpoint**: Bar chart of errors per endpoint
- **Errors by Type**: Pie chart of error types
- **Errors Over Time**: Time series of error rate
- **Unhandled Errors**: List of unhandled errors

#### Performance Monitoring

- **Transactions by Endpoint**: Table of transaction counts
- **Transaction Duration**: Histogram of request durations
- **Slowest Transactions**: List of slowest requests

---

## Log Aggregation

### Backend Logging

**File**: `backend/core/logging.py`

```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add custom fields
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'endpoint'):
            log_data['endpoint'] = record.endpoint
        if hasattr(record, 'status_code'):
            log_data['status_code'] = record.status_code
        
        return json.dumps(log_data)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.FileHandler('logs/atom.log'),
        logging.StreamHandler()
    ]
)

for handler in logging.root.handlers:
    handler.setFormatter(JSONFormatter())
```

### Log Formats

#### API Request Log
```json
{
  "timestamp": "2026-02-02T12:34:56.789Z",
  "level": "INFO",
  "message": "API request received",
  "endpoint": "/api/users/me",
  "method": "GET",
  "user_id": "user-123",
  "status_code": 200,
  "duration_ms": 45
}
```

#### Database Query Log
```json
{
  "timestamp": "2026-02-02T12:34:56.789Z",
  "level": "DEBUG",
  "message": "Database query executed",
  "query": "SELECT * FROM users WHERE id = $1",
  "duration_ms": 12,
  "connection_id": "conn-456"
}
```

#### Error Log
```json
{
  "timestamp": "2026-02-02T12:34:56.789Z",
  "level": "ERROR",
  "message": "API request failed",
  "endpoint": "/api/users/me",
  "error": "User not found",
  "stack_trace": "...",
  "user_id": "user-123"
}
```

---

## Troubleshooting Guide

### High API Error Rate

**Symptoms**:
- Error rate > 0.5%
- Many 5xx errors in logs
- User complaints increasing

**Investigation Steps**:

1. **Check backend logs**:
```bash
tail -1000 /var/log/atom/backend.log | grep ERROR
```

2. **Check database logs**:
```bash
tail -1000 /var/log/postgresql/postgresql.log | grep ERROR
```

3. **Check specific endpoint**:
```bash
grep "/api/users/me" /var/log/atom/backend.log | tail -100
```

4. **Test endpoint directly**:
```bash
curl -H "Authorization: Bearer $TOKEN" https://api.atom.com/api/users/me
```

**Common Causes**:
- Database connection exhausted
- Slow query blocking
- Authentication service down
- Network timeout

**Solutions**:
- Increase DB connection pool size
- Optimize slow queries
- Restart backend service
- Enable fallback to direct DB

---

### High API Latency

**Symptoms**:
- p95 latency > 1s
- Slow page loads
- User complaints

**Investigation Steps**:

1. **Check database query performance**:
```sql
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

2. **Check system resources**:
```bash
top -bn1 | head -20
free -h
iostat -x 1 5
```

3. **Check network latency**:
```bash
ping -c 10 api.atom.com
traceroute api.atom.com
```

**Common Causes**:
- Slow database queries
- Network latency
- High CPU/memory usage
- N+1 query problems

**Solutions**:
- Add database indexes
- Enable query caching
- Scale backend horizontally
- Optimize API responses

---

### Database Connection Pool Exhausted

**Symptoms**:
- Pool usage > 90%
- Connection timeout errors
- "Pool exhausted" in logs

**Investigation Steps**:

1. **Check active connections**:
```sql
SELECT count(*), state
FROM pg_stat_activity
GROUP BY state;
```

2. **Check long-running queries**:
```sql
SELECT pid, query, state, wait_event_type
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start;
```

**Common Causes**:
- Connection leaks (not closing connections)
- Long-running transactions
- Too many concurrent requests

**Solutions**:
- Fix connection leaks
- Kill long-running queries
- Increase pool size
- Enable connection recycling

---

### Feature Flag Not Working

**Symptoms**:
- Frontend not calling backend API
- Direct DB queries still happening
- `USE_BACKEND_API` reads as `false`

**Investigation Steps**:

1. **Check environment variable**:
```bash
ssh frontend-server
cat /var/www/frontend-nextjs/.env.local | grep USE_BACKEND_API
```

2. **Check browser console**:
```javascript
process.env.NEXT_PUBLIC_USE_BACKEND_API
```

3. **Check frontend logs**:
```bash
pm2 logs frontend | grep USE_BACKEND_API
```

**Common Causes**:
- Environment variable not set
- Frontend not restarted after change
- Cache issue
- Build-time vs runtime variable

**Solutions**:
- Set environment variable correctly
- Restart frontend service
- Clear browser cache
- Rebuild frontend

---

## Log Locations

### Backend
- **Application logs**: `/var/log/atom/backend.log`
- **Error logs**: `/var/log/atom/error.log`
- **Access logs**: `/var/log/nginx/access.log`

### Frontend
- **Application logs**: PM2 logs (`pm2 logs frontend`)
- **Browser console**: F12 developer tools

### Database
- **PostgreSQL logs**: `/var/log/postgresql/postgresql.log`
- **Slow query log**: `/var/log/postgresql/slow.log`

---

**Last Updated**: February 2, 2026
**Version**: 1.0.0
