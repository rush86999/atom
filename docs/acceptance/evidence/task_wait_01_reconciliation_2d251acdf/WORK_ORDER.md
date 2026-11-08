# Work order note — TASK-WAIT-01 evidence gap trace

**First deliverable, before any repair.** Source `2d251acdf`; TASK-WAIT-01
stays OPEN. This note records the trace and the decision not to edit runtime.

## Trace completed

1. Read the explicit owner requirement and all eight cases in
   `docs/acceptance/GOAL_COMPLETION_DELTA_2026_11_06.md` §TASK-WAIT-01.
2. Read the current `APP_COMPLETION_STATE_2026_11_07.md` and the 143-claim
   inventory; no denominator/score change is made.
3. Inspected the actual public consumers:
   - Generic: `POST /api/agents/{agent_id}/jobs/{job_id}/answer`
     (`backend/api/agent_routes.py`), `core/information_wait.py`,
     `core/execution_recovery.py`, startup recovery in `main_api_app.py`.
   - Assignment: `POST /api/assignments/{run_id}/sources`
     (`backend/api/assignment_routes.py`), `core/assignment_executor.py`
     idle/deadline/claim/recovery paths.
4. Inspected the actual tests and current-main bytes; ran 82 targeted controls
   on clean `2d251acdf` with `TESTING=1` and scratch stores. All passed.
5. Compared every relevant evidence packet's declared source files to current
   main (`source-identity.json`). Older packet exits are not relabelled.
6. Inspected the actual PR744 browser packet: 29 stages/162 assertions, 8/11
   source files byte-equal to current main, 3 harness files absent. Its health
   badge says `ec69e24f4385-dirty`, not the declared `d3f58d81d`; the
   defensible binding is the per-file Git blob proof, not the badge.

## Decision

No current-main runtime failure was reproduced in the 82 controls. Therefore
no local repair was attempted. The remaining items are scope/evidence gaps,
not a basis for inventing another engine:

- G1 Generic active-vs-absolute wait budget.
- G2 Changed source after acceptance before consumption.
- G3 Generic source upload/selection (the answer event is covered).
- G4 Symmetric Generic two-job isolation.
- G5 Browser source provenance badge mismatch.
- G6 Browser cancellation/deadline/revocation/long-idle/both-order breadth.

If a future authorized slice targets one of these, reproduce failure first in a
fresh scratch `TESTING=1` world, then use the existing lifecycle/route/claim
mechanism and add positive/negative twins. Do not add a second task engine,
event bus, router, store or polling/scheduler.

## Boundaries

No live provider/model/account/credential/send/spend/install/deploy/browser/
KVM/Linux action. No whole-app/general-judgment claim. Root independently
accepts.
