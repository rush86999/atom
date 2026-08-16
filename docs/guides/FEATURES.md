# Atom Features

> **Last Updated**: August 2026  
> **Status**: Production-ready, self-hosted AI agent workforce

Atom is a **self-hosted AI agent workforce** — a team of governed, sandboxed agents your employees can delegate work to with confidence. Features span governance, orchestration, memory, integrations, canvas automation, and security.

---

## Core Platform Features

### 🛡️ Governance & Security (Production-Hardened)

| Feature | Description | Status |
|---------|-------------|--------|
| **Execution Sandbox Layer** | 5-phase deterministic blast-radius defense (FS scope, tool whitelist, caps, Firecracker microVM, provenance, LLM ActionJudge). Default-on for ALL dispatch paths since P9 (Aug 2026). | ✅ Implemented |
| **Agent Maturity Tiers** | 4-tier routing (STUDENT→INTERN→SUPERVISED→AUTONOMOUS) based on confidence scores. Graduation at 10/25/50 clean episodes. | ✅ Implemented |
| **Capability Bindings** | Per-agent zero-trust tool scoping (`agent.capabilities ∩ tier_floor ∩ sandbox_policy`). Enforced at shared MCP gate. | ✅ Implemented |
| **Outbound Gatekeeper** | Per-service policy gate: OAuth refresh, rate limiting, response masking, HITL mutation approval, audit. | ✅ Implemented |
| **Data Taint Tracking** | Sensitivity labels (public→restricted + PII auto-classification). Blocks restricted data egress (`VT_PROVENANCE`). | ✅ Implemented |
| **Blueprint Security** | Credential stripping on canvas fork/share (`strip_credentials` denylist). Fresh IDs, audit rows. | ✅ Implemented |
| **Real MCP Client** | JSON-RPC 2.0 over HTTP+SSE/stdio. Connect to arbitrary external MCP servers (Cloudflare portals). | ✅ Implemented |
| **Credential Encryption** | `IntegrationToken` access/refresh encrypted at rest (Fernet). `BYOK_ENCRYPTION_KEY` persisted (0600). Fail-closed in prod. | ✅ Implemented |
| **Org Ingestion Sharing** | Signed Ed25519 profiles/bundles + optional hub for sharing ingestion config, org data, and GraphRAG memory between org members' local instances. Credentials stripped (fail-closed), P4 sensitivity gate, embeddings never shared (re-embedded locally), full audit trail. Flag `ATOM_ORG_SHARING_ENABLED` (default off). | ✅ Implemented |

### 🧠 Intelligence & Memory

| Feature | Description | Status |
|---------|-------------|--------|
| **Per-Turn Fact Extraction** | Hermes-style 5-category durable facts. `sync_turn` + `on_pre_compress` hooks. Tier-1 SQL (sub-ms) + Tier-2 LanceDB semantic recall. | ✅ Implemented |
| **Episodic Memory** | Hybrid PG+LanceDB. 4 retrieval modes (temporal, semantic, outcome-filtered, graduation-gated). Graduation gates at 10/25/50 episodes. | ✅ Implemented |
| **GraphRAG & Entity Types** | 6 canonical types, PG recursive CTEs, multi-hop scored expansion, Leiden community detection. | ✅ Implemented |
| **Learning LLM Router** | Per-model satisfaction predictors re-rank BPC from observed outcomes (truncation/schema/refusal) + user feedback. DB-persisted, live `/api/chat/feedback`. Flag-gated (`ATOM_LEARNING_ROUTER`). | ✅ Implemented |
| **Cognitive Tier Routing** | 5-tier LLM routing (budget→premium) with ~90% cost reduction via caching. Cache-aware router + escalation manager. | ✅ Implemented |
| **Self-Consistency Voter** | N-sample majority vote (Wang et al. 2022) on structured plans. `VoteResult` tri-state mirrors match-confidence. Shadow mode + audit. | ✅ Implemented |
| **Match-Confidence Layer** | Pre-action selector certainty (high/partial/ambiguous) before click/fill. Deterministic scorer + budget-tier LLM tiebreaker. Gates through ProposalService for ALL tiers. | ✅ Implemented |
| **World Model & Business Facts** | Verified knowledge with citations, JIT verification, GraphRAG integration. | ✅ Implemented |
| **Self-Evolution (Reflection Pool)** | Agents critique failures → generate Memento-Skills → AlphaEvolver optimizes → human approval → install. | ✅ Implemented |

### 👥 Multi-Agent Orchestration

| Feature | Description | Status |
|---------|-------------|--------|
| **Queen Agent** | `WORKFLOW` intents → structured blueprints. Scheduling, monitoring, versioned workflows. | ✅ Implemented |
| **Fleet Admiral** | `TASK` intents → dynamic specialist recruitment. `spawn_agent()` for custom domains. Long-horizon unstructured tasks. | ✅ Implemented |
| **Conductor Agent** | 5 execution strategies (SEQUENTIAL, PARALLEL, HYBRID, ADAPTIVE, ROLLBACK_SAFE) at `POST /api/v1/workflows/conductor/execute`. | ✅ Implemented |
| **Workflow State Machine** | Validated transitions + automatic rollback. EventBus lifecycle events. | ✅ Implemented |
| **Intent Classification** | CHAT / WORKFLOW / TASK routing via `intent_classifier.py`. Automatic dispatch. | ✅ Implemented |
| **Swarm Coordination** | Stigmergic Field Guide (per-workspace ops manual), Parallel Branch Reconciler, Megafile Tripwire. | ✅ Implemented |

### 🎨 Canvas & Office Automation

| Feature | Description | Status |
|---------|-------------|--------|
| **Canvas Presentations** | Charts, markdown, forms with governance. Real-time collaboration. | ✅ Implemented |
| **Office Automation** | Read/write/render docx/xlsx/pptx. Bi-directional canvas/file co-editing + sync. | ✅ Implemented |
| **Workbook Runtime** | Excel formula evaluation: LibreOffice headless → `formulas` library → openpyxl fallback. Agents see computed values, not formula strings. | ✅ Implemented |
| **Canvas AI Accessibility** | Hidden a11y trees, `window.atom.canvas.getState()`, <10ms overhead. Dual representation for agents. | ✅ Implemented |
| **LLM Canvas Summaries** | 50-100 word semantic summaries for episodic memory. | ✅ Implemented |
| **Mini-Apps** | **Stateful, resumable canvas apps** (spreadsheets/docs/decks) authored by chatting with an agent. 13 `mini_app_*` actions: scaffold → write_logic → dev_run → run_tests → revert → publish → install → run. Firecracker microVM runtime (only). Dual-face: user sees canvas, agent sees structured state. Per-instance user↔agent chat. Viewer-capped scopes. | ✅ Implemented |
| **Per-Canvas Python Runtime** | `CanvasLogic` (P7) — server-side Python per canvas, isolated sandbox, per-canvas storage namespace. AUTONOMOUS-gated. | ✅ Implemented |

### 🔌 Integrations & LLM Providers

| Feature | Description | Status |
|---------|-------------|--------|
| **Multi-Provider BYOK** | OpenAI, Anthropic, DeepSeek, Gemini, GLM, MiniMax, OpenRouter, Ollama (local), **OpenCode Go** (subscription gateway). | ✅ Implemented |
| **OpenCode Go Provider** | Low-cost subscription via `https://opencode.ai/zen/v1`. Custom RPM/TPM/context limits feed BPC routing (headroom penalty + context clamp + hard-skip). | ✅ Implemented |
| **LLM Gateway** | Inbound OpenAI/Anthropic-compatible `/v1/chat/completions` + `/v1/messages` over BYOK routing. `atom_sk_*` keys (SHA-256). SSE adapters. Header overrides (`x-atom-model/tier/intent`). Subscription-credential reuse (ChatGPT Plus/Claude Pro). | ✅ Implemented |
| **46+ Service Integrations** | Slack, Discord, Gmail, Outlook, Teams, Notion, Asana, Jira, Linear, Salesforce, HubSpot, Stripe, GitHub, GitLab, Figma, Dropbox, Box, Zoom, Calendly, Shopify, Mailchimp, Twilio, SendGrid, Deepgram, ElevenLabs, Plaid, QuickBooks, Xero, Airtable, Monday, Trello, ClickUp, Zapier, Zoho, DocuSign, Greenhouse, BambooHR, LinkedIn, TikTok, Instagram, Twitter, Facebook. | ✅ Implemented |
| **Browser Automation** | Playwright CDP. INTERN+ required. Sandboxed. | ✅ Implemented |
| **Device Capabilities** | Camera (INTERN+), screen recording (SUPERVISED+), location/notifications (INTERN+), command exec (AUTONOMOUS only). | ✅ Implemented |
| **Atom CLI Skills** | 6 built-in skills, subprocess wrapper with 30s timeout. | ✅ Implemented |
| **Deep Linking** | `atom://agent/{id}`, `atom://workflow/{id}`, etc. | ✅ Implemented |

### 🌐 Federation & Identity

| Feature | Description | Status |
|---------|-------------|--------|
| **Zero-Trust Federation** | DIDs/VCs at `/api/federation/{dids,credentials,verify,security/health}`. DID manager, verifiable credentials, zero-trust security. In-memory state (DB persistence pending). | ✅ Implemented |
| **Workspace-Scoped Context** | Curated knowledge in `Workspace.metadata_json["curated_context"]` + skill assignment via `workspace_skills`. Injected into agent system prompt. | ✅ Implemented |

### 📱 Mobile & Frontend

| Feature | Description | Status |
|---------|-------------|--------|
| **React Native Mobile** | iOS/Android with secure storage (Keychain/EncryptedSharedPreferences), transparent AsyncStorage migration. | ✅ Implemented |
| **Frontend XSS Protection** | DOMPurify `sanitizeHtml()`/`renderMarkdownSafe()` on all `dangerouslySetInnerHTML`. | ✅ Implemented |
| **Real-Time Canvas State** | WebSocket `canvas:update` broadcast, versioned `CanvasState`, latest-wins. | ✅ Implemented |

### 🛠️ Developer & Operations

| Feature | Description | Status |
|---------|-------------|--------|
| **Personal Edition** | Local Docker + SQLite, daemon mode (`atom-os daemon`), FastEmbed embeddings. `docker-compose-personal.yml`. | ✅ Implemented |
| **E2E Testing** | 486 test functions, API-first auth, worker isolation, Page Object Model. `backend/tests/e2e_ui/`. | ✅ Implemented |
| **Bug Discovery** | Atheris fuzzing, mutmut mutation testing, Hypothesis property-based (66+ invariants), Locust chaos engineering. | ✅ Implemented |
| **Stress Testing** | k6 load testing (10/50/100 users), network sim, failure injection, memory leak detection, Lighthouse CI, Percy visual regression, jest-axe accessibility. | ✅ Implemented |
| **Monitoring** | `/health/{live,ready,metrics}` (Prometheus), structlog. Health liveness <10ms, readiness <100ms. | ✅ Implemented |
| **CI/CD** | `.github/workflows/deploy.yml`: test → build → staging → prod (manual) → verify, auto-rollback. | ✅ Implemented |
| **Code Quality** | Python 3.11+, PEP 8, type hints (mypy in CI), Google docstrings. `backend/docs/CODE_QUALITY_STANDARDS.md`. | ✅ Implemented |
| **Safe Expression Evaluator** | AST-validated `safe_eval()` replacing raw `eval()` in workflow conditions, event bus, conductor. | ✅ Implemented |
| **CSV Injection Guard** | Prefixes `= + - @` cells with quote in financial exports (CWE-1236). | ✅ Implemented |
| **Workflow Parameter Validation** | Per-parameter type checks + custom rules (min/max length, min/max value, regex pattern). | ✅ Implemented |

---

## Agent Skills (30+ Built-In)

### Core Skills
- **Calendar Management** — scheduling, conflict detection across Google/Outlook
- **Email Integration** — search, retrieve, send across Gmail/Outlook
- **Contact Management** — CRUD across integrated platforms
- **Task Syncing** — Notion, Trello, Asana, Jira, Linear, ClickUp
- **Meeting Notes** — templates, auto-generation from transcripts
- **Reminder Setup** — deadline-based, cross-platform

### Advanced Skills
- **Workflow Automation** — multi-platform orchestration
- **Web Project Setup** — repo creation, template initialization
- **Data Collection** — web scraping, API retrieval
- **Report Generation** — business intelligence from connected data
- **Template Content** — documents, presentations, decks
- **Financial Data Access** — Plaid real-time + categorization
- **Project Tracking** — status across PM tools
- **Information Gathering** — web research, summarization
- **Sales Tracking** — deals, opportunities in CRM
- **Social Media** — mentions, scheduling
- **Cross-Platform Sync** — automation between systems
- **GitHub Integration** — repos, issues, PRs
- **Dynamic Local Skill Execution** — discover, test, run with streaming feedback

### Specialized Domains (via Fleet Admiral)
- **Small Business Mastery** — smart scheduling, autonomous collections, lifecycle intelligence (POs, SOs, shipping, quotes), stakeholder communication
- **Custom Domain Agents** — `spawn_agent()` for any domain

---

## LLM Provider Comparison

| Provider | Cost Model | Best For | Context | Tools | Vision | Reasoning |
|----------|------------|----------|---------|-------|--------|-----------|
| **Ollama** | Free (local) | Privacy, offline, dev | 8K–128K | ✅ | ❌ | ❌ |
| **OpenCode Go** | Subscription | High volume, code | 200K | ✅ | ❌ | ✅ |
| **OpenAI** | Pay-per-token | General quality | 128K–1M | ✅ | ✅ | ✅ |
| **Anthropic** | Pay-per-token | Reasoning, safety | 200K | ✅ | ✅ | ✅ |
| **DeepSeek** | Pay-per-token | Code, math, reasoning | 64K | ✅ | ❌ | ✅ |
| **Gemini** | Pay-per-token | Long context, multimodal | 2M | ✅ | ✅ | ✅ |
| **OpenRouter** | Pay-per-token | Model variety (100+) | Varies | ✅ | Varies | Varies |
| **GLM** | Pay-per-token | Chinese, reasoning | 128K | ✅ | ❌ | ✅ |
| **MiniMax** | Pay-per-token | Long context | 200K+ | ✅ | ❌ | ❌ |

---

## Deployment Options

| Option | Use Case | Stack |
|--------|----------|-------|
| **Personal Edition** | Local dev, single user | Docker Compose + SQLite + embedded LanceDB |
| **Production** | Multi-user, enterprise | PostgreSQL + Redis + LanceDB (S3/R2) + Firecracker host |
| **DigitalOcean 1-Click** | Quick cloud deploy | Pre-configured app spec |

---

## Quick Links

- [Quick Start](getting_started/quick-start.md) — 15 min to running server
- [LLM Providers Guide](guides/LLM_PROVIDERS.md) — All providers, setup, costs
- [Agent Maturity & Governance](guides/AGENT_MATURITY_GOVERNANCE.md) — Tier system deep dive
- [Memory Systems](guides/MEMORY_SYSTEMS.md) — Three-tier recall, episodic, self-evolution
- [Execution Sandbox](guides/EXECUTION_SANDBOX.md) — Blast-radius defense
- [Mini-Apps Guide](guides/MINI_APPS_GUIDE.md) — Agent-authored stateful apps
- [Office Automation](guides/ATOM_OFFICE_AUTOMATION_GUIDE.md) — Word/Excel/PowerPoint co-editing
- [Production Readiness](operations/production-readiness.md) — Pre-flight checklist

---

*Last Updated: August 2026 · See [CHANGELOG](../RELEASE_NOTES.md) for version history*