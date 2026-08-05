# Mini-Apps — Design

> **Status:** Design (not yet implemented). Last updated Aug 5, 2026.
> **Target app class:** long-running stateful document apps — spreadsheets, docs,
> decks — plus interactive canvases. Atom is the harness; the mini-app is a
> document with logic.

A mini-app is a **canvas-bound document with server-side logic and declared
scopes**, distributed as a versioned blueprint. The platform is the harness:
every side effect flows through the existing security chain
(P1 registry → P3 gatekeeper → P4 taint → P9 sandbox). There is no other path.

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
2. **Sandboxed Python backend per app.** Generated logic runs in `SandboxRuntime.
   execute_python` scoped to a per-app FS namespace — the `CanvasLogicService.run`
   (`canvas_logic_service.py:147`) pattern. **For the target app class (docs/sheets/
   decks), the "backend" is a long-lived stateful document session** (see
   [Stateful document lifecycle](#stateful-document-lifecycle)), not a generic
   one-shot Python call.
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
   canvas snapshot → store as a `CanvasTemplate`-style blueprint
   (`models.py:4306` snapshot format exists).
3. **Install** → hydrate a fresh canvas: new id, `share_token=None`,
   `created_by=installer`, `status="active"`, components re-installed with
   sanitized config (the P5 fork exclusions apply: no audit history, no
   context/artifacts/recordings). `CanvasLogic` source copies; runtime state and
   per-canvas FS namespace reset to the new instance id. Document bytes copy into
   the installer's namespace.
4. **Run** → the instance's logic runs in `SandboxRuntime` (P7) with
   `storage_namespace=instance_id`; enforcement via the viewer-capped scope.

**Copy-on-install, not live binding.** Updates ship as new blueprint versions the
viewer must explicitly accept; a published update never silently mutates running
instances (avoids the push-malicious-logic-to-an-installed-base footgun). Uninstall
= delete the canvas.

---

## Stateful document lifecycle

The target app class (docs/sheets/decks) demands a **long-lived document session**,
not a one-shot `execute_python`. This is the central design challenge.

**What exists today:**
- `WorkbookRuntime` (`workbook_runtime.py`) evaluates formulas via LibreOffice
  headless → `formulas` lib → openpyxl fallback. `ExcelManager.write_cell`
  (`office_service.py:149`) auto-recalcs and returns the computed value.
- **But:** there is no in-memory workbook session — every operation reloads the
  file from disk, and a full recalc spawns a `soffice` process (~60s,
  `workbook_runtime.py:135`). There is no persistent canvas↔document binding (the
  link is passed per-request in `office_sync_service.py` and never persisted).
- **And:** delivery to the canvas is coarse — `office_sync_service.broadcast_file_update`
  (`office_sync_service.py:101`) re-renders the **whole document to HTML** on every
  edit and ships one big blob. No per-cell deltas; no client-side reactive grid.

**The performance threat:** a live spreadsheet app cannot do a full `soffice` recalc
+ whole-doc HTML re-render on every keystroke. Two options, not mutually exclusive:

| Option | Mechanism | Pros | Cons |
|---|---|---|---|
| **A. In-memory workbook session** | Hold the workbook in a long-lived process (one per running mini-app); edits mutate in-memory; recalc in-process; persist to disk on checkpoint | Fast edits; real stateful app; natural for macros | Process lifecycle, crash recovery, memory caps |
| **B. Per-cell deltas + real grid component** | Client-side reactive `data_grid` receives cell-level WS deltas; formula deps recompute in the browser | Snappy UX; low bandwidth | Need a real grid frontend; the `data_grid` component named in `canvas_type_registry.py:146` is **not wired** today |

**Recommended for MVP:** Option A (in-memory session) is what "long-running
stateful document app" literally means, and it composes with the existing
`workbook_runtime` engine (load once, mutate in-process, recalc without respawning
`soffice`, checkpoint to disk). Option B is a UX refinement that can layer on
later. The session lives in the sandbox runtime (P7/P9 isolation) with the per-app
FS namespace as its persistence target.

---

## Net-new pieces (ranked)

Everything below is **additive** unless noted. The hard parts (sandboxed runtime,
per-canvas FS namespace, credential stripping, fork semantics, encryption,
workspace skills/context, real MCP client, office read/write/recalc/render) exist.

1. **`MiniApp` manifest + binding model (new).** A persisted object linking one
   canvas to: its bound office document (file path under a per-app namespace), its
   `CanvasLogic` id, its installed `CustomComponent`s, declared scopes/skills/MCP
   servers, and an entrypoint. Today the canvas↔document↔logic link is ephemeral
   (`office_sync_service.py` never persists it). Includes a nullable
   `canvas.mini_app_id` FK. Migration + model + service.
2. **Document-event → logic binding (new wiring).** Auto-fire the bound
   `CanvasLogic.run()` on document edits (cell/paragraph) and external triggers
   (webhook/schedule), passing the edit as `inputs`, then writing results back into
   the doc. Today logic is **manual-trigger only** (`POST /{canvas_id}/logic/run`,
   `canvas_routes.py:772`).
3. **Stateful document session (new).** A long-lived in-memory workbook/document
   process per running mini-app: load once, mutate in-process, recalc without
   respawning LibreOffice, checkpoint to the per-app FS namespace, recover on
   crash. This is the "backend" for the doc/sheet/deck class — it wraps
   `workbook_runtime` rather than replacing it.
4. **Viewer-capped scope resolution at run (new wiring).** When a viewer runs an
   installed instance, route canvas-logic tool calls through `execute_action` (P1)
   with `min(viewer_capabilities, app_declared_scopes) ∩ tier_floor` as the context,
   not the permissive default. Author edit-time runs at the author's own tier.
5. **Publish/browse/install surface (new).** Publish = sanitize + snapshot to
   blueprint (`CanvasTemplate` format). Browse = a catalog endpoint. Install =
   reuse the P5 `fork_canvas` (`canvas_routes.py:214`) hydration primitive
   (independent copy, reset id/share_token, sanitized component config, fresh FS
   namespace, copied doc bytes).
6. **Document lifecycle tools (new/modify).** Explicit `create_workbook` /
   `create_document` / `create_deck` tools (today `write_cell` creates a file only
   as a side-effect, `office_service.py:154`) + a per-mini-app storage namespace
   for doc bytes (today all docs share one `data/office/` dir).

---

## Phased plan

**Phase A — Binding & manifest (foundation).** `MiniApp` model + migration +
`MiniAppService` (create manifest, bind canvas→doc+logic+components, resolve
scopes). Per-app document namespace under `data/office/<app_id>/`. No UI changes;
exercised via API + tests. *Unblocks everything else.*

**Phase B — Stateful document session.** A `DocumentSession` that holds a workbook
(document) in-process per running mini-app, wraps `workbook_runtime` for recalc,
checkpoints to the per-app FS namespace, and recovers after crash. The
`CanvasLogic.run` path drives it. *This is what makes docs/sheets/decks feel like
apps, not edit-then-re-render.*

**Phase C — Event binding + live update.** Wire document edits (via
`office_sync_service`) and external triggers (webhook/schedule) to fire the bound
`CanvasLogic.run()`, then push results to the canvas over WS. Replace the
whole-doc HTML re-render with session-backed deltas (Option A delivers this
naturally).

**Phase D — Viewer-capped execution.** Route installed-instance logic calls
through `execute_action` (P1) with the intersected viewer scope. Author edit-time
keeps the author's own tier. Tests for the no-privilege-escalation invariant.

**Phase E — Publish / browse / install.** Sanitize-and-snapshot publish; catalog
endpoint; install via P5 fork hydration. Versioning: updates ship as new blueprint
versions, copy-on-install, explicit viewer accept.

**Out of scope for v1:** dep install by generated apps (the author agent may still
install deps at build time via `PackageInstaller`), runtime egress inside the
default Docker sandbox (needs E2B/Firecracker or in-container egress enforcement —
a mini-app that calls external APIs at runtime is a follow-up), real-time
multi-user cursors, and the Option-B reactive `data_grid` frontend refinement.

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
  from-scratch renderer) + stateful hot-reloading session + stream deltas not full
  regenerations.
- **Deliberately avoided:** pi.dev's "no sandbox by default" (irresponsible for
  user-described apps; Atom's P9 default-on sandbox is the correct posture) and
  whole-file rewrite as primary edit strategy (lazy-coding/context-blowup failure
  mode).

Full research notes: coding-harness architecture survey (Claude Code, Cursor,
Aider, Devin, SWE-agent, OpenHands, Cline, pi.dev, v0/bolt/Lovable) and Atom
primitive reuse survey are in the conversation history that produced this doc.

---

## Open questions for review

1. **Session eviction policy** — when does an idle in-memory document session
   checkpoint-to-disk and shut down? (Proposed: configurable TTL with LRU eviction,
   checkpoint-on-evict so no data loss.)
2. **Macro trust boundary** — a `CanvasLogic` macro can call tools (office read/write,
   MCP, etc.). Confirm the viewer-capped scope (Phase D) is the only gate, or whether
   macros also need a per-call approval flow (cf. Cline #10499 — external tools
   bypassing approval). *Recommendation: per-call gatekeeper (P3) for all macro
  side effects, no blanket trust.*
3. **Collaborative editing** — multiple viewers editing one running instance: last-
   write-wins on the session, or operational transform? (Proposed for v1:
   last-write-wins with canvas-audit provenance; OT is a follow-up.)
