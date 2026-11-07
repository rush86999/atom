# Authoritative-scope successor evidence

Predecessor: `ce4938c99` (PR714 initial ORACLE registry repair).
Successor source: `913489383` on the same branch.
Base: `bae68c91d610`.

## Independent review failures repaired

The supplied `LEAD_PROBES/test_lead_oracle_authoritative_scope.py` probes all
failed at `ce4938c99`: after a valid verification, a committed change to any of
these authoritative columns still verified True:

- `MiniApp.tenant_id`
- `MiniApp.workspace_id`
- `MiniApp.created_by`
- `CanvasAudit.tenant_id`
- `CanvasAudit.user_id`

Root cause: the verifier preferred copied `details_json` values over the
authoritative MiniApp/CanvasAudit columns, and `_read_with_db(ctx)` reused the
caller's session/identity map.

## Repair

- The verifier now requires the authoritative `MiniApp` tenant/workspace/owner,
  the current blueprint `Canvas` identity/tenant/workspace, the `CanvasAudit`
  action/canvas/tenant/user, and the copied details to agree with the frozen
  request. Details are corroboration only; no fallback can certify a
  contradiction. Missing frozen tenant/actor/operation evidence is refuted.
- Reads use a **fresh session** bound to the caller's engine (or the existing
  `get_db_session`), never the caller's identity map or uncommitted objects.
- The producer's exact-prior-manifest CAS now also binds owner, tenant,
  workspace and blueprint canvas. A peer scope change yields zero rows and a
  truthful `proven_not_applied` conflict; null-manifest/peer-manifest controls
  remain.
- Added tracked equivalents of all five supplied negatives, a peer-commit
  control, a dirty-caller-session negative, a committed-valid positive, and
  CAS scope-change negatives.

## Final qualification (`913489383`, clean tracked tree)

Fresh owned basetemp root:
`<scratch>/opencode/oracle-final-20261107-b` (new child per run).

- Supplied probes (`test_lead_oracle_missing_verifier.py` +
  `test_lead_oracle_authoritative_scope.py`): **7 passed**.
- CI control step: **166 passed** (includes the predecessor 156 and the new
  authoritative/fresh-read controls; predecessor 158 = 156 + old 2 remains a
  subset).
- Affected cluster: **631 passed, same 11 pre-existing unrelated failures**
  (see `baseline-unrelated-failures.txt`; their code paths are untouched).
- Coverage snapshot at `913489383`: 90 actions, 26 declared mutations,
  15 covered, 11 explicitly uncovered, 0 undeclared; `goals.decompose` remains
  plan-only. Stored in
  `docs/acceptance/evidence/oracle_registry_coverage_20261107_authoritative_scope/`.

Predecessor evidence under `docs/acceptance/evidence/oracle_registry_gap_20261107/`
and `docs/acceptance/evidence/oracle_registry_coverage_20261107/` is preserved
unchanged.

## Boundary

Single-tenant existing user/workspace ownership boundaries only; no new SaaS
qualification, no live provider/VM/model/app/account effect. Does not claim
whole-app ORACLE completion.
