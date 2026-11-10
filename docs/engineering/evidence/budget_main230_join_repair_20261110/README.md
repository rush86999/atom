# Budget main-230 join repair — live feedback session factory

Date: 2026-11-10

Parents:
- `ce70203da1969fb614b99cf39bed869938f55089` (budget branch: atomic cap,
  physical-attempt prerequisites, authoritative scratch scope fixtures)
- `230231f5114612f4b31a602190c318667e94f2f1` (main: PR834)

Worktree: root integration checkout (staged merge preserved; no reset/abort).

## Incident (not a tenant/admission failure)

The joined main-230 gate ended **26 failed, 282 passed**
(`/private/tmp/root-budget-main230-joined-ykhqj1k_/gate.log`). Every failure was
in `tests/test_employee_business_feedback.py`.

The trace is decisive and is NOT what the earlier hosted-12 scope defect
looked like:

- the controlled structured dispatch really ran and parsed a proposal
  (`result_type=EmployeeWorkProposal`), so provider eligibility/admission was
  fine;
- the consumer ran its business evaluation and reported
  `evaluation.recorded == True`;
- `_rows(feedback_db)` was nevertheless **empty** and the router logged
  `business feedback skipped: no exact generation row for <generation>`.

So the annotation was written somewhere other than the authoritative scratch
DB the test owns. No admission/tenant/default behavior is implicated.

## Root cause

`core/learning_llm_router.py` bound the session factory at import time:

```python
from core.database import get_db_session
```

`core.database` deliberately swaps `get_db_session` in harnesses and
bootstrap/worker code (scratch DB, broken-commit controls). If that module was
first imported **while a temporary factory was installed**, the router froze
the temporary factory forever. After the caller restored/rotated to the
authoritative factory, `_persist_feedback` read and wrote the stale (in the
joined gate effectively empty/disposed) store. The exact generation row then
looked missing even though dispatch and evaluation succeeded.

This is import-order sensitivity, not a binding/CAS/classification change and
not a missing tenant row.

## Fix (scoped)

`core/learning_llm_router.get_db_session` is now a thin wrapper that resolves
`core.database.get_db_session` **at call time**:

```python
def get_db_session(*args, **kwargs):
    from core.database import get_db_session as _live_get_db_session
    return _live_get_db_session(*args, **kwargs)
```

- Production behavior is identical (one function object either way).
- The established test seam is preserved: suites that patch
  `core.learning_llm_router.get_db_session` replace the wrapper and still win.
- No new engine, store, router, migration or dependency.
- Exact receipt binding, shared CAS (`_annotate_with_retry` /
  `_commit_annotation_cas`), verdict precedence/classification and scope
  refusal are untouched.

Root independently verified the same source hash
`d2f86d49431545725aed3fb4dc49d0b85afa8f0a8c698ec0984739f935212093` on Python
3.11 and 3.14 (`after/root-independent-after.json`); the before probe at
frozen `973` failed the current-factory control and passed the local-override
control (`before/root-independent-before.json`).

## Permanent failure-first regression

`backend/tests/test_learning_router_live_session_factory.py`:

1. **current factory each call** — two successive rebinds of
   `core.database.get_db_session` are both observed;
2. **existing local override seam** — patching
   `core.learning_llm_router.get_db_session` still wins;
3. **restored-factory write path (subprocess isolate)** — a temporary factory
   is installed, the router is imported while it is installed, then the
   authoritative factory is restored. A business annotation and a legacy
   fabrication correction must both land in the CURRENT authoritative DB
   (exact generation row, `annotated` status, failure classification, quality
   rewrite and one bumped evaluation revision) while the stale DB's rows stay
   untouched.

Failure-first proof at `ce70203da` (same file, pre-fix source):
**2 failed, 1 passed** (`before/permanent-regression-negative.log`):
- current-factory binding failed;
- restored-factory business/legacy writes hit the stale DB;
- the local-override seam passed (it must keep passing).

After the fix: **3 passed** (`after/permanent-regression.log`).

## Gates

| Gate | Result | Log |
|---|---|---|
| joined main-230 selection (exact prior command) | **308 passed** | `after/joined-after.log` |
| permanent regression | **3 passed** | `after/permanent-regression.log` |
| broad affected: feedback + learn-router + scoped CAS + CI-lane contract | **287 passed** | `after/broad-affected.log` |
| pre-fix permanent regression | **2 failed / 1 passed** | `before/permanent-regression-negative.log` |
| root independent after probe (3.11 + corrected 3.14) | pass | `after/root-independent-after.json` |

Scratch SQLite only (`SECRET_KEY=scratch-only-readable`); no live
provider/model/DB/credential/send/spend/deploy; no dependencies.

## CI preservation (both parents)

The merged tree keeps both parents' review gates and adds exactly one normal
step, `Run live session-factory and feedback write controls`, declared once in
`backend/tests/fixtures/ci_backend_additions.json`. The immutable pre-parallel
ledger and every existing command/environment/setup are preserved; the
CI-lane contract test passes in the broad affected run.

## Honest boundaries

- The physical-attempt successor (configured numeric-zero image admission) is
  queued for a separate worktree; the frozen physical packet and its worktree
  are untouched by this repair.
- No claim is made that every suite-wide module with an import-time session
  binding is audited; this repair fixes the feedback write path that was
  reproduced and now has a permanent control.
- Root owns independent acceptance/merge; this packet does not self-accept.
