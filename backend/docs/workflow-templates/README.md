# Workflow Templates

This directory contains workflow templates for automatic workflow triggers when specific entity types are discovered.

Phase 323-05: Workflow Automation Triggers

---

## Available Templates

1. [Purchase Order Approval](./purchase-order-approval.md) - Multi-level PO approval workflow
2. [Security Alert](./security-alert.md) - Urgent security incident response
3. [Invoice Processing](./invoice-processing.md) - Automated invoice validation and payment
4. [Lead Qualification](./lead-qualification.md) - Sales lead scoring and routing
5. [Support Triage](./support-triage.md) - Automated support ticket prioritization

---

## Template Structure

Each workflow template includes:

- **Trigger Condition**: When to auto-trigger the workflow
- **Entity Type**: Which discovered entity type triggers the workflow
- **Workflow Steps**: Sequential steps to execute
- **Escalation Rules**: When to escalate to higher-level workflows
- **Configuration Example**: YAML/JSON configuration for the workflow trigger

---

## Usage

1. Review the workflow template
2. Register the workflow trigger in your code:

```python
from core.workflow_trigger_service import WorkflowTriggerService

service = WorkflowTriggerService(db)

# Example: Register PO approval workflow
service.register_workflow_trigger(
    entity_type="PurchaseOrder",
    workflow_id="purchase_order_approval",
    condition={"amount": {"$gte": 1000}},
    priority=10
)
```

3. Automatically trigger workflows on entity discovery:

```python
# In your entity extraction pipeline
extractor = MultiEntityLLMExtractor()
entities = await extractor.extract_from_email(email_data, tenant_id, workspace_id)

# Trigger workflows for each entity
for entity in entities:
    triggered = await service.check_and_trigger(entity)
    if triggered:
        logger.info(f"Triggered workflows: {triggered}")
```

---

## Configuration Examples

### Simple Trigger (No Condition)

```yaml
entity_type: "Invoice"
workflow_id: "invoice_processing"
trigger_condition: null  # Always trigger
```

### Property-Based Trigger

```yaml
entity_type: "SecurityEvent"
workflow_id: "security_alert_urgent"
trigger_condition:
  severity: "critical"
```

### Range Filter Trigger

```yaml
entity_type: "PurchaseOrder"
workflow_id: "executive_approval"
trigger_condition:
  amount:
    $gte: 50000  # Amount >= $50,000
```

### Logical Operator Trigger

```yaml
entity_type: "SupportTicket"
workflow_id: "escalate_to_vip_support"
trigger_condition:
  $and:
    - severity: "high"
    - customer_tier: "enterprise"
```

---

## Trigger Operators

Supported operators in trigger conditions:

- **Equality**: `{"property": "value"}`
- **Comparison**: `{"$gt": 100}`, `{"$gte": 100}`, `{"$lt": 100}`, `{"$lte": 100}`
- **In List**: `{"$in": ["value1", "value2"]}`
- **Not In List**: `{"$nin": ["value1", "value2"]}`
- **Regex**: `{"$regex": ".*@company.com$"}`
- **Exists**: `{"$exists": true}`
- **Logical**: `{"$and": [...]}`, `{"$or": [...]}`, `{"$not": {...}}`

---

## Debouncing

Workflow triggers include automatic debouncing to prevent duplicate triggers:

- **TTL**: 5 minutes (configurable)
- **Hash Based**: Entity type + key properties
- **Cache**: In-memory cache of recent triggers

```python
# Force trigger (skip debounce)
triggered = await service.check_and_trigger(entity, force_trigger=True)

# Clear debounce cache
service.clear_debounce_cache()
```

---

## Trigger History

All triggered workflows are tracked in trigger history:

```python
# Get trigger history for an entity
history = service.get_triggered_workflows(entity_id="entity-001")

# Output:
[
  {
    "triggered_at": "2026-05-05T10:30:00Z",
    "triggered_workflows": ["po_approval"],
    "entity_type": "PurchaseOrder"
  }
]
```

---

## Best Practices

1. **Use Specific Conditions**: Avoid overly broad triggers that fire too frequently
2. **Set Appropriate Priorities**: Higher priority workflows execute first
3. **Test Triggers**: Use dry-run mode to test triggers before production
4. **Monitor Trigger Rates**: Track trigger frequency to detect spam
5. **Document Workflows**: Keep workflow documentation up to date

---

## Next Steps

- Create custom workflow templates for your use cases
- Register workflow triggers in your application initialization
- Monitor trigger analytics to optimize performance
- Iterate on trigger conditions based on feedback

---

*Documentation Updated: 2026-05-05*
*Phase: 323-05*
