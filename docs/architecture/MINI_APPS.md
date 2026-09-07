# Mini-Apps — Design & Implemented Architecture

> **Status:** **IMPLEMENTED** (backend, Aug 2026). Last updated Aug 6, 2026.
> **WS2 Host-Callback Channel:** **IMPLEMENTED** (Aug 2026) — Mini-apps can now make conditional, parametrized integration calls mid-run via host-mediated vsock channel.
> **Target app class:** long-running stateful document apps — spreadsheets, docs,
> decks — plus interactive canvases. Atom is the harness; the mini-app is a
> document with logic.
>
> The sections below marked **"Implemented"** describe what shipped. The later
> sections preserve the original design narrative; where the implementation
> diverged from it, the divergence is called out explicitly (see
> [Divergences from the original design](#divergences-from-the-original-design)).

A mini-app is a **canvas-bound document with server-side logic and declared
scopes**, distributed as a versioned blueprint. The platform is the harness:
every side effect flows through the existing security chain
(P1 registry → P3 gatekeeper → P4 taint → P9 sandbox). There is no other path.

---

## Implemented architecture (backend, Aug 2026)

**Model (MVC):** `Canvas` = View · `CanvasLogic` (P7) = Controller, executed
one-shot per invocation in a **Firecracker microVM** with state round-tripped
via `CanvasState` and storage ops host-mediated · `MiniApp` manifest = Model.

| Piece | Implemented as |
|---|---|
| **App definition** | `MiniApp` (`models.py`) — name, manifest, `blueprint_canvas_id`, `runtime_image` (ext4 rootfs), `runtime_version`, status (`draft\|published\|archived`), `is_public`, `share_token` |
| **Instance state** | `CanvasState` (`models.py`) — **one row per instance canvas**, versioned, latest-wins. *Not* `CanvasAudit` (which stays the audit/history log) |
| **App assets** | `MiniAppAsset` rows + `core/mini_app_storage.py` (`MiniAppStorage` — pluggable local-FS / S3-R2, path-traversal-guarded) |
| **Runtime** | `core/mini_app_runtime.py` — **Firecracker microVM is the ONLY mini-app runtime.** `get_miniapp_runtime()` fails closed (`RuntimeError`) on non-Linux / missing `firecracker` / missing kernel / missing base rootfs template. No Docker/E2B fallback. Real boot path in `core/sandbox_runtime/firecracker_runner.py` (vsock command channel to `core/sandbox_runtime/firecracker_guest/agent.py`) |
| **Deps** | Manifest `dependencies` → fail-closed pip-audit/Safety scan (`core/package_dependency_scanner.py`) + operator-built per-app ext4 rootfs (`scripts/build_miniapp_rootfs.sh`). `prepare_runtime` scans + verifies rootfs presence — it never auto-builds. Dep change clears `runtime_image` to force rebuild |
| **Execution** | `core/mini_app_service.py` — `scaffold` / `syntax_check` / `publish` (snapshot blueprint + `initial_state`, `strip_credentials`) / `install` (copy-on-install, fresh id, `share_token=None`, `CanvasState` v1, exactly one `mini_app_install` audit) / `run_stateful` (state in → state out envelope, host-executed `storage_ops`, `CanvasState` upsert, WS `canvas:update` broadcast) |
| **API** | `api/mini_app_routes.py` (12 endpoints under `/api/mini-apps`) |
| **Ops** | `docs/deployment/FIRECRACKER_HOST_SETUP.md` (host provisioning, base template, per-app rootfs, real-boot smoke) |
| **Migration** | `alembic/versions/20260805_add_mini_apps.py` (guarded `_table_exists`/`_column_exists`, hybrid SQLite/PG) |

### Agent authoring harness (agent-driven coding — 13 `mini_app_*` actions)

All authoring is **agent-driven**: agents running inside Atom create, author,
test, publish, install, and run mini-apps through the unified action registry
(`core/action_registry.py`), which auto-exposes the actions to the agent MCP
loop (`integrations/mcp_service.get_all_tools`) and the frontend RPC surface
(`api/rpc_routes.py`). Handlers live in `tools/mini_app_tool.py`. Every handler
is fail-closed on identity (requester from `context`, never client-supplied)
and owner-gated for mutations.

The authoring loop (research-backed — see [Research basis](#research-basis)):

```
mini_app_status            # constraint probe: syntax, effective scopes (viewer tier ∩
                           #   declared), dep-scan state, rootfs presence, FC availability
mini_app_scaffold          # create draft app: source canvas + starter logic + manifest
mini_app_write_logic       # syntax-gated save; every save checkpointed to the audit trail
mini_app_dev_run           # dry run in the microVM — resulting state + proposed ops, NO commit
mini_app_set_tests         # declare acceptance cases {initial_state?, inputs?, expect_state?, expect_ops?}
mini_app_run_tests         # grade each case in the microVM — per-case pass/fail + expected-vs-actual diffs
mini_app_logic_history     # list logic checkpoints (oldest → newest)
mini_app_revert_logic      # restore a known-good checkpoint (revert is itself checkpointed)
mini_app_publish           # fail-closed dep scan + rootfs gate; snapshot blueprint + initial_state
mini_app_install           # copy-on-install: hydrate a fresh, immutable instance canvas
mini_app_run               # stateful run of an installed instance (persists state + broadcasts)
mini_app_get_state         # read an instance's current state + version
mini_app_list              # list apps the user owns (or public ones)
```

The **acceptance-test loop** is the generator-evaluator feedback loop: the agent
declares "given this state + inputs, the app must produce this state," the
harness runs every case in the microVM (dry) and returns per-case pass/fail with
diffs, so the agent self-corrects without a human in the loop. Logic checkpoints
give clean-state recovery when a run/test fails.

Tests: `tests/test_mini_app_agent_tools.py` (26 tests, incl. the agent-chat
dispatch seam through `integrations.mcp_service.call_tool`) + `tests/test_mini_apps.py`
+ `tests/test_mini_app_runtime.py` (Firecracker execution mocked — no real VM in
CI).

### User journey — creating a new mini-app

**Path A — agent-driven (primary; "all coding is agent driven").** The user
asks an agent (chat/workflow) to build a mini-app; the agent drives the loop.
**Chat can drive it directly** (Sep 2026): `core/chat_mini_app_authoring.py`
hooks the chat flow before the canvas-edit leg — "build a mini-app inventory
tracker" scaffolds, LLM-authors the logic (syntax-gated), dry-runs, and
reports; "publish it" / "install it" ship it (follow-ups work while the
conversation is about the app; it never auto-publishes). Any app family is
buildable: `spec.canvas_type` accepts any well-formed slug (crm, accounting,
inventory, sheets, …) — the blueprint and every installed instance carry it
so the canvas renders with that type's view; unknown kinds self-register in
`canvas_type_registry` with generic defaults.

1. **Ask** — user: "create a counter mini-app" (or describes the app + deps).
2. **Probe (optional)** — agent calls `mini_app_status` to learn its
   constraints: syntax validity, effective scopes (its own tier ∩ declared),
   dep-scan state, rootfs presence, FC availability.
3. **Scaffold** — `mini_app_scaffold {name, declared_scopes, dependencies}`
   → `{app_id, canvas_id, logic_source}` (starter logic the agent can read).
4. **Iterate (the coding loop)** — `mini_app_write_logic` (syntax-gated; each
   save checkpointed) → `mini_app_dev_run` (dry: resulting state + proposed
   ops, **no commit**) → `mini_app_set_tests` + `mini_app_run_tests`
   (acceptance feedback loop: per-case pass/fail + expected-vs-actual diffs) →
   on failure `mini_app_revert_logic` back to a known-good checkpoint. Repeat.
5. **Provision deps (only when deps declared)** — the operator runs
   `scripts/build_miniapp_rootfs.sh <app_id>`; `mini_app_publish` fails closed
   (dep scan must be clean AND the rootfs must exist).
6. **Publish** — `mini_app_publish` snapshots `initial_state` + blueprint
   (credentials stripped), `status=published`.
7. **Install** — `mini_app_install` → a fresh, immutable instance canvas
   (`CanvasState` v1, `share_token=None`, one `mini_app_install` audit).
8. **Use** — the user (or the agent) runs the instance via `mini_app_run`
   (state persists, version bumps, WS `canvas:update` live update) and reads it
   back with `mini_app_get_state`. Assets upload post-install.

**Path B — human via UI/API (secondary).** A user creates a mini-app through
the canvas harness (Monaco `CanvasLogicPanel` — Save/Run + scaffold/dev-run
buttons, a follow-up UI) or directly via `api/mini_app_routes.py`
(`POST /api/mini-apps/scaffold`, `/logic`, `/dev-run`, `/publish`, `/install`).
Same backend, same fail-closed gates.

**Where the user sees it:** instance canvases render in the canvas page; runs
broadcast live state over the WS `canvas:update` channel (`action:
mini_app_state`).

### Divergences from the original design

The implementation revised the original design in these ways:

1. **Instance state lives in `CanvasState`, not `CanvasAudit`.** A dedicated,
   versioned, latest-wins row per instance canvas. `CanvasAudit` remains the
   append-only audit/history trail.
2. **Firecracker microVM is mandatory** — no Docker runtime for mini apps.
   `get_miniapp_runtime()` fails closed. (The generic sandbox runtime keeps its
   Docker fallback for non-mini-app workloads.)
3. **Blueprint is stored in `MiniApp.manifest["blueprint"]`** (content/style/
   `logic_source`/component configs + `initial_state`) — no separate
   `MiniAppBlueprint` model.
4. **Storage is host-mediated `MiniAppStorage`** (local-FS / S3-R2) with
   `MiniAppAsset` rows — the guest has no host FS and no network. There is no
   bound office document at `data/office/<app_id>`; assets are uploaded after
   install.
5. **No document-event auto-binding.** Runs are explicit (`mini_app_dev_run` /
   `mini_app_run`), not fired by cell/paragraph edits. Event-triggered logic is
   a follow-up.
6. **Scaffold LLM-assisted body** is flag-gated (`ATOM_MINIAAP_LLM_SCAFFOLD`),
   deterministic template by default (testable path).

### Mini-app DB store — records + read bridge (Aug 2026)

Mini-apps get a **host-mediated, per-instance structured data store** plus
pre-fetched reads of existing system data. The microVM has no network/DB, so
the host mediates everything — same trust model as `storage_ops` (the guest
proposes, the host validates and executes).

**Records (`CanvasRecord` — the app's database).** Series-scoped rows with a
monotonic per-(canvas, series) `seq` (append order), JSON `data` payloads, and
full CRUD. Reachable from three surfaces, all flowing through
`core/mini_app_db_service.py` (the single enforcement point):

| Surface | How |
|---|---|
| **MicroVM logic** | `record_ops` appended in the logic (sibling of `storage_ops`), e.g. `record_ops.append({"op": "append", "series": "chart_data", "data": {"label": "Jan", "value": 12}})`. Ops: `append` (optional client `id`), `get`, `query` (equality `filter` + `limit` 1–10000 + `order` by seq, desc default), `count`, `update` (merge), `update_many`, `delete`, `delete_series`, `clear`, `list_series`. Host validates each op (`_validate_record_op`), executes, returns `record_results` in the run result; dry-runs propose without committing; committed writes broadcast `canvas:update` (`action: mini_app_db`) |
| **Agents** | `mini_app_db_query` (read-only; INTERN+) / `mini_app_db_write` (SUPERVISED+) — owner-gated, identity from context, same op vocabulary; auto-exposed via `/api/rpc/*` |
| **Integrations/workflows/UI** | `/api/mini-apps/instances/{canvas_id}/records/*` (query/append/count/series/get/update/delete/delete-series) — `get_current_user` + instance check + owner-gated mutations; no microVM involved |

**Read bridge — inputs pre-fetched at run start.** The host injects as globals
before `execute_python`:
- `records` — own-history pre-fetch for series in `manifest.db.record_queries`
  (latest N, desc) — the app can compute over its own accumulated rows without
  cramming them into `state`.
- `data_sources` — `manifest.data_sources` (`documents.search`) and
  `manifest.mcp_servers` (`{service, action, params}` — no longer a dead stub).
  Integration calls go through `ExternalIntegrationService.execute_integration_action`
  with credentials resolved from `IntegrationToken` (P0-encrypted, decrypted
  host-side); only the result payload is injected — **tokens never reach the
  guest**. Failures/unknown services are logged + skipped; results are
  size-capped (5 MiB/source) — a bad source never crashes a run.

**Config & caps.** `manifest.db = {enabled (default true), max_records_per_series
(10000), max_record_bytes (100 KiB), record_queries: [...]}`; validated in
`validate_manifest`. Series names must match `^[a-z0-9_]{1,64}$`. Per-run cap:
200 ops. Kill switch: `ATOM_MINIAPP_DB_ENABLED=false` rejects all `record_ops`
(`db_disabled`) and errors the record routes (503). v1 filters are host-side
equality matches (SQL pushdown is a follow-up); no per-row ACLs (series-level
only); no compaction/TTL.

---

## The MVC model

| Layer | Atom component | Role in a mini-app |
|---|---|---|
| **View** | `Canvas` (`models.py:3361`) + `content`/`style` + installed `CustomComponent`s | The UI, rendered by the canvas |
| **Controller** | `CanvasLogic` (`models.py:9995`, P7) — per-canvas Python | The app's backend / macros |
| **Model** | **`MiniApp` manifest (new)** + bound document + declared scopes | Intent: what the app may touch |
| **Document** | Real office doc under `data/office/` via `office_service` + `workbook_runtime` | The app's bytes (xlsx/docx/pptx) — the real engine, not a re-implementation |
| **Enforcement** | P1 action registry → P3 gatekeeper → P4 taint → P9 sandbox | The harness; no side effect bypasses it |

**Verdict: wrap a real office document.** The office stack
(`office_service.py`, `workbook_runtime.py`, `office_sync_service.py`) already
gives real read/write/recalc/render for xlsx/docx/pptx. `CustomComponent`
(`custom_components_service.py`) is frontend-JS-only with no document engine —
rebuilding spreadsheet semantics on it would discard a mature engine. A mini-app
composes: a canvas (UI) + a bound office doc (bytes) + a `CanvasLogic` row
(macros/backend) + a manifest (intent).

---

## Decisions (locked)

1. **1 canvas = 1 mini-app.** Every mini-app primitive (UI, logic, namespace, WS
   preview) is already per-canvas. A mini-app is the binding object that owns one
   canvas.
1. **Dual-face access — every mini-app instance is user-faced AND agent-faced.**
   The same instance is a rendered canvas for the human and a structured,
   queryable state for the agent. The canvas **AI-accessibility layer**
   (`frontend-nextjs/hooks/useCanvasState.ts` — hidden a11y trees,
   `window.atom.canvas.getState(canvas_id)`, <10ms) is the agent's view of what
   the user sees; `mini_app_get_state` returns the app's data state + version.
   This gives an agent **situational awareness while a mini-app runs** (it can
   read current UI + state before deciding its next action) and makes the agent a
   first-class **co-editor**: `mini_app_run` persists new state and broadcasts
   `canvas:update` (action `mini_app_state`) so the user's canvas updates live
   and the agent reads the result back through the same channel. Both faces read
   the same `CanvasState`; there is no separate agent-only or user-only copy.
1. **Co-editing is universal — and agents are autonomous operators, not just
   authors.** Every mini-app instance is a live, multi-participant document. The
   WS `canvas:update` broadcast (`action: mini_app_state`) is **app-agnostic**:
   it carries state deltas for sheets, docs, decks, and custom canvases alike, so
   a user and an agent co-edit **any** mini-app in real time — not only
   office-bound ones. Once published and installed, an agent operates the app
   **autonomously**: `mini_app_run` on its own, read the result back via
   `mini_app_get_state`, upload assets, and iterate in a closed
   situational-awareness loop (a11y view → decide → run → verify), gated only by
   the app's declared scopes intersected with the **operating agent's own tier**
   (the same no-escalation rule as viewers). Authoring is a special case: the
   agent builds an app, then keeps operating the thing it built. Document-level
   conflict resolution (last-write-wins today; OT is an open question) is
   orthogonal to the co-editing channel — co-editing works regardless.
1. **Every mini-app instance has a user↔agent chat interface.** Beyond the
   rendered canvas (user) and the structured state (agent), each instance
   carries a **per-instance conversation** binding the user to the agent
   operating that app — the standalone-canvas side-chat co-editor pattern
   (`/canvas` side panel) applied universally. The user instructs in natural
   language ("add a row", "why is the total wrong?", "approve this change"); the
   agent reads current UI + state (dual-face access), acts via
   `mini_app_run`/asset ops, and the result lands live on the canvas and in the
   thread. The chat is scoped to the instance's state, not global — so
   co-editing is conversational, auditable, and grounded in the exact instance
   being worked on.
2. **Sandboxed Python backend per app; state is persistent + resumable (no
   background process).** Generated logic runs in `SandboxRuntime.execute_python`
   scoped to a per-app FS namespace — the `CanvasLogicService.run`
   (`canvas_logic_service.py:147`) pattern. A mini-app is **not** a long-lived
   daemon holding a document in RAM; it is **persistent + resumable**: the
   document bytes live on disk (real `.xlsx`/`.docx`/`.pptx` under a per-app
   namespace) and reopening resumes exactly where you left off — exactly how
   `office_service` + `workbook_runtime` already work today. Logic fires on
   events (edits, triggers), computes, writes results back to the document, and
   the process ends; nothing stays resident between interactions. (See
   [Stateful document lifecycle](#stateful-document-lifecycle).)
   **Instance mutable state lives in `CanvasAudit`** (the append-only audit trail
   that is already the canvas content source of truth — `read_canvas` reads the
   latest `CanvasAudit` row, `canvas_crud_tool.py:61`). So "resume" = reopen the
   document + re-derive state from the latest audit row. No new state table;
   provenance comes for free (every state change is an audited, attributable
   event).
3. **Incremental edits + hot-reload.** Each edit produces a new component version
   (`CustomComponentsService.update_component` bumps `current_version` + writes a
   `ComponentVersion` row) + a new `CanvasLogic` source; the runner pushes a
   `canvas:update` WS message and the frontend remounts the component. "Hot" =
   the user doesn't restart; the canvas refreshes. We do **not** use
   `canvas_execute_javascript` DOM-patching (fragile, denylist-constrained).
4. **Build + run + publish + browse in scope.** The MVP exercises the full
   distribution loop, including the one security decision that matters (viewer
   rights) and the blueprint-hydration install path.

---

## The one security decision that matters

When a **viewer** runs an installed mini-app, whose rights does the canvas logic
execute with?

**Answer: the viewer's standing tier caps the app's declared scopes.** Tool calls
are gated by `min(viewer_capabilities, app_declared_scopes) ∩ tier_floor`, resolved
through P2's `capability_resolver` (`capability_resolver.py`). A SUPERVISED viewer
can never wield an AUTONOMOUS author's powers — no privilege escalation. This is
the deny-first principle applied literally.

**At edit/build time, the author agent runs at the author's OWN standing tier**
(so an AUTONOMOUS author can build and test with full tools; a SUPERVISED author is
capped at SUPERVISED). The declared scopes in the manifest are a *ceiling the
author sets for viewers*, not a ceiling on the author. The intersect-down-to-viewer
rule applies only when a viewer runs an installed instance.

Canvas-logic tool calls already flow through the sandbox runtime (P7); the new
wiring routes them through `execute_action` (P1) with the resolved (intersected)
scope context instead of a permissive default.

---

## Share / install flow

1. **Author** creates a canvas + document + logic + components, declares scopes in
   the manifest.
2. **Publish** → `blueprint_sanitizer.strip_credentials` (P5) over the manifest +
   canvas snapshot → store as a **`MiniAppBlueprint`** (new — see below). Note:
   the existing `CanvasTemplate` model (`models.py:4334`) is **dead schema** (no
   writer, no reader, no migration reference — verified), so it cannot be reused
   as-is; its column *shape* (`canvas_snapshot`, `component_installations`,
   `styles`) is a useful reference, but the blueprint must add a `logic_source`
   field the dead model never carried.
3. **Install** → hydrate a fresh canvas. The P5 `fork_canvas`
   (`canvas_routes.py:214`) primitive is ~80% reusable (new id, `share_token=None`,
   `created_by=installer`, `status="active"`, stripped component configs, one
   fork audit row), but it has **three gaps** that install must close explicitly:
   - **Copy `CanvasLogic`** — fork does NOT copy it; install re-points a new
     `CanvasLogic` row at the new canvas id.
   - **Derive initial state from the audit trail** — fork copies the stale
     `Canvas.content` column, but for sheets/docs/mini-apps the truth is the
     latest `CanvasAudit.details_json`. Install must seed the new instance's
     initial audit row from the blueprint's snapshot (not the stale column).
   - **Component config policy** — decide whether installs keep working configs
     or apply `strip_credentials` (recommend: strip on publish, keep on install —
     the publish step already sanitized).
   Runtime state and the per-canvas FS namespace reset to the new instance id;
   document bytes copy into the installer's namespace.
4. **Run** → the instance's logic runs via `CanvasLogicService.run` (P7, see
   [Execution model](#execution-model-state-in--state-out)) with
   `storage_namespace=instance_id`; enforcement via the viewer-capped scope.

**Copy-on-install, not live binding.** Updates ship as new blueprint versions the
viewer must explicitly accept; a published update never silently mutates running
instances (avoids the push-malicious-logic-to-an-installed-base footgun). Uninstall
= delete the canvas.

---

## Stateful document lifecycle

The target app class (docs/sheets/decks) needs to be **persistent + resumable**,
not backed by a long-lived background process. This is a deliberate, simplifying
choice: it reuses what the office stack already does well and avoids inventing a
session/process subsystem for v1.

**What "stateful" means here (and doesn't):**
- **Yes:** the document persists on disk (real `.xlsx`/`.docx`/`.pptx` under a
  per-app namespace); reopening resumes exactly where you left off; co-editing
  continues live; logic fires on events and writes results back to the document.
- **No:** there is no resident daemon holding a workbook in RAM between
  interactions. Logic runs on demand (event-triggered), mutates the document,
  appends a `CanvasAudit` state row, and the process ends. State survives because
  it's on disk + in the audit log, not because a process stays up.

**Where instance state lives — `CanvasAudit` (reuse, no new table).**
`CanvasAudit` (`models.py:3412`) is already the canvas content source of truth:
`read_canvas` returns the latest row (`canvas_crud_tool.py:61`). A mini-app
instance treats it the same way — every state change (an edit, a logic run, an
external trigger firing) appends an audited, timestamped, attributable row.
"Resume" = reopen the document + re-derive UI state from the latest audit row.
This gives provenance for free and composes with the viewer-capped execution
model (Phase D): every state mutation is already an auditable side effect.

**What exists today (reusable as-is):**
- `WorkbookRuntime` (`workbook_runtime.py`) evaluates formulas (LibreOffice →
  `formulas` → openpyxl); `ExcelManager.write_cell` (`office_service.py:149`)
  auto-recalcs and returns the computed value. Document state is the file.
- `CanvasAudit` append-only history (`models.py:3412`) is the state log.
- `office_sync_service.broadcast_file_update` (`office_sync_service.py:101`)
  renders + WS-broadcasts after a write.

**Known v1 limitation (acceptable, flagged):** a full recalc spawns a `soffice`
process (~60s, `workbook_runtime.py:135`) and canvas delivery is a whole-document
HTML re-render. This is fine for event-triggered logic (edit → compute → refresh)
because recalc is per-interaction, not per-keystroke. It would *not* be fine for
a keystroke-reactive grid — that needs the future optimization below.

**Future optimization (out of scope for v1):** an optional **in-memory document
session** (load once, mutate in-process, recalc without respawning `soffice`,
checkpoint to disk) for app categories that can't tolerate recalc-on-open or need
sub-second cell reactivity. This is additive — it wraps `workbook_runtime`, doesn't
replace the document-on-disk + CanvasAudit model. Paired with per-cell WS deltas
to a real `data_grid` frontend (the component named in `canvas_type_registry.py:146`
is not wired today), it would give the live-spreadsheet feel. Both are post-MVP.

---

## Execution model: state in → state out

A mini-app logic run is a pure-ish function: **current state in, new state out.**
This mirrors how sheets/docs already work (state = latest `CanvasAudit.details_json`)
and requires **no sandbox-core changes**.

- **State in (free today):** `SandboxRuntime.execute_python` injects `inputs` as
  module globals via `globals().update(inputs)` (`skill_sandbox.py:271`). So
  `CanvasLogicService.run` passes `inputs={"state": <latest audit details_json>,
  "event": ..., "storage_namespace": ...}` and the logic sees `state` as a global.
- **State out (convention only):** the wrapped logic serializes its new state to
  stdout in an envelope — `print(json.dumps({"state": new_state, "output": ...}))`
  — and `run` parses that envelope from stdout, appends `new_state` as a
  `CanvasAudit.details_json` row, and broadcasts the WS update via
  `update_canvas_content`. The container is already destroyed after stdout capture
  (`auto_remove=True`), so the stdout envelope is the natural (and only) return
  channel — no `SandboxExecResult`/`SandboxRuntime` change needed.
- **Why not read globals back:** the container is gone before introspection is
  possible; stdout is the pipe. The envelope convention keeps the contract explicit
  and parseable.

**Result:** `CanvasLogicService.run` becomes the entire mini-app execution surface.
A run = load latest state → inject as global → execute wrapped source → parse
stdout envelope → append new state + broadcast. State persists because it's in the
audit log, not because a process stays up.

> **WS note:** live updates reuse `update_canvas_content`
> (`canvas_crud_tool.py` — audit write + `ws_manager.broadcast(channel, msg)` with
> the two-arg form). Do **not** copy `office_sync_service.py:151`, which calls
> `broadcast({...})` with one arg — a latent bug (the signature requires channel
> first).

## Net-new pieces (ranked)

Everything below is **additive** unless noted. The hard parts (sandboxed runtime,
per-canvas FS namespace, credential stripping, the latest-`CanvasAudit`-wins state
pattern, `read_canvas`/`update_canvas_content` + WS live-update, office
read/write/recalc/render) exist and are reused verbatim.

1. **`MiniApp` manifest + binding model (new).** A persisted object linking one
   canvas to: its bound office document (file path under a per-app namespace), its
   `CanvasLogic` id, its installed `CustomComponent`s, declared scopes/skills/MCP
   servers, and an entrypoint. Today the canvas↔document↔logic link is ephemeral
   (`office_sync_service.py` never persists it). Includes a nullable
   `canvas.mini_app_id` FK. Migration + model + service.
2. **State-in/state-out execution convention (new in `CanvasLogicService`, no
   sandbox-core change).** Today `run` returns only `{stdout, stderr, exit_code}`
   and injects `inputs` as globals (free state-IN). State-OUT is a convention: the
   wrapped logic emits a JSON envelope on stdout (`{"state": {...}, "output": ...}`)
   and `run` parses it, appends the new state as a `CanvasAudit.details_json` row,
   and broadcasts via `update_canvas_content`. See
   [Execution model](#execution-model-state-in--state-out).
3. **Document-event → logic binding (new wiring).** Auto-fire the bound
   `CanvasLogic.run()` on document edits (cell/paragraph) and external triggers
   (webhook/schedule), passing `{state: <latest audit details_json>, event: ...}`
   as `inputs`. Today logic is **manual-trigger only** (`POST /{canvas_id}/logic/run`,
   `canvas_routes.py:772`).
4. **Viewer-capped scope resolution at run (new wiring).** When a viewer runs an
   installed instance, route canvas-logic tool calls through `execute_action` (P1)
   with `min(viewer_capabilities, app_declared_scopes) ∩ tier_floor` as the context,
   not the permissive default. Author edit-time runs at the author's own tier.
5. **`MiniAppBlueprint` + publish/browse/install (new).** Publish = sanitize +
   snapshot to a **new `MiniAppBlueprint`** (the existing `CanvasTemplate`
   (`models.py:4334`) is dead schema — no writer/reader/migration — so the
   blueprint is greenfield; mirror its column shape + add `logic_source`).
   Browse = a catalog endpoint. Install = `fork_canvas` (`canvas_routes.py:214`)
   is ~80% reusable but must explicitly (a) copy `CanvasLogic` re-pointed at the
   new canvas, (b) seed the initial audit row from the blueprint snapshot (not the
   stale `Canvas.content` column fork copies), and (c) apply the publish-time
   credential strip. Fresh FS namespace + copied doc bytes.
6. **Document lifecycle tools (new/modify).** Explicit `create_workbook` /
   `create_document` / `create_deck` tools (today `write_cell` creates a file only
   as a side-effect, `office_service.py:154`) + a per-mini-app storage namespace
   for doc bytes (today all docs share one `data/office/` dir).

> **Not needed for v1:** a stateful-session/document-process subsystem. Because
> state is **persistent + resumable** and lives in **`CanvasAudit` + the document
> on disk**, there is no in-memory daemon to build, no process lifecycle, no
> crash recovery, no eviction policy. That machinery becomes an optional future
> optimization (see Stateful document lifecycle §"Future optimization"), not an
> MVP dependency.

---

## Phased plan

**Phase A — Binding & manifest (foundation).** `MiniApp` model + migration +
`MiniAppService` (create manifest, bind canvas→doc+logic+components, resolve
scopes, persist the canvas↔document link that `office_sync_service` today leaves
ephemeral). Per-app document namespace under `data/office/<app_id>/`. No UI
changes; exercised via API + tests. *Unblocks everything else.*

**Phase B — Event binding + state log (the "app" behavior).** Wire document edits
(via `office_sync_service`) and external triggers (webhook/schedule) to fire the
bound `CanvasLogic.run()`, passing the edit as `inputs`; logic computes, writes
results back to the document via the office tools, and the run appends a
`CanvasAudit` state row + broadcasts a WS update. **No new state subsystem** —
state is the document-on-disk + the CanvasAudit log (reuse). This is what makes
docs/sheets/decks behave as apps (edit → logic → recompute → refresh) without a
resident process. *This phase replaces the earlier "stateful session" phase,
which is no longer needed for v1.*

**Phase C — Viewer-capped execution.** Route installed-instance logic calls
through `execute_action` (P1) with the intersected viewer scope. Author edit-time
keeps the author's own tier. Tests for the no-privilege-escalation invariant.

**Phase D — Publish / browse / install.** Sanitize-and-snapshot publish to a new
`MiniAppBlueprint` (the existing `CanvasTemplate` is dead schema); catalog
endpoint; install via `fork_canvas` + the three explicit adds (copy `CanvasLogic`,
seed audit state from the snapshot, apply the publish-time credential strip).
Versioning: updates ship as new blueprint versions, copy-on-install, explicit
viewer accept.

**Out of scope for v1:** dep install by generated apps (the author agent may still
install deps at build time via `PackageInstaller`), runtime egress inside the
default Docker sandbox (needs E2B/Firecracker or in-container egress enforcement —
a mini-app that calls external APIs at runtime is a follow-up), real-time
multi-user cursors, a resident in-memory document session + reactive `data_grid`
frontend (the future optimization in [Stateful document lifecycle](#stateful-document-lifecycle)),
and per-cell WS deltas.

---

## Research basis (selected)

The design adopts the patterns the coding-harness research surfaced as
highest-leverage, adapted to Atom's substrate:
- **SWE-agent ACI:** lint-gate inside the edit tool; explicit "ran successfully, no
  output" feedback; windowed views. (Applied to the build agent's edit loop.)
- **Aider architect/editor split + SEARCH/REPLACE + git-as-checkpoint:** strong
  model plans, fast model edits, every edit group = a versioned checkpoint (the
  `ComponentVersion` + blueprint-version machinery).
- **OpenHands typed action/observation protocol + append-only log + Dockerized
  runtime:** the substrate for isolation and replay. Atom's sandbox + WS event
  stream already approximate this.
- **v0/bolt/Lovable trinity:** one pinned document engine (the office stack, not a
  from-scratch renderer) + persistent/resumable state (document-on-disk + audit
  log) + stream deltas not full regenerations.
- **Deliberately avoided:** pi.dev's "no sandbox by default" (irresponsible for
  user-described apps; Atom's P9 default-on sandbox is the correct posture) and
  whole-file rewrite as primary edit strategy (lazy-coding/context-blowup failure
  mode).

Full research notes: coding-harness architecture survey (Claude Code, Cursor,
Aider, Devin, SWE-agent, OpenHands, Cline, pi.dev, v0/bolt/Lovable) and Atom
primitive reuse survey are in the conversation history that produced this doc.

---

## Open questions for review

> **Resolved (this revision):** mini-apps are **persistent + resumable** (no
> background process), and instance mutable state lives in **`CanvasAudit`** (no
> new state table). The session-eviction question this raised is therefore moot
> for v1 — see [Stateful document lifecycle](#stateful-document-lifecycle).

1. **Macro trust boundary** — a `CanvasLogic` macro can call tools (office
   read/write, MCP, etc.). Confirm the viewer-capped scope (Phase C) is the only
   gate, or whether macros also need a per-call approval flow (cf. Cline #10499 —
   external tools bypassing approval). *Recommendation: per-call gatekeeper (P3)
   for all macro side effects, no blanket trust.*
2. **Collaborative editing** — multiple viewers editing one instance: last-write-
   wins on the document + CanvasAudit, or operational transform? (Proposed for v1:
   last-write-wins with canvas-audit provenance; OT is a follow-up.)
3. **State-derivation on resume** — "resume = reopen the document + re-derive UI
   state from the latest CanvasAudit row": confirm what the audit row should carry
   for a doc/sheet/deck so the reopened canvas reconstructs without a full recalc.
   (Proposed: the audit row carries the rendered snapshot + a content hash; if the
   hash matches the document on disk, skip recalc.)
