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

### Harness-only repair after the first real attempt

The first authorized `--execute` reached `run_isolated.build_world`, provisioned
an API-seeded DB, then failed with:

```text
FileNotFoundError: .../docs/architecture/orchestration_migration/acceptance/venv_freeze.txt
```

`build_world` **writes** `<ACC>/venv_freeze.txt` (and the per-world copy) but
never `mkdir`s `<ACC>`. That file is **generated output**, not a tracked
fixture, and the sparse prep checkout had no `acceptance/` directory. The
correct attribution is: *missing writable ACC parent*, not *missing tracked
file*. Do not “fix” it by committing a `venv_freeze.txt`.

This repair adds only read-only preflight/execute guards plus pure helper tests:

- ACC metadata parent must exist and be writable, and
  `ACC/venv_freeze.txt` must **not** be Git-tracked;
- the real `fixtures/SHA256SUMS` must have exactly 55 named entries, each a
  regular file (no symlink borrow), inside the fixtures dir, with a matching
  SHA-256, and byte-identical to the current Git `HEAD` blob; the checksum file
  itself is also Git-exact and is bound into `source.json`;
- the same launcher/ACC/fixture checks are re-run inside `_build_world` after
  the storage guard and **before** `R.build_world`/any world mkdir.

No world, DB, server, browser, model, pytest run or download was run for this
repair. The retained half-built world `document_export_ui_b324_root_20261108`
is not reused, deleted or rebuilt.

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
- ACC metadata parent exists + writable, and `ACC/venv_freeze.txt` is not
  tracked (it is generated output);
- real `fixtures/SHA256SUMS`: exactly 55 named entries, no empty/duplicate/
  escaped names, every fixture a regular file (no symlink), inside the fixtures
  dir, SHA-256 matching the inventory, and byte-identical to the current Git
  `HEAD` blob; the checksum file is Git-exact and bound into `source.json`;
- disk estimate and whether the build is >=4 GiB (heavy root gate); the
  measured ~1.54 GiB estimate is **not** permission to lower the 4 GiB floor;
- fresh world name, free ports, writable fresh output;
- `backend/venv314`, `frontend-nextjs/node_modules`, node, Chrome;
- the complete existing FastEmbed ONNX cache and the installed fastembed
  source behaviour (read-only; no import/instantiation).

It returns `1` when a real prerequisite or the fixture inventory is absent or
unverified (the report is still written) and `2` for wrong source/profile/
output/world/port. It does not create a world or a cache.

### Materialize the exact Git fixtures (no regeneration)

If the sparse checkout omits `docs/architecture/orchestration_migration/acceptance`,
materialize the **tracked bytes only** — never regenerate a fixture and never
commit a synthetic `SHA256SUMS` or `venv_freeze.txt`:

```sh
cd /private/tmp/atom-document-stored-export-20261107
# Preferred: ask Git to materialize the tracked paths in this sparse worktree.
git sparse-checkout add docs/architecture/orchestration_migration/acceptance/fixtures
# Equivalent explicit checkout from the current HEAD (creates parents):
git checkout HEAD -- docs/architecture/orchestration_migration/acceptance/fixtures
# Prove bytes are Git-exact without rebuilding anything:
git status --porcelain=v1 -- \
  docs/architecture/orchestration_migration/acceptance/fixtures  # must be empty
```

That checkout also creates the writable `acceptance/` parent, so
`build_world` can write its generated `venv_freeze.txt`. Do **not** create an
empty `acceptance/` directory by hand and do **not** add a fake tracked
`venv_freeze.txt`.

The 55 checksummed files are **legacy framework inputs** required by
`run_isolated.build_world` (workbook parquet sheets plus old conversation and
provider fixtures). They are not uploaded as this episode's user document, add
no new business rows, and mostly are not read by the Documents export path.
The actual uploaded TXT is generated separately and labelled synthetic.
Avoid expanding or re-verifying the whole old acceptance history.

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
| `backend/data/acceptance_worlds` | configured (symlink resolves to the atom backend worlds root) | keep the configured root; never hand-create or replace it |
| ACC metadata dir `docs/architecture/orchestration_migration/acceptance` | **absent in the sparse prep worktree** | materialize the tracked fixtures (above); do not `mkdir` an empty dir or fake `venv_freeze.txt` |
| 55 legacy fixtures + `SHA256SUMS` | **absent in the sparse prep worktree** (tracked at HEAD) | `git sparse-checkout add .../acceptance/fixtures`; never regenerate |
| `frontend-nextjs/node_modules` | present | keep as-is; no npm install |
| Google Chrome.app / node | expected present | preflight refuses otherwise |
| FastEmbed cache | **present** at `$TMPDIR/fastembed_cache`: `models--qdrant--bge-small-en-v1.5-onnx-q`, 64 MB, `refs/main` + 5 snapshot files | freeze this exact `TMPDIR`; do not download/install |
| World storage guard | config exists (`layout: local`) and preflight resolves the root | preflight reports; execute requires guard success |
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
- If launcher/ACC/fixture prerequisites fail, `--execute` writes
  `prebuild_blocker.json` and refuses **before** any world/database is created.
  The same checks are re-run inside `_build_world` after the storage guard and
  before `R.build_world`.

### Port probe note

A `ports_free=False` reading that appears only inside a restricted tool sandbox
is an `EPERM` artifact of that sandbox. In an authorized root readback the
ports were free. Do not treat it as a product bug or add a port bypass; root
runs the real gate.

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
- The 55 checksummed files are legacy framework inputs required by the builder,
  not the uploaded document and not new business rows. Preflight proves their
  Git bytes; it does not claim they are exercised by the export journey.

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
- The retained half-built world `document_export_ui_b324_root_20261108` was not
  reused, deleted or rebuilt; it is root-owned evidence of the failed attempt.
- The harness-only repair is not a claim that the new checks were executed
  here. Root must run them from the new frozen harness HEAD.
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
   root available? (This prep worktree uses the configured worlds root.)
2. Are the exact tracked fixtures materialized and the ACC parent writable
   (`git sparse-checkout add .../acceptance/fixtures`; no regeneration)?
3. Is `$TMPDIR/fastembed_cache` still the complete cache preflight certified?
4. Does root own the >=4 GiB build gate (`--root-heavy-approved`)?
5. Is 8047/3147 free and is the evidence `--out` fresh?

If any answer is no, keep the non-executable truth: the harness refuses and
reports the concrete prerequisite. Do not fabricate browser coverage.
