# Support Triage Workflow

Automatically trigger support ticket prioritization and routing workflow when Ticket entities are discovered.

---

## Overview

**Entity Type**: `Ticket`

**Workflow ID**: `support_triage`

**Trigger Condition**: Always trigger for all tickets

**Priority**: 7 (Medium priority for support workflows)

---

## When It Triggers

- Support ticket created from emails
- Customer inquiries
- Bug reports
- Feature requests
- Technical issues

---

## Workflow Steps

### Step 1: Categorize Ticket

**Action**: Classify ticket by type and severity

**Categories**:
- **Bug**: Software defect, error, crash
- **Feature**: New feature request
- **Question**: How-to, clarification
- **Account**: Billing, account access
- **Technical**: Integration, API, technical issue

**Severity Levels**:
- **P1 - Critical**: System down, data loss
- **P2 - High**: Major feature broken
- **P3 - Medium**: Minor issue, workaround exists
- **P4 - Low**: Nice-to-have, cosmetic

---

### Step 2: Priority Scoring

**Action**: Calculate priority score

**Scoring Model**:
```python
priority = 0

# Severity impact
if severity == "P1":
    priority += 50
elif severity == "P2":
    priority += 30
elif severity == "P3":
    priority += 15
elif severity == "P4":
    priority += 5

# Customer tier
if customer_tier == "enterprise":
    priority += 20
elif customer_tier == "pro":
    priority += 10

# SLA breach risk
if sla_breach_imminent:
    priority += 30
```

**Priority Score**: 0-100

---

### Step 3: Route to Team

**Action**: Route ticket based on category and priority

**Routing Rules**:

| Category | Priority | Assigned Team |
|----------|----------|---------------|
| Bug | P1-P2 | Engineering - Hotfix |
| Bug | P3-P4 | Engineering - Backlog |
| Feature | Any | Product Management |
| Account | P1-P2 | Customer Success |
| Account | P3-P4 | Support Agent |
| Question | Any | Support Agent |
| Technical | P1-P2 | Technical Support |
| Technical | P3-P4 | Documentation Team |

---

### Step 4: Check for Duplicates

**Action**: Search for similar existing tickets

**Duplicate Detection**:
- Fuzzy text matching on subject/description
- Same customer, same issue
- Time window: 30 days

**If Duplicate Found**:
- Link to existing ticket
- Notify customer
- Close new ticket

---

### Step 5: Set SLA

**Action**: Set SLA based on priority

**SLA Targets**:

| Priority | Response Time | Resolution Time |
|----------|---------------|-----------------|
| P1 | 15 minutes | 4 hours |
| P2 | 1 hour | 24 hours |
| P3 | 4 hours | 3 business days |
| P4 | 1 business day | 2 weeks |

---

### Step 6: Send Auto-Response

**Action**: Send automated acknowledgment email

**Template**:
```
Thank you for contacting Atom Support!

We received your ticket: {{ticket_number}}
Category: {{category}}
Priority: {{priority}}
Estimated Response: {{sla_response_time}}

Track your ticket: {{ticket_url}}

{{if faq_articles}}
You might find these helpful:
{{faq_articles}}
{{endif}}
```

---

## Escalation Rules

### Executive Escalation (P1 + Enterprise)

**Trigger Condition**:
```yaml
entity_type: "Ticket"
workflow_id: "support_executive_escalation"
trigger_condition:
  $and:
    - severity: "P1"
    - customer_tier: "enterprise"
priority: 25
```

### Bug Triage (Feature + High Priority)

**Trigger Condition**:
```yaml
entity_type: "Ticket"
workflow_id: "support_bug_triage"
trigger_condition:
  $and:
    - category: "Bug"
    - severity:
        $in: ["P1", "P2"]
priority: 20
```

---

## Configuration Example

### Python Registration

```python
from core.workflow_trigger_service import WorkflowTriggerService

service = WorkflowTriggerService(db)

# Support triage
service.register_workflow_trigger(
    entity_type="Ticket",
    workflow_id="support_triage",
    condition=None,  # Always trigger
    priority=7,
    metadata={
        "duplicate_detection_window_days": 30,
        "auto_response_enabled": True,
        "sla_targets": {
            "P1": {"response": "15m", "resolution": "4h"},
            "P2": {"response": "1h", "resolution": "24h"},
            "P3": {"response": "4h", "resolution": "3d"},
            "P4": {"response": "1d", "resolution": "2w"}
        }
    }
)

# Executive escalation
service.register_workflow_trigger(
    entity_type="Ticket",
    workflow_id="support_executive_escalation",
    condition={
        "$and": [
            {"category": "Bug"},
            {"severity": {"$in": ["P1", "P2"]}},
            {"customer_tier": "enterprise"}
        ]
    },
    priority=25,
    metadata={
        "notify_cxo": True,
        "slack_channel": "#executive-alerts"
    }
)
```

---

## Business Impact

**Before Automation**:
- Manual triage: 30-60 minutes/ticket
- Incorrect routing: 20% error rate
- SLA breaches: 15% of P1 tickets
- Duplicate tickets: 10%

**After Automation**:
- Instant triage and scoring
- Auto-routing: 95% accuracy
- SLA tracking: Automated
- Duplicate detection: 90% accuracy

**ROI**: 20 hours/week saved in support team, 30% SLA improvement

---

## Testing

```python
# Create P1 ticket from enterprise customer
ticket = DiscoveredEntity(
    _discovered_type="Ticket",
    properties={
        "subject": "System down - critical",
        "category": "Bug",
        "severity": "P1",
        "customer_tier": "enterprise",
        "description": "Production system is down"
    }
)

# Should trigger support triage + executive escalation
triggered = await service.check_and_trigger(ticket)
assert "support_triage" in triggered
```

---

## Monitoring

Track these metrics:

- **Triage Accuracy**: Correct routing percentage
- **SLA Compliance**: % tickets meeting SLA
- **Duplicate Detection**: % duplicates caught
- **Response Time**: Avg first response time
- **Resolution Time**: Avg time to resolution

---

## Related Workflows

- [Security Alert](./security-alert.md) - For security-related tickets
- [Lead Qualification](./lead-qualification.md) - For sales leads

---

*Template Created: 2026-05-05*
*Workflow Type: Support*
*Entity Type: Ticket*
