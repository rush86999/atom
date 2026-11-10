# PR831 workflow consumer repair — test results

Executed source: `8ec58cf3f`  
Base: `b071c8702cb1c0aed0ad70bb90a12cb343278c44`

Every command ran from `backend/` through the bounded test gate with
`TESTING=1`, `PYTEST_CURRENT_TEST=1`, an explicit scratch SQLite
`DATABASE_URL`, and scratch `ATOM_DATA_DIR`/`ATOM_OFFICE_DIR`/
`ATOM_LANCEDB_PATH`/`LANCEDB_URI`. The CI selections additionally used
`PYTHONPATH=/private/tmp/root-py311-plugins:$PWD` and
`-p no:randomly -p pytest_freezegun`.

## Failure-first on b071

```sh
python3.11 -m pytest \
  tests/test_workflow_public_approval_flow.py \
  tests/test_workflow_scheduled_process_restart.py \
  -q --tb=short -p no:randomly
```

Result: **5 failed, 4 passed** (`failure-first.log`).

## Focused hosted failures after the repair

The exact five hosted failures:

```sh
python3.11 -m pytest \
  tests/test_workflow_public_approval_flow.py::test_public_workflow_approval_is_visible_decidable_and_resumes_once \
  tests/test_workflow_public_approval_flow.py::test_scheduled_real_workflow_approval_join \
  tests/test_workflow_public_approval_flow.py::test_public_workflow_rejection_leaves_zero_effect \
  tests/test_workflow_public_approval_flow.py::test_changed_material_after_review_does_not_execute \
  tests/test_workflow_scheduled_process_restart.py::test_scheduled_approval_join_survives_a_separate_process_restart \
  -q --tb=short -p no:randomly
```

Result: **5 passed** (`focused-after.log`).

## CI workflow selection

Exact line-185 selection from `.github/workflows/ci.yml`.

First attempt without the declared plugin path:
`ci-workflow-env-internalerror.log` — collection INTERNALERROR,
`'freeze_time' not found in markers configuration option`.

Second attempt with `/private/tmp/root-py311-plugins` and
`-p pytest_freezegun`:
`ci-workflow-full.log` — **5 failed, 1032 passed, 1 skipped**.

All five failures were `tests/test_quickstart_python_guard.py` because the
sparse worktree lacked `scripts/quickstart.sh`.

After `git sparse-checkout add scripts/quickstart.sh` (see
`sparse-checkout.txt`):

`ci-quickstart-after.log` — **5 passed**.

Union proof: the 1032 passing tests are unchanged; the five workflow failures
were fixed before the full run; the five quickstart failures were the
sparse-checkout seam and now pass.

## CI workflow subset (exact workflow files)

```sh
python3.11 -m pytest \
  tests/test_workflow_hitl_resume_once.py \
  tests/test_workflow_hitl_persisted_resume.py \
  tests/test_workflow_scheduler_recovery.py \
  tests/test_workflow_approval_scope.py \
  tests/test_workflow_public_approval_flow.py \
  tests/test_workflow_scheduled_process_restart.py \
  -q --tb=short --timeout=300 --timeout-method=thread
```

Result: **24 passed** (recorded in the session log; see `focused-after.log`
for the hosted five).

## HITL bridge unit controls

`hitl-resume-after.log` — **10 passed** after the monkeypatched `_load_action`
fixtures accepted the optional `bind` kwarg.

## Graduation CI selection

Exact line-209 selection from `.github/workflows/ci.yml`.

Before the fixture adaptation: **4 failed, 134 passed**; all four were the
stale `TestPromotionReadinessGate` positives.

After adapting the positives to the real qualification request/approval/
receipt path:

`ci-graduation-after.log` — **138 passed**.

The negative missing-qualification case, exact-scope cases, and the
episode-floor blocked-then-allowed twin remain in the file.

`graduation-readiness-after.log` — **16 passed** for the whole
`tests/test_graduation_readiness_tenant_scoping.py` file.

## Qualification CI selection

Exact line-490 selection from `.github/workflows/ci.yml`.

`ci-qualification-after.log` — **94 passed**.

## Affected selection

`affected-after.log` — **146 passed** across HITL resume, workflow approval,
workflow scope, scheduled process restart, graduation governance, graduation
authority, qualification join, generic information wait, orchestration
checkpoint and chat teaching.

## Boundaries

No live DB/model/provider/send/spend/deploy/deps. No new script, dependency,
table, migration or testconfig. No test deleted, skipped or xfailed.
