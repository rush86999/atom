# Workflow approval and scheduler recovery — evidence

Bounded public workflow/scheduling recovery successor from main `671986755`.
Source checkpoint: `e205b6fb8`.

## Boundary

The approval/effect half already exists in main:
`backend/tests/test_workflow_hitl_resume_once.py` proves policy denial pauses
without executing, an exact durable approval runs the critical step once,
rejection cannot unlock, a different step/execution cannot unlock, a payload
change re-pauses, and a crash-after-dispatch step is never resent.

This change adds the missing scheduler persistence half using the real
`WorkflowScheduler` and its SQLAlchemy jobstore with a harmless local counter
callback:

- paused one-shot job → scheduler restart → **no fire**;
- cancelled one-shot job → scheduler restart → **no fire**;
- job fired exactly once → scheduler restart → **no duplicate fire**.

No workflow/network effect, live provider or external mutation is used.

## Verification

| Gate | Result |
|---|---|
| New scheduler controls, Python 3.11 | **3 passed** |
| Approval-resume files, Python 3.11 | **8 passed** |
| Updated CI selection, Python 3.11 | **630 passed, 1 skipped, 0 failed** |
| Updated CI selection, Python 3.14 | **630 passed, 1 skipped, 0 failed** |
| Hosted backend job 127967456262 | **630 passed, 1 skipped**; memory recall 1.0 |
| Hosted e2e job 127967456302 | API **211 passed, 1 skipped, 1 xfailed**; UI **29 passed**; role UI **40 passed**; zero failures |
| syntax, frontend typecheck, app boot, quickstart, Docker, GitGuardian | pass |

Logs: `scheduler-controls-311.log`, `approval-resume-311.log`,
`ci-selection-311.log`, `ci-selection-314.log`, `hosted-backend.log`,
`hosted-e2e.log`.

## Source hashes

| File | Git blob | SHA-256 |
|---|---|---|
| `backend/tests/test_workflow_scheduler_recovery.py` | `bc6fab32a424fd09299d98bfa7a07c2df7af9a2e` | `01a7c8aa60c17e311ca382e7f0c2fc33c2b85d371a8bb218e936afcc14e40879` |
| `.github/workflows/ci.yml` | `63eda6ead2cbaa38c120a0f88a212e27ef1290e3` | `0c3c2c6fb91c0419242a3dc22790d7d1b3a559cbe39178730922978d5dcd72ac` |

Artifact hashes are in `verification.json`.

## Boundaries

- Scheduler persistence is proven for the SQLAlchemy jobstore in one local
  process/event loop; PostgreSQL/multi-worker/soak remain separate.
- The scheduler callback is a harmless local counter, not a workflow or
  external effect.
- No product/authority change; no live model/provider/account/credential/
  spend/send/download/deployment.
