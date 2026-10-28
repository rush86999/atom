# Canvas capability manifest (schema_version 1)

Stored on the canvas's authoritative `Canvas.content.capability_manifest`
row. It describes shape and declared operations; it never grants authority by
itself.

```json
{
  "schema_version": 1,
  "base_component": "table",
  "data_binding": {
    "resource_id": "canvas:<id>",
    "source_version": "<hash>",
    "subject_field": "Ref",
    "measure_field": "Amount",
    "status_field": "Status"
  },
  "operations": ["read", "select", "calculate", "assess", "edit", "export", "bind"],
  "editable_fields": ["Amount", "Status"],
  "teaching_binding": {"agent_id": "<employee>", "scope_id": "task"},
  "decision_options": ["APPROVE", "REVIEW", "DENY"],
  "task_policy": "Task-owned policy text.",
  "outputs": ["xlsx"],
  "required_approvals": []
}
```

Effective operations = declared ∩ adapter ∩ owner/workspace permission ∩
resource support. The bound dataset lives in `Canvas.content.dataset` with a
source hash and monotonic revision. Edits require the current revision and
are read back from the authoritative row. Fork/copy strips private teaching,
policy, approvals and source identity.
