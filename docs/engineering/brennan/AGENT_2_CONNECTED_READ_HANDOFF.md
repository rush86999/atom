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

## Registered draft/proposal

| Action | Inputs | Result |
|---|---|---|
| `brennan.books.propose_bill` | `proposal_input` | deterministic proposal with `status=proposed` or typed obligations; never posts |
| `brennan.books.create_bill` | `proposal`, `authority_reference`, `operation_id` | exact duplicate check, provider create, authoritative `get_bill` readback |
| `brennan.books.create_estimate` | `organization_id`, `estimate_data`, `authority_reference`, `operation_id` | provider create + `get_estimate` readback |
| `brennan.outlook.create_draft` | `to`, `cc`, `bcc`, `subject`, `body` | draft only; never sends |

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
