# Swarm Coordination Architecture

> **Status**: Implemented (2026-07-21)
> **Research basis**: Cursor *Agent Swarm & Model Economics* (2026)

---

## Overview

This document describes the three advanced multi-agent coordination patterns
implemented in Atom, derived from Cursor's large-scale swarm engineering research.
They address failure modes that emerge when many agents operate concurrently on
shared codebases.

---

## 1. Stigmergic Field Guide

**File**: `backend/core/field_guide_service.py`
**Model**: `backend/core/models.py` → `FieldGuide`
**Migration**: `backend/alembic/versions/20260721_add_field_guides.py`

### Problem

Frozen-weight LLMs cannot update their weights at runtime to capture workspace-specific
rules, quirks, or constraints discovered during execution.  Prior approaches relied on
static vector databases (episodic/semantic memory) curated by developers.

### Solution: Agent-Curated Shared Memory

Per-workspace Markdown content that agents read *and* write during execution.
It is:

- **Automatically injected** into every agent's system prompt via
  `FieldGuideService.get_field_guide_context(workspace_id)`.
- **Updated by agents** whenever they discover a runtime rule or constraint via
  `FieldGuideService.update_field_guide(workspace_id, topic, insight)`.
- **Budget-enforced**: never exceeds 50 lines.  Oldest entries are pruned when the
  budget is reached, keeping the guide fresh.
- **Topic-sectioned**: agents write to named sections (`### Tool Failures`,
  `### File Layout`, etc.) so the guide stays structured.
- **Deduplicated**: identical insights under the same topic are silently skipped.

### Storage — cloud-native PostgreSQL with a filesystem fallback

The guide is persisted differently depending on whether a DB session is passed
to the service:

- **Production (DB-backed)**: content lives in the `field_guides` table — one row
  per `workspace_id` (`FieldGuide` model in `backend/core/models.py`).  This makes
  the guide **pod-restart safe** (Postgres survives ephemeral container
  filesystems) and **horizontally scalable** (every instance reads the same row).
  Concurrent writers are serialised with `SELECT FOR UPDATE` row-level locking so
  parallel agents cannot corrupt the guide.
- **Local dev / unit tests (no DB)**: falls back to a file at
  `backend/core/data/field_guides/<workspace_id>/FIELD_GUIDE.md`, written
  atomically via a temp-rename swap.  This keeps the local experience
  zero-config.

### Key Properties

| Property | Value |
|---|---|
| Line budget | 50 lines (configurable per call) |
| Production storage | PostgreSQL `field_guides` table (one row per workspace) |
| Local-dev / test storage | `backend/core/data/field_guides/<workspace_id>/FIELD_GUIDE.md` |
| Scoping | Per-workspace — isolated operational memories |
| Concurrency (DB) | `SELECT FOR UPDATE` row-level lock |
| Concurrency (FS) | Atomic write via temp-rename swap |

### Usage

```python
from core.field_guide_service import get_field_guide_service

# Production — pass a DB session for PostgreSQL-backed storage
svc = get_field_guide_service(db=db_session)

# Local scripts / unit tests — omit db to use the filesystem fallback
# svc = get_field_guide_service()

# Agent discovers a rule → writes it
result = svc.update_field_guide(
    workspace_id="ws-prod-1",
    topic="Tool Failures",
    insight="The 'shell' tool always times out after 30 s on Python builds. Use run_command instead.",
    agent_id="worker-42",
)
# result["storage"] → "db" (or "fs" for the fallback)
# result["path"]    → row/file identifier for the workspace's guide

# System prompt builder → injects guide
context_block = svc.get_field_guide_context("ws-prod-1")
system_prompt = base_system_prompt + "\n\n" + context_block
```

---

## 2. Parallel Branch Reconciler

**File**: `backend/core/orchestration/conductor_agent.py`
**Method**: `ConductorAgent._reconcile_branch_conflicts`

### Problem

The existing `PARALLEL_CONSENSUS` strategy ran 3 branches and discarded all but the
majority winner.  When all 3 branches diverged (all different), minority work was
wasted and the strategy degenerated to an arbitrary selection.

### Solution: Neutral Third-Party Mediator

When parallel branches disagree, a neutral reconciler synthesises a unified candidate
from *all* branches rather than discarding minority work:

1. Collect all keys from every branch result dict.
2. For each key — if all branches agree → include in merged output (safe zone).
3. For each key — if branches disagree → resolve by **frequency voting** (most common
   value wins for that key).
4. If the merged candidate is non-empty → return it.
5. If reconciliation fails → fall back to majority-vote winner.

### Decision Tree

```
3 branch results
│
├── ≥2 agree (majority) ──────────────→ Use majority winner directly
│
└── All 3 diverge
    │
    ├── Reconcile (per-key freq vote) ─→ Return merged candidate   ✓
    │
    └── Reconciliation empty/fails ────→ Fall back to majority winner
```

### Example

```python
# Branch A: {"action": "read",  "target": "db.py", "status": "ok"}
# Branch B: {"action": "read",  "target": "db.py", "status": "ok"}
# Branch C: {"action": "write", "target": "db.py", "status": "ok"}

# Reconciler merges:
# "action"  → "read"  (2/3 vote)
# "target"  → "db.py" (unanimous)
# "status"  → "ok"    (unanimous)
```

---

## 3. Megafile & Bloat Tripwire

**File**: `backend/core/sandbox_tripwire.py`
**Classes**: `MegafileDetector`, `MegafileWarning`

### Problem

In multi-agent swarms, certain shared files (e.g. `models.py`, `workflow_engine.py`)
become hotspots that every agent wants to edit.  As these files grow, they:

- Overflow agent context windows.
- Create constant merge conflicts between parallel branches.
- Cause agents to hesitate to make structural changes (ossification).

### Solution: Edit-Frequency Tripwire

`MegafileDetector` tracks file edits per execution loop and emits a `MegafileWarning`
when either threshold is crossed:

| Threshold | Default | Trigger |
|---|---|---|
| LOC | > 800 lines | File size exceeds context comfort zone |
| Edit frequency | ≥ 5 edits/loop | File is a conflict hotspot |

When both are exceeded simultaneously, severity escalates from `WARNING` to `CRITICAL`.

Warnings are formatted as `HarnessEvolutionService`-compatible patch proposals via
`MegafileWarning.to_harness_patch_proposal()`, enabling the Self-Healing system to
automatically queue modularization tasks.

### Usage

```python
from core.sandbox_tripwire import MegafileDetector

detector = MegafileDetector(loc_threshold=800, edit_threshold=5)

# Called after every file edit operation
warning = detector.record_edit("/path/to/models.py", line_count=1200)
if warning:
    # Forward to Self-Healing system
    harness_svc.queue_patch(warning.to_harness_patch_proposal())

# Optional: block additional commits to flagged files
if detector.is_blocked("/path/to/models.py"):
    raise BlockedByMegafileTripwire("models.py is flagged — refactor first")

# Reset between execution loops
detector.reset()
```

---

## Integration Map

```
┌────────────────────────────────────────────────────────────┐
│                     Agent Execution                        │
│                                                            │
│  ConductorAgent                                            │
│  ├─ PARALLEL_CONSENSUS ─→ _reconcile_branch_conflicts      │
│  │                        (merge diverging branches)       │
│  │                                                         │
│  └─ Step executor ──→ MegafileDetector.record_edit()       │
│                        (detect bloat, emit warnings)       │
│                                 │                          │
│                                 ▼                          │
│                       HarnessEvolutionService              │
│                       (queue modularization patch)         │
│                                                            │
│  FieldGuideService                                         │
│  ├─ update_field_guide()  ←── Agent discoveries            │
│  └─ get_field_guide_context() ──→ System prompt injection  │
└────────────────────────────────────────────────────────────┘
```

---

## References

- Cursor Research: *Agent Swarms and the New Model Economics* (2026-07-20)
- Stigmergy: Bonabeau et al., *Swarm Intelligence* (1999)
- Self-Harness / HarnessX: Atom internal architecture
