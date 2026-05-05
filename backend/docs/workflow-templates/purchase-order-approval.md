# Purchase Order Approval Workflow

Automatically trigger multi-level purchase order approval workflow when PurchaseOrder entities are discovered.

---

## Overview

**Entity Type**: `PurchaseOrder`

**Workflow ID**: `purchase_order_approval`

**Trigger Condition**: `amount >= 1000` (POs over $1,000 require approval)

**Priority**: 10 (High priority for financial workflows)

---

## When It Triggers

- PurchaseOrder discovered with `amount >= 1000`
- All purchase orders extracted from emails
- Purchase orders from vendor invoices

---

## Workflow Steps

### Step 1: Notify Manager

**Action**: Send email notification to purchasing manager

**Template**: `po_approval_request`

**Data**:
```json
{
  "po_number": "{{properties.po_number}}",
  "vendor": "{{properties.vendor}}",
  "amount": "{{properties.amount}}",
  "currency": "{{properties.currency}}",
  "approval_url": "https://app.atom.com/po/{{id}}"
}
```

**Recipients**: Purchasing manager email (configurable)

---

### Step 2: Await Approval

**Action**: Wait for manager approval via webhook

**Timeout**: 72 hours (3 business days)

**Webhook**: `POST /api/v1/workflows/po-approval/{workflow_id}/approve`

**Payload**:
```json
{
  "approved": true,
  "approved_by": "user-001",
  "notes": "Approved within budget"
}
```

---

### Step 3: Process Approval

**Action**: Update PO status in ERP system

**Status**: `approved`

**ERP Integration**:
- Update PO record in SAP/Oracle/Netsuite
- Send confirmation to vendor
- Notify requester of approval

---

### Step 4: If Rejected

**Action**: Notify requester and update status

**Status**: `rejected`

**Data**:
```json
{
  "rejection_reason": "{{webhook.notes}}",
  "rejected_by": "{{webhook.approved_by}}"
}
```

---

## Escalation Rules

### Executive Approval (amount >= $50,000)

**Trigger Condition**:
```yaml
entity_type: "PurchaseOrder"
workflow_id: "executive_approval"
trigger_condition:
  amount:
    $gte: 50000
priority: 20  # Higher priority
```

**Workflow Steps**:
1. Notify CFO
2. Await executive approval (48 hours)
3. Process approval
4. Board notification for amounts >= $100,000

---

## Configuration Example

### Python Registration

```python
from core.workflow_trigger_service import WorkflowTriggerService

service = WorkflowTriggerService(db)

# Standard PO approval
service.register_workflow_trigger(
    entity_type="PurchaseOrder",
    workflow_id="purchase_order_approval",
    condition={"amount": {"$gte": 1000}},
    priority=10,
    metadata={
        "approval_timeout_hours": 72,
        "approver_role": "purchasing_manager"
    }
)

# Executive approval for large POs
service.register_workflow_trigger(
    entity_type="PurchaseOrder",
    workflow_id="executive_approval",
    condition={"amount": {"$gte": 50000}},
    priority=20,
    metadata={
        "approval_timeout_hours": 48,
        "approver_role": "cfo"
    }
)
```

### YAML Configuration

```yaml
entity_type: "PurchaseOrder"
workflow_id: "purchase_order_approval"
trigger_condition:
  amount:
    $gte: 1000
priority: 10
metadata:
  approval_timeout_hours: 72
  approver_role: "purchasing_manager"
  escalation_threshold: 50000
```

---

## Business Impact

**Before Automation**:
- Manual PO review: 2-3 days
- Lost emails: 15% of POs
- Approval tracking: Spreadsheets

**After Automation**:
- Auto-triggered workflows: Instant
- Centralized tracking: In Atom
- Escalation: Automatic based on amount

**ROI**: 20 hours/week saved in purchasing team

---

## Testing

### Test Case 1: Standard PO Approval

```python
# Create PO entity
po = DiscoveredEntity(
    _discovered_type="PurchaseOrder",
    properties={
        "po_number": "PO-12345",
        "vendor": "Acme Corp",
        "amount": 5000.0,
        "currency": "USD"
    }
)

# Should trigger standard approval workflow
triggered = await service.check_and_trigger(po)
assert "purchase_order_approval" in triggered
```

### Test Case 2: Executive Escalation

```python
# Create large PO
po = DiscoveredEntity(
    _discovered_type="PurchaseOrder",
    properties={
        "po_number": "PO-99999",
        "vendor": "Strategic Supplier",
        "amount": 75000.0,
        "currency": "USD"
    }
)

# Should trigger executive approval
triggered = await service.check_and_trigger(po)
assert "executive_approval" in triggered
```

---

## Monitoring

Track these metrics:

- **Trigger Rate**: POs triggering workflows per day
- **Approval Time**: Avg time from trigger to approval
- **Escalation Rate**: POs escalated to executive approval
- **Rejection Rate**: POs rejected by approvers

---

## Related Workflows

- [Invoice Processing](./invoice-processing.md) - Triggered after PO approval
- [Security Alert](./security-alert.md) - For suspicious POs

---

*Template Created: 2026-05-05*
*Workflow Type: Approval*
*Entity Type: PurchaseOrder*
