# Guided create — atomic acting-agent authority claim

Status: **successor submitted for independent review.** No merge or
self-acceptance.

This is a distinct successor to `employee_agent_guided_create_ba497c196`; the
original source/evidence and the root negative are preserved unchanged.

## Root negative reproduced

Probe: `root-negative/root-parent-commit-probe.py`  
Root proof: `root-negative/root-parent-commit-review.json`  
Root failure log: `root-negative/root-parent-commit-before.log`

The probe changed the acting agent **after** the route's post-generation
list check and **before** `_create_agent_decision`:

- peer moves `acting-agent` from `company/ws-a` to `other/ws-b`;
- peer demotes `autonomous` → `student`.

Both still returned **201 with a committed child and audit row**. The list
check was only a preflight, not a transaction-bound authority claim.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/web-goal14-guided-create-20261110` |
| Parent | `ba497c196` (PR834 code) |
| Successor code | `9d2ba566c` |
| Runtime | real scratch SQLite + FastAPI route + real JWT; guided factory is a deterministic controlled double |

## Repair

`backend/api/agent_onboarding_routes.py`:

- After generation, read the exact acting-agent material directly by id:
  raw tenant/workspace, status, confidence, enabled, `last_exam_id`,
  configuration and capabilities.
- Verify the current tenant/workspace scope with the existing personal-scope
  resolvers.
- Pass the snapshot to `create_agent`.

`backend/core/agent_decision_write_service.py`:

- `create_agent` accepts `parent_authority` and performs a guarded no-op
  `UPDATE` on the exact snapshot **in the same transaction** as the current
  user claim and the child insert.
- A peer scope move, status/confidence/material change, or delete makes the
  claim rowcount 0 → `409 AUTHORITY_CHANGED`, rollback, zero child, zero
  audit, zero scheduler call.
- The audit receipt stores a compact `parent_authority` snapshot: raw
  scope/status/confidence/enabled/`last_exam_id` plus configuration and
  capabilities digests. No raw configuration is stored.
- Replay checks the current actor workspace and the current parent snapshot
  against the receipt; a changed parent returns 409 instead of stale
  `already_applied`.

The existing governance create policy still chooses direct create vs HITL.
No hardcoded maturity threshold or new review engine was added. Human direct
guided remains `GUEST+` and create-only.

## Results

| Check | Result |
|---|---|
| Root parent-commit probe | **2 passed** (`root-probe-after.log`) |
| Guided matrix (root negatives + valid autonomous twin + peer delete/material/status/scope + replay authority) | **19 passed** (`guided-after.log`) |
| Affected onboarding/custom/agent/governance/decision/CI-lane | **265 passed** (`affected-after.log`) |

## Preserved boundaries

- Original `ba497c196` evidence and the root's two-negative proof are kept.
- No live model/provider/DB/credential/send/spend/deploy/dependency.
- No budget/BYOK file, no new table/store, no test weakening.
- No merge or self-acceptance.

## Not yet complete

The guided journey is **not** labelled complete: the pending scoped
`create_agent` HITL still has no resume handler. That is the next finite
boundary, to be staged as a distinct follow-up commit/evidence.
