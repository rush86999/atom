# Mini-Apps User Guide

> **Status**: Implemented (Aug 2026) — agent-driven authoring, Firecracker microVM runtime
> **Audience**: End users, power users, developers
> **Read time**: ~15 minutes

---

## What Are Mini-Apps?

**Mini-apps** are stateful, resumable canvas applications — spreadsheets, documents, decks, dashboards, calculators — that you create **by chatting with an agent**.

Unlike static canvases, mini-apps have:
- **Server-side logic** (Python) that runs in a sandboxed microVM
- **Persistent state** — your data survives reloads, restarts, shares
- **Real Office engine** — Excel formulas actually compute (LibreOffice → `formulas` library)
- **Agent co-pilot** — an agent operates the app alongside you, reads the UI, makes changes
- **Per-instance chat** — talk to the agent about *this specific app instance*

---

## Quick Start: Create Your First Mini-App

### Via Chat (Agent-Driven — Primary Path)

```
You: "Create a mini-app for tracking project budgets with a summary sheet"
```

The agent will:
1. **Scaffold** — create a draft app with starter logic
2. **Iterate** — write logic, dry-run, test, revert if needed
3. **Publish** — snapshot the blueprint (credentials stripped)
4. **Install** — give you a fresh, private instance canvas
5. **Run** — you (or the agent) use the app; state persists

### Via UI (Secondary Path)

1. Open a canvas → **CanvasLogic Panel** (Monaco editor)
2. Write Python logic → **Save** (syntax-gated, checkpointed)
3. **Dev Run** — dry run, see proposed state changes
4. **Set Tests** — declare acceptance cases
5. **Run Tests** — agent grades each case in the microVM
6. **Publish** → **Install** → **Use**

---

## Mini-App Types & Examples

| Type | Use Case | Office Binding |
|------|----------|----------------|
| **Spreadsheet** | Budgets, models, trackers | `.xlsx` — real formula recalc |
| **Document** | Reports, contracts, specs | `.docx` — structured editing |
| **Deck** | Presentations, dashboards | `.pptx` — slide generation |
| **Custom Canvas** | Dashboards, forms, charts | None (pure canvas components) |

---

## How It Works: The Mental Model

```
┌─────────────────────────────────────────────────────────────┐
│                    YOUR INSTANCE CANVAS                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   SHEET     │  │   CHAT      │  │   AGENT PANEL       │  │
│  │  (UI)       │◄─┤  (per-app)  │──┤  (reads state, acts) │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│         ▼                ▼                     ▼             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           CanvasState (versioned, latest-wins)       │    │
│  │  Sheet data + logic outputs + agent actions + assets │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│         ┌────────────────┼────────────────┐                 │
│         ▼                ▼                ▼                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Logic      │  │  Office     │  │  Assets     │         │
│  │  (Firecracker│  │  (LibreOffice│  │  (host-     │         │
│  │   microVM)   │  │   headless) │  │   mediated) │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### Key Properties

| Property | What It Means |
|----------|---------------|
| **Copy-on-install** | Updates are new blueprint versions; you explicitly accept them |
| **Viewer-capped scopes** | You can never exceed your own tier — no privilege escalation |
| **Dual-face** | Same instance = rendered canvas for you + structured state for agent |
| **Per-instance chat** | Conversation scoped to *this* app instance, not global |
| **Resumable** | Close tab, come back tomorrow — state is exactly where you left it |

---

## The Authoring Loop (Agent-Driven)

When you ask an agent to build a mini-app, it drives this loop:

```
┌────────────────────────────────────────────────────────────────┐
│ 1. mini_app_status         # probe constraints                  │
│    → syntax OK? scopes? deps scanned? rootfs ready? FC up?     │
└────────────────────────────┬───────────────────────────────────┘
                             ▼
┌────────────────────────────────────────────────────────────────┐
│ 2. mini_app_scaffold       # create draft app                   │
│    → {app_id, canvas_id, logic_source}                        │
└────────────────────────────┬───────────────────────────────────┘
                             ▼
        ┌────────────────────────────────────────┐
        │       CODING LOOP (repeats)            │
        ├────────────────────────────────────────┤
        │ mini_app_write_logic  # syntax-gated,  │
        │                       # checkpointed    │
        │         │                              │
        │         ▼                              │
        │ mini_app_dev_run      # dry run,       │
        │                       # no commit      │
        │         │                              │
        │         ▼                              │
        │ mini_app_set_tests    # declare cases  │
        │ mini_app_run_tests  # grade in microVM │
        │                       # per-case pass/ │
        │                       # fail + diffs   │
        │         │                              │
        │    (fail?)                             │
        │    /    \                              │
        │   ▼      ▼                             │
        │ revert   continue                      │
        │ (known   (to next                      │
        │  good)   iteration)                   │
        └────────────────────────────────────────┘
                             ▼
┌────────────────────────────────────────────────────────────────┐
│ 3. mini_app_publish        # dep scan + rootfs gate            │
│    → snapshot blueprint + initial_state, strip credentials    │
└────────────────────────────┬───────────────────────────────────┘
                             ▼
┌────────────────────────────────────────────────────────────────┐
│ 4. mini_app_install        # copy-on-install                   │
│    → fresh instance canvas, CanvasState v1, share_token=None  │
└────────────────────────────┬───────────────────────────────────┘
                             ▼
┌────────────────────────────────────────────────────────────────┐
│ 5. mini_app_run /          # stateful run / read state         │
│    mini_app_get_state      # WS canvas:update live broadcast   │
└────────────────────────────────────────────────────────────────┘
```

---

## Using an Installed Mini-App

### As a User

1. **Open the instance canvas** — renders like any canvas
2. **Edit cells / write text / interact** — changes persist to `CanvasState`
3. **Chat with the agent** (side panel) — "Add a row for Q4", "Why is total wrong?"
4. **Agent reads UI + state** → acts via `mini_app_run` → result broadcasts live
5. **Upload assets** — drag/drop images, CSVs into the instance

### As an Agent (Autonomous Operation)

Once installed, an agent can operate the app **autonomously**:

```
Loop:
  1. mini_app_get_state        # read current state + version
  2. Read a11y view            # window.atom.canvas.getState()
  3. Decide action             # based on user instruction / goal
  4. mini_app_run              # execute with inputs
  5. Verify result             # read back, check expectations
  6. Repeat or respond
```

**Gated by**: `min(viewer_capabilities, app_declared_scopes) ∩ tier_floor`

---

## CanvasLogic: Writing App Logic

Every mini-app has a `CanvasLogic` controller — Python code that runs in the microVM.

### Template (Starter)

```python
# CanvasLogic for a budget tracker mini-app
# Inputs injected as globals: state, event, storage_namespace
# Output: print JSON envelope to stdout

def main():
    # state = latest CanvasAudit.details_json (dict)
    # event = {"type": "cell_edit", "cell": "B3", "value": 5000}
    # storage_namespace = instance_id (for file ops)
    
    # Your logic here
    new_state = state.copy()
    
    if event["type"] == "cell_edit":
        # Recompute totals
        new_state["total"] = sum(new_state.get("items", {}).values())
    
    # Return new state + optional output
    print(json.dumps({
        "state": new_state,
        "output": {"message": "Total updated"}
    }))

if __name__ == "__main__":
    main()
```

### Injected Globals (Available in Your Logic)

| Variable | Type | Description |
|----------|------|-------------|
| `state` | `dict` | Latest `CanvasAudit.details_json` |
| `event` | `dict` | Trigger: `{"type": "cell_edit|webhook|schedule", ...}` |
| `storage_namespace` | `str` | Instance ID — use for file read/write |
| `canvas_id` | `str` | The canvas ID |
| `app_id` | `str` | The mini-app ID |

### Output Envelope (Required Convention)

```python
# Your logic MUST print this to stdout:
print(json.dumps({
    "state": {...},      # REQUIRED: new state (merged into CanvasAudit)
    "output": {...},     # OPTIONAL: shown in UI, returned to caller
    "storage_ops": [...] # OPTIONAL: host-mediated file ops
}))
```

### Available Tools (Inside Logic)

Your logic runs in the sandbox with these tools (subject to viewer caps):

| Tool | Use Case |
|------|----------|
| `office_read_cell` / `write_cell` | Excel formula read/write + recalc |
| `office_read_paragraph` / `write_paragraph` | Word doc manipulation |
| `canvas_get_state` / `canvas_update` | Read/write canvas components |
| `storage_read` / `storage_write` | Host-mediated file ops (scoped to namespace) |
| `http_get` / `http_post` | External APIs (if egress enabled + allowlisted) |

---

## Declared Scopes (The App's Permission Ceiling)

When publishing, the author declares what the app **may** do. Viewers are capped at their own tier.

```json
// In MiniApp manifest
{
  "declared_scopes": [
    "office_read",
    "office_write", 
    "canvas_read",
    "canvas_write",
    "storage_read",
    "storage_write"
  ],
  "required_tier": "SUPERVISED",  // minimum viewer tier to run
  "dependencies": ["pandas", "numpy"]  // scanned, built into rootfs
}
```

### Scope Intersection (Enforced at Runtime)

```
effective_scopes = viewer.capabilities ∩ app.declared_scopes ∩ viewer.tier_floor
```

| Viewer Tier | App Declares | Effective |
|-------------|--------------|-----------|
| INTERN | `office_write` | `office_read` only (INTERN floor) |
| SUPERVISED | `office_write`, `canvas_write` | Both (SUPERVISED floor) |
| AUTONOMOUS | `office_write`, `shell_exec` | `office_write` only (app didn't declare shell) |

---

## Assets & Storage

### Uploading Assets (Post-Install)

```bash
# Via API
curl -X POST http://localhost:8000/api/mini-apps/{app_id}/instances/{instance_id}/assets \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@chart.png" \
  -F "path=assets/chart.png"
```

### Reading Assets in Logic

```python
# In CanvasLogic
with open(f"/workspace/{storage_namespace}/assets/chart.png", "rb") as f:
    data = f.read()
# Or use storage_read tool
```

### Storage Architecture

- **Host-mediated**: Guest microVM has NO host FS, NO network
- **Path-guarded**: `MiniAppStorage` prevents traversal
- **Pluggable**: Local FS (dev) or S3/R2 (prod) via `MiniAppStorage`
- **Assets tracked**: `MiniAppAsset` rows with checksums

---

## Sharing & Collaboration

### Share an Instance

```bash
# Generate share token (read-only or read-write)
curl -X POST http://localhost:8000/api/mini-apps/instances/{instance_id}/share \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"permission": "read_write", "expires_hours": 24}'
```

### Co-Editing (User + Agent)

- **WS channel**: `canvas:update` with `action: mini_app_state`
- **Last-write-wins** on document + `CanvasAudit` (OT is follow-up)
- **Agent is a first-class co-editor**: reads a11y tree, acts, broadcasts
- **Per-instance chat**: Conversation scoped to this instance

### Updates (Copy-on-Install)

1. Author publishes new blueprint version (`v2`, `v3`...)
2. Viewer sees "Update available" in instance
3. Viewer **explicitly accepts** — new instance created, old preserved
4. No silent mutation of running instances

---

## Firecracker Runtime (Required)

> **Mini-apps ONLY run in Firecracker microVMs** — no Docker fallback.

### Host Setup (One-Time)

```bash
# See docs/deployment/FIRECRACKER_HOST_SETUP.md for full guide
# Summary:
1. Linux host with KVM (not macOS/Windows directly)
2. Install firecracker, kernel, base rootfs template
3. scripts/build_miniapp_rootfs.sh <app_id>  # per-app rootfs with deps
4. Verify: mini_app_status shows FC available
```

### Rootfs Building (Per-App, When Deps Declared)

```bash
# Operator runs after author declares dependencies
scripts/build_miniapp_rootfs.sh <app_id>

# Does:
# 1. Read manifest.dependencies
# 2. pip-audit + Safety scan (fail-closed)
# 3. Build ext4 rootfs with deps baked in
# 4. Store at ./data/miniapp_rootfs/<app_id>.ext4
# 5. mini_app_publish will verify rootfs exists
```

---

## API Reference

### Core Endpoints (Agent Actions)

| Action | Description | Auth |
|--------|-------------|------|
| `mini_app_status` | Probe constraints (syntax, scopes, deps, FC) | Agent |
| `mini_app_scaffold` | Create draft app | Agent |
| `mini_app_write_logic` | Syntax-gated logic save (checkpointed) | Agent |
| `mini_app_dev_run` | Dry run in microVM (no commit) | Agent |
| `mini_app_set_tests` | Declare acceptance test cases | Agent |
| `mini_app_run_tests` | Grade all cases in microVM | Agent |
| `mini_app_logic_history` | List logic checkpoints | Agent |
| `mini_app_revert_logic` | Restore checkpoint | Agent |
| `mini_app_publish` | Dep scan + rootfs gate → publish | Agent |
| `mini_app_install` | Copy-on-install → fresh instance | Agent/User |
| `mini_app_run` | Stateful run (persists + broadcasts) | Agent/User |
| `mini_app_get_state` | Read instance state + version | Agent/User |
| `mini_app_list` | List owned/public apps | Agent/User |

### REST Endpoints (UI/Direct)

```
POST   /api/mini-apps/scaffold
GET    /api/mini-apps/{app_id}/logic
POST   /api/mini-apps/{app_id}/logic
POST   /api/mini-apps/{app_id}/dev-run
POST   /api/mini-apps/{app_id}/tests
POST   /api/mini-apps/{app_id}/run-tests
GET    /api/mini-apps/{app_id}/logic/history
POST   /api/mini-apps/{app_id}/logic/revert
POST   /api/mini-apps/{app_id}/publish
POST   /api/mini-apps/{app_id}/install
POST   /api/mini-apps/instances/{instance_id}/run
GET    /api/mini-apps/instances/{instance_id}/state
GET    /api/mini-apps
POST   /api/mini-apps/instances/{instance_id}/assets
POST   /api/mini-apps/instances/{instance_id}/share
```

---

## Troubleshooting

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| `mini_app_status` → FC unavailable | Firecracker not on host | Run `FIRECRACKER_HOST_SETUP.md` |
| `mini_app_publish` fails | Dep scan failed / rootfs missing | Fix deps, run `build_miniapp_rootfs.sh` |
| `mini_app_dev_run` → timeout | Logic too slow / infinite loop | Check logic, `MAX_EXEC_SECONDS=600` |
| State not persisting | `CanvasState` not upserted | Check `mini_app_run` response for `storage_ops` |
| Agent can't call tool | Viewer caps too low | Viewer needs higher tier or app declares less |
| WS not updating | `canvas:update` not broadcast | Check `update_canvas_content` call in service |
| Asset upload fails | Path traversal / storage config | Check `MiniAppStorage` backend (local/S3) |

---

## Common Patterns

### Pattern: Budget Tracker (Spreadsheet)

```python
# CanvasLogic
def main():
    items = state.get("items", {})
    if event["type"] == "cell_edit" and event["cell"].startswith("B"):
        # Column B = amounts
        row = int(event["cell"][1:])
        items[f"row_{row}"] = event["value"]
    
    total = sum(items.values())
    state["items"] = items
    state["total"] = total
    
    print(json.dumps({"state": state, "output": {"total": total}}))
```

### Pattern: Document Generator (Word)

```python
# CanvasLogic - triggered by webhook
def main():
    if event["type"] == "webhook" and event["action"] == "generate_report":
        template = storage_read("templates/report.docx")
        doc = office_read_document(template)
        # Fill placeholders from state
        for key, value in state["data"].items():
            doc = office_replace_text(doc, f"{{{key}}}", str(value))
        output_path = storage_write(doc, f"reports/{event['id']}.docx")
        state["last_report"] = output_path
        print(json.dumps({"state": state, "output": {"report": output_path}}))
```

### Pattern: Dashboard (Custom Canvas)

```python
# CanvasLogic - reads data, updates chart components
def main():
    data = storage_read_csv("data/metrics.csv")
    chart_config = {
        "type": "line",
        "data": {"labels": data["date"], "datasets": [{"label": "Revenue", "data": data["revenue"]}]}
    }
    canvas_update("revenue_chart", {"config": chart_config})
    state["last_update"] = datetime.now().isoformat()
    print(json.dumps({"state": state}))
```

---

## Security Model Summary

| Layer | What It Enforces |
|-------|------------------|
| **P1 Action Registry** | Only registered actions executable |
| **P2 Capability Bindings** | `agent.capabilities ∩ tier_floor` |
| **P3 Gatekeeper** | Rate limits, OAuth refresh, HITL approval, field masking |
| **P4 Data Taint** | Blocks restricted data egress (`VT_PROVENANCE`) |
| **P5 Blueprint Sanitizer** | Strips credentials on publish/fork |
| **P9 Sandbox (default-on)** | FS scope, tool whitelist, caps, tripwires, provenance |

**No path bypasses the chain.** Every tool call from mini-app logic flows through `execute_action` → sandbox gate.

---

## Related Documentation

- [MINI_APPS Architecture](../architecture/MINI_APPS.md) — Full design doc
- [Firecracker Host Setup](../deployment/FIRECRACKER_HOST_SETUP.md) — Host provisioning
- [Canvas System](../canvas/README.md) — Canvas primitives
- [Office Automation](../guides/ATOM_OFFICE_AUTOMATION_GUIDE.md) — Office read/write/recalc
- [Execution Sandbox](../guides/EXECUTION_SANDBOX.md) — Sandbox internals
- [Agent Maturity & Governance](../guides/AGENT_MATURITY_GOVERNANCE.md) — Viewer caps

---

*Last Updated: August 2026*