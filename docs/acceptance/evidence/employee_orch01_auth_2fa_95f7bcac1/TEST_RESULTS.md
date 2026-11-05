# ORACLE-01 five-route auth/2FA — test results

Executed source: `95f7bcac1a0375b4f0465a77e15130f68fc9665d`
Accepted canvas base: `fe401e1112fdb544ce07650f7733519c14b25790`
Runtime: real scratch SQLite with fresh sessions; controlled time/rate limiter.

Frozen extraction roots:

- Python 3.14: `/private/tmp/atom-auth2fa-892-314/backend`
- Python 3.11: `/private/tmp/atom-auth2fa-892-311/backend`

Every command ran from the corresponding extraction root with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TESTING=1
export PYTHONPATH=$PWD
PY314=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
PY311=python3.11
```

## Focused 2FA controls

```sh
$PY314 -B -m pytest \
  tests/test_covpush_w89_auth_2fa.py \
  tests/test_oracle_auth_2fa_writes.py \
  tests/test_auth_2fa_boundary_repair.py \
  tests/test_auth_2fa_migration_upgrade.py \
  -q --tb=short
```

Result: **82 passed** (`focused-314.log`). The same command with `$PY311`
gives **82 passed** (`focused-311.log`).

This is the original 47 route/durable controls, 34 boundary/valid-twin
controls (including stale-mirror cleanup) and the pre-migration
scratch-database upgrade control.

## Independent boundary probes

```sh
$PY314 -B -m pytest /private/tmp/test_verifier_auth892_boundaries.py \
  -q --tb=short
```

Result: **12 passed** (`boundary-probes-314.log`). The same probe with `$PY311`
gives **12 passed** (`boundary-probes-311.log`, `-p no:randomly` for the
external-path pytest-randomly/thinc seed issue).

## Pre-migration upgrade

```sh
$PY314 -B -m pytest tests/test_auth_2fa_migration_upgrade.py -q
```

Result: **1 passed** (`migration-314.log`; `migration-311.log` on Python
3.11). The control builds the old users schema, stamps the pre-migration
revision, runs the real Alembic upgrade and checks the revision/defaults plus
the plaintext-to-fingerprint backfill.

## W80B 2FA classes

```sh
$PY314 -B -m pytest tests/test_covpush_w80b_api_routes.py -k "2FA" \
  -q --tb=short
```

Result: **33 passed, 308 deselected** (`w80b-2fa-314.log`). The same command
with `$PY311` gives **33 passed, 308 deselected** (`w80b-2fa-311.log`).

The deselected classes are unrelated workflow-debug coverage in the same
module, not part of this slice.

## Affected auth/HITL/audit/oracle selection

```sh
$PY314 -B -m pytest \
  tests/test_round21_2fa_enable_disable_rate_limit.py \
  tests/test_hitl_approvals_journey.py \
  tests/test_hitl_resume.py \
  tests/test_covpush_w105_workflow_approval_routes.py \
  tests/test_covpush_w104_intervention.py \
  tests/test_covpush_w82_intervention.py \
  tests/test_audit_logger.py \
  tests/test_covpush_w103_audit_logger.py \
  tests/test_audit_routes_api.py \
  tests/test_agent_action_audit.py \
  tests/test_integration_audit.py \
  tests/test_execution_insert_path_audit.py \
  tests/test_oracle_connected_mutations.py \
  tests/test_oracle_effect_families.py \
  -q --tb=short
```

Result: **199 passed, 1 failed** (`affected-314.log`). The same selection on
Python 3.11 gives **199 passed, 1 failed** (`affected-311.log`).

The failure is pre-existing on the accepted canvas base `fe401e111`:

```text
tests/test_covpush_w104_intervention.py::TestGetPendingInterventions::test_default_workspace_no_filter
```

`base-pre-existing.log` records it, plus the unrelated W75 JWT/rate-limit
failures, on that base without this repair.

## Counts

- Focused: 82 passed on both versions.
- Independent boundary probes: 12 passed on both versions.
- W80B 2FA: 33 passed on both versions.
- Affected: 199 passed + 1 pre-existing failure on both versions.
- Migration upgrade: 1 passed on both versions.
- Selections overlap; totals are not added together.

## Coverage matrix

The focused real controls include:

- setup pending-secret preservation and post-enable refusal;
- enable/disable verified state and same-operation replay receipts;
- wrong/expired/replayed TOTP and concurrent same-code;
- single-use backup code, same-operation retry, new-operation replay and
  concurrent consumption;
- legacy plaintext backup-code backfill;
- duplicate/stale enrollment and stale enable/disable writers;
- moved HITL action scope after the final read;
- durable `reviewed_by`/`reviewed_at` after a fresh session;
- foreign tenant/workspace, required-role column/context, rejected/missing
  action;
- audit unavailable/refuted after commit and lost commit confirmation;
- unverified retry 503 and verified retry `already_applied` without a new event;
- complete audit evidence including missing/wrong-type/one-wrong-all-others-right
  workspace, tenant, resource, revision, target, operation, event and success
  fields;
- concurrent actor workspace/status/role and action material changes before the
  claim;
- pre-migration SQLite Alembic upgrade and recovery-code backfill;
- no secret/OTP/recovery code in audit metadata, operation receipts, HTTP
  responses or captured logs.

## Scope

No model, browser, provider, credential, spend, send, download or deployment
operation was used. PostgreSQL concurrency/soak and live identity-provider
operation are not claimed. Whole-app ORACLE-01 remains open.
