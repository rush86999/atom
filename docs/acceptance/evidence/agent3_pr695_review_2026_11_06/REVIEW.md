# Agent 3 independent review — merged #695 agent stop/cancel

Reviewer: Agent 3 (independent verification), 2026-11-06, per
`VERIFIER_PR695_DELIVERY_AND_PR698_STDERR_ACCEPTANCE_20261106.md`. Owner
merge `e93982eec`; code checkpoint `1faccf71c`; evidence/PR head
`3a3e55b41`; reviewed on current main. Recommendation to the lead; owner
authority separate.

## 1. Contract reviewed

`POST /api/agents/{agent_id}/stop` cancels an agent's running tasks with
current authority and scope, an exact-material claim, a durable
AuditLog receipt carrying the truthful cancelled count — replay does not
cancel newly started tasks; no-task stops are no-change without receipt;
receipt failure after a real cancellation reports effect unknown (the
cancellation already happened), never a false not-applied.

## 2. Identity

All 3 runtime files (`agent_routes.py`, `agent_decision_write_service.py`,
`test_agent_stop_scope_contract.py`) hash-identical across code checkpoint
`1faccf71c`, merge, branch tip `3a3e55b41`, and current main. Bundle
`employee_agent_stop_1faccf71c/`: **7/7 declared sources hash-match at the
executed source and main** (`ci.yml` pin describes the executed state;
post-merge drift only), **10/10 artifacts hash-verified at main —
including the previously-missing-class run logs, which are committed**.
Complete and checkout-verifiable; the lead's 17/17 packaging check
independently confirmed.

## 3. Trace (shared engine, callers, task-registry semantics)

`stop_agent` reuses the established decision-write engine exactly:
`_resolve_actor` (MEMBER floor, AGENT_RUN authority label) → id/operation
validation → `_load_agent` + `_agent_visible` (foreign tenant/workspace →
404) → `_replay` keyed on (operation, agent, actor) →
`_active_task_count` == 0 → `_no_change` before any side effect →
`_claim_actor` guarded authority claim → exact-material CAS via
`_run_agent_predicates` (id/tenant/workspace/name/description/
capabilities/floor/status **plus configuration and enabled**) with
`.values(updated_at=...)` as a pure rowcount claim → real cancellation via
`agent_task_registry.cancel_agent_tasks` (per-task asyncio cancellation in
the process registry — **request-to-cancel semantics**: the agent's
durable material is deliberately unchanged, `result_digest =
prior_digest`, and no AgentJob/status transition is claimed) →
receipt-commit failure → `_effect_unknown` **with the truthful
`cancelled_tasks` count attached** (cancellation already occurred) →
audit verify + target readback (material unchanged) → verified.

Route is a thin pass-through mapping the decision envelope to HTTP.

## 4. Independent execution (Python 3.11.16, fresh `TESTING=1` scratch)

- **Decisive gate, once**: `tests/test_agent_stop_scope_contract.py`
  (9 controls) + `tests/api/test_agent_routes.py` (63 controls, pinned by
  the manifest) — **72 passed / 0 failed** (log: `stop-gate-311.log`).
- **Combined with Agent 3 probes, once**: **11 passed / 1 failed** (log:
  `stop-combined-gate-311.log`) — the single failure is the executable
  counterexample below, not a service defect.
- Author's 74-focused (both Pythons) and affected/baseline identities
  (zero added failures) remain author/CI evidence; committed logs
  hash-verified.

## 5. Agent 3 probes (genuinely missing cases)

1. **`enabled` flip before claim** (the submitted target-change control
   covers `configuration`) → 409 `STALE_TARGET`, peer values preserved,
   zero cancel calls, zero audits. **Passes.**
2. **Competing different-operation stop after a successful stop** → 200
   no-change with `cancelled_tasks: 0`, no second receipt/audit; the
   no-task gate short-circuits before the registry call. **Passes.**
3. **Receipt-failure 503 truthfully reports the cancelled count** →
   **FAILS on merged source** — the executable counterexample for the
   finding below.

One probe-authoring iteration recorded: my first draft asserted the
registry cancel-call sequence after the competing stop; the no-task gate
correctly short-circuits before the call, so the sequence assertion was
wrong and the contract outcome (200 no-change, no receipt) was right.

## 6. Finding — bounded consumer gap (Agent 2's lane)

The stop service's receipt-failure path deliberately attaches
`result["data"] = {"agent_id", "cancelled_tasks"}` — the truthful record
of a cancellation that already happened. The route's
`committed_unverified`/`effect_unknown` branch of `_raise_agent_decision`
projects `error`, `verification`, `operation_id`, `audit_id` — but **drops
`result["data"]`** from the HTTPException detail. The truthful cancelled
count therefore never reaches the HTTP surface: the user sees "effect
unknown" with no indication that tasks were actually cancelled or how
many. Service-layer truthfulness is already proven by the submitted
receipt-failure control; this is purely the HTTP projection. Executable
counterexample: probe 3 (committed). Suggested repair for Agent 2:
project `result.get("data")` in that branch (one line); the same branch
also serves `committed_unverified` (run admission's job identity) — worth
including in the same repair.

## 7. Recommendation to the lead

**Accept the merged #695 stop/cancel service contract at its tested
scope**: all 9 submitted controls plus Agent 3's enabled-CAS and
competing-stop probes pass on this runtime, identities are clean end to
end, the request-to-cancel vs durable-state semantics are correctly
distinguished, and the receipt-failure path is truthful at the service
layer. **One bounded consumer-gap finding** (§6) accompanies the verdict
with an executable counterexample for Agent 2 — it does not block
acceptance of the service contract but should be repaired before the
effect-unknown user surface is relied on.
