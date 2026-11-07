# Verified agent stop/cancel — failure truth repair

Status: **submitted for independent verification.** Successor to merged
PR [#695](https://github.com/rush86999/atom/pull/695). The accepted
scope/authority/material/replay positives remain unchanged; this bundle covers
the three failure-outcome cases that were still incorrect. No merge or
deployment was performed.

## Confirmed defects

1. **Known cancellation hidden by HTTP 503.** The service envelope held
   `data.cancelled_tasks` after a receipt commit failure, but the shared
   `_raise_agent_decision` 503 projection omitted `data`. The caller therefore
   received uncertainty without the cancellation that actually happened.
2. **Unreadable task state became an empty set.** `_active_task_count` caught
   every registry read exception and returned `0`, producing HTTP 200 /
   `no_change` / `cancelled_tasks: 0` while tasks remained and no cancellation
   was attempted.
3. **Partial cancellation was labelled `effect=none`.** A cancellation-call
   exception returned HTTP 409 / `AGENT_TRANSACTION_ROLLED_BACK` /
   `effect=none` / replay-safe even when the registry had already removed a
   task. A database rollback cannot undo an external cancellation request.

Pre-fix, the exact five external probes were **3 failed, 2 passed** on both
Python 3.14 and 3.11.

## Repair

- **Typed task-state preflight.** `_active_task_state` distinguishes
  `available` from `unavailable`. An unreadable registry returns typed HTTP 503
  `AGENT_TASK_STATE_UNAVAILABLE` with `effect: none`,
  `replay: safe_after_refresh`, no cancellation and no receipt. A legitimately
  empty registry still returns HTTP 200 / `no_change`.
- **Truthful post-dispatch uncertainty.** An exception from
  `cancel_agent_tasks` now returns HTTP 503 / `effect_unknown` /
  `replay: do_not_repeat` with `CANCEL_CONFIRMATION_UNKNOWN`. It preserves the
  original operation and target, does not invent a cancelled count, and does
  not claim a clean transaction rollback. No second cancellation is issued.
- **Safe observation projection.** The 503 branches forward an explicit
  allowlist of `agent_id` (non-empty string) and `cancelled_tasks` (non-negative
  int, excluding bool). Receipt failure and post-commit unverified readback
  both carry the known cancellation count. Raw job parameters, configuration,
  schedules, exception text and credentials are never dumped. Other decision
  operations with `data=None` remain unchanged.
- **Shared-caller trace.** All six `_raise_agent_decision` callsites
  register/update/delete/admit/replace/stop were reviewed; the projection is
  additive and only stop supplies the observation.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-stop-failure-truth-20261106` |
| Base main | `248a2329623b433e68104c4d89d2965683d81013` |
| Merged predecessor | `e93982eec` (PR #695, code `1faccf71c`) |
| Executed source | `f2a31d0e66ba36d015934875130e777d69f06957` |
| Runtime | scratch SQLite; in-process task-registry fake; no live worker/provider |

## Verification

| Gate | Pre-fix / base `248a23296` | Fixed `f2a31d0e6` |
|---|---|---|
| Five external probes, 3.14 | **3 failed, 2 passed** | **5 passed** |
| Five external probes, 3.11 | **3 failed, 2 passed** | **5 passed** |
| Focused stop/shared-route callers, 3.14 | — | **101 passed** |
| Focused stop/shared-route callers, 3.11 | — | **101 passed** |
| Affected, 3.14 | 385 passed, 3 skipped, 2 failed | **392 passed, 3 skipped, 2 failed** |
| Affected, 3.11 | 367 passed, 1 failed | **374 passed, 1 failed** |

Delta: **+7 controls, zero new failures**.

### Shared baseline failures

- `tests/test_covpush_w29_governance.py::TestRegistry::test_register_new_agent`
  (both versions)
- `tests/contract/test_agent_api_contract.py::TestAgentListContract::test_get_agents_invalid_pagination`
  (3.14 only; the 3.11 environment lacks `schemathesis`)

Both fail identically on exact main and are not claimed as repaired.

## Controls

- Agent 3 receipt-failure probe: 503 `AGENT_EFFECT_UNKNOWN` includes
  `data.agent_id` and `data.cancelled_tasks == 2`.
- Root unreadable-registry probe: 503, `effect: none`, no cancel, tasks remain,
  no audit.
- Root partial-cancel probe: 503, `effect: unknown`, `do_not_repeat`, no audit,
  one fixture task remains.
- New readback twin: post-commit refuted readback returns 503
  `AGENT_COMMITTED_UNVERIFIED` with the known count.
- New safe-projection tests: allowlisted types only; wrong types/private fields
  omitted; `data=None` does not conjure an observation.
- Existing positives retained: member/current scope, cross-tenant/workspace
  refusal, exact material CAS, authority change, legitimate empty no-change,
  successful cancellation, replay without a second cancel, one receipt.

`cancelled_tasks` means the registry's reported cancellation requests/results
at this in-process boundary. It is not proof that every worker physically
terminated.

## Boundaries

- In-process task-registry fake only; no live worker/OS/multi-worker
  cancellation qualification.
- Scratch SQLite only; no PostgreSQL, soak or multi-worker qualification.
- A partial external effect is reported as unknown; it is not rolled back,
  retried or converted to success.
- No live model, provider, credential, spend, send, download or deployment.
- No merge or deployment; independent verification and code-owner review
  remain required.
