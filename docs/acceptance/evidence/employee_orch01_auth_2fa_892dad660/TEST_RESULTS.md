# ORACLE-01 five-route auth/2FA — test results

Executed source: `892dad66025c35febc5b6cdebe3bad0e292cfdfb`
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
  -q --tb=short
```

Result: **47 passed** (`focused-314.log`). The same command with `$PY311`
gives **47 passed** (`focused-311.log`).

This is 29 existing focused 2FA route tests plus 18 real scratch-account
controls.

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

- Focused: 47 passed on both versions.
- W80B 2FA: 33 passed on both versions.
- Affected: 199 passed + 1 pre-existing failure on both versions.
- Unique passing controls: 279 (selections overlap; not added to focused).

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
- no secret/OTP/recovery code in audit metadata or operation receipts.

## Scope

No model, browser, provider, credential, spend, send, download or deployment
operation was used. PostgreSQL concurrency/soak and live identity-provider
operation are not claimed. Whole-app ORACLE-01 remains open.
