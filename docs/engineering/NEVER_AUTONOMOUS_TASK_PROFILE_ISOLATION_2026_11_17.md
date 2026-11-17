# Never-autonomous entry task-profile isolation — proof and limits

Date: 2026-11-17
Worktree branch: `codex/task-profile-isolation-20261117` (base `0ef449aea`)
Scope: `core/task_classification.py`, `core/generic_agent.py`,
`core/workflow_engine.py`, `core/autonomy_policy.py` (token helpers only),
`core/atom_meta_agent.py` (drop the stale dict profile before a rebuild),
the existing never-autonomous test files (explicit token release + AsyncMock
experience fixture), the new real-entry regression file, CI selection ledgers
and this doc. No live DB, owner credentials, provider/model calls, root
private fleet/auth packets or other worktree was touched.

## 1. Two related defects

### 1.1 Test-process ContextVar leak

Pytest runs synchronous test bodies in its thread context. Five tests bound a
profile with `bind_task_profile(...)` and never called
`reset_task_profile(token)`. A later test in the same process inherited that
profile, so:

- `test_ungrantable_classification_outage_blocks_without_model` saw a leaked
  `finance` profile, filed a review, and (when its fixture approved) reached
  the model instead of exercising the blocked branch; the plain-MagicMock
  `record_experience` then masked the assertion as a `TypeError`.
- `test_workflow_unbound_profile_still_pauses_before_first_step` was handed
  the leaked `finance` profile, so only its "unbound premise" assertion failed
  while the pause itself was still correct.

Repair: every leaking synchronous test now releases its tokens in a
`finally`; `_generic_agent` fixtures use `AsyncMock` for
`world_model.record_experience`. No safety assertion was relaxed, and no broad
autouse concealment fixture was added.

### 1.2 Real-entry fallback inheritance

`GenericAgent.execute` and `WorkflowEngine._run_execution` bound a profile
before running the body. If BOTH `build_task_profile[_workflow]` and
`build_unknown_task_profile` raised, the bind was skipped and the entry kept
running in the caller's context. Task admission then read
`current_task_profile()` and consumed the ancestor's profile. Consequences:

- nested parent `marketing` + child `finance` under an enabled finance rule
  was a definite nonmatch against the ancestor, so it ran with no HITL;
- an ancestor profile owned by `u2` made admission prefer `u2` as the policy
  owner while the admitted actor was `u1`, so `u1`'s rule was never checked.

Repair:

- `task_classification.begin_task_profile_boundary(context)` masks the
  profile and run-scoped clearance (ContextVar tokens) and removes the two
  dispatch-dict entries, remembering them.
- Both real entries open the boundary before building, bind only the profile
  they built (or the canonical unknown profile), and in `finally`
  reset/end the boundary. The parent profile/clearance and dispatch-dict
  entries are restored on success, exception and cancellation.
- `_admit_never_autonomous_task` in both entries now takes the policy owner
  from the admitted actor (GenericAgent: context `user_id`/`actor_id`;
  Workflow: workflow creator / run user) before the profile's owner.
- `AtomMetaAgent.execute_unaudited` drops the stale dict-scoped profile before
  rebuilding, so a double builder failure cannot leave an ancestor profile for
  its dict-scoped admission.
- Same-task nested tool checks still see the task's bound profile (the
  ContextVar/dispatch value is only isolated per NEW entry), and true
  nonmatch/no-policy tasks still proceed. Missing profiles with configured
  rules stay fail-closed: GenericAgent returns `blocked` after filing the
  pending review row; WorkflowEngine pauses.

Scoped save/restore uses the documented `contextvars` token contract:
`ContextVar.set` returns a `Token`; `ContextVar.reset(token)` restores the
previous value in the same context
(<https://docs.python.org/3/library/contextvars.html>). The dispatch dict is
saved/restored alongside because `integrations/mcp_service.py` reads the dict,
not the ContextVar.

## 2. Evidence (this worktree, isolated scratch)

Environment for every run: `TESTING=1 PYTEST_VERSION=ci
PYTHON_DOTENV_DISABLED=1`, an absolute scratch `DATABASE_URL` under
`/private/tmp/atom-task-profile-isolation-scratch/`, `ATOM_DATA_DIR` and
`LANCEDB_URI` in that scratch, an empty `HF_HOME`,
`HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1`, and the
cached interpreter
`/private/tmp/atom-macos-quickstart.U2N2Wn/backend/venv/bin/python`.
No live dev DB, provider key, model call or network was used by these tests.

| Run | Result |
|---|---|
| baseline, five files in ONE process, work-order order (before fix) | **76 passed, 2 failed** |
| after fix, same five files, work-order order | **78 passed** |
| after fix, same five files, reverse order | **78 passed** |
| new `tests/test_never_autonomous_entry_profile_isolation.py` alone | **17 passed** |
| negative control: new double-builder-failure tests with the old `generic_agent.py` + `workflow_engine.py` restored | **2 failed** (as expected) |
| negative control: new cross-owner tests with the old entries restored | **2 failed** (as expected) |
| negative control: new meta stale-dict test with the old `atom_meta_agent.py` restored | **1 failed** (as expected) |
| six complete never-autonomous files in ONE process, work-order order | **95 passed** |
| six complete never-autonomous files in ONE process, reverse order | **95 passed** |
| CI lane-preservation contracts (`test_ci_backend_lane_contract.py` + `test_quickstart_matrix_contract.py`) | **642 passed** |
| broader affected policy/agent/workflow set (`test_autonomy_policy_gate.py`, `test_generic_agent.py`, `test_atom_meta_agent.py`, `test_bpe_note_commit_outcome.py`, `test_covpush_w21_workflow_engine.py`) | **281 passed, 1 failed** — the failure (`test_atom_meta_agent.py::TestErrorHandling::test_spawn_failure_handling`) reproduces at `HEAD` with the original `atom_meta_agent.py`; it is pre-existing and unrelated to this change |

The new file covers both real entries (`GenericAgent.execute` and
`WorkflowEngine._run_execution`) for: parent nonmatch + child finance with
both builders failing, cross-owner ancestor, normal classified child review,
unknown fallback review, true-nonmatch child proceeding, restoration after an
exception and after cancellation, and sequential entries not sharing a
profile or review. It also covers the dict-scoped sibling
(`AtomMetaAgent.execute_unaudited`) dropping a stale parent profile when its
own double build fails. SQLite stores, rule matching, HITL rows and durable
admission are real; no reviewer decision is fabricated. The approved path is
not claimed here; the existing five files continue to cover it through
`authorize_task_admission_decision` / `claim_task_admission_decision`.

CI: the additive `backend-core` never-autonomous lane now runs all six
complete files, one process per file, each with its own absolute
runner-temp SQLite. The previous five selectors, order and gates are
unchanged; the new file is appended. `backend/tests/fixtures/ci_backend_additions.json`
matches the YAML step exactly.

## 3. Limits

- SQLite only; no PostgreSQL or multi-worker run in this worktree.
- Fault injection is limited to the two builder functions and (for
  error/cancel tests) the entry body. No matcher, HITL store, reviewer
  authority, receipt validation or production approval path is mocked.
- The unknown-profile fallback is defensive; its dual failure is synthetic.
  No live app entry was observed hitting the double fault.
- No frontend/UI or live-server UAT; no model-quality or release claim.
