# Goal 9 — durable settlement + hard-stop unknown fail-closed

Date: 2026-11-10. This is the implementation phase authorized after the
accepted negative packet `b0a5c04e` (negative evidence only, not Goal 9 pass).
It adds durable actual-cost settlement, makes configured hard-stop refuse on
unknown/unreadable budget, and upgrades a real pre-change SQLite install
through the app's existing startup repair hook. **It does not claim atomic
concurrent reservation**; that remains deferred.

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
`LLMRoutingFeedback` quality classifier was changed. Spend is never filtered
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
- `pricing_status` (`priced` / `free` / `unknown`) is the cost authority;
  `cost_usd` has no default, so unknown is truly NULL and is never silently
  converted to free 0.

### Settlement (`backend/core/spend_aggregation_service.py`)

`record_llm_usage(...)` writes one `TokenUsage` row in a **dedicated session**
(never commits caller work):

- `cost_usd=None` + `pricing_status="unknown"` for unavailable pricing;
  `0.0` + `free` for a trusted known-free contract; otherwise `priced`.
- `attempt_id` idempotency: replaying the same attempt returns the existing
  row; different material under the same key is a conflict, never a second
  charge. Multiple distinct attempt ids count separately.
- Supports `agent_id=None` and `tenant_id=None` without invented identities.
- `SpendAggregationService.get_unpriced_usage(tenant_id)` counts unknown rows
  for the current window; `get_unattributed_unpriced()` counts unknown rows
  with no tenant (unresolved scope).
- A failed settlement write sets a process-local degraded marker
  (`settlement_failure_reason()`), so hard-stop refuses rather than treating
  the lost write as successful budget. It is not a second ledger and is reset
  only by restart/explicit reconciliation.

### Durable paid-liability intent (`begin_llm_usage`)

Before a paid provider dispatch, the handler writes one `TokenUsage` row with
the exact server-owned `attempt_id`, `pricing_status="unknown"`,
`cost_usd=NULL` and `billed=False`. This is the existing ledger's pending
intent, **not** a parallel store:

- if the intent cannot be persisted, the provider is **not dispatched**
  (fail closed); the structured path that previously retried the refusal was
  fixed to exit the request-recovery loop (see retained negative
  `structured-intent-loop-review.json`);
- a successful settlement updates that exact row once (`billed=True`, actual
  tokens/cost/status); a replay is idempotent; a different material after
  settlement is a conflict;
- a provider success followed by a settlement write failure leaves the
  pending/unknown row in place. A restart reads the same `TokenUsage` row, so
  hard-stop still refuses `BUDGET_UNPRICED_USAGE` instead of forgetting the
  charge;
- timeout/failure does not delete or release the liability row; only an
  explicit reconciliation settles it;
- hard-stop counts any `cost_usd IS NULL` row or `pricing_status="unknown"`,
  so a NULL cost with a non-unknown status is not admitted as known-free.
  Only an explicit `free` / `0.0` settlement is known free.

`test_durable_intent_survives_restart_when_settlement_write_fails` runs the
real structured consumer with the provider paid, forces the settlement write
to fail, observes `BUDGET_UNPRICED_USAGE`, then reads the same scratch DB
through a fresh engine/session and observes the same refusal. The bounded
`test_no_provider_dispatch_when_durable_intent_cannot_persist` has a 10s
deadline, asserts zero provider calls, one/two bounded refusal logs, and no
intent row. `test_settle_exact_intent_once` covers update-once/replay/conflict.

### Pending settlement CAS (root source-review concern)

The first pending-settlement implementation could reassign non-None
tenant/workspace/agent/execution/chain values and relied on an ordinary ORM
commit, so two stale pending writers could overwrite each other. The fix uses
one database conditional UPDATE (the same shared CAS shape as the accepted
feedback path; no new table/store/engine):

- the immutable intent binding is exactly
  `request/attempt/provider/model/agent/workspace/tenant/execution/chain`;
  `None` is a real binding value, not "inherit from the caller";
- a settlement binding contradiction is refused before any write and never
  reassigns the scope; omitted fields do not silently take the caller's value;
- the UPDATE matches only the exact binding while the row is still
  `pricing_status="unknown"` and `cost_usd IS NULL` (pending or weak unknown).
  A priced/free actual settlement is never overwritten by a stale actual or
  unknown writer;
- zero rows affected -> rollback + reload the authoritative row; an exact
  material replay returns the existing id, anything else is a conflict/refusal;
- distinct actual attempts still each have their own `attempt_id` and all
  count; this is **not** an atomic budget reservation claim.

`test_pending_cas_two_sessions_actual_survives_stale_writers` preloads the same
pending row in two sessions, settles an actual 7.0 in session A, then has stale
session B attempt a conflicting 9.0, an exact duplicate 7.0, and an unknown
NULL writer; only the exact duplicate is idempotent, the actual value survives,
and a scope contradiction leaves the authoritative row unchanged. This is
source-level + scratch runtime proof; the root's independent source review and
any concurrency qualification remain separate.

### Scope / identity trace (production call path)

The real path is `LLMService` → trusted handler selection → `BYOKHandler` →
`_record_provider_usage` → `record_llm_usage`:

- `LLMService.generate`, `stream_completion`, and
  `generate_structured_response` select the handler with **both**
  `workspace_id` and `tenant_id` (`_get_handler`). A named tenant with no
  unique workspace binding returns `None` and the call refuses **before**
  provider dispatch; no default/guessed tenant or workspace is substituted.
- `BYOKHandler` is constructed with that trusted `(workspace, tenant)` pair.
  `_record_provider_usage` reads `self.workspace_id`/`self.tenant_id` and the
  call-local `agent_id`/`chain_id`; it does not read ambient request context
  or a “current reader”.
- `request_id` is server-owned per cascade/decision and `attempt_id` is stable
  per actual paid generation, so duplicate persistence is idempotent and
  multiple paid fallback attempts remain distinct.
- The structured path creates its settlement identity (UUID) **once before**
  the provider loop; it is not derived from a caller-supplied
  `route_trace_id`, so two independent no-trace/pinned calls with identical
  usage material cannot collapse onto one unique `attempt_id`.
- Unresolved/unknown scope is stored as NULL and remains visible to hard-stop
  via `BUDGET_UNATTRIBUTED_USAGE`; it is never assigned to a tenant by guess.

### Production call paths (`backend/core/llm/byok_handler.py`)

`_record_provider_usage` settles every usage-bearing provider attempt into
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
- a response that carries no usage is recorded as explicit unknown, not
  dropped; an explicit trusted `known_free=True` contract records
  authoritative 0 even without usage (no model-name/brand assumption).

### Structured settlement identity (frozen-75 review)

The previous draft derived the structured settlement `request_id` from
`route_trace_id` and fell back to a global `structured` prefix. Two
independent no-trace/pinned calls with the same material could then share
`structured:1`, colliding with the unique `attempt_id`. The fix creates a
fresh server-owned UUID **once before the provider loop** and uses it for both
`request_id` and the per-attempt key. It is not a client header, not ambient
reader ownership, and not regenerated for a replay of the same settlement.

`test_structured_no_trace_calls_get_distinct_server_identities` drives the
real `generate_structured_response` consumer twice with `route_trace_id=None`
and identical usage material, asserts two distinct rows/attempt ids, then
replays the first settlement and asserts it stays one row.

An earlier durable-intent repair produced a real-consumer runaway: the
structured inner request-recovery `while True` loop retried the
intent-unavailable branch instead of leaving it. The fix re-raises
`_DurableUsageIntentUnavailable` out of that loop so the caller fails closed;
the bounded zero-dispatch test above pins it. The root-preserved negative is
`retained_negative/structured-intent-loop-review.json`.

### Hard-stop fail-closed (`backend/core/budget_enforcement_service.py`)

- Unreadable spend (`"error"` or exception) with configured `hard_stop` now
  refuses with `BUDGET_STATUS_UNAVAILABLE`; it no longer returns
  `allowed=True/unknown`.
- Unknown-priced rows with `hard_stop` refuse with `BUDGET_UNPRICED_USAGE`
  and an actionable reconciliation reason; known-free 0 remains allowed.
- Unknown/unattributed liability reads travel with the spend read
  (`include_liabilities=True`). A read failure becomes
  `spend_result["error"]`, and hard-stop refuses
  `BUDGET_STATUS_UNAVAILABLE`; it no longer silently treats the count as 0.
- Unknown-cost rows with no resolved tenant refuse with
  `BUDGET_UNATTRIBUTED_USAGE` (they do not disappear because they lack a
  tenant id).
- A failed durable settlement write refuses with
  `BUDGET_STATUS_UNAVAILABLE` under hard-stop immediately. The pending
  unknown/liability row is already durable, so after a process restart the
  same attempt still refuses (`BUDGET_UNPRICED_USAGE`); the charge is not
  forgotten. The process-local degraded marker is only an immediate signal,
  not the durability mechanism.
- A failed `token_usage` startup upgrade also refuses
  `BUDGET_STATUS_UNAVAILABLE` under hard-stop, rather than running against a
  legacy ledger that cannot represent non-agent/unknown rows.
- `alert_only` / `soft_stop` observe/warn semantics are preserved (they may
  allow unknown/unpriced work with warnings).
- The governance refusal wrapper preserves the actionable status code instead
  of overwriting every refusal with `BUDGET_EXCEEDED`.

### Existing-install upgrade (the supported startup path)

The app's actual SQLite upgrade hook is
`core.sqlite_schema_repair.repair_known_drift()`, called at
`backend/main_api_app.py:478` **before** `Base.metadata.create_all`. This
change extends that same hook with `ensure_token_usage_upgrade()`:

- detects legacy `NOT NULL` `agent_id`/`tenant_id`/`model_name` or missing
  `provider_id`/`request_id`/`attempt_id`/`pricing_status`;
- rebuilds `token_usage` in place (SQLite cannot drop NOT NULL), copying
  **every existing column** so rows/IDs/values survive;
- when a partially upgraded legacy table already has `pricing_status`, copies
  it with `COALESCE(..., 'priced')`, preserving `unknown`/`free`/`priced` and
  NULL `cost_usd` instead of defaulting every row to `priced`;
- carries unknown/custom columns as TEXT, preserves existing FK clauses (and
  adds the known model FKs if absent), and recreates every explicit custom
  index; if a custom index cannot be recreated, the rebuild is rolled back
  rather than silently losing it;
- recreates the unique `attempt_id` index and reruns idempotently;
- records the repaired key only **after success**. A failed upgrade is
  retryable in-process and sets a process-local failure reason that makes a
  configured hard-stop refuse `BUDGET_STATUS_UNAVAILABLE` until the ledger is
  usable;
- supports the new non-agent / unresolved-scope / unknown-cost contract after
  upgrade.

`backend/tests/test_goal9_token_usage_upgrade.py` covers three real fixtures
through that startup hook (not a hand-written migration):

1. the full legacy schema with NOT NULL agent/tenant/model, prior rows,
   explicit index and FKs; negative-before-upgrade insert rejected, then
   rows/IDs/indexes/FKs preserved, new non-agent/unknown row accepted, rerun
   idempotent;
2. a **partial-schema twin** that already has `pricing_status` values
   `unknown`/`free`/`priced`, a NULL status, NULL/0/positive cost, a custom
   column and a custom index; all flags/data/indexes survive and a rerun
   preserves them (this is the full supported-upgrade twin for the preserved
   reviewer negative `retained_negative/partial-upgrade-review.json`);
3. a forced-failure test proving the key is not marked repaired and the
   failure reason is recorded for hard-stop.

### Migration lineage / reversible DDL

`migration_lineage.md` records the exact landscape and all 42 heads/owners:
`backend/alembic/versions` has **42 revisions / 42 heads** and **no revision
mentions `token_usage`**. Adding a 43rd head would be misleading, so no
Alembic revision/merge head was invented. `migration.sql` contains the
reversible PostgreSQL DDL (SQLite notes) and was **not applied** to any live
DB. Official Alembic guidance for heads/branches and SQLite batch rebuilds is
cited in `migration_lineage.md` and the commit:
https://alembic.sqlalchemy.org/en/latest/branches.html and
https://alembic.sqlalchemy.org/en/latest/batch.html.

## Failure-first verification (scratch)

`backend/tests/test_goal9_durable_settlement.py` (26 tests):

- 90 durable + 7 settlement = 97; second 7 = 104; next hard-stop admission
  refuses (`BUDGET_EXCEEDED`). Each request alone fits; joint exceeds.
- Duplicate `attempt_id` replays idempotently (97, one row; not 104).
- Two distinct paid attempts count separately (104).
- Restart from a new engine/session sees 104 in SpendAggregation **and** the
  next production admission refuses.
- Tenant scope binding: another tenant sees 0.
- Agent vs non-agent settlement; non-agent `agent_id=None`; unknown tenant
  remains NULL, not defaulted.
- Unknown price (`cost=None`) is unpriced (ledger sum unchanged; hard-stop
  refuses `BUDGET_UNPRICED_USAGE`); known free `0.0` is allowed.
- Known-free contract is authoritative 0 even when the response has no usage;
  no model-name/brand assumption.
- A response with no usage fields is recorded as explicit unknown, not dropped.
- Unresolved-scope unknown rows remain visible to hard-stop
  (`BUDGET_UNATTRIBUTED_USAGE`).
- Trusted handler scope carrier: settlement gets the handler's
  workspace/tenant and the call-local agent, never a guessed identity.
- `LLMService` selects the trusted handler scope or refuses an unresolved
  tenant before dispatch.
- Two independent no-trace `generate_structured_response` calls with identical
  usage material create two distinct server-owned attempt ids/rows; replaying
  one settlement stays one row.
- Durable intent: a provider success + forced settlement write failure leaves
  the pending/unknown row; hard-stop refuses, and a fresh engine/session
  (process restart) still refuses `BUDGET_UNPRICED_USAGE`.
- No provider dispatch when the durable intent cannot persist; bounded 10s
  call, zero provider calls, one/two bounded refusal logs.
- The exact pending attempt settles once; replay is idempotent; a different
  later material is a conflict.
- Two-session CAS interleaving: the actual settlement survives stale
  conflicting/unknown writers; exact duplicate replay is idempotent; a scope
  contradiction leaves the row unchanged.
- A NULL cost with non-unknown status is counted as a liability, not free;
  only explicit `free`/0.0 is known free.
- Hard-stop unreadable ledger refuses `BUDGET_STATUS_UNAVAILABLE`;
  `alert_only` still observes/allows.
- An unpriced/unattributed read failure refuses
  `BUDGET_STATUS_UNAVAILABLE` under hard-stop, not 0.
- A failed settlement write does not fake a successful budget: ledger stays
  90, caller work is not committed, no provider redispatch, hard-stop refuses
  `BUDGET_STATUS_UNAVAILABLE`, and it remains refused after the DB recovers.
- A failed `token_usage` upgrade is recorded and keeps hard-stop closed.
- Failed-semantic paid attempt still records its cost (no quality filter).
- Conditional harness 104 twin preserved (explicitly harness-authored).
- Normal 50-under / 100-at-cap valid twin preserved.

`backend/tests/test_goal9_token_usage_upgrade.py` (3 tests): full pre-upgrade
fixture, partial-schema twin preserving `pricing_status`/custom data/indexes,
and forced-failure retry/fail-closed proof through the startup hook.

Gates:

- focused (upgrade + durable/hard-stop): **29 passed**, exit 0
  (`gates/focused.log`)
- upgrade only: **3 passed**, exit 0 (`gates/upgrade.log`)
- affected selection (focused + real MCP budget authority + caller
  transaction + service + concurrent checks + budget control + governance
  matrix + personal budget + spend aggregation): **266 passed**, exit 0
  (`gates/affected.log`)

Coupled consumers reviewed: the nullability relaxation only changes rows that
legitimately have NULL agent/tenant; tenant/agent-scoped queries already
exclude those rows, and the new unattributed/unpriced hard-stop queries make
the liability explicit. `test_personal_budget.py` and
`test_covpush_w104_spend_aggregation.py` pass unchanged; no feedback CAS or
quality-classifier changes.

## Retained original negative / conditional twin

`retained_negative/pre-fix.test.py` and `pre-fix-negative.log` are the exact
pre-fix characterization (in-memory-only settlement, hard-stop fail-open,
unknown-as-zero) from accepted `b0a5c04e`. They are retained verbatim as
historical evidence; the active tests now assert the fixed contract.

`retained_negative/partial-upgrade-review.json` is the reviewer's pre-fix
partial-schema proof: a legacy NOT NULL table that already had
`pricing_status=unknown`/`cost_usd=NULL` was rebuilt to
`pricing_status=priced` by the earlier `ensure_token_usage_upgrade` (source
hash `dc64566e…`). It is retained as negative evidence; the fixed full
startup-hook twin is `test_partial_upgrade_preserves_pricing_status_and_custom_index`.

`retained_negative/structured-intent-loop-review.json` is the root-preserved
real-consumer runaway (original 560MB) where the structured inner
request-recovery loop retried the intent-unavailable branch. It is retained as
negative evidence; the fix re-raises out of that loop and the bounded
zero-dispatch test pins it.

The conditional harness 104 twin remains in the active test file, explicitly
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
- The settlement-write degradation marker is only an immediate signal; the
  durable pending/unknown `TokenUsage` row is what survives restart and keeps
  hard-stop refused. A failed upgrade marker is process-local but retryable
  on startup; hard-stop refuses while it is set. No parallel store is used.
- SQLite scratch only; no PostgreSQL concurrency/soak qualification.
- 143 claims / 18 goals preserved; root owns final independent review/merge.
  No PR merge/approval, no root/PR829/831/active-UI edits.
