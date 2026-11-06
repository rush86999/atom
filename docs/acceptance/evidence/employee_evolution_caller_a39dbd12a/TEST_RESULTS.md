# Sandbox caller-transaction ownership repair — test results

Executed source: `a39dbd12a01bbcaccaf51598f7fc586ed93926f4`  
Product source: `d4cce1625205f79412be9387f7c3fed1023d376f`  
Prior repair: `6346cad2a` (evidence `6fbeb4ebd`)  
Accepted base: `95f7bcac1a0375b4f0465a77e15130f68fc9665d`  
Runtime: real scratch SQLite with fresh sessions and a doubled sandbox; no live
sandbox/model/provider.

Every command ran from the backend root with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TESTING=1
export PYTHONPATH=$PWD
PY314=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
PY311=python3.11
```

## Verifier probes

```sh
$PY314 -B -m pytest -p no:randomly \
  /private/tmp/test_verifier_evolution_e481_parallel.py \
  /private/tmp/test_verifier_evolution634_caller_work.py \
  -q --tb=short
```

Result: **5 passed** (`probes-314.log`): the original changed-lineage and
stale-approved/rejected probes plus the two caller-work loss probes.

## Focused gate

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_evolution_review_tool_mutations.py \
  tests/test_evolution_sandbox_parallel_contract.py \
  tests/test_evolution_caller_transaction_contract.py \
  tests/test_autodev_review_routes.py \
  tests/test_covpush_w100_gaps_f.py::TestSandboxExecuteMutationGap \
  -q --tb=short
```

Result: **65 passed** (`focused-314.log`). The same command with `$PY311`
gives **65 passed** (`focused-311.log`).

The 65 are the prior 58 decision/lineage/freshness controls plus 7 caller
transaction twins.

## Affected evolution selection

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_auto_dev \
  tests/test_evolution_sandbox_parallel_contract.py \
  tests/test_evolution_caller_transaction_contract.py \
  tests/test_agent_evolution_loop.py \
  tests/test_evolution_governance.py \
  tests/test_evolution_pipeline.py \
  tests/test_covpush_w64b_evolution_loop.py \
  tests/test_covpush_w83_evolution.py \
  tests/test_covpush_w104_self_evolution.py \
  tests/test_harness_evolution_api.py \
  -q --tb=short
```

Result: **311 passed, 29 skipped, 1 failed baseline** on both Python 3.14 and
3.11 (`affected-evolution-314.log`, `affected-evolution-311.log`).

The single failure is the known pre-existing
`tests/test_auto_dev/test_reflection_engine.py::TestReflectionEnginePatternDetection::test_identifies_repeated_failure_patterns`
API-drift control; it is identical in the base selection
(`baseline-evolution-314.log`, `baseline-evolution-311.log`).

## Affected review/audit selection

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_evolution_review_tool_mutations.py \
  tests/test_evolution_sandbox_parallel_contract.py \
  tests/test_evolution_caller_transaction_contract.py \
  tests/test_autodev_review_routes.py \
  tests/test_covpush_w100_gaps_f.py::TestSandboxExecuteMutationGap \
  tests/test_reviewed_improvement_apply.py \
  tests/test_reviewed_improvement_boundaries.py \
  tests/test_reviewed_skill_agent_consumption.py \
  tests/test_memento_candidate_review.py \
  tests/test_audit_logger.py \
  tests/test_covpush_w103_audit_logger.py \
  -q --tb=short
```

Result: **111 passed** on both Python 3.14 and 3.11
(`affected-review-audit-314.log`, `affected-review-audit-311.log`).

## Caller-transaction twins

`tests/test_evolution_caller_transaction_contract.py` covers:

- dirty caller edit + peer rejection during worker: result skipped, caller edit
  still uncommitted, caller commit persists it, mutation remains rejected;
- already-flushed caller edit + committed review: zero sandbox calls, result
  skipped, caller commit persists the edit;
- dirty caller edit + pending mutation: worker executes, sandbox result commits
  on the owned session, caller edit stays uncommitted until the caller commits;
- new caller object and deleted caller object survive a skipped result;
- clean caller read transaction still executes once and records passed;
- flushed caller + pending mutation returns deferred `caller_transaction_pending`
  with zero calls and preserves the caller edit.

## Counts

- Verifier probes: 5 passed.
- Focused: 65 passed on both versions.
- Affected evolution: 311 passed + 29 skipped + 1 exact baseline failure on both.
- Affected review/audit: 111 passed on both.
- Selections overlap; totals are not added together.

## Scope

No live sandbox/Docker/model/provider/credential/spend/send/download/
deployment operation. No new status/worker/review/transaction engine.
PostgreSQL runtime/soak and multi-worker qualification remain open.
