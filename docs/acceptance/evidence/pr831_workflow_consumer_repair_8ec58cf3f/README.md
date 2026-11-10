# PR831 workflow consumer repair — HITL resume and real qualification fixtures

Status: **submitted for independent verification.** No merge or deployment was
performed. Root PR831 worktree was not edited.

## Confirmed finding on frozen PR831 head `b071c8702`

The hosted backend-core run reported **5 failed, 1032 passed, 1 skipped**.
All five were the public workflow approval family:

```
tests/test_workflow_public_approval_flow.py::test_public_workflow_approval_is_visible_decidable_and_resumes_once
tests/test_workflow_public_approval_flow.py::test_scheduled_real_workflow_approval_join
tests/test_workflow_public_approval_flow.py::test_public_workflow_rejection_leaves_zero_effect
tests/test_workflow_public_approval_flow.py::test_changed_material_after_review_does_not_execute
tests/test_workflow_scheduled_process_restart.py::test_scheduled_approval_join_survives_a_separate_process_restart
```

The approval decision returned 200, but the resume bridge failed with
`'_GeneratorContextManager' object has no attribute 'close'`. The workflow
stayed `PAUSED` with `Maturity check failed. Required: supervised`; rejection
stayed `PAUSED` instead of `FAILED`; changed material left only the old
`approved` row instead of `approved` + a new `pending` review.

## Root cause

PR831 changed `core/hitl_resume.py::_load_action` from a proper

```python
with get_db_session() as db:
```

block to a bare `session = get_db_session()` followed by `session.query(...)`
and `session.close()`. `get_db_session()` returns a generator context manager,
not a SQLAlchemy `Session`. Every no-bind resume therefore raised
`'_GeneratorContextManager' object has no attribute 'query'`; the `finally`
block then masked it as `... no attribute 'close'`.

The `bind` path (used by qualification receipts) was already a real Session,
so it did not show the same error.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/web-pr831-workflow-consumer-repair-20261110` |
| Base | `b071c8702cb1c0aed0ad70bb90a12cb343278c44` |
| Code commit | `8ec58cf3f` |
| Runtime | real scratch SQLite + real FastAPI routes + scratch JWT; no live DB/model/provider |

## Product repair

`backend/core/hitl_resume.py::_load_action` now enters the session context
manager in both paths:

- no bind: `with get_db_session() as session:` (the context manager creates,
  commits, and closes the real Session);
- bind: `with closing(sessionmaker(bind=bind)()) as session:` so the
  qualification receipt keeps the caller's engine/connection.

No maturity threshold, review binding, workflow approval rule, graduation
qualification rule, or durable state contract was changed.

## Workflow controls (all preserved)

| Control | Result |
|---|---|
| Public approval is visible, decidable, and resumes once | pass |
| Scheduled real workflow approval join | pass |
| Rejection leaves zero effect and reaches FAILED | pass |
| Changed material after review does not execute; new pending review appears | pass |
| Separate OS-process scheduled resume survives and spent job does not re-fire | pass |
| Frozen scope cannot be rewritten by resume inputs | pass |
| Foreign scope cannot see or decide | pass |

Failure-first: `failure-first.log` — **5 failed / 4 passed** in the two
workflow files. After: `focused-after.log` — **5 passed**.

## Graduation fixture adaptation (test-only; production gate unchanged)

The four `TestPromotionReadinessGate` positives in
`tests/test_graduation_readiness_tenant_scoping.py` were stale: they created
readiness evidence only, while PR831 intentionally requires a scoped
capability review/receipt for every upward promotion.

The positives now drive the real server path:

1. seed a real scoped `AgentExecution` with actual durable output;
2. `POST /api/episodes/graduation/qualification/request` with that evidence;
3. approve the resulting review through `POST /api/agents/approvals/{id}`;
4. verify the resume wrote the real qualification receipt;
5. then call the existing promotion route.

The missing-qualification negative, exact-scope controls, and the
episode-floor blocked-then-allowed twin remain. No fake passed receipt, no
broad exemption, and no maturity/evidence relaxation.

`graduation-readiness-after.log` — **16 passed**.
`ci-graduation-after.log` — **138 passed**.
`ci-qualification-after.log` — **94 passed**.

## Quickstart environment seam (not a product failure)

The exact full CI workflow selection first failed collection because
`pytest_freezegun` was not registered; that attempt is preserved in
`ci-workflow-env-internalerror.log`. With the declared
`/private/tmp/root-py311-plugins` path and `-p pytest_freezegun`, the same
selection ran and produced **5 failed / 1032 passed / 1 skipped**; all five
were `tests/test_quickstart_python_guard.py` because this sparse worktree did
not have the tracked `scripts/quickstart.sh`.

The script was materialized in this own worktree with
`git sparse-checkout add scripts/quickstart.sh` (no root checkout, no runtime
change). The exact five controls then passed:

`ci-quickstart-after.log` — **5 passed**.

Union proof: the 1032 passing tests from the full selection are unchanged
product/source; the five workflow failures were fixed before that run; the
five quickstart failures were the sparse-checkout seam and now pass. No full
selection rerun was needed after the test-only graduation adaptation because
that file is not in the line-185 workflow selection.

## Boundaries

- Real scratch SQLite only; no PostgreSQL/soak/multi-worker qualification.
- No live model, provider, credential, send, spend, download, deployment or
  live-administrator change.
- No new dependency, table, migration, script or testconfig.
- No test deleted, skipped or xfailed.
- No merge or self-acceptance; root review remains independent.
