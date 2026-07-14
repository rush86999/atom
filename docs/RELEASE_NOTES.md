# Atom v1.0 Release Notes

## The Agent Platform That Runs on Your Machine

Atom is a complete AI agent platform — chat, automation, office automation, and learning-based model routing — that you can self-host with full data privacy.

## Highlights

### 🧠 Learning-Based LLM Routing
A genuine learning loop: the router observes response quality (truncation, schema failures, refusals), collects user feedback (thumbs up/down + regenerate), and re-ranks model candidates as data accumulates. Per-model satisfaction predictors train on CPU via scikit-learn — no GPU needed.

- Per-model predictors that learn model-specific outcome patterns
- DB-persisted feedback (`llm_routing_feedback` table)
- Quality assessment from `finish_reason`, content validation, schema errors
- Flag-gated (`ATOM_LEARNING_ROUTER`, default off)
- Routing dashboard at `/settings/routing`

### 📊 Workbook Runtime (Excel Engine)
Excel automation with real formula evaluation — not just a file parser. Powered by LibreOffice headless (primary), the `formulas` Python library (fallback), and openpyxl cached values (last resort).

- Writes return computed values immediately (not stale formula strings)
- Structural ops (insert rows/columns) maintain formula references via recalc
- Pixel-accurate HTML rendering with conditional formatting and charts
- Agent tools: `get_excel_formula_result`, `insert_excel_rows`, `recalculate_excel`

### 🖥️ Standalone Canvas Workspace
Canvases are no longer restricted to the chat window. A dedicated workspace at `/canvas` with:
- Full CRUD on all canvas types (sheets, email, docs, coding, charts, terminal, orchestration)
- Side chat panel for live agent co-editing
- Version history via the audit trail
- AI accessibility on every canvas type

### 🦙 Local Model Support (Ollama, LM Studio, vLLM)
Register any OpenAI-compatible local LLM backend and it participates fully in routing:
- Auto-discover available models
- Set per-model capabilities (tools, vision, reasoning, quality/speed scores)
- Local models appear as BPC candidates alongside cloud models — at zero cost
- The learning router prefers local models when they perform well

### 🔄 Integration Resilience Layer
Universal HTTP wrapper for all third-party API calls:
- Circuit breaker, rate limiting, 429 Retry-After parsing
- Exponential backoff on 5xx, 401 token refresh
- Per-integration health monitoring with success rate + latency scoring
- 89 API calls across 13 services wired through the wrapper

### 🏛️ Zero-Trust Federation (Phase 4)
DID/VC identity with HTTP API surface:
- Create/resolve DIDs, issue/revoke verifiable credentials
- Zero-trust request verification (4-stage pipeline)
- DB-persisted identity state

### 🎼 Enhanced Orchestration (Phase 5)
- Conductor Agent with 5 execution strategies (sequential/parallel/hybrid/adaptive/rollback_safe)
- EventBus lifecycle events from every live workflow
- Real step executor injection (not mock stub)

### 📈 GraphRAG Enhancements (Phase 2)
- Multi-hop scored expansion wired into production `local_search`
- Leiden community detection via `build_communities`

### 🔒 Security Hardening
- Rate limiting on auth endpoints (10 failed logins → 429)
- CSRF bypass gated to pytest only (was ungated)
- Login no longer leaks tracebacks
- Admin UUID randomized (was hardcoded)
- Session ID IDOR protection
- Message length validation (32KB cap)
- Learning router race condition fixed (asyncio.Lock)

## Getting Started

### Quick Start
```bash
git clone https://github.com/rush86999/atom.git
cd atom
./scripts/quickstart.sh
./scripts/dev.sh
```

### With Ollama (no API key needed)
```bash
ollama pull llama3:8b
# Set ATOM_LOCAL_ONLY=true in backend/.env
./scripts/dev.sh
```

### Docker
```bash
docker-compose -f docker-compose-personal.yml up -d
```

## Test Coverage

- 204 backend unit/integration tests
- 94 end-to-end journey tests (signup → login → chat → feedback → agents → boards → canvas → federation → local models → workflows → health)
- 18 integration resilience tests
- 12 workbook runtime tests
- 13 canvas CRUD tests

## License

AGPL v3 with a marketplace commercial appendix. See [LICENSE.md](LICENSE.md).
