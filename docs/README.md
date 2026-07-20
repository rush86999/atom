# ⚛️ Atom Documentation Hub

Welcome to the Atom developer and user documentation center. Atom is a self-hosted, multi-agent AI automation platform designed for reliable, governed execution.

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
- [Sandbox Policy Design](architecture/GOVERNANCE_STANDARDIZATION.md) — Detailed governance standards and enforcement rules
- [Package Security](security/packages.md) — Vulnerability scanning and package isolation systems (PyPI, npm)

### 3. 🧠 Memory & Routing Intelligence
Episodic memory systems, GraphRAG community expansion, and cognitive tiering.
- [Context Memory Design](architecture/CONTEXT_MEMORY.md) — Durable-fact extraction, token compression, and graduation memory consolidation
- [Learning-Based LLM Router](architecture/LEARNING_LLM_ROUTER.md) — Outcome predictors, re-ranking, and EMA protocol routing
- [Episodic Memory](intelligence/episodic-memory.md) — How agents build, retrieve, and refine personal experiences
- [GraphRAG](intelligence/graphrag.md) — Leiden community summaries and hybrid graph-episodic search routing
- [Arbor Hypothesis Tree](architecture/ARBOR_FRAMEWORK.md) — MCTS search and cumulative tree memory persistence
- [Self-Evolving Harness](architecture/HARNESS_EVOLUTION.md) — Offline trace analysis, weakness mining, and auto-mutation patches

### 4. 👥 Multi-Agent Orchestration
Workflows, event buses, and multi-agent roles (Queen, Fleet Admiral).
- [Meta-Agent System](agents/meta-agent.md) — Conductor parallel consensus, fleet recruitment, and cognitive routing
- [Queen Agent User Guide](guides/QUEEN_AGENT_USER_GUIDE.md) — Step-by-step workflow builder guidelines
- [Fleet Admiral](agents/fleet-admiral.md) — Orchestrating fleets for unstructured task resolution

### 5. 🔌 Integrations & Canvas Automation
Third-party APIs, real-time collaboration canvas, and headless Office co-editing.
- [Integrations Overview](integrations/OVERVIEW.md) — API integrations, resilience layers, and circuit breakers
- [Office Automation Guide](guides/ATOM_OFFICE_AUTOMATION_GUIDE.md) — Word, Excel (with formulas), PowerPoint co-editing, and transactional canvas snapshots/rollbacks
- [Browser Automation](integrations/browser-automation.md) — Sandboxed browser scraping and element interaction

### 6. 🛠️ Development & Testing
Contribution standards, debugging procedures, and testing frameworks.
- [Development Setup](development/setup.md) — Venv configuration, local DB seeding, and code style
- [Testing Index](testing/index.md) — Testing patterns (E2E journey tests, property-based tests, stress tests)
- [Bugs Found and Fixed](architecture/BUGS_FOUND_AND_FIXED.md) — Defect analysis log from E2E integration test runs

---

## 📑 Complete Document Index
For a comprehensive list of all documentation files in alphabetical order, see the **[Atom Alphabetical Index](INDEX.md)**.
