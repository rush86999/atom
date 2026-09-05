# Canvas User Journey — Create → Attach a Hire → Load Data

Design doc for the direct canvas-creation journey. Before this landed, the
only creation path was chat ("ask an agent to make one") plus PDF upload; a
canvas created outside an agent chat had **no resolvable hire, permanently**,
and every ingestion path was user-scoped with agents irrelevant. This doc
defines the product rule, the journey, the UI, and the build order. Home:
the canvas gallery (`frontend-nextjs/pages/canvas/index.tsx`) and the canvas
page (`frontend-nextjs/pages/canvas/[id].tsx`).

**The product rule: a canvas works through its hire.** Data loading is
refused — in the UI and at the API (same gate) — until an agent is attached
to the canvas.

---

## 1. Current state (grounding — what the system already does)

| Mechanism | Trigger | Result | Code |
|---|---|---|---|
| Blank canvas create | `POST /api/canvas` `{title?, description?, canvas_type?}` | Canvas row + `create` audit row (`details_json.content` is the readers' source of truth) | `backend/api/canvas_routes.py` (`create_blank_canvas`) |
| Attach a hire | `POST /api/canvas/{id}/agents` `{agent_id, role?}` | `AgentCanvasPresence` row (WS join broadcast) + `CanvasContext.agent_id` stamp + `agent_attached` audit row; idempotent | `backend/api/canvas_routes.py`, reuses `core/agent_coordination.py:MultiAgentCanvasService.add_agent_to_canvas` |
| List / detach hires | `GET/DELETE /api/canvas/{id}/agents[/{agent_id}]` | Active presence joined to `AgentRegistry` (name, category, tier, confidence) | `backend/api/canvas_routes.py`, `core/agent_coordination.py:active_canvas_agents` |
| Load data — upload | `POST /api/canvas/{id}/data/upload` (multipart) | Parse + ingest into workspace memory, **role-tagged** to the hire's category; `data_loaded` audit row | `backend/api/canvas_routes.py` → `core/auto_document_ingestion.py:process_file_bytes(role=…)` |
| Load data — drives | `POST /api/zoho-workdrive/ingest[/ingest-folder]`, `/api/gdrive/ingest-folders`, `/api/onedrive/ingest-folders` with optional `canvas_id` | Same gate + role tag; **no `canvas_id` → byte-for-byte old behavior** | `backend/api/zoho_workdrive_routes.py`, `backend/integrations/{gdrive,onedrive}_journey_routes.py` |
| Hire resolution | `GET /api/maturity/training/context` | Explicit attach **outranks** every heuristic (client hint → audit provenance → training-canvas content → session) | `backend/api/agent_maturity_routes.py:get_canvas_training_context` |
| Attach picker source | `GET /api/agents/` | The user's registry agents (existing endpoint; unchanged) | `backend/api/agent_routes.py:116` |

Key properties the UX must respect:

- **The gate is real at the API.** Every canvas-scoped load path returns
  `409 NO_AGENT_ON_CANVAS` when no active `AgentCanvasPresence` exists. The
  UI's disabled state is guidance, never the only guard.
- **Plain (non-canvas) ingestion behavior is unchanged.** Existing callers
  of the drive ingest endpoints see the exact old request/response shapes.
- **An explicit attach outranks heuristics.** When a supervisor puts hire B
  on a canvas whose audit provenance names hire A, the training panel shows
  B — the human decided.
- Ingested content is role-tagged (`AgentRegistry.category`, lowercased) so
  role-aware recall (`WorldModelService`) surfaces it to the attached hire
  first — this is the existing general mechanism, not a new one.

## 2. Personas

- **Employee / any signed-in human** — creates a blank canvas from the
  gallery, attaches a hire (picks one or creates one inline), loads data.
- **Supervisor** — additionally sees the training machinery light up once
  the hire is attached (Training tab, corrections, graduation).
- **Agent (the hire)** — the consumer: co-editor chat runs as this hire,
  loaded data lands role-tagged to it, corrections teach it.

## 3. Journeys

### Journey A — Start from nothing (blank canvas)

*The "I just want a workspace, not a chat command" moment.*

1. Employee opens **Canvases** in the gallery and clicks **New canvas**
   (`POST /api/canvas`). The canvas opens immediately — empty, theirs.
2. The page shows the no-hire state: a banner ("This canvas has no agent
   yet") + an **Add agent** header button. The Load data bar is disabled
   with the hint *"Attach an agent to load data."*
3. **UX**: the empty canvas is never a dead end — both CTAs open the same
   attach modal.

### Journey B — Attach the hire

*The hire turns a blank file into a workspace.*

1. The attach modal lists the user's agents (name · category · tier).
2. Click one → `POST /api/canvas/{id}/agents`. Presence row, context stamp,
   audit row, WS join broadcast. The modal closes; the hire badge lights up
   in the header; the Training tab resolves the hire; the Load data bar
   enables.
3. Or **Create a new agent** inline: guided creation (`POST /api/agents/guided`)
   runs in the modal and attaches the result. A HITL `pending_approval`
   creation can't attach yet — the modal says to approve it from the Agents
   page first.
4. **UX**: attach is idempotent (a double click is one hire). Detach exists
   via `DELETE` (API + badge affordance) and the canvas can hire again.

### Journey C — Load data

*The hire's world gets filled.*

1. With a hire attached, the canvas's **Load data** bar offers **Upload
   file** and folder picks from Zoho WorkDrive / Google Drive / OneDrive.
2. Upload → `POST /api/canvas/{id}/data/upload` → parse + role-tagged
   ingest → `data_loaded` on the canvas journey timeline; notice shows the
   parse outcome honestly (`ingested` / `not ingested (reason)`).
3. Drive pick → folders are selected and the drive's ingest endpoint is
   called **with `canvas_id`**; the job runs in the background and the
   section polls to completion (`files_ingested` tally).
4. Without a hire, everything is disabled — and if the API is hit anyway
   (stale tab, script), `409 NO_AGENT_ON_CANVAS` surfaces as an inline
   notice pointing back to step Journey B.

## 4. UI spec

Canvas page top-to-bottom additions (`pages/canvas/[id].tsx`):

```
┌ Header ───────────────────────────────────────────────────────┐
│ … [Add agent / Attach agent]  [hire badge ● name · cat · tier]│
├ Load data bar (CanvasDataSection) ────────── [NEW] ───────────┤
│ LOAD DATA  [Upload file] [Zoho] [GDrive] [OneDrive]           │
│   gated: hint "Attach an agent to load data." until attached  │
├ No-hire banner [NEW] ──────────────────────────────────────── ┤
│ ⦿ This canvas has no agent yet — [Add an agent]               │
├ Canvas panel ──────────────────────────────────────────────── ┤
│ …                                                             │
└───────────────────────────────────────────────────────────────┘
```

- `AgentAttachModal` (`components/canvas/AgentAttachModal.tsx`) [NEW]:
  list → attach; inline guided create; pending-approval notice.
- `TrainingPanel` no-agent block [CHANGED]: dead-end copy replaced with an
  **Add agent** CTA wired to the same modal (`onAddAgent` prop).
- Gallery (`pages/canvas/index.tsx`) [CHANGED]: **New canvas** button beside
  Upload PDF + the same CTA in the empty state.

Test ids: `new-blank-canvas-button`, `new-blank-canvas-empty-state`,
`add-agent-button`, `banner-add-agent-button`, `canvas-no-agent-banner`,
`agent-attach-modal`, `attach-agent-option-{id}`, `canvas-data-section`,
`canvas-upload-data-button`, `data-gated-hint`, `canvas-data-notice`,
`drive-tab-{zoho|gdrive|onedrive}`, `select-folder-{id}`,
`load-selected-folders`, `training-add-agent-cta`.

## 5. Build order

| Phase | Work | Files |
|---|---|---|
| P1 — create + attach (backend) | Blank create; agents list/attach/detach; presence helper; context resolution upgrade | `backend/api/canvas_routes.py`, `backend/core/agent_coordination.py`, `backend/api/agent_maturity_routes.py` |
| P2 — gated loads (backend) | Canvas upload endpoint; optional `canvas_id` on drive ingests + role plumbing; 409 gate | `backend/api/canvas_routes.py`, `backend/api/zoho_workdrive_routes.py`, `backend/integrations/{zoho_workdrive_service,google_drive_service,gdrive_journey_routes,onedrive_service,onedrive_journey_routes}.py` |
| P3 — gallery (frontend) | `lib/canvas-api.ts`; New canvas button | `frontend-nextjs/lib/canvas-api.ts`, `frontend-nextjs/pages/canvas/index.tsx` |
| P4 — canvas page (frontend) | No-hire banner; attach modal; gated Load data bar; Training CTA | `frontend-nextjs/pages/canvas/[id].tsx`, `frontend-nextjs/components/canvas/{AgentAttachModal,CanvasDataSection,TrainingPanel}.tsx` |
| P5 — proof | API journey tests; UI tests; this doc | `backend/tests/test_canvas_agent_journey.py`, `frontend-nextjs/components/canvas/__tests__/{AgentAttachModal,CanvasDataSection}.test.tsx`, `frontend-nextjs/tests/pages/__tests__/canvas-index.test.tsx` |

Access-control parity: the UI disables, the API refuses (409), both keyed on
the same `AgentCanvasPresence` truth.

## 6. Decision section — why loading data requires a hire

A canvas without a hire is a file; with one, it is a workspace. Requiring
the attachment before data loads is not friction for its own sake:

1. **Provenance by construction.** Every ingested document lands on the
   canvas's journey timeline (`data_loaded`, attributed to the hire) and is
   role-tagged for its recall. Data loaded into a hire-less canvas has no
   owner story and no recall advantage.
2. **One gate, enforced twice.** The maturity-gated surfaces (playbook
   latch, PDF lifecycle) already follow API/UI parity; a UI-only gate here
   would be the first one scripts could walk past.
3. **The attach step is cheap and reversible.** One click for an existing
   agent, one short form for a new one; detach restores the previous state.
   The gate costs seconds and buys the data an owner.

Existing canvases created before this rule (chat-created, PDF uploads) are
not migrated: they show the same attach CTA the first time someone tries to
load data into them, and one click brings them into the journey. Humans
choose the hire; the canvas keeps the story.
