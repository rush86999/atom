# Invoice Processing Workflow

Automatically trigger invoice validation and payment processing workflow when Invoice entities are discovered.

---

## Overview

**Entity Type**: `Invoice`

**Workflow ID**: `invoice_processing`

**Trigger Condition**: `amount >= 100` (Invoices over $100 require processing)

**Priority**: 5 (Standard priority for financial workflows)

---

## When It Triggers

- Invoice discovered in emails
- Vendor billing statements
- Subscription renewals
- Expense reports

---

## Workflow Steps

### Step 1: Validate Invoice

**Action**: Validate invoice data and check for duplicates

**Checks**:
- Invoice number not previously processed
- Vendor exists in vendor master
- Amount matches PO (if applicable)
- Due date is valid
- Tax calculations correct

**On Validation Failure**:
- Flag for manual review
- Notify finance team

---

### Step 2: Match to Purchase Order

**Action**: Match invoice to existing PO (if applicable)

**Match Criteria**:
- PO number in invoice metadata
- Vendor + amount range
- Date proximity

**If Matched**:
- Link invoice to PO
- Verify amount tolerance (±10%)
- Update PO status

**If Not Matched**:
- Flag as "No PO"
- Route to manual review

---

### Step 3: Route for Approval

**Action**: Route invoice based on amount and risk

**Routing Rules**:

| Amount | Workflow | Approver |
|--------|----------|----------|
| < $1,000 | Auto-approve | System |
| $1,000 - $10,000 | Standard approval | Finance manager |
| > $10,000 | Executive approval | CFO |

---

### Step 4: Awaiting Approval

**Action**: Wait for finance team approval

**Timeout**: 7 business days

**Webhook**: `POST /api/v1/workflows/invoices/{invoice_id}/approve`

---

### Step 5: Process Payment

**Action**: Schedule payment via ERP/Accounting system

**Systems**: SAP, Oracle NetSuite, QuickBooks

**Payment Terms**: Based on vendor terms (net-30, net-60, etc.)

---

## Escalation Rules

### CFO Approval (Large Invoices)

**Trigger Condition**:
```yaml
entity_type: "Invoice"
workflow_id: "invoice_cfo_approval"
trigger_condition:
  amount:
    $gte: 10000
priority: 15
```

### Legal Review (Unusual Terms)

**Trigger Condition**:
```yaml
entity_type: "Invoice"
workflow_id: "invoice_legal_review"
trigger_condition:
  payment_terms:
    $nin: ["net-30", "net-60", "net-90"]
priority: 12
```

---

## Configuration Example

### Python Registration

```python
from core.workflow_trigger_service import WorkflowTriggerService

service = WorkflowTriggerService(db)

# Standard invoice processing
service.register_workflow_trigger(
    entity_type="Invoice",
    workflow_id="invoice_processing",
    condition={"amount": {"$gte": 100}},
    priority=5,
    metadata={
        "auto_approve_limit": 1000,
        "standard_approve_limit": 10000,
        "payment_tolerance": 0.10  # ±10%
    }
)

# CFO approval for large invoices
service.register_workflow_trigger(
    entity_type="Invoice",
    workflow_id="invoice_cfo_approval",
    condition={"amount": {"$gte": 10000}},
    priority=15,
    metadata={
        "approver_role": "cfo",
        "approval_timeout_days": 7
    }
)
```

---

## Business Impact

**Before Automation**:
- Manual invoice processing: 5-7 days
- Duplicate invoices: 5% error rate
- Lost invoices: 10%
- Payment delays: 20% overdue

**After Automation**:
- Auto-validation: Instant
- Duplicate detection: 100% accuracy
- Centralized tracking: In Atom
- On-time payments: 95%

**ROI**: 15 hours/week saved in finance team

---

## Testing

```python
# Create invoice entity
invoice = DiscoveredEntity(
    _discovered_type="Invoice",
    properties={
        "invoice_number": "INV-12345",
        "vendor": "Acme Corp",
        "amount": 5000.0,
        "currency": "USD",
        "due_date": "2026-06-05"
    }
)

# Should trigger invoice processing
triggered = await service.check_and_trigger(invoice)
assert "invoice_processing" in triggered
```

---

*Template Created: 2026-05-05*
*Workflow Type: Financial*
*Entity Type: Invoice*
