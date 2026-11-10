# GOAL-11 Office ordinary browser episode — product negative

Source: exact PR826 head resolved before binding:
`96dd3afaf6a519848c04265db7249454020d7e85`.
Worktree/branch: `/private/tmp/atom-goal11-office-browser-20261110` on
`codex/web-goal11-office-ordinary-browser-20261110`.
World: `office_ordinary_browser_96dd3afaf6_1794307192` (one fresh marked
child under the root-verified canonical worlds root; no other world touched).

## What passed

- storage guard with `ATOM_WORLD_STORAGE_PATHS=/Users/rushiparikh/projects/atom/backend/config`:
  PASS; symlink samefile to the canonical real worlds root.
- source proof at exact 96dd: PASS; world build (API-seeded fixture, immutable
  export, seatbelt network boundary): PASS.
- owned backend + isolated frontend copy + system Chrome (no browser download):
  started.
- real bootstrap admin API login and real browser login/onboarding: PASS.
- two supported canvases seeded through authorized public Canvas APIs
  (document/markdown; disclosed as API setup, not UI/model creation): PASS.
- detail UI opened; visible `Download DOCX` control clicked.

## Actual negative

The visible download click issued the real browser request:

```
GET /api/canvas/159081e9-8a82-417f-b755-6248bbef5212/export/office
    ?format=docx&expected_audit_id=ff79f334-bff2-4117-b784-2b375b53cdf4
-> 403 Forbidden
```

No download event arrived; no DOCX/PPTX bytes were produced. The frontend
console recorded the same `handleOfficeExport` 403. The scratch actor/canvas
readback explains the boundary:

- bootstrap admin raw `tenant_id`/`workspace_id`: **NULL**
- canvas/audit scope: `default`
- Office export route's `require_active_actor` resolves the raw actor and
  refuses a missing raw tenant before rendering.

This is a real ordinary-admin product boundary failure, not a browser,
storage, dependency or seed failure. Per the work order, I did not edit
product source or start a repair loop. Root owns `canvas_routes.py`; root
review is required.

## Evidence

- `capture/result.summary.json` — steps, request, stops, failure
- `capture/server_export_failure.proof` — actual route 403
- `capture/frontend_export_failure.proof` — browser/UI 403
- `capture/scope_readback.json` — exact descriptor/health/run DB path samefile,
  URI `mode=ro` readback, admin NULL vs canvas default, canvas/audit ids
- `capture/world_identity.json` — source/world/build identity

No cookies, tokens, raw JWT, private DB, provider/model/send or live DB.
The DB inspection used the exact launched descriptor path (samefile with the
health-observed path) in SQLite URI `mode=ro`; a no-table/path mismatch would
have been treated as harness evidence, not product failure.
No screenshots were retained because the download event never fired; page
title/content and request/status are captured in the step evidence.

## Not claimed

- No DOCX/PPTX download, package, freshness or current-content edit proof.
- No general Office/browser/whole-GOAL-11 claim.
- No product repair, PR, merge or CI change.
