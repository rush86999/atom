# Goal 9 — atomic concurrent budget admission/reservation: full negative evidence

Date: 2026-11-10. Read-only diagnosis plus scratch production-consumer
reproduction. **No product code was changed and no reservation repair was
implemented.** The specified durable `90 + 7 + 7 = 104` race is **not
confirmed end-to-end**, and two real hard-stop defects are confirmed. Root
review is required before any successor slice (including Goal 3).

## Identities

- Current main: `0d5132c2e060a5f2ac338bca143c5e138e607658`
- Branch: `codex/goal9-concurrent-budget-admission-20261110`
- Base: current main; backend-sparse worktree; no root/graduation/Office edits
- Scratch SQLite only; doubled LLM response + controlled pricing stub; no
  provider/model/network/live DB/spend.

## Neighborhood read before editing

Parallel budget/spend mechanisms and their callers:

| Mechanism | Write path | Read/enforcement path | Callers |
|---|---|---|---|
| Durable tenant ledger | **No production writer found** for `TokenUsage.cost_usd` / `ACUConsumption.acu_cost` (only tests/migrations seed them) | `SpendAggregationService.get_total_spend` → `BudgetEnforcementService.check_budget_before_action_sync` | `AgentGovernanceService._check_budget_sync/_async`, `GenericAgent._check_budget_before_react`, `AtomMetaAgent._check_budget_before_react`, MCP/tool dispatch |
| In-memory workspace/day tracker | `BYOKHandler._record_provider_usage` → `llm_usage_tracker.record(...)`; also `LLMService` embeddings | `llm_usage_tracker.is_budget_exceeded(workspace_id)` in `BYOKHandler` | BYOK/LLM completion and gateway paths |
| In-memory gateway alerts | `record_gateway_spend` | notification-only `_daily_spend` | OpenAI gateway route |
| Durable gateway log | `GatewayRequestLog.cost_usd` via `log_gateway_request` | **Not read by** `SpendAggregationService` | Gateway route/log API |
| Personal budget | `personal_budget_service.record_spend` | logging/forecast only; no write to the ledger | `agent_execution_service` |

Key source facts:

- `BudgetEnforcementService.check_budget_before_action_sync`
  (`backend/core/budget_enforcement_service.py:90`) reads
  `SpendAggregationService.update_tenant_spend(..., persist=False)`; it never
  reserves. Its error branches explicitly fail open:
  - unreadable spend (`"error" in spend_result`) returns `allowed=True,
    enforcement_mode="unknown"`;
  - the `except Exception` at ~line 252 returns `allowed=True,
    reason="Unable to verify spend", enforcement_mode="unknown"`.
- `SpendAggregationService.get_total_spend`
  (`backend/core/spend_aggregation_service.py:61`) sums `ACUConsumption.acu_cost`
  and `TokenUsage.cost_usd`.
- `BYOKHandler._record_provider_usage`
  (`backend/core/llm/byok_handler.py:4155`) computes cost from the pricing
  fetcher and calls `llm_usage_tracker.record`; it does **not** insert a
  `TokenUsage` row. A pricing exception leaves `cost=None` and records
  `cost_usd=0.0`.
- `llm_usage_tracker.set_budget` (`backend/core/llm_usage_tracker.py:115`) has
  **no production caller**; `is_budget_exceeded` returns False when no budget
  is set. The BYOK hard guard is therefore inert against the configured tenant
  setting.
- `personal_budget_service.record_spend`
  (`backend/core/personal_budget_service.py:341`) only logs.
- `GatewayRequestLog.cost_usd` is durable but `SpendAggregationService` never
  reads it.

## Reproduction (scratch, doubled provider, real consumers)

Admission consumer: `AgentGovernanceService.can_perform_action_async` (the
same budget path used by GenericAgent/AtomMetaAgent tool dispatch).
Settlement consumer: `BYOKHandler._record_provider_usage` with a doubled
response and a controlled pricing stub.

Seed: tenant limit $100, hard_stop, current durable spend $90.

1. **Specified durable race — NOT confirmed through the production consumer.**
   Two admissions at $90 both allow. Two production settlements at $7 each are
   recorded only in the in-memory tracker (usage 14; budget unset;
   `is_budget_exceeded=False`). The durable `TokenUsage` ledger stays **$90**
   (row count 1); a third admission still allows. The joint 104 does not exist
   in the configured ledger.
2. **Counterexample preserved (harness-authored twin, explicitly not
   production).** Each request alone fits: 90 + 7 = 97 < 100. Two admissions
   at 90 both allow. If the intended durable settlement rows existed
   (two × $7 in `TokenUsage`), the ledger would be **104** and the next
   hard-stop admission refuses. This proves the preflight is non-atomic **if**
   settlement were durable; the production path is not that path.
3. **Configured hard-stop unreadable budget — confirmed unsafe fail-open.**
   With hard_stop and `update_tenant_spend` returning `{"error": ...}`, the
   admission returns `allowed=True`, `enforcement_mode="unknown"`,
   `reason="Unable to verify spend"`.
4. **Configured hard-stop failed admission exception — confirmed fail-open.**
   With the spend read raising, the explicit `except` returns `allowed=True,
   enforcement_mode="unknown"`; the real governance consumer inherits the
   same allow.
5. **Settlement pricing error — confirmed 0/unknown conflation.** A pricing
   failure is swallowed; `_record_provider_usage` returns cost `None` and the
   in-memory tracker records `$0`; the durable ledger is unchanged and
   hard-stop still admits. `0` (genuinely free) and `unknown` are not
   distinguished.
6. **Observe/warn semantics remain distinct.** `alert_only` over budget still
   admits by design; the unsafe behavior is specifically the hard-stop
   unknown/unreadable path. soft-stop's active-episode allowance is a separate
   observed mode.

Reproduction tests: `backend/tests/test_goal9_budget_ledger_negative.py`
(8 tests). The concurrent-check test's `persist` keyword lambda fix
(`backend/tests/integration/budget/test_concurrent_budget_checks.py`) is a
**test-harness compatibility fix only**; it is not a product repair and is not
counted as race proof.

## Gates

- Focused negative file: **8 passed**, exit 0
  (`gates/negative-focused.log`).
- Affected selection (new file + real MCP budget authority + caller
  transaction + service + concurrent checks + budget control): **100 passed**,
  exit 0 (`gates/affected-selection.log`).
- Product files byte-unchanged; only the two test files changed
  (`source/source-hashes.json`).
- No root/graduation/Office worktree edits; no browser/model/provider/live DB;
  no CI/PR/merge.

## Required contract (recommendation; not implemented)

1. **Hard-stop unknown is not an allow.** A configured hard_stop with an
   unreadable budget, failed admission, or unknown estimate must refuse or
   require an explicit operator override. `alert_only` may remain observe/warn;
   `soft_stop` may keep its active-episode allowance. Do not claim the cap is
   enforced when the code fails open.
2. **Truthful settlement.** Persist actual spend into the existing
   `TokenUsage`/ACU ledger from the production settlement path; represent
   `0` and `unknown` distinctly (unknown must not be written as `0`).
3. **Existing shared mechanism, no parallel store.** Reserve against the same
   tenant budget/window/mode/limit and ledger
   (`TenantSetting['billing']` + `TokenUsage`/`ACUConsumption` +
   `SpendAggregationService`). Add an atomic conditional write/reservation on
   that ledger before provider dispatch, reconcile to actual settlement,
   release on failed/refused dispatch, and do **not** blindly release on
   cancellation/timeout while the worker may still spend (reconcile to
   incurred/input cost, as LiteLLM does). Reservation state must survive
   restart and bind the configured scope/window/limit at admission. A schema
   change is justified only if `TokenUsage.billed` cannot represent
   reserved/settled/released/uncertain; the reason must be explicit.
4. **No hard cost cap with unbounded provider cost.** Reserve an authoritative
   server-owned upper bound from the existing cost contract; do not accept a
   client guess. If no estimate exists, fail closed (or require explicit
   opt-in) rather than silently falling back to read-time enforcement.
5. No general PostgreSQL/soak claim from SQLite; a real Postgres qualification
   is a separate environment gate.

## Mature references (read before proposing a repair)

- LiteLLM `litellm/proxy/spend_tracking/budget_reservation.py`
  (https://github.com/BerriAI/litellm/blob/main/litellm/proxy/spend_tracking/budget_reservation.py):
  `reserve_budget_for_request` estimates a max request cost, reserves
  counters atomically before the provider call, rejects over-budget; 
  `reconcile_budget_reservation` settles actual cost; 
  `release_budget_reservation_on_cancel` reconciles in-flight cancellation to
  input cost (not zero) and shields the reconcile; lease renewal keeps a
  reservation alive across long requests; `fail_closed_budget_enforcement`
  rejects when the reservation cannot be written.
- LiteLLM PR #34103 (atomic project budget reservation) and issue #35524:
  when no estimate exists, the reservation path returns without reserving and
  falls back to read-time enforcement, which is **not atomic** and can
  overshoot under concurrency. This is the same no-estimate boundary ATOM
  faces.
- SQLAlchemy 2.0: Using UPDATE and DELETE Statements
  (https://docs.sqlalchemy.org/en/20/tutorial/data_update.html) and Embedding
  SQL Expressions into a Flush / persistence techniques
  (https://docs.sqlalchemy.org/en/20/orm/persistence_techniques.html) —
  `UPDATE ... SET spend = spend + :reserve WHERE spend + :reserve <= :limit`
  is an atomic conditional write; ORM attribute assignment alone is not.
- PostgreSQL UPDATE
  (https://www.postgresql.org/docs/current/sql-update.html): `WHERE`,
  `RETURNING`, and row locking (`FOR UPDATE` / `SKIP LOCKED`) are the
  database-level primitives for an atomic reservation/settlement; SQLite
  scratch can model the conditional update but does not qualify Postgres
  concurrency.

## Decision / next

No product repair was implemented because the specified durable race is not
confirmed through the production consumer; the actual defects are the missing
durable settlement, the unconfigured in-memory guard, and the hard-stop
fail-open/settlement-error conflation. Root owns the decision on the
ledger/settlement design and any reservation repair. Goal 3 (joined document
lifecycle) is not started and remains pending root review.

## Non-claims

143 claims / 18 goals preserved; no self-acceptance; no historical score
change; no whole-app or Postgres/soak claim. The tests pin the current unsafe
behavior as negatives; they are not a pass for the configured cap.
