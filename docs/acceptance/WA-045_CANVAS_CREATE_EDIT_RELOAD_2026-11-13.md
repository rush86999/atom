# WA-045 — Canvas create/edit/reload proven on an isolated world

Date: 2026-11-13
Source under test: `ec7166676` (acceptance-only branch commit based on
`8bb0c66f5fd30988c16585214707bf784fa39d41`, `origin/main`)
Ledger item: `WA-045` — area `canvas`, action “Create a canvas artifact, edit it, reload”
Evidence: `docs/acceptance/evidence/wa045_canvas_blank_20261113/canvas-blank-lifecycle.json`
(harness, 29/29) and
`docs/acceptance/evidence/wa045_canvas_connected_20261113/canvas-connected-browser.json`
(signed-in connected browser, artifact `cbf43d3b-47d5-40a7-aabf-db3e7c3a42a9`)

## What was unproven

The whole-app readiness ledger recorded WA-045 as `unproven` with
`first_failed_transition: "Render only."` — `/canvas` rendered in
`whole-app-world-20261027`, but no canvas artifact transition was executed.
Every existing harness covered a typed slice (email body, capability fields,
Office files, PDF) or a mocked jsdom save; the plain path — gallery **New
canvas** → native document editor → verified audit-trail save → browser reload
— had no signed-in execution on any isolated world.

## What this run executes

1. Signs in through the real login form (`login-email-input`,
   `login-password-input`, `login-submit-button`) with the scratch world’s
   admin credential read from a `0600` file.
2. Presses the gallery’s `new-blank-canvas-button` and captures the real
   `POST /api/canvas` response.
3. Opens the returned `/canvas/{id}` page and waits for the native Monaco
   editor with the empty document envelope.
4. Types an exact five-line body as a user (select-all + `insertText`).
5. Saves through the panel’s own autosave / **Save Changes** path and captures
   the `PUT /api/canvas/{id}` request and response.
6. Reloads the page and re-reads the editor, `GET /api/canvas/{id}`,
   `GET /api/canvas/{id}/history`, and the scratch SQLite database directly.

## Exact assertions (29/29 passed)

Artifact identity — the same UUID must be returned by every boundary:

- `POST /api/canvas` → `canvas_id` (UUID)
- browser URL `/canvas/{canvas_id}`
- `GET /api/canvas/{id}` → `canvas_id`
- `GET /api/canvas/{id}/history` rows (`canvas_id` on every row)
- `PUT /api/canvas/{id}` response (`canvas_id`)
- `canvases.id` and every `canvas_audit.canvas_id` in the scratch DB

Exact text — the same string, byte-for-byte:

- the `PUT` request body is exactly `{"content": "<text>"}` (one key, no
  extra envelope fields; SHA-256 recorded)
- the verified save receipt (`verification.status == "verified"`) carries the
  update `audit_id` and `operation_id`
- `GET /api/canvas/{id}` content is `{"content": "<text>"}`
- the latest audit row’s `details.content` is `{"content": "<text>"}`
- the editor model value after a real `page.reload()` equals the text exactly
- the scratch DB `canvases.content` and `canvas_audit` update row equal it too

Concurrency and history:

- the save binds `expected_prior_audit_id` to the create row’s audit id
- history is exactly `create` + `update` (2 rows) and the read-back
  `revision_audit_id` equals the save’s `audit_id`
- the reloaded version badge reads `v2`

Isolation:

- every non-loopback request is a `GET` for the pinned Monaco editor static
  asset under `cdn.jsdelivr.net/npm/monaco-editor@<version>/min/vs/`
  (@monaco-editor/react’s default loader); no workspace data is sent, and no
  model/provider endpoint is contacted
- no browser `pageerror`; the browser origin set is exactly the frontend,
  the backend, and `blob:` worker URLs

## Result of this run

| Field | Value |
|---|---|
| Artifact id | `f61ca638-241d-479a-b99a-adf28897fe66` |
| Create audit id | `bb36b06a-d4a5-45d1-9c86-f0660a7693e2` |
| Save audit id | `b069e935-49a4-4381-88d5-d8b62c377076` |
| Exact text SHA-256 | `9c0ef0310e6be5040c18c7339892f93a6343f117fb1c09821dbbbc68a04f1487` |
| Save path | explicit **Save Changes** button (the same harness also passes on idle autosave) |
| Save verification | `verified` / effect `committed` |
| History | `update`, `create` (2 rows) |
| Reload version badge | `v2` |
| Editor after reload | exact text (same SHA-256) |
| Checks | 29/29 (23 browser + 6 scratch-DB) |

Reproducibility: the committed harness was re-run on a second fresh world and
again passed 29/29 with the same text hash; the table is that run. An earlier
fresh-world pass exercised the idle-autosave path, so both save entry points
have now been executed end-to-end.

## Connected-browser corroboration (artifact `cbf43d3b…`)

Before the harness was committed, the same scratch-world path was exercised by
a signed-in browser against the live-connected frontend/backend pair
(`127.0.0.1:3177` / `127.0.0.1:8177`) with the backend `/health` identity
reporting `8bb0c66f5fd30988c16585214707bf784fa39d41`, `identity_kind=git`,
`dirty=false`. That run is packaged separately as
`docs/acceptance/evidence/wa045_canvas_connected_20261113/`:

- artifact `cbf43d3b-47d5-40a7-aabf-db3e7c3a42a9`, `document`, "Untitled
  canvas"; the save was bound to prior revision `413b4219-2aed-4060-8ca4-c573bdf6c70c`
- the edit was autosaved with `PUT /api/canvas/{id}` → **200**
- the page was reloaded and the editor model read back the exact 3-line body
  (103 characters, sha256 `22171224…`)
- `GET /api/canvas/{id}` and `GET /api/canvas/{id}/history` returned 200 after
  the reload; no page errors
- the only non-loopback origin was `https://cdn.jsdelivr.net` serving
  `monaco-editor@0.55.1` static assets with `GET` only — no workspace data, no
  credential, no provider/model call (see the package's CDN scope section)

That run proves the save/reopen leg for a specific artifact; artifact creation
and the scratch-DB rows are proven by the 29/29 harness package above. Its raw
worker/backend logs stay outside the repository and are not committed; the
package keeps only allowlisted facts.

## Offline re-verification — bundled editor, external traffic refused

The runs above permitted one non-loopback origin: `@monaco-editor/react`'s
default loader fetched the editor from `cdn.jsdelivr.net`. That is static code
with no workspace data, but it means the same journey could not run on an
air-gapped install, a desktop/Tauri bundle or a firewalled deployment, and the
run could not claim "external traffic refused".

The editor is now bundled with the app:

- `frontend-nextjs/scripts/sync-monaco-assets.js` copies the installed
  `monaco-editor@0.55.1` AMD build into `public/monaco/vs` (version-stamped,
  atomic swap, gitignored). `next.config.js` runs it at every `next dev` /
  `next build` startup, so the harness, Docker and Tauri all serve the same
  assets without an npm lifecycle step.
- `frontend-nextjs/lib/monaco-local.ts` points `@monaco-editor/loader` at
  `/monaco/vs`; all four `Editor` hosts call it at module scope before the
  loader initializes. A structural test fails if a new Monaco surface forgets.
- `frontend-nextjs/middleware.ts` exempts `/monaco/` like `/_next/static`;
  without that, an unauthenticated asset request 307s to
  `/login?callbackUrl=/monaco/...` (observed during the smoke check).

The harness's deny policy now aborts every non-loopback request with
`route.abort` instead of only observing it, records same-origin `/monaco/vs`
requests, and adds three deny-mode checks. An unknown policy value refuses to
start.

| Field | Value |
|---|---|
| Source revision | `f201216b6` (clean; backend identity `source_id=f201216b6d9c`) |
| World | `wa045_canvas_offline_20261113` (fresh scratch DB) |
| Ports | `3182` frontend / `8182` backend (loopback) |
| Artifact id | `30d1b84b-e5aa-41b3-8085-f7ed76553369` |
| Create audit id | `de0d0b2e-cb04-4cd1-8e37-d71fe2c3eeb5` |
| Save audit id | `2f3f5525-f6bd-4d7d-8976-db54e1b0929f` |
| Exact text SHA-256 | `9c0ef0310e6be5040c18c7339892f93a6343f117fb1c09821dbbbc68a04f1487` (same text as both earlier runs) |
| Non-loopback attempts | **0** (0 blocked because none were made) |
| Local editor assets | 26 requests under `/monaco/vs/` |
| Browser origins | `127.0.0.1:3182`, `127.0.0.1:8182` only |
| Checks | **32/32** (26 browser + 6 scratch-DB) |

Evidence: `docs/acceptance/evidence/wa045_canvas_offline_20261113/`
(`canvas-blank-lifecycle.json` + README). The earlier connected-browser package
remains valid for the save/reopen leg it recorded, but it is not evidence of
offline operation and is cited as historical corroboration only.

## Isolation contract

- **World:** fresh `backend/data/acceptance_worlds/wa045_canvas_blank_20261113`
  under the configured worlds root, created only after
  `validate_local_world.py`, `core.world_storage_guard check` and the
  orchestration storage-policy preflight accepted the path.
- **Database:** a brand-new scratch SQLite file inside that world, created by
  the product’s own startup path (`Base.metadata.create_all` + admin
  bootstrap). No backup, copy, or live credential from any other checkout is
  read. The live dev DB path is refused explicitly, and the backend’s
  `/health` identity is verified to report this exact scratch file, pid,
  cwd, port and source revision before the browser runs.
- **Storage:** `ATOM_DATA_DIR`, `LANCEDB_URI(_BASE)`, office, assignment,
  task-lock, attachment and BYOK paths all point into the world.
- **Workers/network:** `ENABLE_SCHEDULER=false`,
  `ENABLE_INGESTION_SYNC=false`, `ATOM_LOCAL_ONLY=true`, and every provider
  credential variable is blanked in both child processes.
- **Ports:** unique loopback ports (`8181` backend, `3181` frontend) checked
  free by the preflight.
- **Logs:** raw backend/frontend/harness logs stay in the private run
  directory (`/private/tmp/atom-wa045-lifecycle`), never in the repository.
  Only the sanitized, secret-free evidence JSON is committed.

## Reproduce

```bash
# from the repository root, with the repo's Python venv and Playwright/Chrome
backend/venv314/bin/python scripts/acceptance/canvas_blank_lifecycle.py
# offline/bundled: abort every non-loopback request (fresh world, unique ports)
CANVAS_BLANK_MONACO_CDN=deny \
  backend/venv314/bin/python scripts/acceptance/canvas_blank_lifecycle.py \
  --world-name wa045_canvas_offline_20261113 \
  --backend-port 8182 --frontend-port 3182 \
  --out-dir docs/acceptance/evidence/wa045_canvas_offline_20261113
# unit-level guards (path/secret/DB checks) without servers or a browser
backend/venv314/bin/python -m pytest scripts/tests/test_canvas_blank_lifecycle.py \
  scripts/tests/test_wa045_offline_evidence.py -q
```

The driver refuses a non-empty world, so delete the world directory first to
re-run (it is a scratch world, not evidence):

```bash
rm -rf backend/data/acceptance_worlds/wa045_canvas_blank_20261113
```

## Boundaries

- The frontend is served by `next dev --webpack` (isolated ports), matching
  the existing whole-app acceptance pattern; this is a development server, not
  a production build.
- The harness accepts whichever panel path wins the race and records it:
  the idle autosave and the explicit **Save Changes** button have each
  produced a passing 29/29 run on a fresh world.
- Monaco's editor assets were loaded from the pinned jsDelivr static URL by
  `@monaco-editor/react` in the earlier runs; the harness recorded every such
  request and failed on any other non-loopback origin. That is static editor
  code, not a provider or data-plane call. **Superseded**: the offline run
  above serves the bundled `/monaco/vs` build and refuses all non-loopback
  traffic, so no CDN is contacted.
- The text selection accelerator is `Meta+A` on macOS and `Control+A`
  elsewhere.

## Ledger update

`scripts/acceptance/build_whole_app_ledger.py` records WA-045 as `verified`
with `config: wa045-canvas-offline-20261113` and all three evidence paths
(offline bundled-editor run, connected browser, original harness); the
2026-10-27 ledger JSON/Markdown were regenerated, and so was the core-release
ledger that embeds the whole-app item. The item is marked
`candidate_bound: false` because the runs re-prove the transition on current
`main` (`f201216b6`, with the earlier pair on `8bb0c66f5`), not on the frozen
`f5f3148d2` candidate.
