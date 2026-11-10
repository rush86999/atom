# Office Personal NULL-scope repair — exact effective-key successor

Predecessor (root reviewed): `def47a93d39afa04286f875e5a5003744c944de6`
and its packet `docs/acceptance/evidence/office_personal_scope_repair_def47a93d/`.
Exact browser 403 negative remains preserved at
`docs/acceptance/evidence/goal11_office_ordinary_browser_episode_96dd3afaf/`
(`a8e9e52f8`).

Successor: `7319a287c43e96cd149a9b49e20f530fef9ce627`.

## Narrow maintainability correction

`require_active_actor` guarantees `effective_tenant_id`/
`effective_workspace_id`. All `_actor` callers in coding/sheets, plus
`reserve_canvas_id` and Office `_resolve_export_job`, now use those exact keys.
The duplicate `actor.get(effective) or actor.get(raw) or "default"` fallbacks
were removed; no silent fake-actor fallback or second resolver was added.
The one synthetic serialization test now supplies the same shared-helper
contract (authority itself remains patched there).

Unchanged: `active_canvas_actor` raw snapshot, `claim_canvas_actor` exact raw
NULL-distinct claim, `canvas_lifecycle_scope_error` null-principal only
unscoped/default policy, and all real opaque/foreign scope checks.

## Gates

| Gate | Result | Log |
|---|---|---|
| New Personal controls + affected coding/sheets/Office/authority callers | 120 passed | `gates/affected_120.proof` |
| Root NULL-Personal probe rerun at successor | 3 passed in 5.13s | `gates/root_null_personal_successor_3.proof` |
| Root independent predecessor | 3 passed in 5.89s, exit 0, same_source true | `root_proof/` |

No browser rerun. No product source beyond the narrow effective-key cleanup.
No PR/merge/CI/goal-index/store/schema/router/launcher/provider/model/send/live
DB.
