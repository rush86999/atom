# Office Personal NULL-scope shared authority repair

Source base: exact PR826 head `96dd3afaf6a519848c04265db7249454020d7e85`.
Exact negative preserved: `docs/acceptance/evidence/goal11_office_ordinary_browser_episode_96dd3afaf/`
at `a8e9e52f891e93a7ab118d8f9006741bd1acc118` (ordinary bootstrap admin
NULL/default own canvas Download DOCX 403).
Repair commit: `def47a93d39afa04286f875e5a5003744c944de6`.
Branch: `codex/office-personal-scope-repair-20261110`.

## Repair (general policy, no admin special case)

- `core.canvas_authority.require_active_actor` now resolves the **effective**
  tenant/workspace from the authoritative User via `core.personal_scope`
  (documented NULL->default), verifies the effective Tenant row exists, and
  returns the existing **raw** actor fields unchanged plus
  `effective_tenant_id`/`effective_workspace_id`. Unknown/inactive/missing
  effective default Tenant still refuse; real opaque scopes are unchanged.
- `reserve_canvas_id` and coding/sheets audit writes use the effective
  Personal scope instead of stringifying raw NULL.
- Office `_resolve_export_job` scopes the existing GoalRunService with the
  effective Personal scope.
- `active_canvas_actor`, `claim_canvas_actor` and
  `canvas_lifecycle_scope_error` raw/null-principal policy are unchanged:
  NULL->default/empty concurrent transitions still fail the exact actor claim.

## Controls

- bootstrap raw NULL/default own DOCX export: 200, real DOCX bytes, raw NULL
  unchanged
- raw NULL actor + foreign real tenant/workspace canvas: 403/404, no file
- inactive, unknown, missing-default-Tenant: refused
- NULL->default and NULL->empty raw transitions: `claim_canvas_actor` false
- real opaque tenant/workspace: raw and effective preserved; same-scope export
  200
- coding/sheets create under NULL: Canvas/audit default, never `"None"`

The initial opaque valid-twin failure was diagnosed as a **test fixture**
error (canvas owned by admin instead of the opaque actor). The runtime was
correct; fixed by assigning the fixture canvas to the opaque owner. It was not
dropped or relaxed.

## Gates

| Gate | Result | Log |
|---|---|---|
| New Personal scope controls | 7 passed | `gates/new_scope_7.proof` |
| Original targeted canvas/office group | 170 passed | `gates/targeted_170.proof` |
| Office/email group | 104 passed, 1 pre-existing unrelated failure | `gates/office_email_104_1pre.proof` |
| Root independent NULL-Personal probe | 3 passed in 5.89s, exit 0, same_source true | `root_proof/` |

The pre-existing failure is
`test_office_canvas_coediting.py::TestPresentPersistence::test_explicit_canvas_id_respected`
(`/present` lacks `canvas_id`), preserved.

## Caller impact

- authority: effective fields additive; raw actor contract unchanged.
- sheets/coding: effective tenant for Canvas/audit; exact raw claim unchanged.
- office export job lookup: effective Personal scope for existing
  GoalRunService.
- email: this PR826 source does not contain PR827's newer shared email repair;
  no email code was copied/clobbered. Downstream PR827 must apply the same
  effective-scope resolution in its shared helper; root integrates/reviews.
- No new store/schema/router/launcher/identity engine; no browser rerun.
