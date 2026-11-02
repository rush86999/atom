# Canvas teaching-boundary repair

Status: **submitted for independent verification; not self-accepted.** This
repairs the four reproduced teaching-boundary failures in the canvas
assignment batch. Earlier canvas acceptance at `4859b0ce2477` and connected
acceptance at `6431bcb78` remain unchanged.

## Executed source

| Item | Value |
|---|---|
| Worktree | `/private/tmp/atom-canvas-successor` |
| Branch | `codex/brennan-canvas-successor-20261101` |
| Executed source | `a87882526323` |
| Tree at execution | clean (`dirty=false`) |
| Backend identity | pid `30391`, source `a87882526323`, instance `a87882526323.30391.1793628386` |
| World | `canvas-successor-20261101-assignment` |
| Frontend | production build `X_PhH8Q4l6qVCB2K0XQLf` on `127.0.0.1:3133` |
| Backend | `127.0.0.1:8092`, real routes/executor/sqlite |

## The four blockers

1. **Stale proposal with new revisions** — promotion recomputes the
   authoritative receipt and compares its digest, state/source/manifest/policy
   bindings and target with the proposal's original provenance. It also
   verifies the reviewed proposal-content digest. A newer request revision
   cannot bless an old proposal; the response is 409 and no journal write
   occurs.
2. **Foreign/moved employee** — the target is resolved from the authoritative
   `AgentRegistry` and authorized against the authenticated user's workspace
   and tenant at proposal, assignment creation and promotion. Foreign,
   nonexistent or moved targets refuse before any journal/task/provider
   mutation. Canvas consumers also recheck the authenticated principal and
   tenant; `canvas.created_by` is not used as authority.
3. **Failed promotion leaves a lesson** — `deliver_teacher_lesson` and both the
   student and standing-guidance journal paths now support `commit=False`.
   Promotion performs the journal append and canvas CAS in one transaction; a
   CAS failure rolls the journal append back. No compensating deletion and no
   falsely promoted proposal.
4. **Promoted lesson unavailable to work** — receipt provenance is stored as a
   structured `entry["provenance"]` field, not as top-level applicability
   context. A global lesson is returned by normal
   `get_agent_lessons(task_context={})`; genuine customer/qualification/task
   context remains the only applicability filter.

## Controls

- Four independent verifier probes: **4/4 passed**.
- Positive twins: global lesson consumed by ordinary work; full provenance
  digest/resource versions preserved; explicit promotion once; duplicate
  promotion `already_promoted`.
- Moved target after proposal: promotion refused, journal unchanged.
- Non-supervisor role: promotion 403, journal unchanged.
- Journal failure: proposal remains `proposed`, no lesson.
- CAS failure after validation: journal append rolled back, no lesson.
- Foreign target at assignment creation: 403/404, no task/provider effect.
- Foreign assignment principal at canvas receipt consumption: failed closed.
- Source/canvas change after proposal: old proposal refused; a fresh proposal
  is required.
- Action guards still recheck revision/manifest/source/action declaration
  immediately before dispatch.

## Tests

| Scope | Result |
|---|---|
| Canvas focused suite | **127 passed** |
| Assignment regression (`routes/executor/quote`) | **167 passed** |
| Verifier canvas + assignment probes | **7 passed** |
| Teaching neighborhood (chat/conversation/canvas/artifact/cross-canvas) | **203 passed** |
| Frontend canvas suites | **7 passed** |
| Ordinary-UI browser smoke | **17/17 checks** |

Known pre-existing mock-only failures: 3 tests in
`tests/test_student_training_service.py` use a generic DB mock that returns the
agent for the duplicate-proposal guard added on 2026-08-27 (`1591320ea`); they
are not caused by this batch and are excluded from the 203. All other affected
teaching suites pass.

## Changed files

```text
backend/api/canvas_capability_routes.py
backend/core/agent_pedagogy.py
backend/core/assignment_executor.py
backend/core/canvas_assignment.py
backend/core/canvas_capability_service.py
backend/core/student_learning_service.py
backend/tests/test_canvas_assignment_integration.py
```

## Exclusions

- No live provider lookup, refresh, write or send.
- Teaching promotion is explicit human approval, not autonomous learning.
- No hosted deployment, universal mini-app/runtime claim, multi-worker/soak or
  unfamiliar-user study.
- Connected acceptance remains `6431bcb78`; historical 111/123 unchanged.
