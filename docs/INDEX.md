# Atom Documentation Index

> **Last Updated**: August 2026  
> **Purpose**: Comprehensive index of all Atom documentation with quick links and descriptions

**📚 [Documentation Hub](../README.md)** — Browse by category (Getting Started, Security, Intelligence, Orchestration, Integrations, Development)

---

## 🎯 Quick Start by Role

| Role | Start Here | Time |
|------|------------|------|
| **New User** | [Quick Start](getting_started/quick-start.md) | 15 min |
| **Developer** | [Development Setup](development/setup.md) | 20 min |
| **Admin** | [Production Readiness](operations/production-readiness.md) | 30 min |
| **AI Engineer** | [LLM Providers Guide](guides/LLM_PROVIDERS.md) | 15 min |

---

## 📚 Documentation by Category

### 🚀 Getting Started & Operations

| Document | Description | Audience |
|----------|-------------|----------|
| [Quick Start](getting_started/quick-start.md) | Fastest path to running local server | All |
| [Installation](getting_started/INSTALLATION.md) | Complete setup (native, Docker, cloud) | All |
| [First Steps](getting_started/FIRST_STEPS.md) | What to do after server is running | New Users |
| [Troubleshooting](getting_started/TROUBLESHOOTING.md) | Common errors and fixes | All |
| [Run with Ollama](getting_started/run-with-ollama.md) | Free local LLM setup (no API keys) | Cost-conscious |
| [Personal Edition](operations/personal-edition.md) | Local Docker + SQLite deployment | Self-hosters |
| [Production Readiness](operations/production-readiness.md) | Pre-flight checklist for staging/prod | Admins |
| [Monitoring & Health](operations/monitoring.md) | Prometheus, health checks, alerts | Admins/DevOps |

### 🛡️ Security & Governance

| Document | Description | Audience |
|----------|-------------|----------|
| [Execution Sandbox Layer](architecture/SANDBOX_LAYER.md) | 5-phase blast-radius defense (default-on) | All |
| [Execution Sandbox Concept Guide](guides/EXECUTION_SANDBOX.md) | **NEW** - Deep dive: phases, config, tripwires | Security/Architects |
| [Trust vs Sandbox](security/TRUST_VS_SANDBOX.md) | Why maturity routing ≠ security boundary | Architects |
| [Prompt Injection Defense](security/PROMPT_INJECTION_DEFENSE_PLAN.md) | Defense plan (implemented) | Security |
| [Data Protection](security/DATA_PROTECTION.md) | Fernet encryption, secrets, migration | Admins |
| [Package Security](security/packages.md) | Python/npm scanning, sandbox controls | Devs |
| [Webhook Verification](security/WEBHOOK_VERIFICATION.md) | Slack/Teams/Gmail signature verification | Devs |
| [LLM Gateway Subscription Reuse](security/LLM_GATEWAY_SUBSCRIPTION_REUSE.md) | ChatGPT Plus / Claude Pro OAuth | Admins |

### 🧠 Intelligence & Memory

| Document | Description | Audience |
|----------|-------------|----------|
| [Context Memory](architecture/CONTEXT_MEMORY.md) | Per-turn fact extraction, 2-tier recall | AI Engineers |
| [Memory Systems Concept Guide](guides/MEMORY_SYSTEMS.md) | **NEW** - Three tiers, episodic, self-evolution | AI Engineers |
| [Learning LLM Router](architecture/LEARNING_LLM_ROUTER.md) | Per-model predictors, feedback re-ranking | AI Engineers |
| [Episodic Memory](intelligence/episodic-memory.md) | Agent learning framework | AI Engineers |
| [GraphRAG](intelligence/graphrag.md) | Knowledge graph, entity extraction | AI Engineers |
| [Cognitive Tier System](architecture/COGNITIVE_TIER_SYSTEM.md) | 5-tier LLM routing | AI Engineers |
| [Arbor Framework](architecture/ARBOR_FRAMEWORK.md) | Hypothesis Tree Refinement (MCTS) | Researchers |
| [Self-Evolving Harness](architecture/HARNESS_EVOLUTION.md) | Offline trace analysis, auto-patches | Researchers |
| [Hermes Comparison](architecture/HERMES_COMPARISON.md) | Atom vs Hermes — what we built/didn't | Architects |

### 👥 Agent Systems & Orchestration

| Document | Description | Audience |
|----------|-------------|----------|
| [Agent Overview](agents/overview.md) | System overview, intent classification | All |
| [Agent Maturity & Governance](guides/AGENT_MATURITY_GOVERNANCE.md) | **NEW** - Tier system, governance flow, graduation | All |
| [Queen Agent User Guide](guides/QUEEN_AGENT_USER_GUIDE.md) | Structured workflow automation | Users/Admins |
| [Queen vs Fleet Admiral](guides/QUEEN_VS_FLEET_ADMIRAL.md) | Which orchestrator to use | Architects |
| [Fleet Admiral](agents/fleet-admiral.md) | Multi-agent fleet coordination | AI Engineers |
| [Unstructured Tasks](agents/unstructured-tasks.md) | Intent classification & dynamic routing | AI Engineers |
| [Agent Guidance System](agents/guidance-system.md) | Real-time operation tracking | Users |
| [Agent Graduation](agents/agent-graduation.md) | Promotion criteria & validation | Admins |
| [Student Training](archive/legacy/STUDENT_AGENT_TRAINING_IMPLEMENTATION.md) | Maturity system (STUDENT→AUTONOMOUS) | Architects |

### 🔌 Integrations & LLM Providers

| Document | Description | Audience |
|----------|-------------|----------|
| [LLM Providers Guide](guides/LLM_PROVIDERS.md) | **NEW** - All providers, setup, costs | All |
| [OpenCode Go Provider](guides/OPENCODE_GO_PROVIDER.md) | **NEW** - Low-cost subscription gateway | Cost-conscious |
| [Ollama Local LLM](getting_started/run-with-ollama.md) | Free local inference | Cost-conscious |
| [BYOK Integration](integrations/community-skills.md) | Multi-provider LLM setup | Devs |
| [Integrations Overview](integrations/OVERVIEW.md) | 46+ service integrations | Devs |
| [Third-Party App Integrations](integrations/THIRD_PARTY_INTEGRATIONS.md) | **NEW** Complete guide: 50+ native, OAuth, governance, webhooks, custom | Devs/Architects |
| [Browser Automation](integrations/browser-automation.md) | Playwright CDP, INTERN+ required | Devs |
| [Device Capabilities](guides/DEVICE_CAPABILITIES.md) | Camera, screen, location, exec | Devs |
| [Deep Linking](archive/legacy/DEEPLINK_IMPLEMENTATION.md) | `atom://` URLs for external apps | Devs |
| [Marketplace](marketplace/connection.md) | Commercial marketplace (atomagentos.com) | Enterprise |

### 🎨 Canvas & Office Automation

| Document | Description | Audience |
|----------|-------------|----------|
| [Canvas System](canvas/README.md) | Presentations, charts, forms, **full CRUD + integration** | Users/Devs |
| [Canvas Reference](canvas/reference.md) | Complete API reference, governance, WebSocket | Devs |
| [Office Automation](guides/ATOM_OFFICE_AUTOMATION_GUIDE.md) | Word/Excel/PowerPoint co-editing | Users |
| [Workbook Runtime](architecture/WORKBOOK_RUNTIME.md) | Excel formula evaluation engine | Devs |
| [Mini-Apps Architecture](architecture/MINI_APPS.md) | Stateful canvas apps (agent-authored) | AI Engineers |
| [Mini-Apps User Guide](guides/MINI_APPS_GUIDE.md) | Create, run, collaborate on mini-apps | Users/Devs |
| [Canvas AI Accessibility](canvas/ai-accessibility.md) | Dual representation for agents | AI Engineers |
| [Canvas State API](canvas/CANVAS_STATE_API.md) | JavaScript real-time state API | Frontend Devs |
| [LLM Canvas Summaries](canvas/llm-summaries.md) | Semantic summaries for memory | AI Engineers |

### 🔐 Authentication & Federation

| Document | Description | Audience |
|----------|-------------|----------|
| [Authentication](api/AUTHENTICATION.md) | OAuth 2.0, sessions, validation | Devs |
| [Federation](guides/FEDERATION_INSTANCE_IDENTITY.md) | DID/VC zero-trust multi-instance | Architects |
| [OAuth Quick Setup](guides/OAUTH_QUICK_SETUP_GUIDE.md) | Provider OAuth in 5 minutes | Devs |
| [OAuth Setup Checklist](guides/OAUTH_SETUP_CHECKLIST.md) | Complete OAuth configuration | Admins |

### 📱 Mobile & Frontend

| Document | Description | Audience |
|----------|-------------|----------|
| [Mobile Quick Start](archive/mobile/MOBILE_QUICK_START.md) | React Native setup | Mobile Devs |
| [Mobile Architecture](archive/mobile/REACT_NATIVE_ARCHITECTURE.md) | Architecture overview | Mobile Devs |
| [Mobile Secure Storage](mobile/src/storage/secureTokenStorage.ts) | Keychain/EncryptedSharedPreferences | Mobile Devs |
| [Frontend XSS Protection](frontend-nextjs/lib/sanitize.ts) | DOMPurify sanitization | Frontend Devs |

### 🛠️ Development & Testing

| Document | Description | Audience |
|----------|-------------|----------|
| [Development Setup](development/setup.md) | Venv, DB seeding, code style | Devs |
| [Code Quality](backend/docs/CODE_QUALITY_STANDARDS.md) | Type hints, mypy, Google docstrings | Devs |
| [E2E Testing Guide](testing/e2e-guide.md) | 486 tests, API-first auth, POM | QA/Devs |
| [Testing Index](testing/index.md) | Unit, integration, E2E, bug discovery | Devs |
| [Bug Discovery](testing/BUG_DISCOVERY_INFRASTRUCTURE.md) | Fuzzing, property-based, chaos | QA |
| [Stress Testing](.planning/phases/236-cross-platform-and-stress-testing/) | k6, network sim, failure injection | QA |
| [API Standards](api/API_STANDARDS.md) | Response formats, error codes | Devs |
| [Database Migrations](archive/legacy/DATABASE_MIGRATION_GUIDE.md) | Alembic + SQLite hybrid patterns | Devs |

### 📊 Reference

| Document | Description |
|----------|-------------|
| [Environment Variables](reference/ENVIRONMENT_VARIABLES.md) | **Complete** — every var, default, required |
| [Routing Headers](reference/ROUTING_HEADERS.md) | `x-atom-*` header overrides |
| [Routing Strategies](reference/ROUTING_STRATEGIES.md) | BPC, fusion, cascade, LKGP |
| [API Overview](api/OVERVIEW.md) | All endpoints |
| [API Contract Testing](api/API_CONTRACT_TESTING.md) | Schema validation |
| [Technical Overview](reference/TECHNICAL_OVERVIEW.md) | High-level system design |
| [Code Structure](reference/CODE_STRUCTURE_OVERVIEW.md) | Code organization |
| [Database Architecture](reference/DATABASE_ARCHITECTURE.md) | Schema, relationships |
| [Feature Matrix](reference/FEATURE_MATRIX.md) | Feature availability by tier |

---

## 🔍 Discover by Topic

### LLM Configuration
- [LLM Providers Guide](guides/LLM_PROVIDERS.md) — **Start here** for all provider setup
- [OpenCode Go](guides/OPENCODE_GO_PROVIDER.md) — Low-cost subscription
- [Ollama](getting_started/run-with-ollama.md) — Free local
- [OpenRouter](integrations/community-skills.md) — Unified gateway
- [Routing Headers](reference/ROUTING_HEADERS.md) — Per-request control

### Security Hardening
- [Sandbox Layer](architecture/SANDBOX_LAYER.md) — Default-on blast radius
- [Execution Sandbox Concept Guide](guides/EXECUTION_SANDBOX.md) — **NEW** Deep dive: phases, config, tripwires
- [Trust vs Sandbox](security/TRUST_VS_SANDBOX.md) — Conceptual foundation
- [Data Protection](security/DATA_PROTECTION.md) — Encryption at rest
- [Package Security](security/packages.md) — Supply chain

### Agent Maturity & Governance
- [Agent Overview](agents/overview.md) — System + intent types
- [Agent Maturity & Governance](guides/AGENT_MATURITY_GOVERNANCE.md) — **NEW** Tier system, governance flow, graduation
- [Agent Graduation](agents/agent-graduation.md) — Promotion criteria
- [Governance Quick Ref](governance/GOVERNANCE_QUICK_REFERENCE.md) — Permissions matrix

### Memory & Context
- [Context Memory](architecture/CONTEXT_MEMORY.md) — Per-turn facts + 2-tier recall
- [Memory Systems Concept Guide](guides/MEMORY_SYSTEMS.md) — **NEW** Three tiers, episodic, self-evolution
- [Episodic Memory](intelligence/episodic-memory.md) — Experience-driven learning
- [GraphRAG](intelligence/graphrag.md) — Knowledge graph + entities
- [Hermes Comparison](architecture/HERMES_COMPARISON.md) — Design decisions

### Canvas & Office
- [Office Automation](guides/ATOM_OFFICE_AUTOMATION_GUIDE.md) — User guide
- [Workbook Runtime](architecture/WORKBOOK_RUNTIME.md) — Engine internals
- [Mini-Apps](architecture/MINI_APPS.md) — Agent-authored apps
- [Canvas State API](canvas/CANVAS_STATE_API.md) — Frontend integration

### Third-Party Integrations
- [Third-Party App Integrations](integrations/THIRD_PARTY_INTEGRATIONS.md) — **NEW** 50+ native services, OAuth, governance, webhooks, custom
- [Integrations Overview](integrations/OVERVIEW.md) — Service catalog
- [OAuth Quick Setup](guides/OAUTH_QUICK_SETUP_GUIDE.md) — 5-minute OAuth
- [OAuth Setup Checklist](guides/OAUTH_SETUP_CHECKLIST.md) — Complete config

---

## 🗂️ Archive (Legacy / Historical)

> These documents are retained for historical reference. Prefer the active docs above.

| Document | Note |
|----------|------|
| [Implementation History](archive/legacy/IMPLEMENTATION_HISTORY.md) | Consolidated timeline |
| [BYOK V6 Migration](architecture/BYOK_V6_MIGRATION_GUIDE.md) | Historical migration |
| [Canvas Implementation](archive/implementation/CANVAS_IMPLEMENTATION_COMPLETE.md) | Historical |
| [Old Guides](archive/old-guides/) | Superseded by current guides |

---

## 🔗 External References

- [FastAPI](https://fastapi.tiangolo.com/) — Web framework
- [React](https://react.dev/) — Frontend library
- [Next.js](https://nextjs.org/docs) — Frontend framework
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/) — ORM
- [LanceDB](https://lancedb.github.io/lancedb/) — Vector store
- [Playwright](https://playwright.dev/) — Browser automation
- [OpenCode](https://opencode.ai) — Low-cost LLM gateway

---

## 🆘 Need Help?

1. **Setup issues** → [Troubleshooting](getting_started/TROUBLESHOOTING.md)
2. **Auth problems** → [Authentication](api/AUTHENTICATION.md)
3. **LLM not working** → [LLM Providers Guide](guides/LLM_PROVIDERS.md)
4. **Agent not executing** → [Agent Overview](agents/overview.md) + [Governance](governance/GOVERNANCE_QUICK_REFERENCE.md)
5. **Performance** → [Monitoring](operations/monitoring.md) + [Performance](operations/performance.md)

**Found an issue?** Report on GitHub or contribute via PR.  
**Keep docs current** — update when you change behavior.

---

*Last Updated: August 2026*