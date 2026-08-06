<div align="center">

# ATOM Platform
### Open-Source AI Agent Platform for Self-Hosted Automation

![Atom Platform](https://github.com/user-attachments/assets/398de2e3-4ea6-487c-93ae-9600a66598fc)

**Automate your workflows by talking to an AI — and let it remember, search, and handle tasks like a real assistant.**

[![License](https://img.shields.io/badge/License-AGPL-blue.svg)](LICENSE.md)
[![CI](https://img.shields.io/github/actions/workflow/status/rush86999/atom/ci.yml?branch=main&label=CI)](https://github.com/rush86999/atom/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-27%2C000%2B-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![Stars](https://img.shields.io/github/stars/rush86999/atom?style=social)]()

</div>

## What is Atom?

Atom is an **open-source, self-hosted AI agent platform** that combines visual workflow builders with intelligent LLM-based agents. Just **speak** or **type** your request, and Atom's specialty agents plan, verify, and execute complex workflows across your entire tech stack.

**Your data stays yours**: workflow data, agent state, and memory live on your infrastructure. LLM inference uses your own API keys (BYOK) — or local models (Ollama/Llama.cpp) for fully private deployments.

**No lock-in**: 16+ LLM providers (OpenAI, Anthropic, DeepSeek, Gemini, MiniMax, Groq…) with automatic cost-aware routing, fallback, and self-healing.

> **Comparing alternatives?** [Atom vs OpenClaw](docs/features/atom-vs-openclaw.md) · [Atom vs Hermes](docs/architecture/HERMES_COMPARISON.md)

---

## ⚡ OpenCode Go — Low-Cost Coding Models ✨ NEW

Atom now ships with **OpenCode Go** as a first-class BYOK provider — a low-cost subscription to [OpenCode Zen](https://opencode.ai/zen)'s tested-and-verified open coding models, all through **one key and one OpenAI-compatible endpoint**:

```bash
# backend/.env — one key unlocks the whole catalog
OPENCODE_API_KEY=oc_...
```

| | What you get |
|---|---|
| **One subscription, zero per-provider signups** | DeepSeek V4 Flash ($0.14/M), V4 Pro, Kimi K2.7 Code, GLM 5.2, MiniMax M3, Qwen 3.7 — the models the OpenCode team benchmarks and verifies for coding agents |
| **Custom rates & limits feed routing** | `OPENCODE_RPM` / `OPENCODE_TPM` / `OPENCODE_MAX_CONTEXT` (defaults 60 / 2M / 200K) — BPC routing applies a **headroom penalty** as the budget tightens, **clamps context** to the gateway cap, and **hard-skips** the provider at exhaustion |
| **Drop-in BYOK** | Works with Atom's tiered routing (budget/mid/premium/code), fallback chains, and the [LLM Gateway](#-use-atom-as-an-llm-gateway) — no architecture changes |
| **Self-hosted privacy** | Gateway zero-retention policy; prompts stay under your control like any BYOK provider |

[OpenCode Go provider docs →](docs/architecture/LLM_GATEWAY.md) · Env reference: `OPENCODE_API_KEY`, `OPENCODE_BASE_URL` (default `https://opencode.ai/zen/v1`), `OPENCODE_RPM`, `OPENCODE_TPM`, `OPENCODE_MAX_CONTEXT`

---

## Why Atom?

| Capability | Atom | OpenClaw | Hermes Agent |
|---|---|---|---|
| **Best For** | Business automation, governed multi-agent workflows | Personal productivity, messaging | Personal coding assistant |
| **Governance** | ✅ 4-tier maturity (Student → Autonomous) + HITL | ❌ None | ❌ None |
| **Memory** | ✅ Episodic + per-turn fact extraction + agent memory tools | ✅ Markdown files | ✅ Mem0/lanceDB providers |
| **Office Automation** | ✅ Real-time Excel/Word/PPTX co-editing on Canvas | ❌ | ❌ |
| **Mini-Apps** | ✅ Agent-authored stateful canvas apps (Firecracker microVMs) | ❌ | ❌ |
| **Cost routing** | ✅ 5-tier cognitive classification + 16+ providers + learning router | ◐ | ◐ Aux-model only |
| **Sandboxing** | ✅ Default-on execution sandbox (all dispatch paths) | ❌ | ❌ |
| **Integrations** | 46+ business (CRM, support, dev tools) | 50+ personal | — |
| **Stack** | Python + FastAPI + PostgreSQL/SQLite + embedded LanceDB | Node.js + local filesystem | Python self-hosted |

[Full comparisons →](docs/features/atom-vs-openclaw.md) · [Hermes deep-dive →](docs/architecture/HERMES_COMPARISON.md)

---

## Key Capabilities

| | |
|---|---|
| 🎙️ **Voice-first** | Build complex workflows with your voice — no proprietary syntax |
| 🤖 **Specialty agents & orchestration** | Sales/marketing/engineering agents, Queen + FleetAdmiral hive orchestration, Conductor (5 execution strategies), validated workflow state machine with rollback, event bus |
| 🛡️ **Governance** | 4-tier maturity (Student → Intern → Supervised → Autonomous), 3-layer policy engine, complete audit trail, AI-powered training |
| 🧠 **Self-evolution** | Experience-based learning, quality-weighted graduation (SUPERVISED → AUTONOMOUS), recursive self-evolution (Memento, AlphaEvolver, HarnessEvolution) with safety pipeline |
| 💾 **Memory & context** | Per-turn durable-fact extraction, two-tier recall (SQL + LanceDB semantic + FTS5), `memory_remember`/`memory_forget`, boundary-protection compression |
| 💼 **Office automation** | Co-edit Excel/Word/PPTX live on Canvas; formula-evaluating Excel runtime; agent↔document sync |
| 🧩 **Mini-Apps** | Agent-authored stateful canvas apps (spreadsheets/docs/decks) — Firecracker microVM isolation, per-instance chat co-editing |
| 🛰️ **LLM Gateway** | OpenAI/Anthropic-compatible API over your BYOK routing — point Claude Code or any OpenAI-SDK app at Atom |
| 🔍 **GraphRAG** | Multi-hop expansion, Leiden community detection, D3 visual explorer |
| 📊 **Data analysis** | Agent-callable code interpreter: datasets, forecasting, sklearn models (sandboxed, governance-gated) |
| 🌐 **Community skills** | 5,000+ skills marketplace with supply-chain security scanning |
| 🔍 **Browser & device automation** | Playwright CDP, pre-action match-confidence (selectors scored before clicking) |

**Plus**: 46+ business integrations, 9 messaging platforms, token compression (15-95% savings), session-dedup, LKGP sticky routing, fusion routing, MCP server, swarm coordination, zero-trust federation (DIDs/VCs), deep links, mobile + macOS menubar companions.

---

## 🛰️ Use Atom as an LLM Gateway

Atom exposes your BYOK routing as an **OpenAI- and Anthropic-compatible API** — point Claude Code, n8n, or any OpenAI-SDK app at Atom and get routing, fallback, self-healing, cost tracking, budget alerts, and a request log:

```bash
ANTHROPIC_BASE_URL=http://localhost:8000 ANTHROPIC_API_KEY=atom_sk_... claude
```

Wire-compatible (`/v1/chat/completions`, `/v1/messages`, SSE streaming) · cost-aware routing + per-request overrides (`x-atom-model`/`x-atom-tier`/`x-atom-intent`) · RTK token compression · subscription reuse (ChatGPT Plus / Claude Pro via OAuth) · MCP tools at `/mcp`.

[LLM Gateway docs →](docs/architecture/LLM_GATEWAY.md) · [Subscription reuse →](docs/security/LLM_GATEWAY_SUBSCRIPTION_REUSE.md)

---

## 🛡️ Production-Ready Security

| Layer | What you get | Default |
|---|---|---|
| **Default-on sandbox** | Filesystem scope, tool whitelist, tripwires, caps, KillRun — enforced on *every* dispatch path | on (`ATOM_SANDBOX_FORCE_ENFORCE=false` = kill switch) |
| **Encrypted credentials** | OAuth integration tokens encrypted at rest (Fernet); production fails closed without a key | on |
| **Per-agent capability bindings** | Zero-trust tool scoping — an agent can never exceed its tier floor | on |
| **Outbound gatekeeper** | Rate limiting, response masking, HITL mutation approval on integration calls | on |
| **Data-taint tracking** | Restricted data observed in a run blocks external outbound actions | on |
| **External MCP client** | Connect to arbitrary external MCP servers | on |

**Plus**: credential-safe canvas fork/template sharing, per-canvas sandboxed Python runtime, 27,000+ tests, AI-enhanced bug discovery.

[Security overview →](docs/architecture/CLOUDFLARE_OS_SECURITY.md) · [Sandbox layer →](docs/architecture/SANDBOX_LAYER.md) · [Data protection →](docs/security/DATA_PROTECTION.md)

---

## 🚀 Quick Start

```bash
git clone https://github.com/rush86999/atom.git && cd atom
make setup                 # one-shot dev bootstrap (venv, deps, .env, frontend)
make backend               # full backend (main_api_app) on :8001
# in a second terminal:
make frontend              # Next.js UI on :3001
```

Prefer hands-on? The verified manual path (Python 3.11 venv + `npm install --legacy-peer-deps`, set `SECRET_KEY` + one LLM key in `backend/.env`), then:

```bash
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m uvicorn main_api_app:app --reload --port 8001
cd frontend-nextjs && printf 'NEXT_PUBLIC_API_URL=http://localhost:8001\nNEXT_PUBLIC_USE_BACKEND_API=true\n' > .env.local && npm run dev -- -p 3001
```

Then set one LLM key in `backend/.env` — `OPENAI_API_KEY`, `OPENCODE_API_KEY` (low-cost), or `ATOM_LOCAL_ONLY=true` for Ollama — and open **http://localhost:3001**.

- **API docs (Swagger)**: http://localhost:8001/docs · **Health**: http://localhost:8001/alive
- **Docker (5 min)**: `docker compose -f docker-compose-personal.yml up -d --build` (single-user SQLite stack; `docker-compose.yml` for the full Postgres stack)
- **DigitalOcean 1-click**: [Deploy →](https://cloud.digitalocean.com/apps/new?repo=https://github.com/rush86999/atom/tree/main&config=deploy/digitalocean/app.yaml)
- [Full quick-start guide ⭐](docs/getting_started/quick-start.md) · [Installation variants](docs/getting_started/INSTALLATION.md) · [Troubleshooting](docs/getting_started/TROUBLESHOOTING.md) · [First steps](docs/getting_started/FIRST_STEPS.md) · [What's new](docs/RELEASE_NOTES.md)

### Repository layout

```
atom/
├── backend/            # FastAPI app — run main_api_app:app (full) or minimal_app:app (smoke)
├── frontend-nextjs/    # Next.js web UI
├── mobile/             # React Native (Expo) companion app
├── menubar/            # Tauri macOS menubar companion
├── scripts/ · infra/ · installer/ · examples/
├── docs/               # project documentation
├── Dockerfile          # dual-app image (backend + frontend)
└── Makefile            # common tasks (start here)
```

---

## Example Use Cases

| **Department** | **Scenario** |
|----------------|-------------|
| **Sales** | New lead in HubSpot → Research → Score → Notify Slack |
| **Finance** | PDF invoice in Gmail → Extract → Match QuickBooks → Flag discrepancies |
| **Support** | Zendesk ticket → Analyze sentiment → Route urgent → Draft response |
| **HR** | New employee in BambooHR → Provision → Invite → Schedule orientation |

---

## Documentation

- **[User Guide Index ⭐](docs/USER_GUIDE_INDEX.md)** · [Docs Index](docs/INDEX.md) · [Env Variables Reference](docs/reference/ENVIRONMENT_VARIABLES.md) · [Development Guide](docs/development/overview.md)

**Architecture & deep-dives**: [Agent system](docs/agents/overview.md) · [Governance](docs/agents/governance.md) · [Episodic memory](docs/intelligence/episodic-memory.md) · [GraphRAG](docs/intelligence/graphrag.md) · [Context memory](docs/architecture/CONTEXT_MEMORY.md) · [Learning router](docs/architecture/LEARNING_LLM_ROUTER.md) · [LLM Gateway](docs/architecture/LLM_GATEWAY.md) · [Mini-Apps](docs/architecture/MINI_APPS.md) · [Sandbox layer](docs/architecture/SANDBOX_LAYER.md) · [Swarm coordination](docs/architecture/SWARM_COORDINATION.md) · [Token compression](docs/architecture/TOKEN_COMPRESSION.md) · [MCP server](docs/architecture/MCP_SERVER.md) · [Data analysis](docs/architecture/DATA_ANALYSIS.md) · [Office automation](docs/guides/ATOM_OFFICE_AUTOMATION_GUIDE.md)

**Guides**: [Quick start](docs/getting_started/quick-start.md) · [User guide](docs/guides/USER_GUIDE.md) · [Meta-agent routing](docs/agents/meta-agent.md) · [Community skills](docs/integrations/community-skills.md) · [Personal edition](docs/operations/personal-edition.md) · [Cloud deployment](docs/deployment/CLOUD_DEPLOYMENT.md)

**Testing**: [E2E suite](backend/tests/e2e_ui/README.md) · [Quality assurance](docs/testing/QUALITY_ASSURANCE.md) · [Bug-fix process](docs/testing/BUG_FIX_PROCESS.md)

---

## Marketplace (Commercial Service)

Commercial marketplace for agents, domains, components, and skills at [atomagentos.com](https://atomagentos.com) (requires `ATOM_SAAS_API_TOKEN`). Core platform is AGPL v3; marketplace items are proprietary. [Terms →](LICENSE.md#marketplace-commercial-appendix)

---

## Security & Privacy

Self-hosted deployment · BYOK (OpenAI/Anthropic/Gemini/DeepSeek/MiniMax/OpenCode Go) · encrypted credential storage · audit logs · human-in-the-loop approvals · package supply-chain scanning · 5-phase execution sandbox (default-on) · data-taint tracking · 27,000+ tests.

For maximum privacy: `ATOM_LOCAL_ONLY=true` + local models (Ollama/Llama.cpp) keeps every byte on your hardware.

[Security docs →](docs/security/) · [Sandbox →](docs/architecture/SANDBOX_LAYER.md)

---

## Contributing & Support

We welcome contributions — see [CONTRIBUTING.md](CONTRIBUTING.md). Quality bar: tests pass (100%), coverage ≥70%, review required, docs updated.

- **Issues**: [GitHub Issues](https://github.com/rush86999/atom/issues) · **Blog**: [Substack](https://substack.com/@rish2atom/posts)
- **License**: AGPL v3 — [LICENSE.md](LICENSE.md)

---

<div align="center">

**Built with** [FastAPI](https://fastapi.tiangolo.com/) **|** [SQLAlchemy](https://www.sqlalchemy.org/) **|** [LangChain](https://langchain.com/) **|** [Playwright](https://playwright.dev/) **|** [Next.js](https://nextjs.org/)

**Experience the future of self-hosted AI automation.**

⭐ Star us on GitHub — it helps!

</div>
