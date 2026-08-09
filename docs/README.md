# ⚛️ Atom Documentation Hub

Welcome to the Atom developer and user documentation center. Atom is a self-hosted **AI agent workforce** — a team of governed, sandboxed agents your employees can delegate work to with confidence.

> [!NOTE]
> Are you setting up Atom for the first time? See the [🚀 Quick Start Guide](getting_started/quick-start.md) or follow the [📖 User Guide Index](USER_GUIDE_INDEX.md).

---

## 🗺️ Navigation Index

To keep configuration and reference material easily discoverable, the documentation is organized into six core pillars:

### 1. 🚀 Getting Started & Operations
Steps to boot, deploy, configure, and maintain Atom instances in production.
- [Quick Start Guide](getting_started/quick-start.md) — 15-minute quick start guide
- [Installation Guide](getting_started/INSTALLATION.md) — Complete setup options (Local, Docker, Cloud)
- [Production Readiness](operations/production-readiness.md) — Pre-flight checklist for staging and production
- [Monitoring & Health](operations/monitoring.md) — Prometheus integration, health checks, and alerts

### 2. 🛡️ Sandbox & Security Layer
Deterministic execution isolation, permission tiers, and code analysis boundaries.
- [Execution Sandbox Layer](architecture/SANDBOX_LAYER.md) — FS scope, Firecracker microVMs, egress, and AST invariants
- [Execution Sandbox Concept Guide](guides/EXECUTION_SANDBOX.md) — **NEW** Deep dive: phases, config, tripwires, audit
- [Sandbox Policy Design](architecture/GOVERNANCE_STANDARDIZATION.md) — Detailed governance standards and enforcement rules
- [Package Security](security/packages.md) — Vulnerability scanning and package isolation systems (PyPI, npm)
- [Data Protection](security/DATA_PROTECTION.md) — Fernet encryption, secrets management, migration

### 3. 🧠 Memory & Routing Intelligence
Episodic memory systems, GraphRAG community expansion, hybrid search, and cognitive tiering.
- [Context Memory Design](architecture/CONTEXT_MEMORY.md) — Durable-fact extraction, token compression, and graduation memory consolidation
- [Learning-Based LLM Router](architecture/LEARNING_LLM_ROUTER.md) — Outcome predictors, re-ranking, and EMA protocol routing
- [Episodic Memory](intelligence/episodic-memory.md) — How agents build, retrieve, and refine personal experiences
- [GraphRAG](intelligence/graphrag.md) — Leiden community summaries and hybrid graph-episodic search routing
- [Agent Hybrid Search](architecture/AGENT_HYBRID_SEARCH.md) — **NEW** BM25 + vector RRF fusion for `documents.search` (semantic + precise, citable)
- [Knowledge VFS](architecture/KNOWLEDGE_VFS.md) — **NEW** Agent-native document tree — `ls`/`cat`/`grep` with line-numbered citations
- [Oracle Verification](architecture/ORACLE_VERIFICATION.md) — **NEW** Postcondition oracle re-derives success against the system of record
- [Arbor Hypothesis Tree](architecture/ARBOR_FRAMEWORK.md) — MCTS search and cumulative tree memory persistence
- [Self-Evolving Harness](architecture/HARNESS_EVOLUTION.md) — Offline trace analysis, weakness mining, and auto-mutation patches
- [Memory Systems Concept Guide](guides/MEMORY_SYSTEMS.md) — **NEW** Three-tier recall, episodic memory, self-evolution

### 4. 👥 Multi-Agent Orchestration
Workflows, event buses, and multi-agent roles (Queen, Fleet Admiral, lateral radio).
- [Meta-Agent System](agents/meta-agent.md) — Conductor parallel consensus, fleet recruitment, and cognitive routing
- [Queen Agent User Guide](guides/QUEEN_AGENT_USER_GUIDE.md) — Step-by-step workflow builder guidelines
- [Fleet Admiral](agents/fleet-admiral.md) — Orchestrating fleets for unstructured task resolution
- [Fleet Orchestration](architecture/FLEET_ORCHESTRATION.md) — **NEW** CSO→Division→Specialist wiring, ranked specialist matching, depth-enforced delegation
- [Agent Radio](architecture/AGENT_RADIO.md) — **NEW** Lateral peer-to-peer messaging (mention-first, budget-governed)
- [Agent Environment](architecture/AGENT_ENVIRONMENT.md) — **NEW** Goal-driven ReAct loop, `definition_of_done` termination, stuck-detection
- [Reviewer Loop](architecture/REVIEWER_LOOP.md) — **NEW** Re-delegation on review rejection + diversity-aware MoA
- [Agent Maturity & Governance](guides/AGENT_MATURITY_GOVERNANCE.md) — **NEW** Tier system, governance flow, graduation

### 5. 🔌 Integrations & Canvas Automation
Third-party APIs, real-time collaboration canvas, and headless Office co-editing.
- [Integrations Overview](integrations/OVERVIEW.md) — API integrations, resilience layers, and circuit breakers
- [Third-Party App Integrations](integrations/THIRD_PARTY_INTEGRATIONS.md) — **NEW** 50+ native services, OAuth, governance, webhooks, custom integration
- [LLM Providers Guide](guides/LLM_PROVIDERS.md) — All providers, setup, costs, routing strategies
- [OpenCode Go Provider](guides/OPENCODE_GO_PROVIDER.md) — Low-cost subscription gateway (~90% savings)
- [Office Automation Guide](guides/ATOM_OFFICE_AUTOMATION_GUIDE.md) — Word, Excel (with formulas), PowerPoint co-editing, and transactional canvas snapshots/rollbacks
- [Mini-Apps Architecture](architecture/MINI_APPS.md) — Stateful, resumable canvas apps authored by chatting with an agent (Firecracker microVM runtime)
- [Mini-Apps User Guide](guides/MINI_APPS_GUIDE.md) — Create, run, and collaborate on mini-apps
- [Firecracker Host Setup](deployment/FIRECRACKER_HOST_SETUP.md) — Provision the microVM runtime for mini-apps
- [Browser Automation](integrations/browser-automation.md) — Sandboxed browser scraping and element interaction

### 6. 🛠️ Development & Testing
Contribution standards, debugging procedures, and testing frameworks.
- [Development Setup](development/setup.md) — Venv configuration, local DB seeding, and code style
- [Testing Index](testing/index.md) — Testing patterns (E2E journey tests, property-based tests, stress tests)
- [Bugs Found and Fixed](architecture/BUGS_FOUND_AND_FIXED.md) — Defect analysis log from E2E integration test runs

---

## 📑 Complete Document Index
For a comprehensive list of all documentation files in alphabetical order, see the **[Atom Alphabetical Index](INDEX.md)**.
