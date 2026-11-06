# Agent 3 independent review — merged PR675 run admission

Reviewer: Agent 3 (independent verification). Issued 2026-11-06 under
`docs/engineering/AGENT3_INTEGRATION_VERIFICATION_GUIDANCE_2026_11_06.md`.
Recommendation to the lead; the lead owns the final acceptance record and the
repository owner's code-owner review/merge authority remains separate (the
owner already merged #675; this review evaluates that merged admission).

## 1. User contract reviewed

`POST /api/agents/{agent_id}/run` admits one agent execution in the caller's
scope: current-authority binding, exact prior agent material claim, one
durable `AgentJob` + one `AuditLog` receipt in the same transaction, dispatch
of the existing execution only after commit, replay without redispatch, and
conflict/refusal envelopes that leave no partial state.

## 2. Source identity (the three identities reconciled)

| Identity | Value | Role |
|---|---|---|
| Executed source | `1a76d7151105d8e7c845b0f7512a4bbf0e576f52` | what the author ran |
| PR head (`#675`) | `684f1a2c645a1c4a343aeae9a87aea053cb02716` | last submitted |
| Owner merge (squash) | `93e19ed78bf42cd3696c208ff203d2f90056c54c` | in main |
| Current main | `33b8d6472605b7fbb4c84a9e21286c3d168b7d5c` | reviewed here |

**Correction (lead disposition 2026-11-06, supersedes the original summary
below):** the original text claimed "all 9 manifest-declared source files
hash identically at all four refs", which contradicts its own ci.yml
sentence. The accurate statement is: **eight** runtime/test/policy files
(`agent_decision_write_service.py` `4995472c…`, `agent_routes.py`
`68e507f9…`, `test_agent_run_admission_contract.py` `1f0eedf3…`,
`tests/unit/api/test_agent_routes.py` `9d34605b…`,
`tests/test_agent_routes_coverage.py` `efd48f84…`, `core/models.py`
`4b238c35…`, `core/security/rbac.py` `48a7ecdb…`, `core/personal_scope.py`
`f07dd35c…`) are identical across executed source, PR head, merge and
reviewed main. The **ninth** file, `.github/workflows/ci.yml`, differs
across refs; all nine match the manifest **at the declared executed source
only**. The reviewed runtime code on current main is exactly the executed
code either way.

Local checkout note: the conversation-local `main` (`ec69e24f4`) does NOT
contain the merged #675; current main with this work is `origin/main`
(`33b8d6472`). Review executed in a dedicated worktree on `33b8d6472`.

## 3. Evidence bundle disposition

Committed and sha256-verified against `MANIFEST.json`: `README.md`,
`TEST_RESULTS.md`, `routes.json`, `verification.json` — all match.

**Missing from Git at review time (reported separately from hash
mismatches):** 8 declared artifacts existed only as hashes of never-committed
local files — `focused-311.log`, `focused-314.log`, `affected-311.log`,
`affected-314.log`, `baseline-673-311.log`, `baseline-673-314.log`,
`cross-tenant-repro-base.log`, `source-tree.txt`. The committed summaries
were the only Git-verifiable record; the original bundle was therefore
**delivery-incomplete**.

Shared engineering cause: `.gitignore:621` carries a blanket `*.log` rule
(and `*.txt` is likewise ignored), which explains the omission.

**Correction (lead disposition 2026-11-06):** ignore rules explain the
omission but do not make files uncommittable — deliberate tracking after a
secrets check is an established delivery requirement, not a new convention
requiring approval (this bundle's force-added clean log demonstrates the
mechanics). An incomplete original bundle must not be classified as
checkout-verifiable. Subsequent state, recorded without a rerun: the PR675
evidence artifacts were restored and are now hash-verified in Git (root
verified 9 sources + 12 artifacts at `7e9150e40`; PR686 owner-merged as
`3925cf359`). The missing-artifact finding is historical; the
current bundle on main is complete.

## 4. Independent execution (Python 3.11.16, fastapi 0.128.8, sqlalchemy 2.0.23, pytest 8.4.2)

Environment: dedicated worktree at `33b8d6472`; `TESTING=1`; unique scratch
`DATABASE_URL`/data paths under `/tmp/agent3-pr675-scratch/`; per-test
`tmp_path` SQLite from the submitted fixture; execution stubbed at the
documented leaf (`api.agent_routes.execute_agent_task`, route-module symbol).

- Decisive gate, once: `tests/test_agent_run_admission_contract.py` —
  **12 passed** (exact nodes: the 12 collected controls of that file).
- Agent 3 probes, once:
  `tests/test_agent3_pr675_admission_independent_probes.py` — **3 passed**.
- Combined, once: **15 passed** in 29.32s (log:
  `combined-gate-311.log`).
- Author-reported Python 3.14 focused/affected results remain author evidence
  (this host lacks the 3.14 deps); the committed logs backing them are not in
  Git (§3).

One initial combined run errored (15 setup errors, `unable to open database
file`): my scratch directory was not created — harness setup error,
classified as environment, fixed, rerun clean. Not a product regression.

## 5. Admission matrix coverage

Covered by the submitted 12 controls at the real HTTP boundary (reused, not
duplicated): allowed member/admin; foreign tenant and cross-workspace 404;
deprecated/paused 400 and running 409; pre-existing active job 409; target
`name` change before claim → `STALE_TARGET` with peer preserved; actor
deactivate/demote before claim → refusal, effect=none; duplicate same
operation → `already_applied` without second dispatch; changed parameters →
`OPERATION_CONFLICT`; audit rollback → `not_applied`, no partial state;
readback failure → `committed_unverified` with zero dispatch; execution
failure → job `failed`, agent status restored; sync happy path.

Added by Agent 3 probes (the matrix items the submitted suite lacked):

1. **`enabled` + `configuration` change before claim** → 409
   `STALE_TARGET`; peer values preserved; zero jobs/audits/dispatch.
2. **Concurrent winner between load and claim** → loser 409
   `ALREADY_RUNNING`, winner `running` preserved, loser emits zero job/audit/
   dispatch (zero losing admissions; the guarded UPDATE is the CAS — not a
   bare `SELECT FOR UPDATE`). **Correction (lead disposition):** this is a
   *controlled interleaving* (peer mutation at the documented `_load_agent`
   seam under SQLite single-writer semantics), **not** proof of two
   simultaneous full worker admissions; multi-worker serialization remains
   unqualified.
3. **Replay after lifecycle completion** → `already_applied` with
   `replay=do_not_repeat`; one job; one audit; no redispatch; durable job
   receipt carries only `operation_id` + `parameters_digest` (no raw
   parameters), tenant bound to target (`t1`).

## 6. Durable truth (fresh sessions)

Verified in code and by probes reading through new sessions: `AgentRegistry`
transitions `student→running` only via the guarded exact-material UPDATE and
is restored by the lifecycle's guarded `running→prior` write; `AgentJob`
(id, tenant, agent, status, `{operation_id, parameters_digest}` receipt,
`start_time`/`end_time`) is created inside the admission transaction and
read back with the same operation id; the `AuditLog` receipt (id =
operation_id) records schema/action/event/target/tenant/digests/actor/role
and `extra.job_id`, `success=true`, `security_level=high` — no raw
parameters, configuration or secrets (asserted against a real secret value
`RUN-SECRET` in the submitted control). Different-actor replay of another
actor's operation_id yields `OPERATION_CONFLICT` (actor_id binding), not the
peer's result.

## 7. Exact seam and exclusions (recorded, not certified)

- Controlled execution seam: `monkeypatch.setattr(agent_routes,
  "execute_agent_task", …)` — qualifies admission and lifecycle handoff
  only. No model work, employee judgment, provider effects or spend is
  qualified.
- Declared boundary preserved: process death between admission commit and
  dispatch leaves a running job/agent status; stale-job reconciliation is out
  of scope and remains an unqualified operational boundary to rank separately
  by the lead.
- SQLite single-writer only; PostgreSQL, multi-worker serialization, soak and
  live breadth remain unqualified (declared).

## 8. Recommendation to the lead

**Accept the merged #675 run-admission scope as independently verified**:
the contract reproduced end-to-end at the public boundary on this runtime,
with zero failing or missing in-scope transitions and the declared
exclusions intact.

Non-blocking findings for the acceptance record:

1. **Evidence packaging gap (historical, resolved)**: 8 manifest artifacts
   (all run logs + `source-tree.txt`) were absent from Git at review time.
   Corrected classification per lead disposition: the bundle was
   delivery-incomplete; blanket ignore rules explain but do not excuse the
   omission, and deliberate tracking after a secrets check is an established
   delivery requirement. The artifacts have since been restored and
   hash-verified in Git via PR686 (`3925cf359`); no rerun performed.
2. `ci.yml` manifest pin reflects the executed source, not post-merge main;
   informational only.
3. Harness incident during this review (missing scratch dir) was Agent 3
   environment error, resolved; recorded for truthfulness.

Next independent review continues per guidance §7 (Agent 1's submitted
approval-scope successor when ready, else Agent 2's next bounded family).
