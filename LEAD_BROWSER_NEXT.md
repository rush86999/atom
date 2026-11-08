# LEAD_BROWSER_NEXT — ordinary Documents stored-text export

Prepared 2026-11-07. **No world, server, browser, model, pytest run or download
was launched during preparation.** Root owns all execution/acceptance.

## 1. Exact source

- Branch: `codex/document-stored-export-20261107`
- Frozen product base: `ccf31f073f3fda88163e2a5dcc94fd545affae53`
  (PR756 packet; the 37-case API evidence is at
  `docs/acceptance/evidence/document_export_lead_011b8373e`)
- Episode source: **the branch commit that contains this file**. Dispatch it
  explicitly, never by guesswork:

  ```sh
  cd /private/tmp/atom-document-stored-export-20261107
  git status --porcelain=v1 --untracked-files=no   # must be empty
  EPISODE_SHA="$(git rev-parse HEAD)"
  ```

  `--expect-source-sha "$EPISODE_SHA"` is mandatory. The driver fails if HEAD,
  the tracked tree, every per-file Git blob, or the harness/helper bytes differ.
- Product files were not edited by this slice. The retained 37-case manifest's
  nine source/test hashes still match the current bytes; preflight refuses if
  they drift. Do not re-run the broad API/model/browser matrix to “refresh” it.

## 2. New files (harness only)

- `scripts/acceptance/browser_document_export_ui.py` — finite browser harness,
  preflight by default, root-only `--execute`.
- `scripts/tests/test_browser_document_export_ui.py` — pure helper tests
  (no world/server/browser/model/download). Root test gate may collect it with
  the existing `scripts/tests` suite; it was **not run during preparation**.
- `LEAD_BROWSER_NEXT.md` — this handoff.

No product/runtime/frontend/export-authorization file changed. `opencode.jsonc`
stays untracked.

## 3. Preflight (safe; launches nothing)

Use a scratch env for the driver's own imports (never the live DB):

```sh
SCRATCH="$(mktemp -d /private/tmp/doc-export-preflight.XXXXXX)"
TESTING=1 \
DATABASE_URL="sqlite:///$SCRATCH/atom.db" \
ATOM_DATA_DIR="$SCRATCH/data" \
ATOM_OFFICE_DIR="$SCRATCH/office" \
ATOM_PRODUCT_PROFILE=core \
python3 scripts/acceptance/browser_document_export_ui.py \
  --preflight \
  --expect-source-sha "$EPISODE_SHA" \
  --out "$SCRATCH/report"
```

`mkdir -p` the three scratch directories first if the platform requires
pre-existing env paths. Preflight writes only `$SCRATCH/report/preflight.json`
and refuses a report inside the worlds tree.

It proves/refuses:

- exact HEAD + clean tracked tree + per-file Git byte equality;
- retained 37-case source/test hashes unchanged;
- core profile: Documents enabled, Search/Tasks/Boards deferred;
- frozen upload/detail/export source strings (Blob + object URL + three
  formats + strict export route);
- world-storage guard configured/ready (read-only `preflight()`, **no mkdir**);
- disk estimate and whether the build is >=4 GiB (heavy root gate);
- fresh world name, free ports, writable fresh output;
- `backend/venv314`, `frontend-nextjs/node_modules`, node, Chrome;
- the complete existing FastEmbed ONNX cache and the installed fastembed
  source behaviour (read-only; no import/instantiation).

It returns `1` when a real prerequisite is absent (report is still written) and
`2` for wrong source/profile/output/world/fixture/SHA. It does not create a
world or a cache.

## 4. Execute-ready command (root only; do not run in preparation)

Run from a prepared capture worktree whose tracked HEAD is the episode SHA.
`--out` must be fresh or contain only `preflight.json`.

```sh
TESTING=1 \
DATABASE_URL="sqlite:///<scratch>/preflight.db" \
ATOM_DATA_DIR="<scratch>/data" \
ATOM_OFFICE_DIR="<scratch>/office" \
ATOM_PRODUCT_PROFILE=core \
python3 scripts/acceptance/browser_document_export_ui.py \
  --execute \
  --expect-source-sha "$EPISODE_SHA" \
  --world "document_export_ui_${EPISODE_SHA:0:10}" \
  --backend-port 8047 \
  --frontend-port 3147 \
  --out "/private/tmp/doc-export-evidence-$(date +%s)" \
  --provision-admin-password
```

Add `--root-heavy-approved` only when root owns a >=4 GiB build. Add
`--headed` only if root wants the visible browser. Do not reuse a world or an
evidence dir; the driver refuses both. It also refuses
`ATOM_WORLD_STORAGE_BYPASS`.

## 5. Prerequisites / current machine truth

| Requirement | State at preparation | Root action |
|---|---|---|
| `backend/venv314/bin/python` | **absent in the prep worktree** | run from/provision the prepared capture worktree; do not install |
| `backend/data/acceptance_worlds` | **absent in the prep worktree** (goal capture worktree has it) | use a worktree with the configured worlds root; never hand-create it |
| `frontend-nextjs/node_modules` | present | keep as-is; no npm install |
| Google Chrome.app / node | expected present | preflight refuses otherwise |
| FastEmbed cache | **present** at `$TMPDIR/fastembed_cache`: `models--qdrant--bge-small-en-v1.5-onnx-q`, 64 MB, `refs/main` + 5 snapshot files | freeze this exact `TMPDIR`; do not download/install |
| World storage guard | config exists (`layout: local`) but this worktree lacks the root | preflight reports; execute requires guard success |
| Ports 8047/3147 | assumed free | preflight/execute refuse busy/known live ports |

Operational note: the frontend's shared axios client has a 10 s request
timeout. The first FastEmbed load is local (cache-first) but can be slower than
10 s on a cold/slow machine; if so the browser request aborts and the episode
fails truthfully. The harness does not hide this with a longer client timeout,
a monkeypatch, a synthetic pre-warm row or a one-size sleep.

### FastEmbed trace (no model was started)

- Product default: `EMBEDDING_PROVIDER=fastembed`,
  `FASTEMBED_MODEL=BAAI/bge-small-en-v1.5`.
- `EmbeddingService._preprocess_text` truncates only the EMBEDDING input to
  8192 chars; `LanceDBHandler.add_document` stores the FULL parsed text in the
  row. The export reads that full stored text, not the model view.
- Installed fastembed is `0.8.0` in the capture venv. It first tries
  `download_files_from_huggingface(..., local_files_only=True)`; a complete
  cache therefore loads with **no external call**. The seatbelt profile also
  contains `(deny network*)` and allows only loopback ports 8047/3147.
- `launch_server` does not forward `FASTEMBED_CACHE_PATH`,
  `FASTEMBED_MODEL` or `HF_HUB_OFFLINE`; the effective server path is inherited
  `TMPDIR/fastembed_cache`. Preflight verifies `TMPDIR` is forwarded, the
  snapshot file sizes/refs, and the package's cache-first/offline behaviour.
- If the cache is incomplete/unusable, `--execute` writes
  `prerequisite_blocker.json` and refuses. Do **not** install a model, patch
  `EmbeddingService`, or pre-seed a synthetic LanceDB row.

## 6. What one execution proves (and how)

- Normal admin form login; public onboarding status + visible wizard
  (Next ×3, Start Automating) with durable completion.
- Data → real `#file-upload` upload of one disclosed synthetic TXT (>24k chars
  with a unique final tail), through `/api/documents/upload` only.
- Upload response id/version bound to the fixture; list card opens exactly
  `/documents/<doc_id>`; reload keeps the same id/full content.
- Text/Markdown/JSON selected in the existing export control. For each:
  browser download event from a `blob:` URL; downloaded file bytes, API
  response body bytes, `X-Document-Export-Sha256`, stored-text SHA and the full
  stored text/tail all match; expected filename, content type, disposition and
  `X-Document-*` provenance/scope headers match.
- JSON envelope `document_id`, `source_version`, `content`, byte count and SHA
  match the current upload response, SQL `ingested_documents` row and the
  LanceDB index metadata. TXT-only; explicitly **not** an original-binary
  download claim.
- Personal NULL/default scope is preserved and disclosed: bootstrap admin has
  NULL raw workspace/tenant, the route resolves the `default_shared` store, and
  the SQL mirror is `default`. No scope broadening, member account or foreign
  workspace is created.
- Background worker defaults are proven off from the actual server process
  env and/or the startup log; no provider shim, no BYOK config, no live DB.
- Only this harness's own backend/frontend PIDs are stopped and their actual
  exit is recorded. The world is preserved, never reset.

## 7. Evidence the driver writes

`preflight.json`, `source.json`, `scenario.json`, `requests.json`,
`network.json`, `retained_evidence.json`, `DOCUMENT_EXPORT_UI_RUN.json`,
`fixture/*.txt`, `downloads/<format>__<filename>`, `page_text/*.txt`,
`screenshots/*.png`. No raw token, password, cookie, JWT or Authorization
header is written; response headers are restricted to the safe document
metadata set.

## 8. Unrun limits / not claimed

- No tests, pytest, server, browser, app model/provider, embedding computation,
  download, install, deploy or merge was run by this preparation.
- No backend/frontend restart. Reload + fresh SQL/index readback already binds
  the same document; a restart would duplicate accepted general upload proof and
  is outside this finite export journey.
- No document search, grounding, retrieval quality, original binary, live
  provider/account, PostgreSQL/soak/multi-worker/whole-app acceptance.
- Missing-source, foreign-scope, revoked/stale, wrong-revision and unsafe-header
  controls remain the retained unchanged 37-case API evidence; the browser
  episode does not repeat them.
- The cached local index write is not claimed as provider embedding quality.

## 9. Root decision

Before `--execute`, decide only:

1. Is a prepared capture worktree with `backend/venv314` and a usable worlds
   root available? (This prep worktree lacks both.)
2. Is `$TMPDIR/fastembed_cache` still the complete cache preflight certified?
3. Does root own the >=4 GiB build gate (`--root-heavy-approved`)?
4. Is 8047/3147 free and is the evidence `--out` fresh?

If any answer is no, keep the non-executable truth: the harness refuses and
reports the concrete prerequisite. Do not fabricate browser coverage.
