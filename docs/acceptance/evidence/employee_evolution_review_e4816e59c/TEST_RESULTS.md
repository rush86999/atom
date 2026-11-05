# ORACLE-01 tool-mutation review — test results

Executed source: `e4816e59c84041333c7571988ebf5da90f1dc1ce`  
Product source: `eaba0cb8f551796677a8c516155a4be7399207ff`  
Accepted base: `95f7bcac1a0375b4f0465a77e15130f68fc9665d`  
Runtime: real scratch SQLite with fresh sessions and controlled
interleaving/fault seams. No model/provider/browser operation.

Every command ran from the backend root with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TESTING=1
export PYTHONPATH=$PWD
PY314=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
PY311=python3.11
```

`-p no:randomly` is used for deterministic evidence. The combined long-run
selection was split into three complete groups below; a single combined
invocation was killed by the test harness at 85% (exit 152, no test summary),
so it is not used as a gate.

## Focused decision gate

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_evolution_review_tool_mutations.py \
  tests/test_autodev_review_routes.py \
  tests/test_covpush_w100_gaps_f.py::TestSandboxExecuteMutationGap \
  -q --tb=short
```

Result: **47 passed** (`focused-314.log`). The same command with `$PY311`
gives **47 passed** (`focused-311.log`).

This is 39 decision-matrix controls, 5 Auto-Dev route controls and 3
sandbox-gap controls.

## Affected Auto-Dev selection

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_covpush_autodev.py \
  tests/test_covpush_autodev2.py \
  tests/test_covpush_autodev3.py \
  tests/test_covpush_autodev_comms.py \
  tests/test_covpush_w82a_autodev.py \
  tests/test_covpush_w84c_autodev2.py \
  tests/test_covpush_w100_gaps_f.py \
  -q --tb=short
```

Result: **747 passed, 28 failed baseline** on both Python 3.14 and 3.11
(`affected-autodev-314.log`, `affected-autodev-311.log`). The 28-test failure
list is byte-identical to the same command on `95f7bcac1`
(`baseline-autodev-95f7-314.log`, `baseline-autodev-95f7-311.log`).

Failure categories on both source revisions:

- 14 in `tests/test_covpush_autodev_comms.py` (LanceDBHandler /
  ReflectionEngine API drift).
- 8 in `tests/test_covpush_w84c_autodev2.py` (ReflectionEngine API drift).
- 3 in `tests/test_covpush_w82a_autodev.py` (DynamicBenchmarkFetcher).
- 3 in `tests/test_covpush_autodev2.py` (ReflectionEngine API drift).

## Affected evolution selection

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_auto_dev \
  tests/test_agent_evolution_loop.py \
  tests/test_evolution_governance.py \
  tests/test_evolution_pipeline.py \
  tests/test_covpush_w64b_evolution_loop.py \
  tests/test_covpush_w83_evolution.py \
  tests/test_covpush_w104_self_evolution.py \
  tests/test_harness_evolution_api.py \
  -q --tb=short
```

Result: **293 passed, 29 skipped, 1 failed baseline** on both Python 3.14 and
3.11 (`affected-evolution-314.log`, `affected-evolution-311.log`). The single
failure is
`tests/test_auto_dev/test_reflection_engine.py::TestReflectionEnginePatternDetection::test_identifies_repeated_failure_patterns`,
which fails identically on `95f7bcac1`
(`baseline-evolution-95f7-314.log`, `baseline-evolution-95f7-311.log`).

## Affected reviewed-improvement/audit selection

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_reviewed_improvement_apply.py \
  tests/test_reviewed_improvement_boundaries.py \
  tests/test_reviewed_skill_agent_consumption.py \
  tests/test_audit_logger.py \
  tests/test_covpush_w103_audit_logger.py \
  tests/test_oracle_connected_mutations.py \
  tests/test_memento_candidate_review.py \
  tests/test_tool_error_memento_lifecycle.py \
  -q --tb=short
```

Result: **63 passed** on both Python 3.14 and 3.11
(`affected-review-audit-314.log`, `affected-review-audit-311.log`), identical
to `95f7bcac1` (`baseline-review-audit-95f7-*.log`).

## Coverage matrix

The focused suite covers:

- TEAM_LEAD and admin valid twins; member/viewer/guest/anonymous refusal.
- Missing target, foreign-tenant target, and foreign-tenant actor refusal.
- Approve `pending`/`passed`; refuse approve `failed`; reject
  `pending`/`passed`/`failed`.
- Competing decisions: one winner, one 409, one receipt, winner preserved.
- Same operation id + same material: `already_applied`, one receipt, one status
  write.
- Same operation id + different decision: `OPERATION_CONFLICT`.
- Later material revision after decision: `committed_unverified`.
- Stale material and actor demotion before the claim: 409 `effect=none`.
- Sandbox after approve/reject: skipped, sandbox not invoked, decision
  preserved.
- Sandbox racing a reviewer: guarded update matches zero rows, review wins.
- Pending/failed sandbox writes: passed/failed recorded only with exact
  material; failed rerun clears the old error.
- Audit constraint failure: 409 `not_applied`, `effect=none`, target/audit
  absent.
- Post-commit readback failure: 503 `committed_unverified`,
  `effect=committed`, identity.
- Lost confirmation: 503 `effect_unknown`, identity, `do_not_repeat`, no
  secret/exception text.
- 14 audit-tamper variants (action, actor, tenant, workspace, success, security
  level, resource, decision, prior/result status, target, code/error/material/
  result digests): never certified.
- No raw mutated code or execution-error text in decision responses, audit
  metadata, descriptions or captured logs.

## Counts

- Focused decision gate: 47 passed on both versions.
- Affected Auto-Dev: 747 passed + 28 exact baseline failures on both.
- Affected evolution: 293 passed + 29 skipped + 1 exact baseline failure on
  both.
- Affected reviewed-improvement/audit: 63 passed on both.
- Selections overlap; totals are not added together.

## Scope

No live model, provider, credential, spend, send, download, deployment,
administrator/account/budget or PostgreSQL/soak operation was used. No new
table or migration was added; the existing `AuditLog` is the durable ledger.
The admin repair at `5fbb377a4` is independent and not a dependency.
