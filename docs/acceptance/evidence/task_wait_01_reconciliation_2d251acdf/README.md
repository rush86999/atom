# TASK-WAIT-01 requirement-to-evidence reconciliation

**Source:** current main `2d251acdfddae2aca27c6b43dc3f0de97654a9cb`.
**Status:** reconciliation checkpoint. TASK-WAIT-01 remains **OPEN** at the
framework/whole-app scope. No runtime file was changed in this checkpoint.
No claim denominator or historical score is changed.

This packet was produced in a new isolated sparse worktree
(`/private/tmp/atom-task-wait-01-reconciliation-20261107`), detached from
current main. The image worktree and other owners' worktrees were not edited.
No live provider, model, account, credential, send, spend, install, deploy,
browser, KVM or Linux action occurred.

## 1. What was actually executed here

Three targeted contract selections were run on clean current main with
`TESTING=1` and a fresh scratch SQLite/data/Lance root per selection. These
are the exact TASK-WAIT contract files, not the broad backend suite:

| Selection | Files | Actual result | Log |
|---|---|---|---|
| Assignment public routes/negatives | `test_task_wait_source_trigger_contract.py`, `test_task_wait_two_fact_events.py`, `test_task_wait_two_job_isolation.py`, `test_task_wait_source_revocation.py` | **6 passed**, exit 0 | `targeted-assignment-routes.log` |
| Assignment restart/budget/replay | `test_task_wait_source_continuation_regressions.py`, `test_task_wait_process_recovery.py` | **21 passed**, exit 0 (includes 3 real-OS-process cases) | `targeted-assignment-recovery.log` |
| Generic wait/answer/recovery/authority | 10 Generic information/wait/job contract files (see HANDOFF) | **55 passed**, exit 0 (includes 6 real-process cases) | `targeted-generic-waits.log` |

**Total: 82 targeted controls passed, actual pytest exit 0.** The test process
reported `revision=2d251acdfdda dirty=False (0 modified, 0 untracked)`.
These are **new executions at `2d251acdf`**, not relabelled exits from the
older evidence packets. Where an older packet's source files are not
byte-identical to current main, its exit remains attributed only to its own
`executed_source`.

Commands used (one scratch root per selection; no live DB):

```bash
cd /private/tmp/atom-task-wait-01-reconciliation-20261107/backend
PY=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
S=$(mktemp -d /private/tmp/atom-task-wait-XXXXXX); mkdir -p "$S"/{data,office,lancedb}
TESTING=1 DATABASE_URL="sqlite:///$S/atom.db" \
ATOM_DATA_DIR="$S/data" ATOM_OFFICE_DIR="$S/office" \
LANCEDB_URI="$S/lancedb" ATOM_TEST_PYTHON="$PY" PYTHONPATH="$PWD" \
"$PY" -m pytest <selection> -q --tb=short
```

## 2. Requirement-to-evidence matrix (all eight cases)

The rows distinguish **framework Generic** (ordinary Agents job/wait/answer and
browser) from **employee assignment** (durable assignment `/sources` route,
compiler/executor and recovery). A pass in one scope is not transferred to the
other.

| # | Required observation | Generic / browser evidence (actual assertions) | Employee-assignment evidence (actual assertions) | Disposition |
|---|---|---|---|---|
| 1 | Missing prerequisite creates a durable targeted wait; useful work retained; no dependent effect/final artifact | Browser steps 12/20: same job/execution, `job_status=waiting`, exact question and missing fact, `no_completion`, `no_result`; `test_agent_generic_information_wait.py` asserts a 202 wait receipt and no effect. | `test_task_wait_two_fact_events.py` asserts exactly one question, requested report path absent, zero reconciliations, zero applied artifacts; `test_task_wait_independent_work.py` and `test_sequential_fact_completion_contract.py` keep the artifact withheld while a fact is open. | Covered at both scopes. |
| 2 | Relevant authorized input wakes the same task and real continuation produces verified output without a second objective/manual advance | Browser steps 19/23: one answer POST, same job/execution, final `tasks.create` with `oracle_verified=true`, one durable BoardTask; `test_agent_generic_information_wait.py` and actual-process test assert the same job resumes. | Public `POST /api/assignments/{run_id}/sources`: `test_authorized_source_answer_continues_same_task[False]` completes the same run with one `invoice.reconcile` result `140.25` and no separate advance; the `[True]` twin is retained only as an explicit-advance control. `test_two_fact_events` produces one verified `130.00` document after both facts. | Covered at both scopes; the explicit-advance twin is **not** proof of automatic continuation. |
| 3 | Real restart/long wait preserves task/wait/subject/question/receipts; prolonged wait does not consume active allowance; absolute deadline still enforced | Browser steps 15-18: real backend+frontend stop/relaunch, same job/execution/wait/correlation/question, empty answer input, `no_new_provider_call`. Actual-process tests use distinct PIDs and the same job/execution. | `test_task_wait_process_recovery.py` (3 cases) uses real OS child processes, hard exit 17, successor recovery, claim lease/deferred wake; `test_prolonged_information_wait_does_not_consume_active_wall_budget` uses a two-hour controlled clock with a 900s active allowance and still completes; `test_absolute_deadline_is_not_extended_by_source_arrival` keeps the past deadline and blocks. Packet `task_wait_idle_budget_419ab9f44` records 97 controls. | Assignment restart + active/absolute budget covered; Generic restart covered. **Generic/framework active-vs-absolute budget evidence is absent** (G1). |
| 4 | Both event orders: input before restart and input after restart while waiting | Generic actual-process test accepts the answer before a crash-before-claim and a fresh process resumes it; browser covers answer **after** restart. | `test_source_acceptance_survives_interruption_and_replay_recovers` explicitly covers Order A (rebuild while waiting before answer) and Order B (durably accept source, interrupt before adaptation, rebuild from DB, replay); `test_task_wait_process_recovery.py` covers accepted source before a real process restart. | Mechanism/process orders covered; **no single browser capture covers both orders** (G6). |
| 5 | Unrelated/wrong-subject/wrong-scope/stale/revoked/empty/ambiguous input cannot settle another wait or manufacture a result | Browser step 21: stale answer `409`, same second wait, no provider/task/job. Generic tests: wrong correlation `409`, old answer `409`, unbound answer `422`, answer after cancellation `409`; recovery refuses unbound/foreign/old/terminal waits; authority refuses moved/demoted/deactivated/admin-replaced actors. | `test_two_fact_events.py` wrong-subject invoice returns `resolved_question_ids=[]` with `mismatched_question_ids=[first]`; `test_task_wait_source_continuation_regressions.py` rejects unrelated/partial evidence with zero reconciliation and no adaptation; `test_task_wait_source_revocation.py` returns `403` before read and leaves the exact question open; stale source versions are refused at resolution by `test_assignment_resource_boundary.py`. | Covered at both scopes for the tested orders. **Changed source after acceptance but before consumption is not directly exercised** (G2). |
| 6 | Duplicate/concurrent delivery preserves identity, does not repeat an effect/artifact, and replay is acknowledged truthfully | `test_agent_generic_information_wait.py` duplicate answer returns `already_resumed=true` with unchanged call count; wrong/old answers are refused. Process tests race two startup workers and assert exactly one resumes; interrupted claim stays `uncertain` and is not resent. | Duplicate source delivery is `already_present`/inert with one reconciliation; two concurrent recovery successors produce one model call/one result; claim completion/retain require the exact generation token; stale finish cannot consume a successor claim. Browser step 27: duplicate final answer `409` (or already-resumed), same task count, no new provider call. | Covered. |
| 7 | Cancellation, explicit deadline, revoked authority, or changed source prevents late input from resurrecting work; stale receipts cannot certify a new result | `test_agent_generic_information_wait.py` answer after cancellation is `409` and job stays cancelled; current-authority tests refuse moved/demoted/deactivated actors even after acceptance, and the real registered-effect twin creates zero tasks for a moved actor. | `test_cancelled_task_refuses_source_arrival_without_resurrection` keeps status cancelled and zero reconciliations; `test_absolute_deadline...` and `test_restart_owner_does_not_revive_expired_or_cancelled_work` keep the past deadline/cancelled state; `test_task_wait_source_revocation.py` refuses revoked grants. | Covered for cancellation/deadline/revocation-before-read. **Post-acceptance source change/revalidation is an evidence gap** (G2); browser does not run terminal negatives (G6). |
| 8 | A second missing prerequisite pauses again; later valid input resumes remaining work; unrelated receipts survive; final UI/durable task/outcome agree; evidence arrival alone cannot complete | Browser steps 20/22/23/26: second wait has a new id/correlation, first wait approved with the title, same execution, reload preserves the second question, final one job/one execution/two waits/one BoardTask. `test_information_wait_maturity_neutral.py` keeps the same execution and confidence `0.35`/`autonomous` across two waits; terminal success/failure still update maturity. | `test_two_fact_events` retains the first read/receipt and produces one DOCX only after both facts; `test_task_wait_artifact_content_contract.py` asserts the final DOCX contains `105.00`, `270.00` and the PO and is receipt-bound; `test_sequential_fact_completion_contract.py` and `test_task_wait_independent_work.py` confirm facts/model retain alone do not complete or publish. | Covered at both scopes for the tested outputs. Generic **document** output is not used; browser output is the requested task. Cross-app output breadth remains open. |

## 3. Source identity and packet reuse

`source-identity.json` records, for every inspected packet, its own
`executed_source`, how many declared source files are byte-identical at
`2d251acdf`, and which differ/are absent. Summary:

| Packet | Source files equal current main | Reuse statement |
|---|---:|---|
| `task_wait_source_revocation_ebe4cbd9b` | 9/9 | Byte-equal runtime/tests; packet exit reusable at this source. |
| `task_wait_two_job_isolation_cb13bee87` | 8/8 | Byte-equal; reusable. |
| `sequential_information_integrated_5d7609d8f` | 7/8 (CI file differs) | Runtime/tests equal; only CI differs. |
| `sequential_isolation_integrated_b5fdea5ac` | 8/9 (CI differs) | Runtime/tests equal; only CI differs. |
| `source_revocation_main_a8cb0cba6` | 8/9 (CI differs) | Runtime/tests equal; only CI differs. |
| `task_wait_output_guard_2e23b37cf` | 12/18 | Packet exit remains at its source; current-main assignment output/continuation contracts were re-executed in the 21-control selection. |
| `task_wait_idle_budget_419ab9f44` | 7/12 | Same: older packet not relabelled; current-main budget/deadline tests passed in the 21-control selection. |
| `task_wait_recovery_integrated_227579321` | 3/9 | Same: current-main process/lease tests passed in the 21-control selection. |
| `generic_information_recovery_integrated_e08482e81` | 7/10 | Packet exit remains at its source; current-main Generic recovery/authority selection passed 55 controls. |
| `generic_information_authority_9067ee922` | 5/6 | Current-main authority tests passed; packet exit not relabelled. |
| `generic_information_wait_actual_process_e1ffc9743` | 5/10 | Current-main process tests passed; packet exit not relabelled. |
| `information_wait_maturity_neutral_e0ad2336c` | 1/3 (later Generic changes) | Current-main maturity test passed; source-bound negative preserved. |
| Browser `generic_information_browser_d3f58d81d` (PR744) | 8/11; 3 harness files absent on main | Eight runtime files are byte-equal to current main; the three missing files are the PR744 harness/test. See §4. |

The older packets remain at their original sources and retain their original
negatives. A green count is not transferred merely because a later main
contains the same feature.

## 4. Browser episode — exact evidence and provenance caveat

The ordinary-browser episode is in the PR744 worktree
`/private/tmp/atom-browser-capture-frozen-20261107`:
`docs/acceptance/evidence/generic_information_browser_d3f58d81d/`
(PR #744 head `1f6018fd7`; not merged on current main).

- Declared frozen source: `d3f58d81d8ec8c728f331d5511b8710853ef4fe3`.
- Actual driver exit 0; 29 stages/162 boolean assertions.
- Strict Git packet: 11 sources/18 artifacts; copied key files are retained
  here as `browser-*.json`/`browser-README.md`.
- The packet proves: real login/onboarding, one objective, durable question,
  real backend/frontend restart, same wait, first answer, second question,
  reload, second answer, real `tasks.create` with default Oracle, one durable
  task, duplicate/stale refusal, and no model polling on reads.
- It does **not** prove served-model quality, every event order, long-idle
  budget, cancellation/deadline/revocation in the browser, or whole-app
  completion.

**Provenance caveat (must not be hidden):** `scenario.json` step 17 records the
running backend health identity as `ec69e24f4385-dirty.d48cacd2123b`
(git commit `ec69e24f4385`), while the packet declares `d3f58d81d`. Step 18
only asserts the source id is the *same before/after restart*; it does not
assert equality to `d3f58d81d`. The packet's `initial_backend_source_bound`
step instead compares 7,730 exported backend files against Git blobs at
`d3f58d81d` with zero mismatches. Therefore the episode is **not accepted from
the health badge alone**; its defensible binding is the per-file export/blob
proof (and the 8 runtime files here are byte-equal to current main). This is a
source-attribution risk for root, not a reproduced wait-runtime failure. No
browser replay is warranted solely because a successor commit exists.

Also independent of the wait contract: the episode's final success re-banded a
manually promoted agent from autonomous/0.35 to student/0.36. PR745 is the
separate pending repair; it is not closed or redefined here.

## 5. Exact gaps (no failure reproduced)

- **G1 — Generic/framework budget kind:** no evidence that an ordinary
  Generic job's prolonged information wait is excluded from an active wall
  allowance or that a Generic absolute deadline is enforced. The active/idle
  and absolute-deadline controls are employee-assignment controls.
- **G2 — Changed source after acceptance:** revocation is proven before the
  source is read, and stale versions are refused at resolution. A source
  changed after acceptance but before dependent consumption is coded
  (`source_version` checks in `core/assignment_executor.py`) but not directly
  exercised by the wait matrix.
- **G3 — Generic source upload/selection:** the Generic surface proves the
  answer event; the assignment surface proves the authorized source event.
  The requirement's “answer or source upload/selection or supported event” is
  not uniformly evidenced on the same framework consumer.
- **G4 — Generic two-job isolation:** assignment has a symmetric two-job
  isolation proof. Generic job/execution identities are distinct, but no
  symmetric Generic two-wait test is in this selection.
- **G5 — Browser source badge:** the health identity mismatch in §4; root must
  accept the per-file binding or require a driver/identity correction.
- **G6 — Browser breadth:** no browser cancellation, absolute-deadline,
  authorization-revocation, long-idle or before-restart-answer capture. Those
  remain API/process evidence at their recorded scopes.

None of G1-G6 is a reproduced current-main failure. The 82 targeted controls
passed. No runtime repair was made, and no second engine/event bus/router/
store/polling loop/scheduler was introduced.

## 6. What this checkpoint does not claim

It does not close TASK-WAIT-01, whole-app acceptance, general adaptive
judgment, served-model quality, PostgreSQL/multi-worker/soak, live provider
breadth, guest execution or the 143-claim denominator. It does not replace the
PR744 browser packet or PR745 maturity repair. Root retains independent
acceptance.
