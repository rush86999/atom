# Original-goal reconciliation — goals 10–18 (read-only, 2026-11-10)

Status: **read-only reconciliation and next-work queue**. No implementation, new
tests, browser/model campaign, new world, source edit, CI edit, goal-index edit,
PR/merge or live action was performed.

## Catalog preservation

The canonical catalog is preserved exactly:

- **143 historical claims**
- **18 goal rows**
- **app_complete: false**

This report covers **goals 10–18 only**. Goals 1–9 are owned by another native
session and are not re-audited or duplicated here. The catalog and original
counts are referenced, not reset.

Canonical sources:

- `docs/engineering/APP_GOALS_INDEX.json`
- `docs/engineering/APP_COMPLETION_REQUIREMENT_AUDIT_2026_11_07.json`
- `docs/engineering/APP_COMPLETION_WEB_RECONCILIATION_2026_11_09.json`

Current main basis: `0d5132c2e060a5f2ac338bca143c5e138e607658` (PR824 integrated
the main-web deliveries). The index quick-reference still labels PRs 817/819–823
submitted; PR824 commit/readback is the current integration, so this report uses
the evidence packets rather than stale queue labels. PR829 (`08743676d`) and
PR830 (`e5c75c538`) are pending CI/security and are not merged.

## Classification of goals 10–18

| # | Goal | Classification | Remaining gap |
|---|---|---|---|
| 10 | TASK-WAIT-01 | **bounded-pass / open at whole-app** | Both event orders across Generic/assignment/workflow; repeated pauses + final usable output; current-main ordinary UI |
| 11 | Documents, presentations, email drafts | demonstrated controlled scope + missing ordinary breadth | Ordinary document journey, provider draft/readback, recipient delivery |
| 12 | Repeatable workflows/schedules | demonstrated controlled scope + missing served process | Served/restart scheduled result/receipt; PostgreSQL/multi-worker/soak |
| 13 | Fleet, goals, background | demonstrated controlled scope + missing served reliability | Served model quality and operational reliability |
| 14 | Direct mutations / whole-app ORACLE | **missing/contradicted/unverified** | 827 mutating routes / 366 high-risk / 311 provider writes unqualified |
| 15 | Remaining exposed application | **regression-only at repaired board boundary; missing general audit** | Tasks/boards and other enabled surfaces need primary-action/durable-readback audit |
| 16 | Installation, compatibility, operations | **open / environment-external unverified** | COMPAT-01/02/03/04, PostgreSQL, mobile/menubar, backup/restore/rollback, public login/restore/restart |
| 17 | Performance/comparative | **unverified** | No reproducible environment/workload/sample/source for PERF/MKT numbers |
| 18 | Profile breadth | **deferred owner decision** | Do not force-enable deferred profiles or add SaaS gates |

Regression-only examples are not promoted to capability: board owner
atomic/consumer repairs (goal 15), restore-child repairs (goal 16), and PR817
web regression gates are bounded repairs, not general acceptance. PR824 is an
integration, not a new claim.

## Highest-impact genuinely unclosed main-web requirement

**Goal 10 — TASK-WAIT-01.** It is explicit original user requirement #1:
domain-independent long-running jobs can wait for missing information for days,
survive restart, continue independent useful work, and resume the same job when
authorized relevant information arrives. The matrix is still open at whole-app
scope, and the existing evidence is partial on both event orders, repeated
pauses, final usable output and current-main ordinary UI.

### Existing mechanism and real callers/consumers

- `backend/core/information_wait.py` — request/receipt/recover/drain
- `backend/core/generic_agent.py` — ReAct `information_wait`
- `backend/api/agent_routes.py` — `resume_information_wait_action`
- `backend/api/assignment_routes.py` — `_record_information_wait`, source/resume routes
- `backend/core/assignment_executor.py` — gap/resume
- `backend/core/goals/goal_run_events.py` — `_resume_woken_run`
- `backend/core/goals/goal_run_executor.py`, `goal_run_router.py`
- `backend/core/hitl_resume.py`
- existing tests: `backend/tests/test_task_wait_*`,
  `test_generic_information_wait_*`, `test_lead_wait_*`

No new wait engine, store, schema or lifecycle is needed.

### Finite acceptance

On one ordinary main-web surface (assignment or goal run):

1. Two missing facts settle in **both event orders**.
2. The same job/execution/task IDs resume after a **real process restart**.
3. **Repeated pauses** are allowed.
4. Irrelevant/foreign/stale answers do **not** release work.
5. Final usable artifact is published only when current; no manual advance.
6. No duplicate effect; current authority and source revision are revalidated.
7. Scratch SQLite/controlled source fixture; no live provider/model or send.

### No-live-action path

Use the existing controlled source fixture and local UI/API; disable the
external transport leaf only in the fixture if needed. No real identity
provider, connector, send, spend or live model.

## Ordered next-work queue

1. **TW-01** (Goal 10) — the recommended next slice above.
2. **EXPO-01** (Goal 15) — one enabled tasks/boards primary action through durable readback.
3. **DOC-01** (Goal 11) — ordinary document upload/open/export/reload.
4. **WF-01** (Goal 12) — one served/restart scheduled workflow result and receipt.
5. **ORACLE-01** (Goal 14) — rebase inventory and qualify one high-risk mutation family.
6. **OPS-01** (Goal 16) — backup/isolated restore/rollback and public restart child.
7. **PERF-01** (Goal 17) — declared measurement source; otherwise remain unverified.
8. **FLEET-01** (Goal 13) — served operational reliability; live model authority separate.
9. **PROFILE-01** (Goal 18) — owner decision only.

## Honest scope

General autonomy, live breadth, performance/comparative numbers,
PostgreSQL/multi-worker/soak, mobile/menubar and full profile breadth remain
unqualified. Bounded controlled evidence does not prove universal judgment,
live provider quality or whole-app completion. The 143/18 catalog is preserved.

## Root attribution

`root-retained-ui-readback.json` is an exact copy of the root-provided
readback `/private/tmp/root-graduation-ordinary-ui-retained-readback-20261110.json`
(agent INTERN, one exact receipt/history, one internal notification). It is
attributed to the root and retains its controlled-fixture boundary; it is not
relabelled as fresh model competence.
