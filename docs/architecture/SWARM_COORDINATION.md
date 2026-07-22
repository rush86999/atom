# Swarm Coordination Architecture

> **Status**: Implemented (2026-07-21)
> **Research basis**: Cursor *Agent Swarm & Model Economics* (2026)

---

## Overview

This document describes the four advanced multi-agent coordination patterns
implemented in Atom, derived from Cursor's large-scale swarm engineering
research and the domain-aware verification literature (MAV, AlphaCodium, VERGE).
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

**File**: `backend/core/orchestration/verification/voting.py` (`VotingVerifier`)
**Shim**: `backend/core/orchestration/conductor_agent.py` → `ConductorAgent._reconcile_branch_conflicts` (backward-compat delegate)
**Dispatched by**: `VerificationOrchestrator` (see §4) when the resolved strategy is `VOTING`

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

> The reconciler now lives in `VotingVerifier` (`verification/voting.py`). It
> originated as a **coding-coordination** technique — merging divergent
> coding-agent action dicts (e.g. `{"action":"read","target":"db.py"}`) — and is
> now composed into the CODE domain's 2-stage pipeline (§4: reconcile → execute).
> It also remains the **universal fallback** for the cascade: every untagged step
> (`UNKNOWN` domain) and every domain-specific strategy that fails to produce a
> winner falls through to it. The Conductor's `_reconcile_branch_conflicts` method
> is retained as a thin shim that delegates to `VotingVerifier.reconcile_only`,
> preserving the original contract and metadata tags (`_reconciled`,
> `_reconciler`, `_branch_count`, `step_id`).

### Decision Tree

```
3 branch results
│
├── Classify domain (§4) ──→ pick verification strategy
│
├── ≥2 agree (majority) ──────────────→ Use majority winner directly
│
└── All 3 diverge
    │
    ├── Strategy-specific verifier ──→ (see §4 cascade)
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

## 4. Domain-Aware Verification Cascade

**Package**: `backend/core/orchestration/verification/`
**Entry point**: `VerificationOrchestrator.verify(candidates, step, context)`
**Wired into**: `ConductorAgent._execute_parallel_consensus` (replaces the inline majority-vote block)
**Tests**: `backend/tests/unit/core/orchestration/verification/`

### Problem

The original reconciler (§2) applied **one** verification strategy to every step:
JSON-normalised majority vote → per-key frequency reconciliation. This is
domain-blind. "Correct" means different things in different domains — code must
*run*, math must be *provable*, extraction must be *schema-valid*, prose has no
cheap ground truth — so a single strategy either wastes effort (running tests on
a prose summary) or misses errors (majority-voting three subtly-broken programs).
The verification literature (MAV, AlphaCodium, VERGE) confirms no single verifier
fits all domains; the right architecture is a **cascade that picks the verifier
per domain**.

A second, subtler problem is that **code tasks have two distinct concerns** that
the original reconciler conflated: *coordination* (merging divergent agent action
dicts — which file to read, which action to take) and *correctness* (the code
itself runs and passes tests). The reconciler handles coordination well but has
no execution gate, so three subtly-broken programs that happen to produce
identical action dicts would pass. The `CODE_PIPELINE` strategy composes both.

### Solution: Strategy dispatcher with a universal voting fallback

For each `PARALLEL_CONSENSUS` step, the orchestrator:

1. **Resolves the domain** — explicit tag first (`step.parameters["task_domain"]`),
   else heuristic inference from the step's capability/name/description/parameters.
2. **Resolves the strategy** — explicit override
   (`step.parameters["verification_strategy"]`), else the domain→strategy map below.
3. **Runs the matching verifier**, which returns a `VerificationResult` (`winner`,
   `confidence`, `details`, `reason`).
4. **Falls back to voting** if the chosen strategy returns `winner=None` — the
   swarm is never worse off than the original single-strategy behaviour.
5. **Records a Field Guide insight** when the domain was *inferred* (not explicit),
   so the workspace accumulates feedback on which inference mappings pay off.

### Domain → strategy map

| Domain | Strategy | Rationale | Ground-truth signal |
|---|---|---|---|
| `UNKNOWN` | `VOTING` | Preserves original behaviour | None cheap |
| `CODE` | `CODE_PIPELINE` | Reconcile agent action dicts, then execute the code (tests are oracle — AlphaCodium) | Strong — runs/tests |
| `MATH` | `FORMAL` | Provability (VERGE) | Strong — proof/sympy |
| `QA` | `GROUNDED` | Faithfulness to sources | Partial — retrieved evidence |
| `EXTRACTION` | `SCHEMA` | Cheapest strong signal | Partial — schema/types |
| `PLANNING` | `VOTING` | Self-consistency semantics | Weak — goal at end |
| `PROSE` | `JUDGE` | No ground truth; LLM judge | None — subjective |

### Strategies

| Strategy | File | What it does | Degrades to VOTING when… |
|---|---|---|---|
| `VOTING` | `voting.py` | Majority (≥2/3) → per-key freq reconcile → majority fallback | (is the fallback) |
| `SCHEMA` | `schema_verifier.py` | Validates each candidate against `output_schema` / `required_fields`; first valid wins | No schema configured, or no candidate validates |
| `EXECUTION` | `execution.py` | Runs candidate code in `SandboxRuntime`; first passing the `tests` spec wins | No sandbox runtime, runtime raises, no candidate passes |
| `CODE_PIPELINE` | `code_pipeline.py` | **2-stage for CODE**: reconcile divergent action dicts (stage 1) → execute the merged code in sandbox (stage 2) | Sandbox unavailable (stage 2 skipped, reconciled winner returned); code fails tests (`winner=None` → voting) |
| `FORMAL` | `formal.py` | SymPy equivalence (`simplify(a-b)==0`); largest equivalence group wins | `sympy` not installed, no parseable majority |
| `GROUNDED` | `grounded.py` | LLM faithfulness check per candidate against retrieved sources; first grounded wins | No LLM service, no sources, timeout, circuit open |
| `JUDGE` | `judge.py` | LLM-as-judge ranks candidates (display-order shuffled); top-ranked wins | No LLM service, timeout, circuit open |

### CODE_PIPELINE — the 2-stage coding cascade

`CODE_PIPELINE` is the strategy the `CODE` domain routes to by default. It
composes the two distinct concerns of a coding step:

```
candidates (coding-agent outputs: action dicts and/or code)
   │
   ├─ Stage 1 — RECONCILE  (VotingVerifier, §2)
   │    merge divergent agent action dicts via per-key frequency vote
   │    → merged_candidate (or majority winner if all-distinct)
   │
   ├─ Stage 2 — EXECUTE  (ExecutionVerifier)
   │    extract code from merged_candidate (code/source/output keys)
   │    if code found → run in sandbox against the step's tests spec
   │       passes → return merged_candidate (verified)           ✓
   │       fails  → winner=None (correctness gate → voting fallback)
   │    if no code found → return reconciled winner (coordination-only step)
   │
   └─ result.details carries both stages' diagnostics
```

This separates **coordination** (did the agents agree on the action?) from
**correctness** (does the resulting code actually work?) — the original
reconciler handled the first but had no answer for the second. Stage 2 is
skipped gracefully when the merged candidate carries no code (a pure action
plan like `{"action":"read","target":"f.py"}`), preserving the original
reconciler behaviour for coordination-only steps.

### Cascade flow

```
3 parallel branches → candidates: List[Dict]
   │
   ├─ resolve domain: step.parameters['task_domain']  OR  infer_domain(step)
   ├─ resolve strategy: step.parameters['verification_strategy']  OR  DOMAIN_STRATEGY_MAP[domain]
   │
   ├─ run Verifier.verify(candidates, step, context) → VerificationResult
   │     VOTING       → majority + per-key freq reconcile
   │     SCHEMA       → validate against schema; first valid wins
   │     EXECUTION    → run in sandbox; first passing tests wins
   │     CODE_PIPELINE → reconcile action dicts → execute merged code
   │     FORMAL       → sympy equivalence; largest group wins
   │     GROUNDED     → LLM faithfulness check against sources
   │     JUDGE        → LLM-as-judge ranks candidates
   │
   ├─ if winner is None → universal fallback to VOTING
   └─ record (domain, strategy, outcome) to Field Guide if domain was inferred
```

### Graceful-degradation guarantees

The cascade is designed to land in the codebase and light up incrementally —
no external service is required:

- **No LLM service wired** → `GROUNDED` and `JUDGE` return `winner=None` → voting fallback. Circuit breaker + `asyncio.wait_for` timeout mirror the `ActionJudge` pattern.
- **No sandbox runtime** → `EXECUTION` and `CODE_PIPELINE`'s stage 2 return `winner=None`. `CODE_PIPELINE` treats this as infra (not a correctness failure): stage 2 is skipped and the reconciled winner is returned. `EXECUTION` alone falls through to voting.
- **`sympy` not installed** → `FORMAL` returns `winner=None` → voting fallback.
- **`jsonschema` not installed** → `SCHEMA` falls back to manual required-field + type checks.
- **Any verifier raises** → orchestrator catches, logs, and falls back to voting.

The Conductor constructs a default `VerificationOrchestrator` lazily on first
`PARALLEL_CONSENSUS` run; callers wire real services via
`ConductorAgent.set_verification_orchestrator(VerificationOrchestrator(
    llm_service=..., sandbox_runtime=..., field_guide_service=...))`.

### Usage

```python
from core.orchestration.verification import (
    VerificationOrchestrator, TaskDomain, VerificationStrategy,
)

# Default — every domain-specific strategy degrades to voting.
orch = VerificationOrchestrator()

# Wired — lights up EXECUTION (sandbox), GROUNDED + JUDGE (LLM), and
# records inferred-domain feedback to the Field Guide.
orch = VerificationOrchestrator(
    llm_service=llm_service,
    sandbox_runtime=get_runtime(),
    field_guide_service=get_field_guide_service(db=db_session),
)

# Inject into the Conductor.
conductor.set_verification_orchestrator(orch)

# Tag a step explicitly to force a strategy (bypasses inference).
step = WorkflowStep(
    step_type=StepType.AGENT,
    name="implement the login endpoint",
    parameters={"task_domain": "code"},  # → EXECUTION
)
# Or override the strategy directly.
step.parameters["verification_strategy"] = "judge"  # forces JUDGE regardless of domain
```

---

## Integration Map

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Execution                         │
│                                                             │
│  ConductorAgent                                             │
│  ├─ PARALLEL_CONSENSUS                                      │
│  │   └─ VerificationOrchestrator.verify(candidates, step)   │
│  │       ├─ resolve domain (explicit tag OR inference)      │
│  │       ├─ dispatch → VOTING / SCHEMA / EXECUTION /        │
│  │       │                 FORMAL / GROUNDED / JUDGE        │
│  │       └─ universal fallback → VOTING on winner=None      │
│  │                                                          │
│  │   (VotingVerifier holds the per-key reconcile algorithm  │
│  │    previously inline in _reconcile_branch_conflicts)     │
│  │                                                          │
│  └─ Step executor ──→ MegafileDetector.record_edit()        │
│                        (detect bloat, emit warnings)        │
│                                 │                           │
│                                 ▼                           │
│                       HarnessEvolutionService               │
│                       (queue modularization patch)          │
│                                                             │
│  FieldGuideService                                          │
│  ├─ update_field_guide()  ←── Agent discoveries             │
│  ├─ update_field_guide()  ←── VerificationOrchestrator      │
│  │                          (inferred-domain feedback, §4)  │
│  └─ get_field_guide_context() ──→ System prompt injection   │
└─────────────────────────────────────────────────────────────┘
```

---

## References

- Cursor Research: *Agent Swarms and the New Model Economics* (2026-07-20)
- Stigmergy: Bonabeau et al., *Swarm Intelligence* (1999)
- Self-Harness / HarnessX: Atom internal architecture
- **Domain-aware verification cascade (§4)**:
  - Lifshitz, McIlraith, Du — *Multi-Agent Verification: Scaling Test-Time Compute with Multiple Verifiers* (arXiv:2502.20379, 2025). Aspect verifiers combine without retraining; scaling verifiers beats scaling samples.
  - Ridnik et al. — *Code Generation with AlphaCodium* (arXiv:2401.08500, 2024). Test-based iterative flow; execution is the oracle for code.
  - VERGE — *Formal Refinement and Guidance Engine for Verifiable LLM Reasoning*. SMT solvers + consensus cascade for math/formal domains.
  - *ReVeal: Self-Evolving Code Agents via Iterative Generation-Verification* (arXiv:2506.11442, 2025). Generation-verification cycle with structured feedback.
  - "Verification Over Generation" framing (2025-2026): verification is the bottleneck in coding agents, not generation.
