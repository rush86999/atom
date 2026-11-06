# Community-skill promote/delete — test results

Executed source: `371cf002e` (product `acfee403b`) on a clean detached worktree.
Runtime: scratch SQLite with fresh sessions; no live model/provider/sandbox/
package call.

## Focused gate

Command (same selection on Python 3.14 and 3.11):

```
TESTING=1 PYTHONPATH=$PWD python -B -m pytest -p no:randomly \
  tests/test_community_skill_write_contract.py \
  tests/unit/api/test_skill_routes.py \
  tests/test_covpush_skill_registry.py \
  tests/test_covpush_w116_skill_registry.py \
  tests/test_skill_registry_service.py -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **126 passed** | `focused-314.log` |
| Python 3.11 | **126 passed** | `focused-311.log` |

The 21 new controls are in `tests/test_community_skill_write_contract.py`:
anonymous/member refusal, team-lead and cross-tenant platform authority,
promote/delete success, already-active no-op, replay, changed skill, later
revision, stale promote/delete, cloud-row refusal, audit rollback, post-commit
readback, lost confirmation, 10 audit-tamper variants and raw-material
omission.

## Affected selection

Command (same selection on both versions):

```
TESTING=1 PYTHONPATH=$PWD python -B -m pytest -p no:randomly \
  tests/test_community_skill_write_contract.py \
  tests/unit/api/test_skill_routes.py \
  tests/core/skills/test_skill_registry_service_coverage.py \
  tests/core/systems/test_skill_registry_coverage.py \
  tests/test_skill_registry_service.py \
  tests/test_covpush_skill_registry.py \
  tests/test_covpush_w116_skill_registry.py \
  tests/test_reviewed_skill_agent_consumption.py \
  tests/test_audit_logger.py \
  tests/test_integration_audit.py -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **252 passed** | `affected-314.log` |
| Python 3.11 | **252 passed** | `affected-311.log` |

## Unrelated baseline

`tests/test_round22_marketplace_security.py` has 4 pre-existing failures at the
accepted admin base `9d73552d2` (4 passed, 4 failed): package approve/install
auth inspection, marketplace install auth inspection and a `str(e)` leak check.
The same 4 failures are present with this slice; they are not the two reviewed
routes. Log: `baseline-round22-9d73552d2.log`.

An order-sensitive `test_integration_audit.py::TestLogIntegrationComplete::test_log_integration_complete_with_error`
(`duration > 0`) can also fail when the marketplace file runs in the same
process; it is the same pre-existing timing flake observed on the base and is
not part of the 252-pass affected selection above.

## Failure-first coverage

| Contract | Control |
|---|---|
| Anonymous / member / team-lead authority | `test_authority_and_promote_roundtrip` |
| Cross-tenant platform review | same test (other-tenant lead twin) |
| Promote success + audit readback | same test |
| Replay / changed skill / later revision | `test_promote_replay_changed_material_and_later_revision` |
| Stale promote preserves peer | `test_promote_stale_writer_refuses_without_overwrite` |
| Delete success / replay / missing / cloud / stale | `test_delete_replay_missing_stale_and_cloud_scope` |
| Already-active no new audit | `test_already_active_is_noop_without_audit` |
| Rollback `effect=none` for promote/delete | `test_audit_rollback_reports_effect_none` |
| Post-commit readback | `test_post_commit_readback_is_committed_unverified` |
| Lost confirmation | `test_lost_confirmation_is_effect_unknown` |
| Audit tamper | `test_wrong_audit_receipt_is_never_verified` |
| Raw material omission | `test_raw_skill_material_is_absent_from_audit_and_logs` |
| Anonymous routes | `test_anonymous_requests_are_refused` |

## Boundaries

No import, execute, sandbox, Docker, package install, live-code execution,
provider, model, credential, spend, send, download or deployment operation was
used. No new table or migration. PostgreSQL runtime/soak and multi-worker
serialization remain open.
