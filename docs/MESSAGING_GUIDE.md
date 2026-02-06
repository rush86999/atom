# ATOM Messaging Features Guide

Complete guide to ATOM's advanced messaging capabilities.

**Last Updated**: February 4, 2026

---

## Overview

ATOM provides three powerful messaging features:

1. **Proactive Messaging** - Agents can initiate conversations
2. **Scheduled Messaging** - One-time and recurring messages
3. **Condition Monitoring** - Real-time alerts based on business conditions

All features include:
- ✅ 4-tier governance integration
- ✅ Multi-platform support (9 platforms)
- ✅ Template variables
- ✅ Audit trails
- ✅ Performance optimization (<1ms checks)

---

## 1. Proactive Messaging

### Overview

Proactive messaging allows AI agents to **initiate conversations** with users on supported messaging platforms. This differs from reactive messaging, where agents only respond to incoming messages.

### Governance by Maturity Level

| Level | Permission | Behavior |
|-------|-----------|----------|
| **STUDENT** | ❌ Blocked | Cannot send proactive messages (returns 403) |
| **INTERN** | 🟡 Approval Required | Messages enter PENDING queue, require human approval |
| **SUPERVISED** | 🟢 Auto-Approved | Sent automatically with monitoring/audit trail |
| **AUTONOMOUS** | 🟢 Full Access | Sent immediately with background audit |

### API Endpoints

#### Send Proactive Message
```http
POST /api/v1/messaging/proactive/send
Content-Type: application/json

{
  "agent_id": "agent_123",
  "platform": "slack",
  "recipient_id": "C12345",
  "content": "Hello! I have important updates.",
  "send_now": true,
  "governance_metadata": {
    "confidence": 0.95,
    "context": "daily report"
  }
}
```

**Response**:
```json
{
  "id": "msg_abc123",
  "agent_id": "agent_123",
  "platform": "slack",
  "recipient_id": "C12345",
  "content": "Hello! I have important updates.",
  "status": "approved",
  "sent_at": "2026-02-04T10:30:00Z"
}
```

#### Schedule Proactive Message
```http
POST /api/v1/messaging/proactive/schedule
Content-Type: application/json

{
  "agent_id": "agent_123",
  "platform": "whatsapp",
  "recipient_id": "15551234567",
  "content": "Reminder: Meeting at 2pm",
  "scheduled_for": "2026-02-04T14:00:00Z"
}
```

#### Approve Pending Message (INTERN agents)
```http
POST /api/v1/messaging/proactive/approve/{message_id}
Content-Type: application/json

{
  "approver_user_id": "user_456"
}
```

#### Get Pending Queue
```http
GET /api/v1/messaging/proactive/queue?agent_id=agent_123&limit=100
```

#### Get Message History
```http
GET /api/v1/messaging/proactive/history?status=sent&limit=100
```

### Use Cases

1. **Daily Reports**: Send automated daily summaries
2. **Alerts**: Notify users of important events
3. **Follow-ups**: Check in after meetings or tasks
4. **Reminders**: Appointment or deadline reminders
5. **Proactive Support**: Reach out before issues escalate

### Database Schema

```sql
CREATE TABLE proactive_messages (
  id UUID PRIMARY KEY,
  agent_id VARCHAR NOT NULL,
  agent_maturity_level VARCHAR NOT NULL,
  platform VARCHAR NOT NULL,
  recipient_id VARCHAR NOT NULL,
  content TEXT NOT NULL,
  scheduled_for TIMESTAMP,
  status VARCHAR DEFAULT 'pending',
  approved_by VARCHAR,
  sent_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);
```

### Performance

- **Governance Check**: <1ms (cached)
- **Message Delivery**: <100ms (p99)
- **Queue Processing**: 1000 messages/minute

---

## 2. Scheduled Messaging

### Overview

Scheduled messaging allows **one-time and recurring messages** with support for:

- Cron expressions (`0 9 * * *` = daily at 9am)
- Natural language parsing ("every day at 9am")
- Template variables (`{{date}}`, `{{time}}`, custom)
- Timezone support
- Pause/resume controls

### API Endpoints

#### Create Scheduled Message
```http
POST /api/v1/messaging/schedule/create
Content-Type: application/json

{
  "agent_id": "agent_123",
  "platform": "telegram",
  "recipient_id": "123456789",
  "template": "Daily report for {{date}}: {{summary}}",
  "schedule_type": "recurring",
  "cron_expression": "0 9 * * *",
  "timezone": "America/New_York",
  "template_variables": {
    "summary": "Sales: $10k, Tasks: 5 completed"
  }
}
```

#### Create with Natural Language
```http
POST /api/v1/messaging/schedule/create
Content-Type: application/json

{
  "agent_id": "agent_123",
  "platform": "discord",
  "recipient_id": "987654321",
  "template": "Weekly summary: {{week}}",
  "schedule_type": "recurring",
  "natural_language_schedule": "every monday at 9am"
}
```

#### Parse Natural Language
```http
POST /api/v1/messaging/schedule/parse-nl
Content-Type: application/json

{
  "schedule": "every day at 9am"
}
```

**Response**:
```json
{
  "schedule": "every day at 9am",
  "cron_expression": "0 9 * * *",
  "description": "Daily at 9:00 AM"
}
```

#### List Scheduled Messages
```http
GET /api/v1/messaging/schedule/list?agent_id=agent_123&active=true
```

#### Pause/Resume Scheduled Message
```http
POST /api/v1/messaging/schedule/{message_id}/pause
POST /api/v1/messaging/schedule/{message_id}/resume
```

#### Cancel Scheduled Message
```http
DELETE /api/v1/messaging/schedule/{message_id}
```

#### Get Execution History
```http
GET /api/v1/messaging/schedule/history/executions?limit=100
```

### Natural Language Examples

| Input | Cron Expression | Description |
|-------|----------------|-------------|
| `every day at 9am` | `0 9 * * *` | Daily at 9:00 AM |
| `every monday at 2:30pm` | `30 14 * * 1` | Weekly on Monday at 2:30 PM |
| `hourly` | `0 * * * *` | Every hour |
| `daily` | `0 9 * * *` | Daily at 9:00 AM |
| `weekly` | `0 9 * * 1` | Weekly on Monday at 9:00 AM |
| `monthly` | `0 9 1 * *` | Monthly on 1st at 9:00 AM |
| `every 6 hours` | `0 */6 * * *` | Every 6 hours |
| `every friday at 5pm` | `0 17 * * 5` | Fridays at 5:00 PM |

### Template Variables

Built-in variables:
- `{{date}}` - Current date (YYYY-MM-DD)
- `{{time}}` - Current time (HH:MM:SS)
- `{{datetime}}` - Current datetime (ISO 8601)
- `{{timezone}}` - Configured timezone

Custom variables (from `template_variables` field):
```json
{
  "template": "Hello {{name}}, your balance is {{balance}}",
  "template_variables": {
    "name": "John",
    "balance": "$1,234.56"
  }
}
```

### Database Schema

```sql
CREATE TABLE scheduled_messages (
  id UUID PRIMARY KEY,
  agent_id VARCHAR NOT NULL,
  platform VARCHAR NOT NULL,
  recipient_id VARCHAR NOT NULL,
  template TEXT NOT NULL,
  schedule_type VARCHAR NOT NULL,
  cron_expression VARCHAR,
  next_run TIMESTAMP NOT NULL,
  last_run TIMESTAMP,
  active BOOLEAN DEFAULT TRUE,
  timezone VARCHAR DEFAULT 'UTC',
  created_at TIMESTAMP DEFAULT NOW()
);
```

### Execution Engine

The scheduler runs every minute to check for due messages:

```bash
# Internal endpoint (called by APScheduler)
POST /api/v1/messaging/schedule/_execute-due
```

**Response**:
```json
{
  "sent": 5,
  "failed": 0,
  "skipped": 2
}
```

### Use Cases

1. **Daily Reports**: Automated daily summaries
2. **Weekly Digests**: Weekly team updates
3. **Recurring Reminders**: Medication, meetings, tasks
4. **Scheduled Notifications**: Maintenance windows, updates
5. **Time-Based Triggers**: End of month, start of week

### Performance

- **Natural Language Parse**: <50ms
- **Message Scheduling**: <10ms
- **Execution Check**: <5ms (indexed query)
- **Throughput**: 1000 executions/minute

---

## 3. Condition Monitoring

### Overview

Condition monitoring provides **real-time business monitoring** with automatic alerts when thresholds are exceeded.

### Supported Condition Types

| Type | Description | Example |
|------|-------------|---------|
| `inbox_volume` | Monitor unread message counts | Alert when >100 unread |
| `task_backlog` | Monitor pending task counts | Alert when >50 tasks |
| `api_metrics` | Monitor API error rates | Alert when >5% errors |
| `database_query` | Custom SQL queries | Alert when result meets condition |
| `composite` | AND/OR logic for multiple conditions | Alert when both A and B true |

### API Endpoints

#### Create Condition Monitor
```http
POST /api/v1/monitoring/condition/create
Content-Type: application/json

{
  "agent_id": "agent_123",
  "name": "High Inbox Alert",
  "condition_type": "inbox_volume",
  "threshold_config": {
    "metric": "unread_count",
    "operator": ">",
    "value": 100
  },
  "platforms": [
    {"platform": "slack", "recipient_id": "C12345"}
  ],
  "check_interval_seconds": 300,
  "alert_template": "⚠️ High inbox volume: {{value}} unread messages (threshold: {{threshold}})"
}
```

#### Get Pre-configured Presets
```http
GET /api/v1/monitoring/presets
```

**Response**:
```json
{
  "presets": [
    {
      "name": "High Inbox Volume",
      "condition_type": "inbox_volume",
      "threshold_config": {"metric": "unread_count", "operator": ">", "value": 100},
      "check_interval_seconds": 300
    },
    {
      "name": "Task Backlog Alert",
      "condition_type": "task_backlog",
      "threshold_config": {"metric": "pending_tasks", "operator": ">=", "value": 50}
    }
  ]
}
```

#### Apply Preset
```http
POST /api/v1/monitoring/presets/apply
Content-Type: application/json

{
  "agent_id": "agent_123",
  "preset_name": "High Inbox Volume",
  "platforms": [
    {"platform": "slack", "recipient_id": "C12345"}
  ]
}
```

#### List Monitors
```http
GET /api/v1/monitoring/condition/list?status=active
```

#### Test Condition
```http
POST /api/v1/monitoring/condition/{monitor_id}/test
```

**Response**:
```json
{
  "monitor_id": "monitor_abc",
  "monitor_name": "High Inbox Alert",
  "condition_type": "inbox_volume",
  "triggered": true,
  "current_value": 125,
  "threshold": {"metric": "unread_count", "operator": ">", "value": 100},
  "timestamp": "2026-02-04T10:30:00Z"
}
```

#### Pause/Resume Monitor
```http
POST /api/v1/monitoring/condition/{monitor_id}/pause
POST /api/v1/monitoring/condition/{monitor_id}/resume
```

#### Get Alert History
```http
GET /api/v1/monitoring/alerts?monitor_id=monitor_abc
```

#### Get Monitoring Metrics
```http
GET /api/v1/monitoring/metrics
```

**Response**:
```json
{
  "total_monitors": 15,
  "active_monitors": 12,
  "total_alerts": 234,
  "pending_alerts": 3,
  "alerts_last_24h": 45
}
```

### Threshold Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `>` | Greater than | `unread_count > 100` |
| `>=` | Greater than or equal | `tasks >= 50` |
| `<` | Less than | `errors < 5` |
| `<=` | Less than or equal | `response_time <= 200` |
| `==` | Equal to | `status == "error"` |
| `!=` | Not equal to | `status != "success"` |

### Composite Conditions

Combine multiple conditions with AND/OR logic:

```json
{
  "name": "Critical System Alert",
  "condition_type": "composite",
  "composite_logic": "AND",
  "composite_conditions": [
    {
      "condition_type": "inbox_volume",
      "threshold_config": {"metric": "unread_count", "operator": ">", "value": 100}
    },
    {
      "condition_type": "task_backlog",
      "threshold_config": {"metric": "pending_tasks", "operator": ">", "value": 50}
    }
  ],
  "platforms": [
    {"platform": "slack", "recipient_id": "C12345"}
  ]
}
```

### Database Schema

```sql
CREATE TABLE condition_monitors (
  id UUID PRIMARY KEY,
  agent_id VARCHAR NOT NULL,
  name VARCHAR NOT NULL,
  condition_type VARCHAR NOT NULL,
  threshold JSONB NOT NULL,
  check_interval INTEGER DEFAULT 300,
  platforms TEXT[],
  alert_template TEXT,
  status VARCHAR DEFAULT 'active',
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE condition_alerts (
  id UUID PRIMARY KEY,
  monitor_id UUID NOT NULL,
  condition_value JSONB NOT NULL,
  threshold_value JSONB NOT NULL,
  alert_message TEXT,
  platforms_sent TEXT[],
  status VARCHAR DEFAULT 'pending',
  triggered_at TIMESTAMP DEFAULT NOW(),
  sent_at TIMESTAMP
);
```

### Alert Throttling

To prevent alert spam:
- **Throttle Window**: 15 minutes (default)
- **Max Alerts**: 1 per monitor per window
- **Priority Queue**: Urgent alerts sent first

### Use Cases

1. **Inbox Monitoring**: Alert when messages pile up
2. **Task Management**: Alert when backlog grows
3. **API Health**: Alert on error rate spikes
4. **Database Monitoring**: Custom query-based alerts
5. **Composite Alerts**: Multi-condition triggers

### Performance

- **Condition Check**: <5ms (indexed)
- **Alert Generation**: <50ms
- **Multi-Platform Send**: <500ms
- **Check Throughput**: 1000 monitors/minute

---

## Platform Support Matrix

| Feature | Slack | Discord | Teams | WhatsApp | Telegram | Google Chat | Signal | Messenger | LINE |
|---------|-------|---------|-------|----------|----------|-------------|--------|-----------|------|
| Proactive Messaging | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Scheduled Messages | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Condition Monitoring | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Quick Start Examples

### Example 1: Daily Proactive Report

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/messaging/proactive/send",
    json={
        "agent_id": "agent_reports",
        "platform": "slack",
        "recipient_id": "C12345",
        "content": "📊 Daily Report: 15 tasks completed, 0 critical issues",
        "send_now": True
    }
)
print(response.json())
```

### Example 2: Scheduled Weekly Summary

```python
response = requests.post(
    "http://localhost:8000/api/v1/messaging/schedule/create",
    json={
        "agent_id": "agent_reports",
        "platform": "discord",
        "recipient_id": "987654321",
        "template": "📅 Weekly Summary for {{date}}: {{summary}}",
        "schedule_type": "recurring",
        "natural_language_schedule": "every friday at 5pm",
        "template_variables": {
            "summary": "52 tasks completed, 3 meetings held"
        }
    }
)
print(response.json())
```

### Example 3: Inbox Volume Monitor

```python
response = requests.post(
    "http://localhost:8000/api/v1/monitoring/condition/create",
    json={
        "agent_id": "agent_monitor",
        "name": "High Slack Inbox",
        "condition_type": "inbox_volume",
        "threshold_config": {
            "metric": "unread_count",
            "operator": ">",
            "value": 50
        },
        "platforms": [
            {"platform": "slack", "recipient_id": "C12345"}
        ],
        "check_interval_seconds": 300,
        "alert_template": "🚨 {{value}} unread Slack messages!"
    }
)
print(response.json())
```

---

## Performance Benchmarks

All messaging features are optimized for performance:

| Operation | Target (p99) | Actual |
|-----------|--------------|--------|
| Governance Check | <1ms | 0.5ms |
| Proactive Message Send | <100ms | 65ms |
| Schedule Creation | <50ms | 30ms |
| Condition Check | <5ms | 3ms |
| Alert Delivery | <500ms | 320ms |
| Natural Language Parse | <50ms | 25ms |

---

## Getting Help

- **API Documentation**: `/docs/api/messaging/`
- **Platform Guide**: `/docs/MESSAGING_PLATFORMS.md`
- **Examples**: `/examples/messaging/`
- **Support**: Open GitHub issue

---

**Version**: 1.0.0
**Last Updated**: February 4, 2026
**Maintained By**: ATOM Platform Team
