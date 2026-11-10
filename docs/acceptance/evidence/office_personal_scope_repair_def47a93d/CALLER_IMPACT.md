# Caller impact — Office Personal NULL scope repair

## Changed behavior

`require_active_actor` no longer refuses an active User solely because raw
`tenant_id`/`workspace_id` are NULL. It resolves the documented Personal
default from the authoritative User, verifies the effective Tenant exists,
and returns effective fields. Raw fields are still returned unchanged for
`claim_canvas_actor`.

## Callers / affected surfaces

- `core/canvas_authority.require_active_actor`: additive effective fields;
  raw snapshot/claim semantics unchanged.
- `core/canvas_authority.reserve_canvas_id`: Canvas tenant/workspace now use
  effective Personal scope (fixes `"None"` tenant for bootstrap admin).
- `core/canvas_coding_service.py`: create audit tenant uses effective scope;
  `claim_active_actor` still gets the raw snapshot.
- `core/canvas_sheets_service.py`: same.
- `backend/api/canvas_routes.py` Office `_resolve_export_job`: existing
  GoalRunService now scoped with effective Personal tenant/workspace.
- `backend/tests/api/test_web_canvas_authority.py`: distinguishes documented
  bootstrap NULL/default (valid Personal) from an absent effective Tenant
  (refused); no authority mock/escape.
- Email: not part of this PR826 source's shared authority path. PR827 has a
  newer shared email repair in another worktree; this branch neither copies
  nor modifies it. Root must ensure PR827 uses the same effective-scope
  resolution before its unchanged NULL probe.

## Explicit non-changes

- `active_canvas_actor` / `claim_canvas_actor` raw nullable snapshot.
- `canvas_lifecycle_scope_error` null-principal only unscoped/default policy.
- Exact-target CAS: NULL -> default/empty concurrent changes still match zero
  rows and refuse.
- Foreign/opaque real scopes are preserved and checked exactly.
