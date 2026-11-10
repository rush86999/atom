# Goal 9 — durable settlement + hard-stop unknown fail-closed

Date: 2026-11-10. This is the implementation phase authorized after the
accepted negative packet `b0a5c04e` (negative evidence only, not Goal 9 pass).
It adds durable actual-cost settlement and makes configured hard-stop refuse
on unknown/unreadable budget. **It does not claim atomic concurrent
reservation**; that remains deferred.

## Branch / base

- Branch: `codex/goal9-durable-settlement-20261110`
- Base: `b0a5c04e7069fae43b74f2cac91699fcb741e673` (accepted negative
  evidence; current main product bytes `0d5132c2e`)
- Backend-sparse worktree; no root/graduation/PR829/PR831/active-UI edits.
- Scratch SQLite, doubled LLM response, controlled pricing stub only; no
  provider/model/network/live DB/live spend/send.

## Design decision: one authoritative ledger

`TokenUsage` is the single authoritative durable usage/accounting ledger.
`SpendAggregationService` already reads it, and the budget admission already
binds to it, so no parallel budget store/engine is introduced. The existing
in-memory `llm_usage_tracker` remains a diagnostic/cache only.

Existing durable measurements traced before choosing the extension:

| Mechanism | Contains actual cost? | Full LLM path? | Budget-read? | Decision |
|---|---|---|---|---|
| `TokenUsage` | yes (cost_usd) | writer was missing | yes (`SpendAggregation`) | **authoritative ledger** |
| `ACUConsumption` | yes (acu_cost) | hosting only | yes | unchanged, additive with TokenUsage |
| `LLMRoutingFeedback` | yes (`actual_cost`) | routing feedback only; tenant/model/task, no provider/attempt/workspace | no | not used for LLM settlement |
| `GatewayRequestLog` | yes (`cost_usd`) | gateway route only | no | not used; would double-count if also written |
| `RateUsageRecord` | no (tokens only) | quota-aware calls | no | not a cost ledger |
| `LLMCallTracker` | no | per-attempt instrumentation | no | in-memory diagnostics |
| `llm_usage_tracker` | yes (float, 0 on unknown) | LLM handler | no | diagnostic/cache only |
| `personal_budget_service` | no (logging only) | agent execution | no | not a ledger |

The existing shared feedback CAS/transport/scope was not rewritten; no
`LLMRoutingFeedback` quality classifier was touched. Spend is never filtered
by semantic quality/grounding/fabrication verdict: a paid failed attempt is
still recorded.

## Implemented changes

### Durable ledger (`backend/core/models.py`)

`TokenUsage` now supports legitimate agent and non-agent calls without
inventing ownership:

- `agent_id`, `tenant_id`, `model_name` nullable (non-agent calls; unknown
  ownership is NULL, never defaulted).
- `provider_id`, `request_id`, `attempt_id` (server-owned identity);
  `attempt_id` is unique for idempotent settlement.
- `pricing_status` (`priced` / `free` / `unknown`); `cost_usd` remains
  numeric but unknown is explicitly `unknown`, not silently free 0.

### Settlement (`backend/core/spend_aggregation_service.py`)

`record_llm_usage(...)` writes one `TokenUsage` row in a **dedicated session**
(never commits caller work):

- `cost_usd=None` + `pricing_status="unknown"` for unavailable pricing;
  `0.0` + `free` for known-free; otherwise `priced`.
- `attempt_id` idempotency: replaying the same attempt returns the existing
  row; different material under the same key is a conflict, never a second
  charge. Multiple distinct attempt ids count separately.
- Supports `agent_id=None` and `tenant_id=None` without invented identities.
- `SpendAggregationService.get_unpriced_usage(tenant_id)` counts unknown rows
  (status unknown or legacy NULL cost) for the current window.

### Production call paths (`backend/core/llm/byok_handler.py`)

`_record_provider_usage` now settles every usage-bearing provider attempt into
`TokenUsage` in addition to the diagnostic tracker, with provider/model,
tokens, cost (None/0 distinction), scope, request id, and attempt id:

- non-streaming `generate_response` (all provider attempts, including empty
  visible output that still billed),
- `generate_chat_completion` success and empty-output attempts,
- `generate_structured_response` success and missing-output attempts,
- streaming: provider stream usage is not reliably exposed by every provider;
  an explicit **unknown/unpriced** request row is recorded (`pricing_status
  unknown`) rather than 0. This is a truthful liability; a hard stop refuses
  until reconciled.

### Hard-stop fail-closed (`backend/core/budget_enforcement_service.py`)

- Unreadable spend (`"error"` or exception) with configured `hard_stop` now
  refuses with `BUDGET_STATUS_UNAVAILABLE`; it no longer returns
  `allowed=True/unknown`.
- Unknown-priced rows with `hard_stop` refuse with `BUDGET_UNPRICED_USAGE`
  and an actionable reconciliation reason; known-free 0 remains allowed.
- `alert_only` / `soft_stop` observe/warn semantics are preserved (they may
  allow unknown/unpriced work with warnings).
- The governance refusal wrapper preserves the actionable status code instead
  of overwriting every refusal with `BUDGET_EXCEEDED`.

### Migration

`migration.sql` contains the reversible DDL (Postgres; SQLite notes). It was
**not applied** to any live DB. No Alembic revision file was added because the
current `backend/alembic/versions` tree has 42 divergent heads and no single
safe `down_revision`; adding a 43rd head would be misleading. The owner applies
the DDL through the normal process.

## Failure-first verification (scratch)

`backend/tests/test_goal9_durable_settlement.py` (12 tests):

- 90 durable + 7 settlement = 97; second 7 = 104; next hard-stop admission
  refuses (`BUDGET_EXCEEDED`). Each request alone fits; joint exceeds.
- Duplicate `attempt_id` replays idempotently (97, one row; not 104).
- Two distinct paid attempts count separately (104).
- Restart read from a new engine/session sees 97.
- Tenant scope binding: another tenant sees 0.
- Agent vs non-agent settlement; non-agent `agent_id=None`; unknown tenant
  remains NULL, not defaulted.
- Unknown price (`cost=None`) is `unpriced` (ledger sum unchanged; hard-stop
  refuses `BUDGET_UNPRICED_USAGE`); known free `0.0` is allowed.
- Hard-stop unreadable ledger refuses `BUDGET_STATUS_UNAVAILABLE`;
  `alert_only` still observes/allows.
- Failed-semantic paid attempt still records its cost (no quality filter).
- Conditional harness 104 twin preserved (explicitly harness-authored).
- Normal 50-under / 100-at-cap valid twin preserved.

Gates:

- focused: **12 passed**, exit 0 (`gates/focused.log`)
- affected budget selection (new file + real MCP budget authority + caller
  transaction + service + concurrent checks + budget control + governance
  matrix): **200 passed**, exit 0 (`gates/affected.log`)

## Retained original negative / conditional twin

`retained_negative/pre-fix.test.py` and `pre-fix-negative.log` are the exact
pre-fix characterization (in-memory-only settlement, hard-stop fail-open,
unknown-as-zero) from accepted `b0a5c04e`. They are retained verbatim as
historical evidence; the active tests now assert the fixed contract. The
conditional harness 104 twin remains in the active test file, explicitly
labelled harness-authored, not production evidence.

## What is still open / honest cap

- **Atomic concurrent reservation is deferred.** The durable settlement is now
  real, but two admissions can still both read 97 and pass before either
  settles 7. Check-only enforcement is non-atomic; no new cap claim is made.
  The next phase may add an atomic conditional reservation on this same
  `TokenUsage`/budget ledger (LiteLLM reservation pattern; see the negative
  packet's citations).
- Streaming cost is recorded as explicit unknown per request until provider
  stream usage is captured; a hard stop refuses it rather than treating it as
  free.
- SQLite scratch only; no PostgreSQL concurrency/soak qualification.
- 143 claims / 18 goals preserved; root owns final independent review/merge.
  No PR merge/approval, no root/PR829/831/active-UI edits.
