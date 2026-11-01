# Agent 2 → Agent 1 connected-read handoff

Base: `587fbc25148a6203f3785c46e56992ddcf54bd70`
Agent 2 branch: `codex/brennan-knowledge-accounting-20261101`

Use these through the existing `action.registry` assignment adapter. Read
actions declare `{"effect":"read"}`; the planner classifies them as
`read_only` and does not require an outbound grant. The draft action declares
`{"effect":"create"}` and requires an outbound/approval path.

## Registered reads

| Action | Inputs | Result |
|---|---|---|
| `brennan.workdrive.list_page` | `folder_id`, `workspace_id`, `team_id`, `cursor`, `page_size` | `items`, `next_cursor`, `has_more`, `read_receipt` |
| `brennan.workdrive.read_file` | `file_id`, `workspace_id`, optional `max_bytes` | `file`, `content_b64`, `sha256`, `bytes`, `read_receipt` |
| `brennan.onedrive.list_page` | `folder_id`, `drive_id`, `site_id`, `cursor`, `page_size` | `items`, `next_cursor`, `has_more`, `read_receipt` |
| `brennan.onedrive.read_file` | `file_id`, optional `max_bytes` | `file`, `content_b64`, `sha256`, `bytes`, `read_receipt` |
| `brennan.crm.get_record` | `module`, `record_id` | `data`, `read_receipt` |
| `brennan.crm.search_records` | `module`, `query` | `items`, `read_receipt` |
| `brennan.inventory.get_item` | `item_id`, optional `organization_id` | `data` (observed availability; not a reservation), `read_receipt` |
| `brennan.inventory.check_stock` | `item_id`, optional `organization_id` | observed stock, `read_receipt` |
| `brennan.books.get_bill` | `organization_id`, `bill_id` | `data`, `read_receipt` |
| `brennan.books.get_estimate` | `organization_id`, `estimate_id` | `data`, `read_receipt` |
| `brennan.workdrive.sync_page` | `folder_id`, `provider_workspace_id`, `team_id`, optional `cursor`, `page_size`, `fresh`, `max_rows` | one indexed page, `next_cursor`, `coverage`, durable `checkpoint`, `missing_external_ids` |
| `brennan.onedrive.sync_page` | `folder_id`, `drive_id`, `site_id`, optional `cursor`, `page_size`, `fresh`, `max_rows` | one indexed page, `next_cursor`, `coverage`, durable `checkpoint`, `missing_external_ids` |
| `brennan.knowledge.sync_status` | `provider` (`zoho_workdrive`/`onedrive`), folder/drive/site identity | `coverage`, `stale`, `age_seconds`, `checkpoint`, `missing_external_ids`, `last_error` |

`sync_page` persists the cursor and counters in the existing per-workspace
`IngestionSettings.usage_stats_json.sync_cursors` row. A call without a cursor
resumes an unfinished checkpoint; `fresh=true` starts a new complete
enumeration and retains the previous ID set for deletion comparison. A
complete re-listing returns disappeared items in `missing_external_ids` but
never deletes memory rows automatically. A revoked grant is persisted as
`coverage=revoked` and returned as a typed error.

The same surface is exposed to the UI as
`GET /api/document-ingestion/integrations/{integration_id}/sync-status` and
`POST /api/document-ingestion/integrations/{integration_id}/sync-page`.

## Registered draft/proposal

| Action | Inputs | Result |
|---|---|---|
| `brennan.books.propose_bill` | `proposal_input` | deterministic proposal with `status=proposed` or typed obligations; never posts |
| `brennan.books.create_bill` | `proposal`, `authority_reference`, `operation_id`, optional `payload_sha256`, `proposal_version` | exact duplicate sweep, provider create, authoritative `get_bill` readback and field comparison |
| `brennan.books.create_estimate` | `organization_id`, `estimate_data`, `authority_reference`, `operation_id`, optional `payload_sha256`, `artifact_version` | provider create + `get_estimate` readback and field comparison |
| `brennan.outlook.create_draft` | `to`, `cc`, `bcc`, `subject`, `body`, `operation_id`, optional `authority_reference`, `payload_sha256` | draft only; never sends |

Each write action signs the exact effect payload with the same
`_approval_payload_hash` the executor uses. The result carries
`payload_sha256` and `provider_receipt{operation_id, authority_reference,
payload_sha256, ...}`. If the caller supplies `payload_sha256`, a mismatch is
returned as `action_result=conflict` before any provider call.

Same-target financial writes are serialized in-process by the registered
action (the durable cross-process guarantee remains the executor's effect
arbiter). A second concurrent call for the same provider/organization/external
ID runs its duplicate sweep after the first readback and returns
`duplicate`/`proven_not_applied` instead of creating a second provider object.

Write results use the shared vocabulary:

| `action_result` | Meaning |
|---|---|
| `applied` | provider create returned an id and the authoritative readback matches the authorized payload |
| `proven_not_applied` | validation, authority, duplicate, digest or pre-dispatch failure; no effect was attempted |
| `uncertain` | the create may have landed (5xx, transport failure, unreadable create response, or readback unavailable) |
| `conflict` | the readback exists but differs from the authorized payload (total, vendor, reference, currency or date) |
| `unavailable` | no trustworthy provider result and the effect state cannot be proven |

The current `_action_registry_adapter` in `assignment_executor.py` wraps every
action result as `status=applied`. Agent 1 must map the action's
`action_result` into the executor outcome (`applied`, `uncertain`, or failed)
before marking the operation complete. Do not treat a `conflict` allocation as
applied.

## Receipt shape

Every read returns `status=success` plus:

```json
{
  "provider": "zoho_books",
  "operation": "get_bill",
  "resource_id": "bill-1",
  "version": "provider-version-if-any",
  "retrieved_at": "2026-11-01T...",
  "coverage": "single|paged|partial|bounded|complete",
  "fields": ["..."],
  "evidence": [{"kind": "file", "id": "...", "sha256": "..."}],
  "continuation": {"next_cursor": "...", "has_more": true}
}
```

Provider failures return `status=error` with `error_kind` in
`auth_expired|auth_revoked|auth_unavailable|unauthorized|not_found|rate_limited|
transient|invalid_request|parse_error|provider_error`, plus
`retryable`/`requires_reconnect`. They are never converted to an empty array.

## Required executor context

The action adapter supplies `workspace_id`, `user_id` (employee), `run_id`,
`assignment_id`, `agent_id`, `tenant_id` and task revision. The connected
actions resolve the provider token from that scope; do not pass a global token
in a normal plan.

Example planner step:

```json
{
  "step_id": "read-price-list",
  "title": "Read the authorized price list",
  "operation_type": "retrieve",
  "adapter": "action.registry",
  "effect": "read_only",
  "inputs": {
    "action": "brennan.workdrive.list_page",
    "arguments": {
      "folder_id": "folder-from-the-user-connection",
      "workspace_id": "workspace-from-the-user-connection"
    }
  }
}
```

For a write, the plan must obtain approval/authority first and pass the exact
proposal plus `authority_reference` and the durable `operation_id`. The action
performs a provider create and an authoritative readback; it does not send
email and does not auto-retry outside the shared assignment effect arbiter.

## Current controlled boundaries

- No live Zoho/Microsoft credentials in the base checkout; all verification is
  controlled/fixture based.
- WorkDrive/OneDrive paging and binary reads are implemented, but explicit
  SharePoint libraries require `site_id` + `drive_id`; `/me/drive` is not
  qualified for arbitrary SharePoint libraries.
- Zoho Books conditional-version headers are not claimed; changed remote
  objects are detected by readback and exact duplicate identity is checked
  before create.
- Outlook draft only; the previous one-use send authorization is exhausted and
  is not reused.

## Verification in the Agent 2 branch

- Provider contract matrix: no unresolved/missing business-critical rows.
- Focused provider + connected-action suite: **149 passed** after the current
  batch.
- Contract errors, CRM `create_record` argument shape, strict unavailable
  reads, WorkDrive/OneDrive error envelopes, binary file reads, exact duplicate
  and unauthorized-post controls have focused tests.
