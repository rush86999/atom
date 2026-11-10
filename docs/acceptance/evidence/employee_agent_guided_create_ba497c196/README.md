# Guided public agent creation — current authority, exact material, durable receipt

Status: **submitted for independent review.** No merge or self-acceptance.

## Confirmed gaps on `fb4d7f554`

`POST /api/agents/guided` is the employee self-serve creation surface. It
designed a server-owned blueprint but then inserted `AgentRegistry` and
committed directly. The failure-first scratch route matrix found:

| Finding | Before |
|---|---|
| No operation identity / durable audit receipt / replay | response had no `operation_id`/`audit_id`; replay created a second agent |
| Concurrent actor deactivation | still created the agent (201) |
| NULL→`{}` schedule change | replayed 201 instead of 409 |
| Replay followup | scheduler ran twice |
| Foreign `acting_agent_id` | queued a HITL row (202) for an agent outside the caller's scope |
| Acting-agent HITL material | params lacked exact workspace/tenant/schedule/acting-agent binding |

Failure-first: `failure-first.log` — **6 failed / 1 passed** (the inactive-user
401 control passed).

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/web-goal14-guided-create-20261110` |
| Base | `fb4d7f5549169b58a1601a1083207e3f0bb44a6b` (NULL/{} custom repair) |
| Code commit | `ba497c196` |
| Runtime | real scratch SQLite + FastAPI route + real JWT; the guided factory is a deterministic controlled double; no live product model |

The frozen PR833/PR831 worktrees were not edited.

## Repair

`backend/core/agent_decision_write_service.py`:

- `create_agent` now accepts server-owned `confidence_score`, `user_id`,
  `parent_agent_id`, `capabilities`, `minimum_role` and `authority_label`.
- Confidence is validated below the INTERN floor; the default remains
  `NEW_AGENT_CONFIDENCE` (0.35), while guided passes 0.1.
- The optional identity/parent/capabilities material is bound in the request
  digest, AuditLog `extra`, and fresh-session result-state readback.
- Custom create passes no optional values, so its material and policy are
  unchanged.

`backend/api/agent_onboarding_routes.py`:

- Guided direct create calls the shared `create_agent` decision writer with
  the generated blueprint, server-owned STUDENT/0.1/user/parent/capabilities,
  and the caller's resolved actor scope.
- The route keeps the existing self-serve policy (`minimum_role=GUEST`, no
  `AGENT_MANAGE`) and remains create-only (no name-based upsert).
- An explicit `acting_agent_id` is authorized against the caller's governance
  scope before the trust/HITL gate and re-checked after generation, so a
  foreign or concurrently deleted actor cannot queue/create a dangling
  parent binding.
- The HITL review now carries exact goal/context/workspace/tenant/schedule/
  acting-agent material and caller execution context.
- Scheduler runs only after the first verified create; replay/conflict do not
  schedule again.

## Controls (real scratch route/JWT/SQLite)

- valid employee twin: current scope, STUDENT, confidence 0.1, user_id,
  capabilities, role curriculum, audit receipt, replay;
- forged body identity/scope/status/confidence/maturity ignored;
- forged generated-blueprint status/confidence/scope/identity ignored;
- inactive user and concurrent deactivation refused;
- foreign acting agent 404 with no HITL row;
- same-scope acting-agent review 202 with exact scoped material;
- acting agent deleted during generation 404;
- NULL/{} schedule changed-material 409, unchanged replay 201;
- changed generated material 409;
- scheduler once;
- commit failure 503 `AGENT_EFFECT_UNKNOWN` with rollback;
- unreadable readback 503 `AGENT_COMMITTED_UNVERIFIED`;
- create-only preserves an existing same-name agent.

`guided-after.log` — **13 passed**; `ci-guided-step.log` — **13 passed** under
the exact additive CI env.

## Affected selection

`affected-after.log` — **259 passed** across onboarding, guided create, custom
create, agent routes, governance and the decision contract.
`ci-lane-contract.log` — **41 passed** for the additive CI manifest/workflow
contract.

## CI regression

Added a new `Run guided agent create authority and receipt controls` step to
`.github/workflows/ci.yml` and the identical entry to
`backend/tests/fixtures/ci_backend_additions.json`. The pre-parallel baseline
file was not changed; `test_ci_backend_lane_contract.py` verifies the additive
union.

## Remaining candidates

- Guided pending-approval resume is still a separate candidate: an immature
  acting agent queues a scoped review, but no `create_agent` resume handler
  exists yet. This slice does not claim that approval executes creation.
- `POST /api/agents/spawn` remains the next unclosed create alias.

## Boundaries

No live DB/model/provider/credential/send/spend/deploy/dependency, no
budget/BYOK file, no new table/store, no test deleted/skipped/xfailed, no
maturity/scope/authority relaxation. Existing 143 claims / 18 goals are
unchanged.
