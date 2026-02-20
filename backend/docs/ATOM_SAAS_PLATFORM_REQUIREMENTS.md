# Atom SaaS Platform Requirements

**Document Version:** 1.0.0
**Last Updated:** 2026-02-19
**Status:** Requirements Specification (For Future Deployment)

---

## Overview

### Purpose

This document defines the requirements for the **Atom SaaS Platform** - a cloud-based service that enables local Atom instances to sync skills, categories, and ratings with a centralized marketplace.

### Architecture

```
┌─────────────────────┐         HTTP/WebSocket          ┌──────────────────────┐
│   Local Atom        │ ◄─────────────────────────────► │  Atom SaaS Platform  │
│   (Self-Hosted)     │   Sync every 15 minutes (poll)  │   (Cloud)            │
│                     │   Real-time (WebSocket)         │                      │
└─────────────────────┘                                   └──────────────────────┘

Key Components:
- Local Atom: Self-hosted Atom instances (Personal Edition, Enterprise)
- Atom SaaS Platform: Cloud-hosted marketplace and sync service
- Sync Modes: Polling (HTTP), Real-time (WebSocket)
```

### Sync Modes

**Polling Mode (HTTP)**:
- Local Atom polls Atom SaaS API every 15 minutes (configurable)
- Fetches all skills, categories, and ratings
- Used as fallback when WebSocket unavailable

**Real-Time Mode (WebSocket)**:
- Atom SaaS pushes updates immediately when skills/categories change
- 30-second heartbeat to detect stale connections
- Automatic reconnection with exponential backoff (1s → 16s max)

### Data Flow

```
1. Local Atom startup → Initialize SyncService → Connect to Atom SaaS API
2. Poll every 15 minutes → GET /api/v1/skills → Update SkillCache
3. WebSocket connects → WS wss://api.atomsaas.com/ws → Listen for updates
4. User rates skill → POST /api/v1/ratings → Sync to Atom SaaS
5. Skill updated on SaaS → WebSocket message → Update local cache
```

---

## Required HTTP API Endpoints

### Authentication

**All API endpoints require Bearer token authentication:**

```http
Authorization: Bearer ATOM_SAAS_API_TOKEN
```

Token format: UUID v4 or JWT
Token source: Environment variable `ATOM_SAAS_API_TOKEN`

---

### 1. Fetch Skills from Marketplace

**Endpoint:** `GET /api/v1/skills`

**Description:** Fetch paginated list of skills from Atom SaaS marketplace

**Query Parameters:**

| Parameter  | Type    | Default | Max    | Description                            |
| ---------- | ------- | ------- | ------ | -------------------------------------- |
| `query`    | string  | ""      | -      | Full-text search query                 |
| `category` | string  | null    | -      | Filter by category (e.g., "automation") |
| `page`     | integer | 1       | -      | Page number                            |
| `page_size`| integer | 100     | 1000   | Results per page                       |

**Response:**

```json
{
  "skills": [
    {
      "skill_id": "uuid-v4",
      "name": "Send Email",
      "description": "Send emails via SMTP",
      "version": "1.0.0",
      "code": "def send_email(to, subject, body):\n    ...",
      "command": "python",
      "python_packages": ["smtplib"],
      "npm_packages": [],
      "tags": ["email", "automation"],
      "metadata": {
        "author": "Atom Team",
        "documentation_url": "https://..."
      },
      "category": "automation",
      "average_rating": 4.5,
      "rating_count": 42,
      "created_at": "2026-01-01T00:00:00Z",
      "updated_at": "2026-01-15T10:30:00Z"
    }
  ],
  "page": 1,
  "page_size": 100,
  "total": 1500,
  "total_pages": 15
}
```

**Error Responses:**

| Code | Description                  | Headers            |
| ---- | ---------------------------- | ------------------ |
| 401  | Invalid/expired token        | WWW-Authenticate   |
| 429  | Rate limit exceeded          | Retry-After: 60    |
| 500  | Internal server error        | -                  |

**Rate Limit:** 100 requests/minute per Atom instance

---

### 2. Fetch Single Skill by ID

**Endpoint:** `GET /api/v1/skills/{skill_id}`

**Description:** Get detailed skill information

**Path Parameters:**

| Parameter  | Type   | Description            |
| ---------- | ------ | ---------------------- |
| `skill_id` | string | UUID v4 skill identifier |

**Response:**

```json
{
  "skill_id": "uuid-v4",
  "name": "Send Email",
  "description": "Send emails via SMTP",
  "version": "1.0.0",
  "code": "def send_email(to, subject, body):\n    ...",
  "command": "python",
  "python_packages": ["smtplib"],
  "npm_packages": [],
  "tags": ["email", "automation"],
  "metadata": {
    "author": "Atom Team",
    "documentation_url": "https://...",
    "examples": [
      {
        "description": "Send a simple email",
        "input": { "to": "user@example.com", "subject": "Hello", "body": "World" },
        "output": { "success": true, "message": "Email sent" }
      }
    ]
  },
  "category": "automation",
  "average_rating": 4.5,
  "rating_count": 42,
  "ratings": [
    {
      "user_id": "user@example.com",
      "rating": 5,
      "comment": "Great skill!",
      "created_at": "2026-01-15T10:30:00Z"
    }
  ],
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-15T10:30:00Z"
}
```

**Error Responses:**

| Code | Description              |
| ---- | ------------------------ |
| 404  | Skill not found          |

---

### 3. Fetch Categories

**Endpoint:** `GET /api/v1/categories`

**Description:** Fetch all skill categories from Atom SaaS

**Response:**

```json
{
  "categories": [
    {
      "name": "automation",
      "description": "Automation and workflow skills",
      "skill_count": 150,
      "icon_url": "https://...",
      "created_at": "2026-01-01T00:00:00Z"
    },
    {
      "name": "integration",
      "description": "Third-party service integrations",
      "skill_count": 85,
      "icon_url": "https://...",
      "created_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

---

### 4. Submit Skill Rating

**Endpoint:** `POST /api/v1/ratings`

**Description:** Submit a skill rating to Atom SaaS (bidirectional sync)

**Request Body:**

```json
{
  "skill_id": "uuid-v4",
  "rating": 5,
  "comment": "Great skill!",
  "user_id": "user@example.com"
}
```

**Field Validation:**

| Field    | Type    | Required | Validation         |
| -------- | ------- | -------- | ------------------ |
| skill_id | string  | Yes      | UUID v4 format     |
| rating   | integer | Yes      | 1-5 range          |
| comment  | string  | No       | Max 1000 chars     |
| user_id  | string  | Yes      | Email or user ID   |

**Response:**

```json
{
  "success": true,
  "rating_id": "uuid-v4",
  "skill_id": "uuid-v4",
  "rating": 5,
  "average_rating": 4.7,
  "rating_count": 43,
  "created_at": "2026-02-19T10:30:00Z"
}
```

**Error Responses:**

| Code | Description                      |
| ---- | -------------------------------- |
| 400  | Invalid rating (not 1-5)         |
| 404  | Skill not found                  |
| 409  | Rating already exists (update only) |

**Conflict Resolution:** Timestamp-based (newest wins)

---

### 5. Install Skill from Marketplace

**Endpoint:** `POST /api/v1/skills/{skill_id}/install`

**Description:** Install skill from Atom SaaS marketplace

**Request Body:**

```json
{
  "agent_id": "local-agent-id",
  "auto_install_deps": true
}
```

**Response:**

```json
{
  "success": true,
  "skill_id": "uuid-v4",
  "installed_at": "2026-02-19T10:30:00Z",
  "dependencies_installed": ["numpy==1.21.0", "pandas>=1.3.0"]
}
```

**Note:** This endpoint is for future enhancement when Atom SaaS supports remote skill installation

---

### 6. Health Check

**Endpoint:** `GET /health`

**Description:** Health check endpoint for monitoring Atom SaaS availability

**Response:**

```json
{
  "status": "healthy",
  "timestamp": "2026-02-19T10:30:00Z",
  "version": "1.0.0"
}
```

**Response Codes:**

| Code | Description                |
| ---- | -------------------------- |
| 200  | Atom SaaS is healthy       |
| 503  | Atom SaaS is unavailable   |

---

## Required WebSocket Endpoint

### WebSocket Connection

**Endpoint:** `WS wss://api.atomsaas.com/ws`

**Authentication:** Query parameter `?token=ATOM_SAAS_API_TOKEN`

**Connection Example:**

```javascript
const ws = new WebSocket('wss://api.atomsaas.com/ws?token=YOUR_TOKEN');

ws.onopen = () => {
  console.log('Connected to Atom SaaS WebSocket');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Received:', message.type, message.data);
};
```

---

### Message Format (Server → Client)

All messages follow this structure:

```json
{
  "type": "skill_update" | "category_update" | "rating_update" | "skill_delete",
  "data": { ... },
  "timestamp": "2026-02-19T10:30:00Z"
}
```

---

### Message Types

#### 1. Skill Update

**Type:** `skill_update`

**Data Structure:**

```json
{
  "skill_id": "uuid-v4",
  "name": "Send Email",
  "description": "Send emails via SMTP",
  "version": "1.0.1",
  "code": "def send_email(to, subject, body):\n    ...",
  "command": "python",
  "python_packages": ["smtplib"],
  "npm_packages": [],
  "tags": ["email", "automation"],
  "metadata": {},
  "category": "automation",
  "average_rating": 4.5,
  "rating_count": 42,
  "updated_at": "2026-02-19T10:30:00Z"
}
```

**Action:** Local Atom upserts skill to `SkillCache` table

---

#### 2. Category Update

**Type:** `category_update`

**Data Structure:**

```json
{
  "name": "automation",
  "description": "Automation and workflow skills",
  "skill_count": 150,
  "icon_url": "https://...",
  "updated_at": "2026-02-19T10:30:00Z"
}
```

**Action:** Local Atom upserts category to `CategoryCache` table

---

#### 3. Rating Update

**Type:** `rating_update`

**Data Structure:**

```json
{
  "skill_id": "uuid-v4",
  "rating": 5,
  "average_rating": 4.7,
  "rating_count": 43,
  "updated_at": "2026-02-19T10:30:00Z"
}
```

**Action:** Local Atom updates `SkillCache.skill_data` with new rating

---

#### 4. Skill Delete

**Type:** `skill_delete`

**Data Structure:**

```json
{
  "skill_id": "uuid-v4",
  "deleted_at": "2026-02-19T10:30:00Z"
}
```

**Action:** Local Atom deletes skill from `SkillCache` table

---

### Heartbeat Protocol

**Ping (Server → Client):**

```json
{
  "type": "ping",
  "timestamp": "2026-02-19T10:30:00Z"
}
```

**Pong (Client → Server):**

```json
{
  "type": "pong",
  "timestamp": "2026-02-19T10:30:00Z"
}
```

**Heartbeat Interval:** Every 30 seconds

**Pong Timeout:** 10 seconds (if no pong, connection considered stale)

---

### Reconnection Strategy

**Exponential Backoff:**

| Attempt | Delay | Max Delay |
| ------- | ----- | --------- |
| 1       | 1s    | 1s        |
| 2       | 2s    | 2s        |
| 3       | 4s    | 4s        |
| 4       | 8s    | 8s        |
| 5+      | 16s   | 16s       |

**Max Reconnection Attempts:** 10

**Fallback Mode:** After 3 consecutive WebSocket failures, switch to polling-only mode for 1 hour

---

### Rate Limiting (WebSocket)

| Metric                | Limit         |
| --------------------- | ------------- |
| Messages per second   | 100           |
| Message size          | 1MB max       |
| Connection duration   | No limit      |

**Action:** Drop messages exceeding limit, log warning

---

## Authentication

### API Token

**Format:** UUID v4 or JWT

**Example:**

```bash
# UUID v4 token
ATOM_SAAS_API_TOKEN=550e8400-e29b-41d4-a716-446655440000

# JWT token
ATOM_SAAS_API_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Token Source:** Environment variable `ATOM_SAAS_API_TOKEN`

**Token Rotation:** Support token refresh without service interruption (future enhancement)

---

### Token Generation (Atom SaaS Side)

**Endpoint:** `POST /api/v1/tokens` (Admin only)

**Request:**

```json
{
  "instance_id": "local-atom-instance-1",
  "description": "Production Atom instance"
}
```

**Response:**

```json
{
  "token": "uuid-v4",
  "instance_id": "local-atom-instance-1",
  "created_at": "2026-02-19T10:30:00Z",
  "expires_at": null
}
```

**Token Revocation:**

```bash
DELETE /api/v1/tokens/{token}
```

---

## Rate Limiting

### HTTP API

| Metric                  | Limit                     |
| ----------------------- | ------------------------- |
| Requests per minute     | 100 per Atom instance     |
| Concurrent connections  | 10 per Atom instance      |
| Request size            | 1MB max                   |

**Rate Limit Exceeded Response:**

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
Content-Type: application/json

{
  "error": "Rate limit exceeded",
  "retry_after": 60
}
```

---

### WebSocket

| Metric                | Limit         |
| --------------------- | ------------- |
| Messages per second   | 100           |
| Connection attempts   | 10 per minute |
| Message size          | 1MB max       |

**Action:** Drop messages, close connection if abuse detected

---

## Error Handling

### HTTP Error Codes

| Code | Description                  | Retry Strategy           |
| ---- | ---------------------------- | ------------------------ |
| 400  | Bad request                  | Fix request, retry       |
| 401  | Invalid/expired token        | Refresh token, retry     |
| 404  | Resource not found           | Verify ID, retry         |
| 429  | Rate limit exceeded          | Wait Retry-After, retry  |
| 500  | Internal server error        | Exponential backoff      |
| 503  | Maintenance mode             | Wait, retry later        |

**Retry Strategy (General):**

| Attempt | Delay | Max Retries |
| ------- | ----- | ----------- |
| 1       | 1s    | 3           |
| 2       | 2s    | -           |
| 3       | 4s    | -           |

---

### WebSocket Error Handling

**Automatic Actions:**

1. **Connection Lost:** Reconnect with exponential backoff
2. **Heartbeat Timeout (10s):** Close connection, reconnect
3. **Message Validation Failed:** Log warning, drop message
4. **Rate Limit Exceeded:** Drop messages, log warning
5. **Max Reconnect Attempts Reached:** Switch to polling mode

**Error States Tracked:**

- `connected`: Boolean
- `reconnect_attempts`: Integer
- `consecutive_failures`: Integer
- `last_disconnect_reason`: String

---

## Monitoring Requirements

### Health Check Endpoint

**Endpoint:** `GET /health`

**Purpose:** Kubernetes liveness/readiness probes

**Response:**

```json
{
  "status": "healthy" | "degraded" | "unhealthy",
  "timestamp": "2026-02-19T10:30:00Z",
  "checks": {
    "database": "healthy",
    "redis": "healthy",
    "api": "healthy"
  }
}
```

**Performance Targets:**

| Metric | Target  |
| ------ | ------- |
| P50    | <50ms   |
| P95    | <100ms  |
| P99    | <200ms  |

---

### Metrics Endpoint (Prometheus)

**Endpoint:** `GET /metrics`

**Format:** Prometheus text-based format

**Required Metrics:**

```
# API request duration histogram
atom_saas_api_request_duration_seconds{endpoint="/api/v1/skills",method="GET",status="200"} 0.123

# API request total counter
atom_saas_api_requests_total{endpoint="/api/v1/skills",method="GET",status="200"} 1234

# WebSocket connections gauge
atom_saas_websocket_connections_total 42

# WebSocket messages total
atom_saas_websocket_messages_total{type="skill_update",direction="incoming"} 5678

# Sync operations
atom_saas_sync_duration_seconds{instance_id="local-atom-1"} 5.43
atom_saas_sync_success_total{instance_id="local-atom-1"} 123
atom_saas_sync_errors_total{instance_id="local-atom-1",error_type="timeout"} 5
```

**Scrape Interval:** 15 seconds

**Retention:** 15 days

---

### Alerting Rules (Prometheus)

**Critical Alerts:**

```yaml
- alert: AtomSaaSHighErrorRate
  expr: rate(atom_saas_api_requests_total{status=~"5.."}[5m]) > 0.05
  for: 5m
  annotations:
    summary: "Atom SaaS error rate > 5%"

- alert: AtomSaaSWebsocketDisconnected
  expr: atom_saas_websocket_connections_total < 10
  for: 10m
  annotations:
    summary: "WebSocket connections dropped below 10"

- alert: AtomSaaSSyncStale
  expr: time() - atom_saas_sync_last_success_timestamp_seconds > 1800
  for: 10m
  annotations:
    summary: "Atom SaaS sync stale for > 30 minutes"
```

**Warning Alerts:**

```yaml
- alert: AtomSaaSHighLatency
  expr: histogram_quantile(0.95, atom_saas_api_request_duration_seconds) > 0.5
  for: 10m
  annotations:
    summary: "Atom SaaS P95 latency > 500ms"
```

---

## Environment Variables

### Required for Sync

```bash
# Atom SaaS API base URL
ATOM_SAAS_API_URL=https://api.atomsaas.com
  Description: Base URL for Atom SaaS API
  Required: Yes
  Default: None
  Example: https://api.atomsaas.com

# Atom SaaS API authentication token
ATOM_SAAS_API_TOKEN=your_token_here
  Description: API bearer token for authentication
  Required: Yes
  Default: None
  Security: Never log or commit this value
  Format: UUID v4 or JWT
```

---

### Optional Configuration

```bash
# Atom SaaS WebSocket URL
ATOM_SAAS_WS_URL=wss://api.atomsaas.com/ws
  Description: WebSocket URL for real-time updates
  Required: No (falls back to polling)
  Default: wss://api.atomsaas.com/ws
  Example: wss://api.atomsaas.com/ws

# Skill sync interval in minutes
ATOM_SAAS_SYNC_INTERVAL_MINUTES=15
  Description: Skill sync interval in minutes
  Required: No
  Default: 15
  Range: 5-60
  Example: 15

# Rating sync interval in minutes
ATOM_SAAS_RATING_SYNC_INTERVAL_MINUTES=30
  Description: Rating sync interval in minutes
  Required: No
  Default: 30
  Range: 10-120
  Example: 30

# WebSocket reconnection max attempts
ATOM_SAAS_WS_RECONNECT_ATTEMPTS=10
  Description: Max WebSocket reconnection attempts
  Required: No
  Default: 10
  Range: 1-100
  Example: 10

# Default conflict resolution strategy
ATOM_SAAS_CONFLICT_STRATEGY=remote_wins
  Description: Default conflict resolution strategy
  Required: No
  Default: remote_wins
  Options: remote_wins, local_wins, merge, manual
  Example: remote_wins

# WebSocket enabled flag
ATOM_SAAS_WS_ENABLED=true
  Description: Enable WebSocket real-time updates
  Required: No
  Default: true
  Options: true, false
  Example: true

# API request timeout in seconds
ATOM_SAAS_API_TIMEOUT_SECONDS=30
  Description: API request timeout in seconds
  Required: No
  Default: 30
  Range: 10-120
  Example: 30
```

---

### Local Marketplace Mode (No Sync)

```bash
# Disable Atom SaaS sync entirely
ATOM_SAAS_ENABLED=false
  Description: Disable Atom SaaS sync, use local marketplace only
  Required: No
  Default: true
  Options: true, false
  Example: false
```

**Behavior:**
- No API calls to Atom SaaS
- No WebSocket connection
- Only local skills available
- No rating sync

---

## Production Deployment Checklist

### Pre-Deployment

- [ ] **Atom SaaS Platform Deployed**
  - [ ] Atom SaaS API accessible at `ATOM_SAAS_API_URL`
  - [ ] WebSocket endpoint accessible at `ATOM_SAAS_WS_URL`
  - [ ] Health check endpoint responding: `GET /health`
  - [ ] Metrics endpoint accessible: `GET /metrics`

- [ ] **API Credentials Generated**
  - [ ] Generate `ATOM_SAAS_API_TOKEN` for each Atom instance
  - [ ] Store tokens securely (environment variables, secrets manager)
  - [ ] Document token rotation procedure
  - [ ] Test token authentication: `curl -H "Authorization: Bearer $TOKEN" https://api.atomsaas.com/health`

- [ ] **Environment Configuration**
  - [ ] Set `ATOM_SAAS_API_URL` to production URL
  - [ ] Set `ATOM_SAAS_API_TOKEN` (never commit to git)
  - [ ] Set `ATOM_SAAS_WS_URL` (if using WebSocket)
  - [ ] Configure sync intervals (15min skills, 30min ratings)
  - [ ] Set conflict resolution strategy (`remote_wins` recommended)

- [ ] **Network Configuration**
  - [ ] Allow outbound HTTPS to `api.atomsaas.com:443`
  - [ ] Allow outbound WSS to `api.atomsaas.com:443`
  - [ ] Configure firewall rules if needed
  - [ ] Test connectivity: `telnet api.atomsaas.com 443`

---

### Deployment Verification

- [ ] **API Endpoint Verification**
  ```bash
  # Test health check
  curl https://api.atomsaas.com/health

  # Test skills fetch
  curl -H "Authorization: Bearer $TOKEN" \
    "https://api.atomsaas.com/api/v1/skills?page=1&page_size=10"

  # Test categories fetch
  curl -H "Authorization: Bearer $TOKEN" \
    "https://api.atomsaas.com/api/v1/categories"
  ```

- [ ] **WebSocket Connection Verification**
  ```bash
  # Using websocat
  websocat "wss://api.atomsaas.com/ws?token=$TOKEN"

  # Using wscat
  wscat -c "wss://api.atomsaas.com/ws?token=$TOKEN"
  ```

  **Expected:** Connection established, heartbeat pings every 30s

- [ ] **Sync Verification**
  ```bash
  # Check SyncService is initialized
  curl http://localhost:8000/api/admin/sync/status

  # Trigger manual sync
  curl -X POST http://localhost:8000/api/admin/sync/trigger

  # Check SkillCache populated
  sqlite3 atom.db "SELECT COUNT(*) FROM skill_cache"
  ```

- [ ] **Health Check Verification**
  ```bash
  # Local Atom sync health
  curl http://localhost:8000/health/sync

  # Expected response
  {
    "status": "healthy",
    "last_sync_time": "2026-02-19T10:30:00Z",
    "websocket_connected": true,
    "scheduler_running": true
  }
  ```

---

### Post-Deployment

- [ ] **Monitoring Setup**
  - [ ] Configure Prometheus scrape of `/metrics`
  - [ ] Import Grafana dashboard (sync-dashboard.json)
  - [ ] Configure alerting rules (prometheus-alerts.yml)
  - [ ] Set up Slack/PagerDuty notifications for critical alerts

- [ ] **Log Aggregation**
  - [ ] Sync logs: `grep "sync" logs/atom.log`
  - [ ] WebSocket logs: `grep "websocket" logs/atom.log`
  - [ ] Error logs: `grep "ERROR" logs/atom.log | grep "saas"`

- [ ] **Performance Verification**
  - [ ] API response time P95 < 200ms
  - [ ] WebSocket heartbeat < 10s
  - [ ] Sync duration < 5s (100 skills)
  - [ ] Cache hit rate > 90%

- [ ] **Rollback Plan**
  - [ ] Disable sync: `ATOM_SAAS_ENABLED=false`
  - [ ] Restart Atom service
  - [ ] Verify local marketplace still works
  - [ ] Monitor error rates for 10 minutes

---

## Testing Procedures

### 1. API Connectivity Test

**Purpose:** Verify Atom SaaS API is accessible

**Command:**

```bash
curl -v -H "Authorization: Bearer $ATOM_SAAS_API_TOKEN" \
  "https://api.atomsaas.com/api/v1/skills?page=1&page_size=1"
```

**Expected Output:**

```json
{
  "skills": [...],
  "total": 1500,
  "page": 1
}
```

**Success Criteria:**
- HTTP 200 response
- JSON response with `skills` array
- Response time < 200ms

---

### 2. WebSocket Connection Test

**Purpose:** Verify WebSocket connection works

**Command (using websocat):**

```bash
websocat "wss://api.atomsaas.com/ws?token=$ATOM_SAAS_API_TOKEN"
```

**Expected Output:**

```json
{"type":"ping","timestamp":"2026-02-19T10:30:00Z"}
```

**Success Criteria:**
- Connection established
- Heartbeat pings every 30s
- No disconnections within 1 minute

---

### 3. Sync Verification Test

**Purpose:** Verify sync populates local cache

**Command:**

```bash
# Trigger manual sync
curl -X POST http://localhost:8000/api/admin/sync/trigger

# Wait 5 seconds
sleep 5

# Check cache
sqlite3 atom.db "SELECT COUNT(*) FROM skill_cache"
```

**Expected Output:**

```
1500
```

**Success Criteria:**
- Sync completes without errors
- SkillCache populated with skills
- CategoryCache populated with categories

---

### 4. Metrics Verification Test

**Purpose:** Verify Prometheus metrics are exposed

**Command:**

```bash
curl http://localhost:8000/metrics/sync
```

**Expected Output:**

```
atom_saas_sync_duration_seconds 5.43
atom_saas_sync_success_total 123
atom_saas_sync_errors_total{error_type="timeout"} 5
atom_saas_sync_skills_cached_total 1500
```

**Success Criteria:**
- All 12 metrics present
- Values are non-zero for active sync
- Labels are correct

---

## Fallback/Mock Options

### Local Marketplace Only Mode

**When to Use:** Atom SaaS platform not available, offline mode

**Configuration:**

```bash
ATOM_SAAS_ENABLED=false
```

**Behavior:**
- No API calls to Atom SaaS
- No WebSocket connection
- Only local skills available
- Skills must be manually imported

**Limitations:**
- No skill sync from marketplace
- No rating sync
- No real-time updates

---

### Mock Server (Development)

**When to Use:** Development/testing without Atom SaaS

**Tools:**
- WireMock (HTTP mocking)
- websockets-mock (WebSocket mocking)

**Example (WireMock):**

```python
from wiremock import WireMockServer

wm = WireMockServer(8080)
wm.start()

# Mock skills endpoint
wm.stub_for(
    wm.get(wm.url_path_equal_to("/api/v1/skills"))
    .with_header("Authorization", wm.containing("Bearer"))
    .will_return(
        wm.a_response()
        .with_status(200)
        .with_body('{"skills": [], "total": 0}')
    )
)
```

**Note:** Mock server is NOT production-equivalent. Use for development only.

---

### Docker Compose Mock (Local Testing)

**docker-compose.yml:**

```yaml
version: '3.8'
services:
  atom-saas-mock:
    image: wiremock/wiremock:latest
    ports:
      - "5058:8080"
    volumes:
      - ./mock/mappings:/home/wiremock/mappings
```

**mock/mappings/skills.json:**

```json
{
  "request": {
    "method": "GET",
    "urlPathPattern": "/api/v1/skills"
  },
  "response": {
    "status": 200,
    "jsonBody": {
      "skills": [],
      "total": 0,
      "page": 1
    }
  }
}
```

**Start:**

```bash
docker-compose up -d
export ATOM_SAAS_API_URL=http://localhost:5058
```

---

## Security Considerations

### API Token Security

- **Never log tokens** (sanitize in logs)
- **Never commit tokens** (use environment variables)
- **Rotate tokens regularly** (recommended: 90 days)
- **Revoke compromised tokens immediately**
- **Use HTTPS only** (never HTTP)

### Data Privacy

- **User IDs in ratings:** Use hashed IDs, not emails
- **Skill code:** May contain sensitive logic, encrypt at rest
- **Audit trail:** Log all sync operations with timestamps
- **GDPR compliance:** Support data export/deletion requests

### Network Security

- **TLS 1.3 only** for API and WebSocket
- **Certificate pinning** (recommended for production)
- **IP whitelisting** (optional, restrict access)
- **Rate limiting** per Atom instance (100 req/min)

---

## Performance Targets

### API Performance

| Metric                     | Target  |
| -------------------------- | ------- |
| Skill fetch latency (P50)  | <100ms  |
| Skill fetch latency (P95)  | <200ms  |
| Skill fetch latency (P99)  | <500ms  |
| Category fetch latency     | <100ms  |
| Rating submit latency      | <200ms  |

### WebSocket Performance

| Metric                     | Target  |
| -------------------------- | ------- |
| Connection establishment   | <1s     |
| Message delivery latency   | <100ms  |
| Heartbeat round-trip       | <1s     |
| Reconnection time          | <5s     |

### Sync Performance

| Metric                     | Target  |
| -------------------------- | ------- |
| Full sync duration (1k skills) | <30s  |
| Incremental sync duration  | <5s     |
| Cache write latency        | <10ms   |
| Cache read latency         | <1ms    |

---

## Troubleshooting

### Common Issues

#### 1. "Invalid API Token"

**Symptom:** HTTP 401 on all API requests

**Diagnosis:**

```bash
curl -v -H "Authorization: Bearer $TOKEN" https://api.atomsaas.com/health
```

**Solutions:**
- Verify token is set: `echo $ATOM_SAAS_API_TOKEN`
- Check token format (UUID v4 or JWT)
- Generate new token from Atom SaaS admin panel
- Verify token hasn't expired

---

#### 2. "WebSocket Connection Failed"

**Symptom:** WebSocket won't connect

**Diagnosis:**

```bash
websocat -v "wss://api.atomsaas.com/ws?token=$TOKEN"
```

**Solutions:**
- Check firewall allows WSS on port 443
- Verify WebSocket URL is correct
- Check proxy settings (if behind corporate proxy)
- Test with HTTP polling mode (disable WebSocket)

---

#### 3. "Sync Not Running"

**Symptom:** Skills not updating in local cache

**Diagnosis:**

```bash
# Check sync status
curl http://localhost:8000/api/admin/sync/status

# Check logs
tail -f logs/atom.log | grep sync
```

**Solutions:**
- Verify Atom SaaS is reachable: `curl https://api.atomsaas.com/health`
- Check sync interval: `echo $ATOM_SAAS_SYNC_INTERVAL_MINUTES`
- Trigger manual sync: `curl -X POST http://localhost:8000/api/admin/sync/trigger`
- Check scheduler is running: `ps aux | grep scheduler`

---

#### 4. "High Sync Error Rate"

**Symptom:** Many sync failures in logs

**Diagnosis:**

```bash
# Check metrics
curl http://localhost:8000/metrics/sync | grep errors

# Check recent errors
curl http://localhost:8000/api/admin/sync/errors?limit=10
```

**Solutions:**
- Check Atom SaaS API health
- Verify network connectivity
- Check rate limit headers (Retry-After)
- Reduce sync frequency temporarily
- Switch to local marketplace mode if needed

---

## Environment Variable Examples

### Production Configuration

```bash
# Atom SaaS Configuration - Production
ATOM_SAAS_ENABLED=true
ATOM_SAAS_API_URL=https://api.atomsaas.com
ATOM_SAAS_API_TOKEN=prod_token_here_from_secrets_manager
ATOM_SAAS_WS_URL=wss://api.atomsaas.com/ws
ATOM_SAAS_SYNC_INTERVAL_MINUTES=15
ATOM_SAAS_RATING_SYNC_INTERVAL_MINUTES=30
ATOM_SAAS_WS_RECONNECT_ATTEMPTS=10
ATOM_SAAS_CONFLICT_STRATEGY=remote_wins
ATOM_SAAS_WS_ENABLED=true
ATOM_SAAS_API_TIMEOUT_SECONDS=30
```

### Development Configuration

```bash
# Atom SaaS Configuration - Development
ATOM_SAAS_ENABLED=true
ATOM_SAAS_API_URL=http://localhost:5058/api
ATOM_SAAS_API_TOKEN=dev_token_12345
ATOM_SAAS_WS_URL=ws://localhost:5058/api/ws/satellite/connect
ATOM_SAAS_SYNC_INTERVAL_MINUTES=5
ATOM_SAAS_RATING_SYNC_INTERVAL_MINUTES=10
ATOM_SAAS_WS_RECONNECT_ATTEMPTS=5
ATOM_SAAS_CONFLICT_STRATEGY=local_wins
ATOM_SAAS_WS_ENABLED=true
ATOM_SAAS_API_TIMEOUT_SECONDS=10
```

### Testing/Mock Configuration

```bash
# Atom SaaS Configuration - Testing with Mock Server
ATOM_SAAS_ENABLED=true
ATOM_SAAS_API_URL=http://localhost:8080
ATOM_SAAS_API_TOKEN=test_token_67890
ATOM_SAAS_WS_URL=ws://localhost:8080/ws
ATOM_SAAS_SYNC_INTERVAL_MINUTES=1
ATOM_SAAS_RATING_SYNC_INTERVAL_MINUTES=2
ATOM_SAAS_WS_RECONNECT_ATTEMPTS=3
ATOM_SAAS_CONFLICT_STRATEGY=manual
ATOM_SAAS_WS_ENABLED=false  # Disable WebSocket for tests
ATOM_SAAS_API_TIMEOUT_SECONDS=5
```

### Local Marketplace Only (No Sync)

```bash
# Atom SaaS Configuration - Local Marketplace Only
ATOM_SAAS_ENABLED=false
# All other ATOM_SAAS_* variables are ignored when enabled=false
```

---

## Environment Variable Validation

### Startup Validation

Atom validates environment variables at startup:

```python
# Required when ATOM_SAAS_ENABLED=true
if ATOM_SAAS_ENABLED:
    assert ATOM_SAAS_API_URL, "ATOM_SAAS_API_URL required when sync enabled"
    assert ATOM_SAAS_API_TOKEN, "ATOM_SAAS_API_TOKEN required when sync enabled"

# Range validation
assert 5 <= ATOM_SAAS_SYNC_INTERVAL_MINUTES <= 60, "Sync interval must be 5-60 minutes"
assert 10 <= ATOM_SAAS_RATING_SYNC_INTERVAL_MINUTES <= 120, "Rating sync interval must be 10-120 minutes"
assert 1 <= ATOM_SAAS_WS_RECONNECT_ATTEMPTS <= 100, "Reconnect attempts must be 1-100"

# Enum validation
assert ATOM_SAAS_CONFLICT_STRATEGY in ["remote_wins", "local_wins", "merge", "manual"]
```

**Startup Failure:** If validation fails, Atom logs error and exits with status code 1

---

## Environment Variable precedence

### Configuration Precedence (Highest to Lowest)

1. **Environment Variables** (runtime configuration)
2. **.env file** (local development)
3. **Default values** (hardcoded in code)

### Example Override Behavior

```bash
# .env file
ATOM_SAAS_SYNC_INTERVAL_MINUTES=15

# Environment variable (takes precedence)
export ATOM_SAAS_SYNC_INTERVAL_MINUTES=30

# Result: Sync interval is 30 minutes
```

---

## Secrets Management

### Production Secrets Storage

**Recommended Approaches:**

1. **AWS Secrets Manager:**
   ```bash
   aws secretsmanager get-secret-value --secret-id atom/saas/api-token
   ```

2. **HashiCorp Vault:**
   ```bash
   vault kv get -field=api_token secret/atom/saas
   ```

3. **Kubernetes Secrets:**
   ```yaml
   apiVersion: v1
   kind: Secret
   metadata:
     name: atom-saas-token
   type: Opaque
   data:
     api-token: <base64-encoded-token>
   ```

4. **Docker Secrets:**
   ```bash
   echo "your_token_here" | docker secret create atom_saas_api_token -
   ```

**Never:**
- Commit secrets to git
- Log secrets in application logs
- Pass secrets via CLI arguments (visible in ps aux)
- Store secrets in config files

---

## Appendix A: Complete .env.example File

```bash
# =============================================================================
# Atom SaaS Configuration
# =============================================================================

# Enable/disable Atom SaaS sync
# When false: Local marketplace only, no API calls, no WebSocket
ATOM_SAAS_ENABLED=true

# -----------------------------------------------------------------------------
# Required Configuration (when ATOM_SAAS_ENABLED=true)
# -----------------------------------------------------------------------------

# Atom SaaS API base URL
# Format: https://api.atomsaas.com (production) or http://localhost:5058 (dev)
ATOM_SAAS_API_URL=https://api.atomsaas.com

# Atom SaaS API authentication token
# Format: UUID v4 (e.g., 550e8400-e29b-41d4-a716-446655440000) or JWT
# Security: Never commit to git, use secrets manager in production
ATOM_SAAS_API_TOKEN=your_token_here

# -----------------------------------------------------------------------------
# Optional Configuration
# -----------------------------------------------------------------------------

# Atom SaaS WebSocket URL for real-time updates
# Format: wss://api.atomsaas.com/ws (production) or ws://localhost:5058/ws (dev)
# Default: Derived from ATOM_SAAS_API_URL if not set
ATOM_SAAS_WS_URL=wss://api.atomsaas.com/ws

# Skill sync interval in minutes
# Default: 15
# Range: 5-60
# Recommended: 15 for production, 5 for development
ATOM_SAAS_SYNC_INTERVAL_MINUTES=15

# Rating sync interval in minutes
# Default: 30
# Range: 10-120
# Recommended: 30 for production, 10 for development
ATOM_SAAS_RATING_SYNC_INTERVAL_MINUTES=30

# WebSocket reconnection max attempts
# Default: 10
# Range: 1-100
# Recommended: 10 for production, 5 for development
ATOM_SAAS_WS_RECONNECT_ATTEMPTS=10

# Default conflict resolution strategy
# Default: remote_wins
# Options:
#   - remote_wins: Atom SaaS data overwrites local (recommended)
#   - local_wins: Local data overwrites Atom SaaS
#   - merge: Merge fields (description/tags merge, code stays local)
#   - manual: Require admin intervention for all conflicts
ATOM_SAAS_CONFLICT_STRATEGY=remote_wins

# Enable WebSocket real-time updates
# Default: true
# Options: true, false
# When false: Polling mode only (every ATOM_SAAS_SYNC_INTERVAL_MINUTES)
ATOM_SAAS_WS_ENABLED=true

# API request timeout in seconds
# Default: 30
# Range: 10-120
# Recommended: 30 for production, 10 for development
ATOM_SAAS_API_TIMEOUT_SECONDS=30

# -----------------------------------------------------------------------------
# Local Marketplace Only Mode (fallback)
# -----------------------------------------------------------------------------
# To disable Atom SaaS sync and use local marketplace only:
# 1. Set ATOM_SAAS_ENABLED=false
# 2. All other ATOM_SAAS_* variables are ignored
# 3. Only skills in CommunitySkill table are available
# 4. Skills must be manually imported via API

# ATOM_SAAS_ENABLED=false

# -----------------------------------------------------------------------------
# Development Examples
# -----------------------------------------------------------------------------

# Development with local Atom SaaS mock server:
# ATOM_SAAS_API_URL=http://localhost:5058/api
# ATOM_SAAS_WS_URL=ws://localhost:5058/api/ws/satellite/connect
# ATOM_SAAS_SYNC_INTERVAL_MINUTES=5
# ATOM_SAAS_RATING_SYNC_INTERVAL_MINUTES=10
# ATOM_SAAS_API_TIMEOUT_SECONDS=10

# Testing with WireMock:
# ATOM_SAAS_API_URL=http://localhost:8080
# ATOM_SAAS_WS_ENABLED=false
# ATOM_SAAS_SYNC_INTERVAL_MINUTES=1
# ATOM_SAAS_API_TIMEOUT_SECONDS=5

# Local marketplace only (offline mode):
# ATOM_SAAS_ENABLED=false
```

---

## Appendix B: API Response Examples

### Full Skill Sync Flow

**1. Fetch Skills (Page 1):**

```http
GET /api/v1/skills?page=1&page_size=100 HTTP/1.1
Host: api.atomsaas.com
Authorization: Bearer TOKEN
```

**Response:**

```json
{
  "skills": [
    {
      "skill_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Send Email",
      "description": "Send emails via SMTP",
      "version": "1.0.0",
      "code": "def send_email(to, subject, body):\n    import smtplib\n    ...",
      "command": "python",
      "python_packages": [],
      "npm_packages": [],
      "tags": ["email", "automation"],
      "metadata": {},
      "category": "automation",
      "average_rating": 4.5,
      "rating_count": 42,
      "created_at": "2026-01-01T00:00:00Z",
      "updated_at": "2026-01-15T10:30:00Z"
    }
  ],
  "page": 1,
  "page_size": 100,
  "total": 1500,
  "total_pages": 15
}
```

**2. Fetch Categories:**

```http
GET /api/v1/categories HTTP/1.1
Host: api.atomsaas.com
Authorization: Bearer TOKEN
```

**Response:**

```json
{
  "categories": [
    {
      "name": "automation",
      "description": "Automation and workflow skills",
      "skill_count": 150,
      "icon_url": "https://atomsaas.com/icons/automation.png",
      "created_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

**3. Submit Rating:**

```http
POST /api/v1/ratings HTTP/1.1
Host: api.atomsaas.com
Authorization: Bearer TOKEN
Content-Type: application/json

{
  "skill_id": "550e8400-e29b-41d4-a716-446655440000",
  "rating": 5,
  "comment": "Great skill!",
  "user_id": "user@example.com"
}
```

**Response:**

```json
{
  "success": true,
  "rating_id": "550e8400-e29b-41d4-a716-446655440001",
  "skill_id": "550e8400-e29b-41d4-a716-446655440000",
  "rating": 5,
  "average_rating": 4.7,
  "rating_count": 43,
  "created_at": "2026-02-19T10:30:00Z"
}
```

---

## Appendix C: WebSocket Message Examples

### Skill Update Message

```json
{
  "type": "skill_update",
  "data": {
    "skill_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Send Email",
    "description": "Send emails via SMTP",
    "version": "1.0.1",
    "code": "def send_email(to, subject, body):\n    ...",
    "command": "python",
    "python_packages": [],
    "npm_packages": [],
    "tags": ["email", "automation"],
    "metadata": {},
    "category": "automation",
    "average_rating": 4.5,
    "rating_count": 42,
    "updated_at": "2026-02-19T10:30:00Z"
  },
  "timestamp": "2026-02-19T10:30:00Z"
}
```

### Heartbeat Ping

```json
{
  "type": "ping",
  "timestamp": "2026-02-19T10:30:00Z"
}
```

### Heartbeat Pong

```json
{
  "type": "pong",
  "timestamp": "2026-02-19T10:30:00Z"
}
```

---

## Document Revision History

| Version | Date        | Author         | Changes                         |
| ------- | ----------- | -------------- | ------------------------------- |
| 1.0.0   | 2026-02-19  | Atom Team      | Initial requirements document   |

---

**Next Steps:**

1. Deploy Atom SaaS platform with these endpoints
2. Generate API tokens for each Atom instance
3. Configure environment variables in local Atom
4. Run verification tests (API, WebSocket, sync)
5. Monitor metrics and logs for issues

**Contact:** For questions about Atom SaaS platform requirements, contact the Atom Team.

---

*End of Document*
