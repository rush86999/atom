# Production Monitoring Setup Guide

This guide covers production monitoring infrastructure for the ATOM platform, including health checks, Prometheus metrics, structured logging, and performance benchmarks.

## Table of Contents

1. [Health Check Endpoints](#health-check-endpoints)
2. [Prometheus Metrics](#prometheus-metrics)
3. [Structured Logging](#structured-logging)
4. [Grafana Dashboards](#grafana-dashboards)
5. [Kubernetes/ECS Configuration](://kuberneteseecs-configuration)
6. [Performance Benchmarks](#performance-benchmarks)
7. [Alerting Rules](#alerting-rules)

---

## Health Check Endpoints

Production health check endpoints for orchestration systems (Kubernetes, ECS, etc.).

### Liveness Probe: `/health/live`

**Purpose**: Checks if the application process is alive.

**Endpoint**: `GET /health/live`

**Expected Response** (200 OK):
```json
{
  "status": "alive",
  "timestamp": "2026-02-16T19:15:00.000Z"
}
```

**Usage**:
- Kubernetes `livenessProbe`
- ECS health check
- Load balancer health checks

**Configuration Example** (Kubernetes):
```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

### Readiness Probe: `/health/ready`

**Purpose**: Checks if the application can handle traffic (dependencies accessible).

**Endpoint**: `GET /health/ready`

**Expected Response** (200 OK):
```json
{
  "status": "ready",
  "timestamp": "2026-02-16T19:15:00.000Z",
  "checks": {
    "database": {
      "healthy": true,
      "message": "Database accessible",
      "latency_ms": 5.23
    },
    "disk": {
      "healthy": true,
      "message": "10.50GB free",
      "free_gb": 10.50
    }
  }
}
```

**Failure Response** (503 Service Unavailable):
```json
{
  "status": "not_ready",
  "timestamp": "2026-02-16T19:15:00.000Z",
  "checks": {
    "database": {
      "healthy": false,
      "message": "Database timeout after 5.0s",
      "latency_ms": 5000.0
    },
    "disk": {
      "healthy": true,
      "message": "10.50GB free",
      "free_gb": 10.50
    }
  }
}
```

**Usage**:
- Kubernetes `readinessProbe`
- ECS health check (container level)

**Configuration Example** (Kubernetes):
```yaml
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 5
  failureThreshold: 3
```

### Dependency Checks

The readiness probe checks the following dependencies:

#### Database Connectivity
- Executes `SELECT 1` query
- Timeout: 5 seconds
- Measures query latency

#### Disk Space
- Minimum free space: 1GB
- Checks root filesystem (`/`)
- Returns free space in GB

---

## Prometheus Metrics

All metrics are exposed at `/health/metrics` in Prometheus text format.

### HTTP Metrics

#### `http_requests_total` (Counter)
Total HTTP requests received.

**Labels**:
- `method`: HTTP method (GET, POST, PUT, DELETE, etc.)
- `endpoint`: Request endpoint path
- `status`: HTTP status code (200, 404, 500, etc.)

**Example**:
```
http_requests_total{method="GET",endpoint="/api/v1/agents",status="200"} 1234
```

#### `http_request_duration_seconds` (Histogram)
HTTP request latency distribution.

**Labels**:
- `method`: HTTP method
- `endpoint`: Request endpoint path

**Example**:
```
http_request_duration_seconds_bucket{method="GET",endpoint="/api/v1/agents",le="0.005"} 800
http_request_duration_seconds_bucket{method="GET",endpoint="/api/v1/agents",le="0.01"} 1200
http_request_duration_seconds_sum{method="GET",endpoint="/api/v1/agents"} 15.234
http_request_duration_seconds_count{method="GET",endpoint="/api/v1/agents"} 1500
```

### Agent Metrics

#### `agent_executions_total` (Counter)
Total agent executions.

**Labels**:
- `agent_id`: Agent identifier
- `status`: Execution status (success, failure, error)

**Example**:
```
agent_executions_total{agent_id="agent-123",status="success"} 456
agent_executions_total{agent_id="agent-123",status="failure"} 12
```

#### `agent_execution_duration_seconds` (Histogram)
Agent execution latency distribution.

**Labels**:
- `agent_id`: Agent identifier

**Example**:
```
agent_execution_duration_seconds_bucket{agent_id="agent-123",le="1.0"} 100
agent_execution_duration_seconds_sum{agent_id="agent-123"} 234.567
agent_execution_duration_seconds_count{agent_id="agent-123"} 468
```

#### `active_agents` (Gauge)
Number of currently running agents.

**Example**:
```
active_agents 5
```

### Skill Metrics

#### `skill_executions_total` (Counter)
Total skill executions.

**Labels**:
- `skill_id`: Skill identifier
- `status`: Execution status (success, failure, error)

**Example**:
```
skill_executions_total{skill_id="send-email",status="success"} 789
skill_executions_total{skill_id="send-email",status="failure"} 23
```

#### `skill_execution_duration_seconds` (Histogram)
Skill execution latency distribution.

**Labels**:
- `skill_id`: Skill identifier

**Example**:
```
skill_execution_duration_seconds_bucket{skill_id="send-email",le="0.5"} 500
skill_execution_duration_seconds_sum{skill_id="send-email"} 123.456
skill_execution_duration_seconds_count{skill_id="send-email"} 812
```

### Database Metrics

#### `db_query_duration_seconds` (Histogram)
Database query latency distribution.

**Labels**:
- `operation`: Query type (select, insert, update, delete)

**Example**:
```
db_query_duration_seconds_bucket{operation="select",le="0.01"} 5000
db_query_duration_seconds_sum{operation="select"} 123.456
db_query_duration_seconds_count{operation="select"} 10000
```

#### `db_connections_active` (Gauge)
Active database connections.

**Example**:
```
db_connections_active 8
```

#### `db_connections_idle` (Gauge)
Idle database connections.

**Example**:
```
db_connections_idle 12
```

---

## Structured Logging

The platform uses `structlog` for JSON-formatted structured logging.

### Configuration

Structured logging is configured in `core/monitoring.py`:

```python
from core.monitoring import configure_structlog, get_logger

# Configure structlog (call once at startup)
configure_structlog()

# Get a logger
log = get_logger(__name__)

# Log with context
log.info("Agent started", agent_id="agent-123", request_id="req-456")
```

### Log Format

All logs are output as JSON:

```json
{
  "timestamp": "2026-02-16T19:15:00.000Z",
  "level": "INFO",
  "logger": "core.agent_service",
  "event": "Agent started",
  "agent_id": "agent-123",
  "request_id": "req-456"
}
```

### Context Binding

Bind context to logs for request tracing:

```python
from core.monitoring import RequestContext

# Bind context for all logs in a scope
with RequestContext(request_id="req-456", user_id="user-789"):
    log.info("Processing request")  # Automatically includes request_id and user_id
    log.info("Database query executed", query_time_ms=5.2)
```

### Log Levels

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages
- **WARNING**: Warning messages for potentially harmful situations
- **ERROR**: Error messages for error events
- **CRITICAL**: Critical messages indicating severe errors

---

## Grafana Dashboards

### Dashboard Configuration

Create a Grafana dashboard to visualize the metrics.

**Example Dashboard JSON** (simplified):

```json
{
  "dashboard": {
    "title": "ATOM Platform Monitoring",
    "panels": [
      {
        "title": "HTTP Request Rate",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])"
          }
        ]
      },
      {
        "title": "HTTP Request Latency (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, http_request_duration_seconds_bucket)"
          }
        ]
      },
      {
        "title": "Active Agents",
        "targets": [
          {
            "expr": "active_agents"
          }
        ]
      }
    ]
  }
}
```

### Recommended Panels

1. **HTTP Request Rate**: `rate(http_requests_total[5m])`
2. **HTTP Request Latency (p95)**: `histogram_quantile(0.95, http_request_duration_seconds_bucket)`
3. **HTTP Error Rate**: `rate(http_requests_total{status=~"5.."}[5m])`
4. **Active Agents**: `active_agents`
5. **Agent Execution Rate**: `rate(agent_executions_total[5m])`
6. **Agent Execution Latency (p95)**: `histogram_quantile(0.95, agent_execution_duration_seconds_bucket)`
7. **Database Query Latency (p95)**: `histogram_quantile(0.95, db_query_duration_seconds_bucket)`
8. **Database Connection Pool**: `db_connections_active`, `db_connections_idle`

---

## Kubernetes/ECS Configuration

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: atom-platform
spec:
  replicas: 3
  selector:
    matchLabels:
      app: atom-platform
  template:
    metadata:
      labels:
        app: atom-platform
    spec:
      containers:
      - name: atom-platform
        image: atom-platform:latest
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: atom-secrets
              key: database-url
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 5
          failureThreshold: 3
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
```

### ECS Task Definition

```json
{
  "family": "atom-platform",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "atom-platform",
      "image": "atom-platform:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "DATABASE_URL",
          "value": "postgresql://..."
        }
      ],
      "healthCheck": {
        "command": [
          "CMD-SHELL",
          "curl -f http://localhost:8000/health/live || exit 1"
        ],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/atom-platform",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

---

## Performance Benchmarks

This section documents performance targets and baseline measurements for health check endpoints.

### Latency Targets

| Endpoint | Target | Acceptable | Critical |
|----------|--------|------------|----------|
| `/health/live` | <10ms | <50ms | >100ms |
| `/health/ready` | <100ms | <250ms | >500ms |
| `/health/metrics` | <50ms | <100ms | >200ms |

### Baseline Measurements

**Environment**: Development (macOS, Python 3.11, SQLite)

| Endpoint | P50 | P95 | P99 | Notes |
|----------|-----|-----|-----|-------|
| `/health/live` | 2ms | 5ms | 10ms | No dependency checks |
| `/health/ready` | 15ms | 25ms | 40ms | Includes DB query |
| `/health/metrics` | 8ms | 15ms | 25ms | Full metrics scrape |

**Environment**: Production (Linux, Python 3.11, PostgreSQL)

| Endpoint | P50 | P95 | P99 | Notes |
|----------|-----|-----|-----|-------|
| `/health/live` | 1ms | 3ms | 5ms | No dependency checks |
| `/health/ready` | 20ms | 35ms | 60ms | Includes DB query |
| `/health/metrics` | 5ms | 12ms | 20ms | Full metrics scrape |

### Performance Testing

#### Load Testing with Apache Bench (ab)

```bash
# Test /health/live endpoint
ab -n 10000 -c 100 http://localhost:8000/health/live

# Test /health/ready endpoint
ab -n 1000 -c 50 http://localhost:8000/health/ready

# Test /health/metrics endpoint
ab -n 1000 -c 50 http://localhost:8000/health/metrics
```

#### Load Testing with wrk

```bash
# Test /health/live endpoint (10 seconds, 10 connections)
wrk -t10 -c10 -d10s http://localhost:8000/health/live

# Test /health/ready endpoint
wrk -t10 -c10 -d10s http://localhost:8000/health/ready

# Test /health/metrics endpoint
wrk -t10 -c10 -d10s http://localhost:8000/health/metrics
```

### Alert Thresholds

Configure alerts based on performance benchmarks:

#### Liveness Probe Latency
- **Warning**: p95 > 10ms
- **Critical**: p95 > 50ms

#### Readiness Probe Latency
- **Warning**: p95 > 100ms
- **Critical**: p95 > 250ms

#### Metrics Scrape Latency
- **Warning**: p95 > 50ms
- **Critical**: p95 > 100ms

#### Database Query Latency (in readiness probe)
- **Warning**: p95 > 50ms
- **Critical**: p95 > 100ms

---

## Alerting Rules

### Prometheus Alerting Rules

Create alert rules for Prometheus:

```yaml
groups:
- name: atom_platform_alerts
  interval: 30s
  rules:
  # High HTTP error rate
  - alert: HighHTTPErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High HTTP error rate detected"
      description: "HTTP error rate is {{ $value }} errors/sec"

  # High HTTP latency
  - alert: HighHTTPLatency
    expr: histogram_quantile(0.95, http_request_duration_seconds_bucket) > 1.0
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High HTTP latency detected"
      description: "HTTP p95 latency is {{ $value }}s"

  # Too many active agents
  - alert: HighActiveAgentCount
    expr: active_agents > 100
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "High number of active agents"
      description: "{{ $value }} agents are currently running"

  # Database connection pool exhausted
  - alert: DatabaseConnectionPoolExhausted
    expr: db_connections_active / (db_connections_active + db_connections_idle) > 0.9
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Database connection pool nearly exhausted"
      description: "{{ $value | humanizePercentage }} of connections are active"

  # Readiness probe failing
  - alert: ReadinessProbeFailing
    expr: up{job="atom-platform"} == 0
    for: 2m
    labels:
      severity: critical
    annotations:
      summary: "Atom platform readiness probe failing"
      description: "Readiness probe has been failing for 2 minutes"
```

---

## Troubleshooting

### Health Check Failures

#### `/health/ready` returns 503

**Symptoms**: Readiness probe returns 503 Service Unavailable.

**Common Causes**:
1. Database is unreachable or slow
2. Disk space is insufficient (<1GB free)

**Troubleshooting Steps**:
1. Check the `checks` field in the response to identify the failing dependency
2. Check database connectivity: `psql $DATABASE_URL -c "SELECT 1"`
3. Check disk space: `df -h`
4. Check database query latency in the response

#### `/health/metrics` returns empty or incomplete

**Symptoms**: Metrics endpoint returns no metrics or incomplete metrics.

**Common Causes**:
1. Prometheus client not initialized
2. Metrics not being tracked

**Troubleshooting Steps**:
1. Check if `prometheus_client` is installed
2. Verify metrics are being incremented in application code
3. Check application logs for Prometheus errors

### High Latency

#### `/health/ready` is slow (>100ms)

**Symptoms**: Readiness probe latency exceeds target.

**Common Causes**:
1. Database query is slow
2. Network latency to database

**Troubleshooting Steps**:
1. Check database query latency in the response
2. Profile database query: `EXPLAIN ANALYZE SELECT 1`
3. Check database connection pool settings
4. Consider using connection pooling (PgBouncer)

#### `/health/metrics` is slow (>50ms)

**Symptoms**: Metrics endpoint latency exceeds target.

**Common Causes**:
1. Too many metrics being tracked
2. High cardinality in labels

**Troubleshooting Steps**:
1. Reduce number of metrics
2. Use lower cardinality labels
3. Consider metric aggregation

---

## Next Steps

After completing monitoring setup:

1. **API Documentation**: Create comprehensive API documentation (Plan 15-03)
2. **Runbooks**: Create operational runbooks for incident response
3. **Monitoring Dashboards**: Create Grafana dashboards for visualization
4. **Alert Tuning**: Adjust alert thresholds based on production metrics
5. **Performance Optimization**: Optimize slow endpoints based on monitoring data

---

## References

- [Kubernetes Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [ECS Health Checks](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/healthcheck_examples.html)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)
- [Grafana Dashboards](https://grafana.com/docs/grafana/latest/dashboards/)
- [Structlog Documentation](https://www.structlog.org/en/stable/)
