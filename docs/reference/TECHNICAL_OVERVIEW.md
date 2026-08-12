# Atom Technical Overview

> **Last Updated**: August 2026 · **Version**: v8.0.0 (main_api_app)

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend Layer                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Next.js 16.2  │  │   React 18.3    │  │   TypeScript    │ │
│  │  (Pages Router) │  │                 │  │    5.9.2        │ │
│  │ • API Routes    │  │ • Hooks & State │  │ • Type Safety   │ │
│  │ • SSR/SSG       │  │ • Context API   │  │ • Interfaces    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Chakra UI 3.3 │  │   TailwindCSS   │  │   Framer Motion │ │
│  │ • Component Lib │  │    3.2.7        │  │ • Animations     │ │
│  │ • Theme System  │  • Utility Classes │  • Transitions    │ │
│  │ • Accessibility │  • Responsive      │  • Interactions   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────────┐
│                      Backend Layer                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   FastAPI       │  │   PostgreSQL    │  │   Redis         │ │
│  │   (Python 3.11) │  │   (optional)    │  │   (optional)    │ │
│  │ • REST API      │  • Primary DB      │  • WS pub/sub     │ │
│  │ • OAuth 2.0     │  • ORM (SQLAlchemy)│  • Caching        │ │
│  │ • WebSockets    │  • 137 migrations  │  • (graceful off) │ │
│  │ • 197 routers   │  • Alembic         │  │                 │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   LanceDB       │  │   Docker        │  │   Gunicorn      │ │
│  │   (embedded)    │  │                 │  │   (prod)        │ │
│  │ • Vector Store  │  • Containerization│  • Process Mgmt   │ │
│  │ • FastEmbed     │  • Personal Ed.   │  • Worker Pools   │ │
│  │ • Semantic Srch │  • E2E Testing    │  • Graceful Stop  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### Frontend (Next.js 16.2.2 — Pages Router)

- **Pages Router** (not App Router) — `frontend-nextjs/pages/`
- **Standalone output** for Docker deployments
- **Proxy**: rewrites `/api/*` → `http://127.0.0.1:8000`
- Config: `next.config.js`, `tsconfig.json`, `tailwind.config.js`, `jest.config.js`

### Backend (FastAPI, Python 3.11)

- **Entry point**: `backend/main_api_app.py` (v8.0.0, 197 routers)
- **Smoke entry**: `backend/minimal_app.py` (v6.0.0, ~125 routes)
- **Safe mode**: `backend/main_api_app_safe.py` (mocks numpy/pandas/lancedb if missing)
- **No `main.py`** — the canonical entry is `main_api_app:app`

### Key Backend Directories

```
backend/
├── core/                  # Agent governance, LLM routing, models, sandbox
├── api/                   # Route handlers (auth, health, agents, canvas, etc.)
├── tools/                 # Agent tools (browser, canvas, memory, device, etc.)
├── integrations/          # 44+ external service integrations
├── middleware/             # Governance, CORS, security headers
├── llm/                   # LLM providers, BYOK, cognitive tiers, gateway
├── intelligence/          # Episodic memory, GraphRAG, turn facts
├── accounting/            # Financial exports, GL, CSV injection guard
├── sales/                 # CRM, pipeline management
├── finance/               # Stripe, QuickBooks, Xero, Plaid
├── skills/                # Atom CLI skills, marketplace
├── tests/                 # 1250+ test files, E2E UI (POM pattern)
├── scripts/               # DB migration, miniapp rootfs, calibration
├── alembic/               # 137 migration files
├── cli/                   # Daemon mode, CLI entry point
└── data/                  # SQLite DB, LanceDB, runtime data
```

## Database Architecture

### SQLite (Personal Edition — default)
- `DATABASE_URL=sqlite:///./atom_dev.db`
- Schema via `Base.metadata.create_all` on first boot
- Alembic for migrations (137 versions)

### PostgreSQL (Enterprise/Production)
- `DATABASE_URL=postgresql://user:pass@host:5432/db`
- Full ACID compliance
- `psycopg2-binary` driver

### LanceDB (embedded vector store)
- `LANCEDB_PATH=./data/lancedb`
- FastEmbed (`BAAI/bge-small-en-v1.5`) — 384-dim, local
- Episodic memory, document embeddings, semantic search

## Authentication & Security

### Auth Flow
```
User → Email/Password or OAuth → JWT Session → API Access
```

### Security Layers (Rounds 18–72)
- **Execution Sandbox** (P9, default-on): filesystem scope, tool whitelist, tripwires, resource caps
- **BYOK Encryption** (P0): Fernet encryption of OAuth tokens at rest
- **Capability Resolver** (P2): per-agent zero-trust tool scoping
- **Outbound Gatekeeper** (P3): per-service policy gate
- **Data Taint Tracker** (P4): sensitivity classification, blocks restricted data outbound
- **Blueprint Sanitizer** (P5): credential stripping on canvas fork/share
- **Match Confidence** (R41): pre-action selector certainty scoring
- **Self-Consistency Voter** (R42): N-sample majority vote for hallucination mitigation
- **CSV Injection Guard** (R51): prefixes `= + - @` cells in financial exports
- **Rate Limiting**: `AuthRateLimiter` (10/min login, 3/5min register)
- **Webhook Verification**: HMAC signatures for Slack, Teams, Gmail, Shopify, etc.

## Health Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /alive` | Fly.io liveness (`{"status":"alive","debug_id":"v8.0.0"}`) |
| `GET /` | Root info (`{"name":"ATOM Platform API","version":"8.0.0"}`) |
| `GET /health` | Consolidated (DB, Redis, vector_store, memory_mb) |
| `GET /health/live` | K8s/ECS liveness probe |
| `GET /health/ready` | Readiness probe (DB + disk check) |
| `GET /health/db` | Database connectivity with pool status |
| `GET /health/metrics` | Prometheus metrics endpoint |
| `GET /health/stage-router` | Stage router phase guidance |

## Agent Governance & Maturity

### Maturity Levels (confidence-based routing)
| Level | Confidence | Capabilities |
|-------|-----------|-------------|
| STUDENT | <0.5 | Read-only (BLOCKED → training) |
| INTERN | 0.5–0.7 | Streaming, forms (PROPOSAL → approval) |
| SUPERVISED | 0.7–0.9 | State changes (under supervision) |
| AUTONOMOUS | >0.9 | All actions |

### Action Complexity
| Level | Description | Min Tier |
|-------|-------------|----------|
| 1 LOW | Presentations | STUDENT+ |
| 2 MODERATE | Streaming | INTERN+ |
| 3 HIGH | State changes | SUPERVISED+ |
| 4 CRITICAL | Deletions | AUTONOMOUS only |

## Key Features

### LLM Providers
- **OpenAI**, **Anthropic**, **DeepSeek**, **Google Gemini**, **Z.ai GLM**, **Moonshot/Kimi**
- **Ollama** (local, free, no API key)
- **OpenCode Go** (low-cost subscription gateway at opencode.ai/zen/v1)
- **OpenRouter** (unified gateway, 300+ models)
- **Cognitive Tier System**: 5-tier LLM routing, ~90% cost reduction via caching
- **Learning Router**: per-model satisfaction predictors re-rank candidates

### Agent Systems
- **Queen Agent**: WORKFLOW intents → structured blueprints
- **Fleet Admiral**: TASK intents → multi-agent recruitment
- **Agent Radio**: lateral peer messaging (mention-first delivery)
- **Goal-Driven Loop**: definition_of_done early exit + stuck-detector

### Canvas & Office
- **Canvas**: charts, markdown, forms with governance
- **Office Automation**: read/write/render docx/xlsx/pptx
- **Workbook Runtime**: formula-evaluating Excel engine
- **Mini-Apps**: stateful, resumable canvas-UI apps on Firecracker microVMs

### Intelligence
- **Episodic Memory**: hybrid PG+LanceDB, 4 retrieval modes
- **Per-Turn Fact Extraction**: Mem0's 5 durable-fact categories
- **Hybrid Search**: BM25 + LanceDB vector fused by RRF
- **Knowledge VFS**: agent-native `ls`/`cat`/`grep` over documents
- **Oracle Verification**: postcondition re-derivation against system of record

## Deployment

### Personal Edition (Docker)
```bash
cp .env.personal .env
docker compose -f docker-compose-personal.yml up -d --build
# Backend: http://localhost:8001  Frontend: http://localhost:3001
```

### Development (Makefile)
```bash
make setup       # one-shot bootstrap
make backend     # full backend on :8001
make frontend    # frontend dev server on :3001
make dev         # both together
make test        # unit tests
```

### Production
- Docker dual-app image (Node 22 + Python 3.11 + LibreOffice)
- Fly.io deployment (`fly.toml`, app `atom-saas`, region `iad`)
- GitHub Actions CI/CD (`.github/workflows/deploy.yml`)
- PostgreSQL + Redis for multi-user

## Testing

### Backend
- **pytest** with 333-line config (`backend/pytest.ini`)
- Unit, integration, property-based, chaos, stress, load, soak tests
- Coverage target: 80% (`fail_under = 80`)
- Pre-commit hooks: Black, isort, Flake8

### E2E UI (486 tests)
- `backend/tests/e2e_ui/` — API-first auth, POM pattern, worker isolation
- Playwright 1.58.0 for browser automation
- `make test-e2e`

### Frontend
- Jest 30.x + React Testing Library
- Stryker mutation testing
- Bundle size tracking (bundlesize)

## Technology Stack Summary

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend | Next.js (Pages Router) | 16.2.2 |
| Frontend | React | 18.3.1 |
| Frontend | TypeScript | 5.9.2 |
| Frontend | Chakra UI | 3.3.0 |
| Frontend | Tailwind CSS | 3.2.7 |
| Frontend | Jest | 30.0.5 |
| Backend | Python | 3.11+ |
| Backend | FastAPI | 0.104+ |
| Backend | SQLAlchemy | 2.0+ |
| Backend | Pydantic | 2.0+ |
| Database | SQLite (Personal) | — |
| Database | PostgreSQL (Enterprise) | 15 |
| Vector Store | LanceDB | 0.5.3+ |
| Embeddings | FastEmbed | 0.2+ |
| Browser | Playwright | 1.58.0 |
| CI/CD | GitHub Actions | — |
| Container | Docker | — |
| Linter | mypy | Python 3.11 |
| Formatter | Black | 23.12.0 |

---

*Last Updated: August 2026*