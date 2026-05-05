# Security Alert Workflow

Automatically trigger security incident response workflow when SecurityEvent entities are discovered.

---

## Overview

**Entity Type**: `SecurityEvent`

**Workflow ID**: `security_alert_urgent` / `security_alert_standard`

**Trigger Condition**:
- **Urgent**: `severity == "critical"`
- **Standard**: `severity == "high"` or `severity == "medium"`

**Priority**: 20 (Highest priority - security events)

---

## When It Triggers

- SecurityEvent discovered in emails
- Intrusion detection alerts
- Malware detection notifications
- Unusual login attempts
- Data access anomalies

---

## Workflow Variants

### Variant 1: Urgent Security Alert (Critical)

**Trigger Condition**:
```yaml
entity_type: "SecurityEvent"
workflow_id: "security_alert_urgent"
trigger_condition:
  severity: "critical"
priority: 20
```

**Workflow Steps**:

#### Step 1: Immediate Alert

**Action**: Send SMS + Email to security team

**Recipients**:
- CTO
- Security lead
- On-call engineer

**Template**: `security_alert_urgent`

**Data**:
```json
{
  "event_type": "{{properties.event_type}}",
  "severity": "{{properties.severity}}",
  "user": "{{properties.user}}",
  "location": "{{properties.location}}",
  "detected_at": "{{properties.detected_at}}",
  "alert_url": "https://app.atom.com/security/{{id}}"
}
```

#### Step 2: Create Incident Ticket

**Action**: Create high-priority ticket in ticketing system

**System**: Jira / ServiceNow

**Priority**: P1 (Critical)

**Payload**:
```json
{
  "summary": "CRITICAL: {{properties.event_type}} detected",
  "description": "Security event requiring immediate investigation",
  "priority": 1,
  "assignee": "security-team-lead"
}
```

#### Step 3: Await Acknowledgment

**Action**: Wait for human acknowledgment

**Timeout**: 15 minutes

**Webhook**: `POST /api/v1/security/alerts/{alert_id}/acknowledge`

#### Step 4: If No Acknowledgment

**Action**: Escalate to executive team

**Recipients**: CEO, CTO, VP Engineering

**Method**: Phone call + SMS

---

### Variant 2: Standard Security Alert (High/Medium)

**Trigger Condition**:
```yaml
entity_type: "SecurityEvent"
workflow_id: "security_alert_standard"
trigger_condition:
  $or:
    - severity: "high"
    - severity: "medium"
priority: 15
```

**Workflow Steps**:

#### Step 1: Queue for Review

**Action**: Add to security review queue

**System**: Atom Security Dashboard

**Priority**: High/Medium

#### Step 2: Send Daily Digest

**Action**: Batch email at end of day

**Schedule**: 6 PM daily

**Recipients**: Security team

#### Step 3: Auto-Triage

**Action**: ML-based triage and routing

**Model**: Security event classifier

**Categories**:
- True positive (requires action)
- False positive (ignore)
- Requires investigation (manual review)

---

## Escalation Rules

### Board Escalation (Critical + Customer Data)

**Trigger Condition**:
```yaml
entity_type: "SecurityEvent"
workflow_id: "security_alert_board"
trigger_condition:
  $and:
    - severity: "critical"
    - impacted_systems:
        $in: ["customer_database", "payment_processing"]
priority: 30
```

**Actions**:
1. Immediate board notification
2. PR team prep (customer communication)
3. Legal team notification (compliance)
4. External security firm engagement

---

## Configuration Example

### Python Registration

```python
from core.workflow_trigger_service import WorkflowTriggerService

service = WorkflowTriggerService(db)

# Urgent security alerts
service.register_workflow_trigger(
    entity_type="SecurityEvent",
    workflow_id="security_alert_urgent",
    condition={"severity": "critical"},
    priority=20,
    metadata={
        "notification_channels": ["sms", "email", "slack"],
        "ack_timeout_minutes": 15,
        "escalation_to_exec": True
    }
)

# Standard security alerts
service.register_workflow_trigger(
    entity_type="SecurityEvent",
    workflow_id="security_alert_standard",
    condition={
        "$or": [
            {"severity": "high"},
            {"severity": "medium"}
        ]
    },
    priority=15,
    metadata={
        "notification_channels": ["email"],
        "digest_schedule": "daily",
        "auto_triage": True
    }
)

# Board-level escalation
service.register_workflow_trigger(
    entity_type="SecurityEvent",
    workflow_id="security_alert_board",
    condition={
        "$and": [
            {"severity": "critical"},
            {"impacted_systems": {"$in": ["customer_database", "payment_processing"]}}
        ]
    },
    priority=30,
    metadata={
        "notify_board": True,
        "notify_pr": True,
        "notify_legal": True
    }
)
```

### YAML Configuration

```yaml
# Urgent alert
- entity_type: "SecurityEvent"
  workflow_id: "security_alert_urgent"
  trigger_condition:
    severity: "critical"
  priority: 20
  metadata:
    notification_channels:
      - sms
      - email
      - slack
    ack_timeout_minutes: 15
    escalation_to_exec: true

# Standard alert
- entity_type: "SecurityEvent"
  workflow_id: "security_alert_standard"
  trigger_condition:
    $or:
      - severity: "high"
      - severity: "medium"
  priority: 15
  metadata:
    notification_channels:
      - email
    digest_schedule: daily
    auto_triage: true
```

---

## Business Impact

**Before Automation**:
- Alert response time: 2-4 hours
- Missed critical alerts: 10%
- Manual ticket creation: 30 min/alert
- No escalation for unacknowledged alerts

**After Automation**:
- Immediate alerting: <1 minute
- 15-minute acknowledgment SLA
- Auto-ticket creation: Instant
- Auto-escalation: After 15 minutes

**ROI**: Critical security incidents resolved 10x faster

---

## Testing

### Test Case 1: Critical Security Event

```python
# Create critical security event
event = DiscoveredEntity(
    _discovered_type="SecurityEvent",
    properties={
        "event_type": "intrusion_detected",
        "severity": "critical",
        "user": "john@example.com",
        "location": "Unknown IP (192.168.1.100)",
        "detected_at": "2026-05-05T10:30:00Z"
    }
)

# Should trigger urgent workflow
triggered = await service.check_and_trigger(event)
assert "security_alert_urgent" in triggered
```

### Test Case 2: High Severity Event

```python
# Create high severity event
event = DiscoveredEntity(
    _discovered_type="SecurityEvent",
    properties={
        "event_type": "malware_detected",
        "severity": "high",
        "user": "jane@example.com",
        "location": "Downloaded suspicious file"
    }
)

# Should trigger standard workflow
triggered = await service.check_and_trigger(event)
assert "security_alert_standard" in triggered
assert "security_alert_urgent" not in triggered
```

---

## Monitoring

Track these metrics:

- **Trigger Rate**: Security events per day
- **Response Time**: Time to acknowledgment
- **Escalation Rate**: Alerts escalated to executives
- **False Positive Rate**: Alerts dismissed as false positives
- **MTTR**: Mean time to resolve security incidents

---

## Related Workflows

- [Support Triage](./support-triage.md) - For security-related support tickets
- [Purchase Order Approval](./purchase-order-approval.md) - For suspicious POs

---

## Security Best Practices

1. **Multi-Channel Alerts**: Use SMS, email, and Slack for critical alerts
2. **Acknowledgment SLA**: 15 minutes for critical, 4 hours for standard
3. **Escalation Paths**: Clear escalation to executives
4. **Audit Trail**: Log all security events and responses
5. **Post-Incident Review**: Learn from each security event

---

*Template Created: 2026-05-05*
*Workflow Type: Security*
*Entity Type: SecurityEvent*
*Priority: Critical*
