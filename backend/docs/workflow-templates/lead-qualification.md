# Lead Qualification Workflow

Automatically trigger sales lead scoring and routing workflow when Lead entities are discovered.

---

## Overview

**Entity Type**: `Lead`

**Workflow ID**: `lead_qualification`

**Trigger Condition**: Always trigger for all leads

**Priority**: 8 (Medium-high priority for sales workflows)

---

## When It Triggers

- Lead discovered in emails
- Website contact forms
- Event registrations
- Demo requests
- Partnership inquiries

---

## Workflow Steps

### Step 1: Score Lead

**Action**: Calculate lead score based on properties

**Scoring Model**:
```python
score = 0

# Company size (30 points)
if company_size == "enterprise":
    score += 30
elif company_size == "midmarket":
    score += 20
elif company_size == "small":
    score += 10

# Intent (40 points)
if demo_requested:
    score += 20
if pricing_inquired:
    score += 20

# Timeline (20 points)
if timeline == "immediate":
    score += 20
elif timeline == "30_days":
    score += 10

# Budget (10 points)
if budget_provided:
    score += 10
```

**Score Categories**:
- **Hot Lead** (80-100): Immediate follow-up
- **Warm Lead** (50-79): Standard nurturing
- **Cold Lead** (0-49): Long-term nurturing

---

### Step 2: Route to Sales Rep

**Action**: Route lead based on score and territory

**Routing Rules**:

| Score | Territory | Assigned To |
|-------|-----------|-------------|
| 80-100 | Enterprise | Enterprise sales team |
| 80-100 | SMB | Inside sales team |
| 50-79 | Any | Account executive |
| 0-49 | Any | Marketing automation |

---

### Step 3: Enrich Lead Data

**Action**: Enrich lead data from external sources

**Data Sources**:
- LinkedIn (company info)
- Clearbit (technographics)
- Crunchbase (funding data)
- ZoomInfo (contact info)

---

### Step 4: Add to CRM

**Action**: Create lead record in CRM system

**Systems**: Salesforce, HubSpot, Pipedrive

**Fields**:
- Lead name, email, phone
- Company, title, industry
- Lead score, source, territory
- Assigned sales rep

---

### Step 5: Send Follow-up Email

**Action**: Automated follow-up based on lead score

**Templates**:
- **Hot Leads**: Personal email from sales rep within 1 hour
- **Warm Leads**: Automated nurture sequence
- **Cold Leads**: Monthly newsletter

---

## Configuration Example

### Python Registration

```python
from core.workflow_trigger_service import WorkflowTriggerService

service = WorkflowTriggerService(db)

# Lead qualification
service.register_workflow_trigger(
    entity_type="Lead",
    workflow_id="lead_qualification",
    condition=None,  # Always trigger
    priority=8,
    metadata={
        "hot_lead_threshold": 80,
        "warm_lead_threshold": 50,
        "auto_response_hours": 1,
        "enrichment_sources": ["linkedin", "clearbit"]
    }
)
```

---

## Business Impact

**Before Automation**:
- Lead response time: 24-48 hours
- Manual lead scoring: Spreadsheets
- Lost hot leads: 30%
- No data enrichment

**After Automation**:
- Instant lead scoring
- Auto-routing to right rep
- 1-hour response for hot leads
- Auto-enrichment from 3+ sources

**ROI**: 25% increase in lead conversion rate

---

## Testing

```python
# Create hot lead
lead = DiscoveredEntity(
    _discovered_type="Lead",
    properties={
        "name": "John Smith",
        "email": "john@enterprise.com",
        "company": "Enterprise Corp",
        "demo_requested": True,
        "timeline": "immediate"
    }
)

# Should trigger lead qualification
triggered = await service.check_and_trigger(lead)
assert "lead_qualification" in triggered
```

---

*Template Created: 2026-05-05*
*Workflow Type: Sales*
*Entity Type: Lead*
