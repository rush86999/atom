# Architecture Documentation

System architecture, design patterns, and technical specifications.

## 📚 Quick Navigation

### Core Architecture
- **[Backend Architecture](BACKEND_ARCHITECTURE.md)** - Backend system design
- **[Database Schema](DATABASE_SCHEMA.md)** - Database structure and relationships
- **[Database Standardization](DATABASE_STANDARDIZATION.md)** - Database standards

### BYOK LLM Integration
- **[BYOK Implementation Summary](../archive/implementation/BYOK_IMPLEMENTATION_SUMMARY.md)** - BYOK overview
- **[BYOK LLM Integration Complete](../archive/implementation/BYOK_LLM_INTEGRATION_COMPLETE.md)** - Complete LLM integration
- **[BYOK V6 Migration Guide](BYOK_V6_MIGRATION_GUIDE.md)** - Migration to v6.0

### Cognitive Systems
- **[Cognitive Tier System](COGNITIVE_TIER_SYSTEM.md)** - 5-tier LLM routing (rule-based)
- **[Learning LLM Router](LEARNING_LLM_ROUTER.md)** - Per-model satisfaction predictors that re-rank BPC candidates from observed outcomes; DB-persisted feedback, live `/api/chat/feedback`, quality signals, flag-gated ✨

### Document Runtime
- **[Workbook Runtime](WORKBOOK_RUNTIME.md)** ✨ - Excel engine: LibreOffice headless (recalc + pixel-accurate render + structural edits) → `formulas` library → openpyxl cached values; replaces openpyxl-as-parser so agents see computed results
- **[Mini-Apps](MINI_APPS.md)** ✨ NEW (design) - Long-running stateful document apps (spreadsheets/docs/decks) on canvases. MVC: Canvas=View, CanvasLogic=Controller, MiniApp manifest=Model; wraps the real office engine. Platform is the harness (P1→P3→P4→P9); viewer rights always cap declared scopes.

### Memory & Context
- **[Context Memory (Per-Turn Fact Extraction)](CONTEXT_MEMORY.md)** - Hermes-style durable-fact extraction layer; `sync_turn` + `on_pre_compress` hooks; two-tier recall (SQL + LanceDB); extraction-first over compression-first ✨
- **[AgentRadio (Lateral Coordination)](AGENT_RADIO.md)** ✨ NEW - Passive-awareness peer-to-peer messaging between agents (3 `radio.*` actions: create_thread / send_message / wait_for_mention). Mention-first, cost-governed, breakpoint-gated; a fixed team is never the default. Complements (does not replace) Conductor/Fleet/Queen orchestration.
- **[Atom vs. Hermes Comparison](HERMES_COMPARISON.md)** - Evidence-based capability matrix, decision log, and what Atom deliberately didn't build (and why)
- **[Pre-Action Match-Confidence Layer](MATCH_CONFIDENCE.md)** - Pre-action selector-certainty scorer mirroring the post-action `VerifiedOutcome` tri-state; gates ambiguous/partial matches through ProposalService for ALL tiers (including AUTONOMOUS) ✨
- **[Selector Confidence Thresholds](SELECTOR_CONFIDENCE_THRESHOLDS.md)** - One-pager on tuning env vars, score curve, per-agent opt-out

### Search & Retrieval
- **[Agent Hybrid Search (BM25 + Vector RRF)](AGENT_HYBRID_SEARCH.md)** ✨ NEW (Aug 2026) - `documents.search` fused from two legs via Reciprocal Rank Fusion (k=60): BM25 over FTS5 (SQLite) / tsvector+GIN (Postgres) + 1536-dim LanceDB ANN. Join-key bridge (`pg_document_id`) closes the PG↔LanceDB silo; legacy ILIKE fallback ladder; multi-source legs (episodes/turn_facts/reasoning-steps) are additive.
- **[Knowledge VFS](KNOWLEDGE_VFS.md)** ✨ NEW (Aug 2026) - Agent-native virtual document tree under `knowledge/` — `documents.ls/cat/grep/head/tail/search/…` (11 actions) with line-numbered, VFS-citable content (`knowledge/documents/<id>/content.lines:L47`). Additive, flag-gated (`ATOM_KNOWLEDGE_VFS_ENABLED`), legacy ILIKE preserved as kill-switch path. Composes with hybrid search: search finds the doc, VFS cites the line.

### Verification & Confidence
- **[Postcondition Oracle & Two-Tier Confidence](ORACLE_VERIFICATION.md)** ✨ NEW (Aug 2026) - Closes the self-attestation gap: `tool_outcome_verifier` grades the tool's own return, the oracle **re-derives** success against the system of record (DB read-back) independently. Only `EXTERNAL_VERIFIED` is credible; `INTERNAL_HIGH` (incl. LLM tiebreak) is not. Verify-before-retry (arXiv 2608.02645) prevents duplicate side effects. Flag: `ATOM_ORACLE_VERIFIER_ENABLED` (default on).
- **[Reviewer Re-delegation Loop](REVIEWER_LOOP.md)** ✨ NEW (Aug 2026) - REVIEW strategy: rejected candidates are re-delegated to the originating specialist with the reviewer's feedback, not swapped or debated (deliberately not multi-round debate — Debate-or-Vote martingale, Cost-of-Consensus sycophancy). Pairs with diversity-aware MoA sampling (P4a).
- **[Agent Environment (Goal-Driven Loop)](AGENT_ENVIRONMENT.md)** ✨ NEW (Aug 2026) - Phase 5 of the Stanford-biotech-insights program: objective + `definition_of_done` termination predicate (no more always-`max_steps`), maturity success ratio as explicit utility target, maturity-gated custom action surface (`register_action`), stuck-detector. Flag: `ATOM_OBJECTIVE_LOOP_ENABLED` (default on).
- **[Self-Evolving Harness](HARNESS_EVOLUTION.md)** - Offline Meta-Runtime: mines `agent_reasoning_steps` failure clusters, proposes micro-patches to the harness, runs regression tests in an isolated sandbox, deploys mutated config. Kills "loopmaxxing" in live sessions.

### Security & Sandbox Layers
- **[Production-Ready Security Hardening (P0–P9)](CLOUDFLARE_OS_SECURITY.md)** ✨ NEW (Aug 2026) - Start here. Ten-phase hardening overview: default-on sandbox for all dispatch paths, encrypted credentials, per-agent capability bindings, outbound gatekeeper, data-taint tracking, credential-safe sharing, external MCP client, per-canvas runtime, workspace context.
- **[Execution Sandbox Layer](SANDBOX_LAYER.md)** ✨ - Deterministic blast-radius
  layer (Rounds 43-47). Five phases: (A) policy + audit table, (B) filesystem
  scope, (C) tripwires + resource caps + KillRun, (D) Firecracker microVM +
  dual-proxy egress, (E) provenance tagging + LLM ActionJudge. Default-on
  enforcement since P9 (Aug 2026) for all dispatch paths via shared
  `core/sandbox_gate.py` — closes the "tier is routing, not security" gap
  documented in [../security/TRUST_VS_SANDBOX.md](../security/TRUST_VS_SANDBOX.md).
- **[Self-Consistency Voter](SELF_CONSISTENCY_VOTER.md)** - N-sample majority
  vote on structured plans (Round 42). Composes with sandbox — voter gates
  plan agreement, sandbox bounds execution scope.
- **[Match-Confidence Layer](MATCH_CONFIDENCE.md)** - (See Memory & Context
  above.) Pre-action selector certainty; Phase E provenance layer extends
  this to context-window chunks.

### Multi-Agent Coordination
- **[Fleet Orchestration (CSO→Division→Specialist Wiring)](FLEET_ORCHESTRATION.md)** ✨ NEW (Aug 2026) - The previously-dead `route_with_governance` path wired into live `AtomMetaAgent.execute()`; real `SpecialistMatcher` with ranked candidates (capability overlap + tier + verified-episode ratio), depth-enforced delegation nesting (`DelegationChain.max_depth`), fleet budget/memory hooks. Flag: `ATOM_FLEET_ROUTING_ENABLED` (default off — live-traffic change).
- **[Swarm Coordination](SWARM_COORDINATION.md)** ✨ - Three patterns from
  Cursor swarm research for coordinating many concurrent agents on a shared
  codebase:
  - **Stigmergic Field Guide** (`core/field_guide_service.py`): per-workspace
    agent-curated ops manual, auto-injected into system prompts, persisted in
    the `field_guides` table (PostgreSQL) with a filesystem fallback for local
    dev. 50-line budget, deduplicated, `SELECT FOR UPDATE` concurrency.
  - **Parallel Branch Reconciler** (`ConductorAgent._reconcile_branch_conflicts`):
    neutral third-party mediator that merges per-key output from diverging
    parallel branches instead of discarding minority work.
  - **Megafile & Bloat Tripwire** (`sandbox_tripwire.MegafileDetector`): tracks
    file edits per loop; blocks hotspot megafiles (>800 LOC or ≥5 edits/loop)
    and emits `HarnessEvolutionService`-compatible patch proposals.

### Application Design
- **[Decorator Application Complete](../archive/implementation/DECORATOR_APPLICATION_COMPLETE.md)** - Decorator patterns
- **[API Reference](API_REFERENCE.md)** - Architecture API reference

### Database Sessions
- **[Database Session Guide](DATABASE_SESSION_GUIDE.md)** - Session management

## 🏗️ System Architecture

### Layer Architecture
```
┌─────────────────────────────────────────┐
│         Presentation Layer               │
│      (Next.js + TypeScript)              │
├─────────────────────────────────────────┤
│         API Layer (FastAPI)              │
│   REST + WebSocket + Streaming           │
├─────────────────────────────────────────┤
│         Business Logic Layer             │
│  Agent Governance | LLM | Canvas | Tools │
├─────────────────────────────────────────┤
│         Data Access Layer                │
│    SQLAlchemy ORM + Repository Pattern   │
├─────────────────────────────────────────┤
│         Data Storage Layer               │
│  PostgreSQL | Redis | LanceDB | Files    │
│  (Personal Edition: SQLite + embedded    │
│   file-based LanceDB — no servers)       │
└─────────────────────────────────────────┘
```

### Key Design Patterns

#### Repository Pattern
```python
class AgentRepository:
    def get(self, agent_id: str) -> Agent:
        return db.query(Agent).filter(Agent.id == agent_id).first()
```

#### Service Layer Pattern
```python
class AgentGovernanceService:
    def can_execute_action(self, agent_id: str, action: str) -> bool:
        # Business logic here
        pass
```

#### Dependency Injection
```python
@app.get("/agents/{agent_id}")
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    return agent_service.get_agent(agent_id, db)
```

## 🎯 Architecture Principles

### 1. Single Responsibility
- Each component has one clear purpose
- Services handle business logic
- Repositories handle data access
- Controllers handle HTTP concerns

### 2. Separation of Concerns
- Frontend and backend are separate
- Business logic independent of frameworks
- Data access abstracted behind repositories

### 3. Governance First
- Every AI action is attributable
- Maturity-based access control
- Complete audit trail

### 4. Performance Matters
- Sub-millisecond cached governance checks
- Hybrid storage (hot + cold)
- Efficient database queries with proper indexing

## 📊 Database Architecture

### Core Tables
- **users**: User accounts
- **workspaces**: Tenant/workspace isolation
- **agent_registry**: Agent definitions
- **agent_executions**: Execution history
- **agent_reasoning_steps**: Persisted ReAct steps (thought/action/observation)
- **turn_facts**: Durable facts extracted per-turn (see [Context Memory](CONTEXT_MEMORY.md))
- **episodes**: Episodic memory
- **canvases**: Canvas presentations

### Relationships
```
users (1) → (N) workspaces
workspaces (1) → (N) agent_registry
agent_registry (1) → (N) agent_executions
agent_registry (1) → (N) episodes
episodes (1) → (N) episode_segments
```

## 🔧 Technology Choices

### Why FastAPI?
- **Performance**: ASGI support, async/await
- **Type Safety**: Automatic validation with Pydantic
- **Documentation**: Auto-generated OpenAPI docs
- **Modern**: Python 3.11+ features

### Why PostgreSQL?
- **Reliability**: ACID compliance
- **Features**: JSONB, CTEs, full-text search
- **Performance**: Excellent query optimization
- **Extensibility**: Custom functions, extensions

### Why Next.js?
- **Performance**: Server-side rendering
- **Developer Experience**: React + TypeScript
- **Ecosystem**: Rich component library
- **SEO**: Built-in optimization

## 📖 Related Documentation

- **[Technical Overview](../reference/TECHNICAL_OVERVIEW.md)** - Technical overview
- **[Code Structure](../reference/CODE_STRUCTURE_OVERVIEW.md)** - Code organization
- **[Database Architecture](../reference/DATABASE_ARCHITECTURE.md)** - Database design

---

*Last Updated: August 8, 2026*
