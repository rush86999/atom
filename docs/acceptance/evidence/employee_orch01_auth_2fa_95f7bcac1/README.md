# ORACLE-01 / five-route auth-2FA verified-write slice

Status: **submitted for independent verification.** This is the bounded
five-route auth/2FA slice from the accepted canvas evidence
`fe401e111` (runtime `82ac9681a`). Whole-app ORACLE-01 and the full auth family
remain open.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-auth-2fa-20261105` |
| Base accepted canvas evidence | `fe401e1112fdb544ce07650f7733519c14b25790` |
| Accepted canvas runtime | `82ac9681ad66b276a135ce06e1d2b7f03cbb30d9` |
| Executed source | `95f7bcac1a0375b4f0465a77e15130f68fc9665d` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime | real scratch SQLite with fresh sessions; controlled time/rate limiter |
| Model/provider/browser calls | none |

## Scope

Only these five mounted routes:

- `POST /api/auth/2fa/setup`
- `POST /api/auth/2fa/enable`
- `POST /api/auth/2fa/disable`
- `POST /api/auth/2fa/backup/verify`
- `POST /api/auth/2fa/verify-action/{action_id}`

Login, password reset/change, SSO, passkeys, mobile biometric, provider
disconnect and full auth-family coverage are outside this slice. No live
account/factor change, credential/provider setup, message, spend or deployment
authority was used.

## Durable state added

- `User.two_factor_last_totp_step` and `User.two_factor_revision`.
- `auth_2fa_backup_codes`: one conditional single-use row per recovery code,
  storing only a keyed HMAC fingerprint.
- `auth_2fa_operations`: one safe receipt per logical operation, bound to
  actor/scope/action/target/factor revision/material fingerprint. It never
  stores raw OTP, secret or recovery codes.
- Alembic migration `20261105_auth_2fa_durable_state.py`, guarded for databases
  already created from the current models and backfilling pre-migration
  plaintext recovery-code mirrors once into fingerprint rows.
- Existing `HITLAction.reviewed_by` / `reviewed_at` are now populated durably.

## Product contracts

### Setup

- A retry while setup is pending returns the SAME scanned pending secret and
  provisioning URL; it does not replace the enrollment.
- Once 2FA is enabled, setup refuses and never exposes or replaces the secret.
- A new pending secret is created only when no pending secret exists.

### Enable / disable

- TOTP is verified against the current factor secret; the factor revision and
  last accepted time-step are conditional-write predicates.
- Enable persists the enabled flag, five recovery codes, the code hash rows,
  factor revision and last step, then reads back the exact state.
- Disable clears the secret, recovery codes and hash rows under the same
  revision/step guard.
- A stale writer, replay, or concurrent factor change matches zero rows and
  leaves the factor unchanged.

### TOTP single-use

- The accepted time-step is stored on the User row. A code/time-step already
  accepted for this factor can never be accepted again, even for a different
  operation or after a fresh session.
- Concurrent same-code requests use a conditional `last_step < step` update;
  exactly one wins.
- The existing OTP library/window and rate limiter are unchanged.

### Recovery codes

- Enable delivers the five codes exactly once.
- A backup code is consumed by a conditional update on its
  `auth_2fa_backup_codes` row (`consumed_at IS NULL`). Concurrent/replayed use
  matches zero rows.
- Legacy plaintext-only code lists are backfilled once into hash rows on first
  use; the User plaintext list remains a compatibility projection. Consumption
  also removes any stale legacy mirror entries whose durable row is already
  consumed, so a stale list/count cannot resurrect a code.
- A consumed code is never accepted again; a same-operation retry returns an
  already-applied receipt without a new authentication success.

### HITL action verification

- The exact action is loaded and checked against the authenticated actor's
  tenant/workspace, the action's required-role column and the existing
  intervention role policy.
- The action claim is a conditional update
  `status IN (pending, pending_2fa)` plus the exact action scope snapshot,
  setting `status=approved`, `reviewed_by=actor`, `reviewed_at=now`.
- Pending, rejected, foreign, stale, missing or mismatched actions release
  zero descendants; a moved scope after the read matches zero rows and rolls
  back the TOTP step.
- The durable HITL resolver is verified from a fresh session. A committed but
  unverified approval returns HTTP 503 with action/operation identity, not a
  successful authentication grant.

### Audit and effect states

- Audit is written and then read back independently. One strict helper freezes
  the expected actor, tenant/workspace, action, resource, factor revision,
  target and operation id. Missing required evidence is unverified; a present
  contradiction (including a wrong type or a `default` workspace alias for a
  scoped actor) is refuted.
- Enable/disable/setup are state changes; an audit-unavailable state change is
  returned with `verification.status=unavailable` and
  `replay=do_not_repeat`. A refuted state readback is 503.
- Backup-code verification and action approval are authentication grants; an
  unverified or refuted result is 503 with identity, never a success grant.
- A lost commit confirmation returns `effect_unknown` with operation/action
  identity and `replay=do_not_repeat`; it is not classified as a clean refusal.
- A retry reconciles the original operation's effect, actor authority and audit
  evidence from durable state. An unverified retry remains 503 with the original
  identity and `do_not_repeat`; it consumes no additional code, resolves no
  action and dispatches no callback. A verified retry may acknowledge the
  original result as `already_applied`, without a new authentication event.
- The actor workspace/status/role and the complete reviewed HITL target, policy
  and material snapshot are conditional-write predicates in the same
  transaction as OTP consumption, `reviewed_by`/`reviewed_at` and the receipt.
  A concurrent change matches zero rows, rolls back the OTP step and leaves the
  action unapproved with zero callbacks.
- Commit/audit failures are reduced to safe stage/class codes; raw SQL,
  parameters, OTPs, factor secrets and recovery codes are never returned or
  logged. Setup/commit test failures assert the synthetic secret is absent from
  both the HTTP response and captured logs.
- Verified paths preserve the existing success/error shapes and add additive
  `verification`/`operation_id`/`audit_id` metadata.

## Controls

- **Focused: 82 passed on Python 3.14 and 3.11** — the original 47
  route/durable controls, 34 boundary/valid-twin controls (including stale
  legacy-mirror cleanup) and the pre-migration scratch-database upgrade
  control.
- **Independent boundary probes: 12 passed** on both versions, matching the
  verifier's failure-first matrix.
- **W80B 2FA classes: 33 passed** on both versions (the unrelated workflow
  debug classes in that module are excluded).
- **Affected auth/HITL/audit/oracle selection: 199 passed, 1 pre-existing
  failure** on both versions.
- Selections overlap and are not added to the focused total.

The real controls cover valid twins and wrong/expired/replayed TOTP, concurrent
same-code, concurrent backup consumption, same-operation retry versus new
operation, duplicate/stale enrollment, stale enable/disable writers, lost
confirmation, audit unavailable/refuted after commit, missing audit/readback,
wrong actor/tenant/workspace/target/role, malformed/partial operation binding,
moved scope after the final check, durable resolver attribution after a fresh
session, and no secret/code in audit or receipt artifacts.

## Pre-existing exclusions

- `tests/test_covpush_w104_intervention.py::TestGetPendingInterventions::test_default_workspace_no_filter`
  fails on the accepted canvas base `fe401e111` without this repair.
- Unrelated W75 JWT/rate-limit failures (`test_covpush_w75_auth_helpers.py`,
  `test_covpush_w75_auth_endpoints.py`) also reproduce on that base and are
  excluded from the final affected selection; they are environment/test-seam
  failures, not 2FA route regressions.
- The W80B workflow-debug classes are unrelated to this slice and are excluded
  via `-k 2FA`.
- One intermediate 3.14 affected run hit the unrelated millisecond-clock
  assertion in `test_integration_audit.py::TestLogIntegrationComplete::test_log_integration_complete_with_error`;
  it passes in isolation and in the retained rerun.

## Boundaries

- No second authentication, OTP, review, approval or operation engine; the
  slice uses the existing `pyotp`, `User` factor fields, `HITLAction`,
  `AuditLog` and `InterventionService`.
- No new approval prompt beyond existing factor verification.
- No funneling manual enrollment into an employee Assignment.
- PostgreSQL concurrency/soak, live identity-provider operation, login/session
  behavior and deployment remain unqualified.
- The accepted canvas/feedback/wait/employee lanes and historical
  `111/123`/tags/model scores are unchanged.
- Whole-app ORACLE-01 remains open; registration counts do not establish
  runtime qualification.

## Artifacts

`focused-*.log`, `boundary-probes-*.log`, `migration-*.log`,
`w80b-2fa-*.log`, `affected-*.log`, `base-pre-existing.log`, `README.md`,
`TEST_RESULTS.md`, `verification.json`, `routes.json`. `MANIFEST.json` records
the SHA-256 of every artifact and changed source file.
