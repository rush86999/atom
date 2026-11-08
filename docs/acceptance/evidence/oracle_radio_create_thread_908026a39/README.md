# `radio.create_thread` — exact-row / authority Oracle successor

Executed source: `908026a39` (implementation commit on
`codex/oracle-refresh-20261107`). Base after a normal merge of current main
`4590560d7` (`86f666d00`). The failure-first trace remains preserved at
`../oracle_radio_create_thread_trace_20261107/`; this packet is the implemented
successor.

## What changed

The registered action previously committed an `AgentThread` row and returned
raw success. It did not re-read the row, bind the operation, or check the
creator/member `AgentRegistry` scope, so the shared Generic mutation consumer
could only report `no registered postcondition verifier`.

The successor uses only existing mechanisms:

- `core/agent_radio/radio_thread_mutations.py` — server-owned thread payload,
  pre-effect authority, exact fresh readback, operation-id binding, durable
  receipt projector/matcher.
- `core/oracle/request_expectations.py` — freezes name, creator, normalized
  roster, scope, tenant and workspace from the accepted business arguments plus
  the server-owned runtime identity. Model-supplied `agent_id`, `tenant_id` or
  `workspace_id` arguments cannot override them.
- `core/oracle/postcondition_verifiers.py` — exact fresh-session row/material
  verification, current AgentRegistry authority re-check, duplicate-operation
  detection, durable replay projector/matcher.
- `core/agent_radio/radio_actions.py` — delegates the write to the shared
  producer after the existing kill-switch/tier/agent-id pre-checks.

No new engine, router, store or approval lifecycle was added. The send-message
successor branch and PR752 were not touched; only the accepted general
`_text`/`read_thread` shape and durable-receipt projection pattern were ported
by source identity (`3a188840d`).

## Single-tenant authority semantics

The app is single-tenant. The authority contract deliberately reuses the
existing personal-scope rule, not a new SaaS gate:

- `AgentRegistry.workspace_id` / `tenant_id` NULL and the literal `"default"`
  are the same personal scope.
- A request scoped to `"default"` (or no scope) may use NULL/`"default"` rows.
- A request scoped to a concrete workspace/tenant requires the same concrete id;
  a partial match is refused.
- The creator must be registered, not explicitly disabled, not
  paused/stopped/deprecated/deleted, and at the existing INTERN+ maturity floor
  (persisted status wins over a caller-supplied tier).
- Members must be registered, not explicitly disabled, and in the same
  compatible personal/workspace/tenant scope. Members do not need INTERN+.
- No user-role, plan, seat or other SaaS authorization was invented.

Pre-effect refusals are `failed_before_effect`/`proven_not_applied`. The
authority read and insert share one transaction. After commit, the producer
re-reads the exact row in a fresh session; an unavailable, missing or mismatched
readback is `uncertain` and keeps the known thread id. The verifier re-runs the
same authority checks in a fresh session, so a later disabled/moved/deleted
creator or member is a truthful stale-authority refusal.

## Controls

All controls use `TESTING=1`, explicit fresh scratch SQLite/data/Lance/output,
and the shared bounded gate where applicable. No live provider/model/network/
account/sandbox/install/spend/deployment was used.

| log | result |
|---|---|
| `focused-oracle.log` | **29 passed**, exit 0 |
| `original-probe-successor.log` | **2 passed**, exit 0 (original failure-first probe now passes) |
| `affected-units.log` | **24 passed**, exit 0 |
| `registry-contract.log` | **59 passed**, exit 0 |
| `service-adapter-server.log` | **29 passed**, exit 0 |
| `effect-families.log` | **46 passed**, exit 0 |
| `heavy-full-radio-not-dispatched.log` | exit **75** — shared gate refused dispatch at <4 GiB; **not** a test failure |

The original negative run remains at
`../oracle_radio_create_thread_trace_20261107/probe-failure-first.log`
(2 failed, actual exit 1). It is not rewritten.

Covered twins in `backend/tests/test_oracle_radio_create_thread.py`:

- valid exact-row apply with real Generic consumer and Oracle;
- same-operation replay with one row and no second dispatch;
- changed material on the same operation refuses before dispatch;
- changed roster, changed name case, missing row, and two rows for one
  operation are independently refuted;
- stale disabled member and moved-workspace member are refuted on replay;
- exact commit-failure rollback leaves no row and reports uncertainty;
- producer readback unavailable/mismatch preserves the known id and is
  uncertain;
- nonexistent/disabled/paused/below-INTERN creator and nonexistent/disabled/
  moved member are refused before effect;
- missing/invalid name, empty/self-only roster, invalid scope, missing creator
  id are refused before effect;
- valid NULL personal scope and `"default"` scope both succeed;
- model-supplied creator/tenant/workspace business arguments cannot override
  the server-owned scope.

## Registry state at this source

Refreshed enabled registry with lazy AgentRadio/BPE loaded:

- **98** actions, **30** declared mutations, **25 covered, 5 uncovered**
- remaining uncovered: `radio.send_message` (implemented on
  `codex/oracle-next-20261107`, pending merge; not duplicated),
  `workspace.commit`, `workspace.note` (deferred), `mini_app_run`
  (unqualified guest runtime), `shopify_create_fulfillment` (root worker 56636,
  PRs 745/748/749/750; not touched).

## Command shape

The focused runs used:

```
/private/tmp/atom-agent-cli/run_bounded_test_gate.py --profile bounded \
  --cwd <worktree>/backend -- <python> -m pytest <exact nodes> \
  -q --disable-warnings -p no:cacheprovider
```

The heavy 219-case `tests/test_covpush_w80a_radio.py` was attempted with
`--profile heavy`; it exited 75 before dispatch because free space was below the
4 GiB heavy floor. That result is preserved, not treated as a test verdict.

## Boundaries

No live app, model, provider, account, credential, send, spend, install,
deploy, VM, PostgreSQL or sandbox execution. No all-827 sweep and no new
product scope. Root owns independent review, PR, CI and merge.
