# WA-045 offline/bundled canvas editor evidence

This package records the same plain canvas transition the readiness ledger left
unproven — gallery **New canvas** → native editor → verified audit-trail save →
browser reload — with **every non-loopback request refused**. It supersedes the
CDN allowance in the earlier WA-045 runs: the editor now loads from the app's
own `/monaco/vs` bundle, so the transition no longer depends on internet access.

- **Source revision:** `f201216b6d9ce9711ab6d9a8d27e43191f5844cf`
  (`f201216b6`, clean tree; the backend `/health` identity reports
  `source_id=f201216b6d9c`, no `-dirty` suffix)
- **Artifact:** `30d1b84b-e5aa-41b3-8085-f7ed76553369` (`document`,
  "Untitled canvas"), created by the gallery's `new-blank-canvas-button`
- **Create audit:** `de0d0b2e-cb04-4cd1-8e37-d71fe2c3eeb5`
- **Save audit:** `2f3f5525-f6bd-4d7d-8976-db54e1b0929f`, verification
  `verified` / effect `committed`, bound to the create revision
- **Save path:** explicit **Save Changes** button (`save_changes_button`)
- **Reload:** the same `/canvas/{id}` URL reloaded; the editor model,
  `GET /api/canvas/{id}`, the latest audit row and the scratch SQLite rows all
  return the exact body below
- **Text:** 5 lines, 109 characters,
  sha256 `9c0ef0310e6be5040c18c7339892f93a6343f117fb1c09821dbbbc68a04f1487`
  (identical to the earlier online runs)
- **Checks:** 32/32 (26 browser + 6 scratch-DB)

```text
WA-045 canvas durability check

Line 1 exact: ORD-WA045-ALPHA
Line 2 exact: 17 * 3 = 51
End marker: WA045-END
```

`canvas-blank-lifecycle.json` is the artifact; this README is a human view of
the same facts.

## Offline contract

`CANVAS_BLANK_MONACO_CDN=deny` makes the Playwright harness abort every
non-loopback request (`route.abort`) rather than merely observing it, so a CDN
regression fails the journey at the editor. Recorded in the evidence:

- `external_traffic.policy = "deny"`, `attempted_count = 0`,
  `blocked_count = 0`
- `journey.non_loopback = []`; browser origins are exactly
  `http://127.0.0.1:3182` (frontend) and `http://127.0.0.1:8182` (backend)
- 26 same-origin requests under `/monaco/vs/` served by the frontend
- the harness's three deny-mode checks pass: CDN not contacted, zero
  non-loopback attempts, editor rendered from the bundled build

The bundle is product code, not harness injection:
`frontend-nextjs/scripts/sync-monaco-assets.js` copies the installed
`monaco-editor@0.55.1` AMD build into `public/monaco/vs` at every
`next dev` / `next build` startup, `frontend-nextjs/lib/monaco-local.ts`
points `@monaco-editor/loader` at that path, and `middleware.ts` serves
`/monaco/` like `_next/static` (public vendor JS/CSS/workers).

## Environment and isolation

- Fresh scratch world `backend/data/acceptance_worlds/wa045_canvas_offline_20261113`
  with a brand-new SQLite `atom.db` created by the product's own startup path;
  no backup, copy, or live credential was read.
- Loopback ports `127.0.0.1:3182` (frontend, `next dev --webpack`) and
  `127.0.0.1:8182` (backend, uvicorn); process identity (pid, cwd, database,
  port, source revision) is verified before the browser mutates anything.
- `ENABLE_SCHEDULER=false`, `ENABLE_INGESTION_SYNC=false`,
  `ATOM_LOCAL_ONLY=true`; every provider credential variable is blanked in both
  child processes. No provider/model call was made.

## What this does and does not prove

- **Proves:** signed-in blank-canvas creation, exact multiline edit, verified
  save, and exact read-back after reload — with the editor served from the
  app's own bundle and external traffic refused — on `f201216b6`.
- **Does not restate:** the historical connected-browser run
  (`docs/acceptance/evidence/wa045_canvas_connected_20261113/`), which used the
  jsDelivr CDN and remains valid only for the save/reopen leg it recorded.
- The frontend is a `next dev --webpack` server, not a production build. A
  production build is expected to trace the same `public/monaco` tree via
  `output: 'standalone'`; that build path was not separately exercised here.
- Raw backend/frontend/harness logs stay in the private run directory
  (`/private/tmp/atom-wa045-lifecycle`) and are not committed. Only the
  sanitized, secret-free evidence JSON is in this package.

## Reproduce

```bash
# from the repository root, with the repo's Python venv and Playwright/Chrome
CANVAS_BLANK_MONACO_CDN=deny \
  backend/venv314/bin/python scripts/acceptance/canvas_blank_lifecycle.py \
  --world-name wa045_canvas_offline_20261113 \
  --backend-port 8182 --frontend-port 3182 \
  --out-dir docs/acceptance/evidence/wa045_canvas_offline_20261113
```

The driver refuses a non-empty world; delete the scratch world first to re-run
(it is a scratch world, not evidence):

```bash
rm -rf backend/data/acceptance_worlds/wa045_canvas_offline_20261113
```
