# Environment Variables Reference

> Canonical reference for **every** environment variable Atom reads, its
> default, whether it's required, and which file to set it in.
>
> **Source of truth**: `backend/core/config.py` (Python settings module) +
> `backend/.env.example` + `frontend-nextjs/.env.example`.

---

## Where each variable goes

| File | Used by | When |
|------|---------|------|
| `backend/.env` | The FastAPI backend (native dev / `make backend`) | Local native development |
| `frontend-nextjs/.env.local` | The Next.js frontend (`npm run dev`) | Local native development |
| `.env` (repo root) | Docker Compose stacks | `docker compose -f docker-compose.yml` or `-f docker-compose-personal.yml` |

The backend loads `backend/.env` automatically (via `python-dotenv`). The
Docker stacks read the root `.env` (copy `.env.personal` → `.env`).

---

## Minimum to boot (Personal Edition)

```bash
# backend/.env  —  everything else has a working default
DATABASE_URL=sqlite:///./atom_dev.db
SECRET_KEY=$(openssl rand -base64 48)     # required for persistent JWTs
```

That's it. Everything below is optional — including LLM keys. The server
boots without any API key; LLM features (chat, agents, workflows) are
disabled until you configure a provider (see §6).

---

## 1. Core / Runtime

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `ENVIRONMENT` | `development` | — | `development` \| `staging` \| `production`. Production enforces `SECRET_KEY` and disables dev escapes. |
| `HOST` | `0.0.0.0` | — | FastAPI bind host. |
| `PORT` | `8000` | — | FastAPI bind port (container). Dev launch uses `--port 8001`. |
| `WORKERS` | `1` | — | Uvicorn workers (production). Use `1` with `--reload`. |
| `ATOM_EXTERNAL_DRIVE` | _(unset)_ | — | Opt-in external volume path (e.g. `/Volumes/MyDrive`) for drive-hosted layouts: `restart_backend.sh` mirrors DB snapshots to `<volume>/atom-backups/` and `scripts/drive_status.sh` treats the layout as drive-hosted. Unset (default) = local-only layout, no external drive required; a dangling memory-store symlink also marks the layout drive-hosted. |
| `DEBUG` | `false` | — | Enables debug logging / verbose errors. |
| `RELOAD` | `false` | — | Uvicorn auto-reload on file change. |
| `APP_URL` | `http://localhost:3000` | — | App's public URL (password-reset links, OAuth redirects). |
| `CORS_ORIGINS` | `http://localhost:3000,...:3001` | — | Comma-separated allowed browser origins. |
| `ALLOWED_ORIGINS` | (same as CORS_ORIGINS) | — | Read by `main_api_app.py` CORSMiddleware. |
| `BYPASS_RATE_LIMIT` | unset | — | Set to `1` to lift register/login rate limits (dev/E2E only). |

---

## 2. Security & Secrets

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `SECRET_KEY` | random per restart (dev) | **Production** | Signs JWT sessions. Generate: `openssl rand -base64 48`. |
| `JWT_SECRET_KEY` | (falls back to SECRET_KEY) | Docker | Alternate JWT secret name; required by the Docker stacks. |
| `JWT_EXPIRATION` | `86400` (24h) | — | JWT lifetime in seconds. |
| `ENCRYPTION_KEY` | unset | — | Legacy Fernet-style general secrets encryption (`core/secrets_encryption.py`). **OAuth integration tokens use `BYOK_ENCRYPTION_KEY` instead (P0)** — see [DATA_PROTECTION.md](../security/DATA_PROTECTION.md). |
| `BYOK_ENCRYPTION_KEY` | unset (or `./data/byok_encryption_key`) | Docker | **(P0)** Encrypts `IntegrationToken` access/refresh tokens at rest (Fernet). Env var wins; else the persisted key file `./data/byok_encryption_key` (0600) is the durable fallback so ciphertext survives restarts. **Fail-closed in production** (`ENVIRONMENT=production`): raises `MissingKeyError` rather than minting a throwaway key. In dev, a missing key is generated + persisted. Generate with `openssl rand -base64 32`. Override the file path with `BYOK_ENC_KEY_FILE`. |
| `ATOM_ENCRYPTION_KEY` | unset | — | Frontend-side encryption key alias. |
| `ALLOW_DEV_TEMP_USERS` | `false` | — | Allow short-lived dev temp users. Never in production. |
| `ADMIN_PASSWORD` | unset | — | Set the bootstrap admin password yourself. If unset, one is generated to `backend/logs/bootstrap_admin_password.txt`. |

---

## 3. Database

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `DATABASE_URL` | `sqlite:///atom_data.db` | — | SQLite (Personal) or `postgresql://user:pass@host:5432/db` (Enterprise). |
| `SQLITE_PATH` | `./data/atom.db` | — | SQLite file path. |

---

## 4. Vector Store & Embeddings

Always local (FastEmbed / ONNX runtime) — embeddings never leave your machine.

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `LANCEDB_PATH` / `LANCE_DB_PATH` | `./data/lancedb` | — | LanceDB (episodic memory) storage path. |
| `ENABLE_LANCEDB` | `true` | — | Enable the local vector store. |
| `LANCEDB_CLOUD_ENABLED` | `false` | — | Cloud (S3/R2) LanceDB paths. Personal = embedded-only. |
| `EMBEDDING_PROVIDER` | `fastembed` | — | `fastembed` \| `openai` \| `cohere`. |
| `FASTEMBED_MODEL` | `BAAI/bge-small-en-v1.5` | — | Local embedding model. |

---

## 5. Redis & Background Tasks

The app runs without Redis (background tasks degrade gracefully).

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | — | Redis connection URL (RQ task queue). |
| `REDIS_HOST` | `localhost` | — | Override host. |
| `REDIS_PORT` | `6379` | — | Override port. |
| `REDIS_DB` | `0` | — | Override DB index. |
| `REDIS_PASSWORD` | unset | — | Override password. |
| `ENABLE_BACKGROUND_TASKS` | `true` | — | Enable background workers. |
| `ENABLE_SCHEDULER` | `true` | — | Enable the workflow scheduler. |
| `SCHEDULER_JOB_STORE_TYPE` | `sqlalchemy` | — | `sqlalchemy` \| `redis`. |
| `SCHEDULER_JOB_STORE_URL` | `sqlite:///jobs.sqlite` | — | Job store DSN. |
| `SCHEDULER_MISFIRE_GRACE_TIME` | `3600` | — | Misfire grace (seconds). |

---

## 5b. Email / Communication Ingestion

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `ATOM_OUTLOOK_POLL_SECONDS` | `60` | — | How often the Outlook poller checks Graph for new mail (floor 15s). An explicit `polling_interval_seconds` passed to `start_outlook_poller` wins over this. |
| `ATOM_EMAIL_REDACTION_ENABLED` | `true` | — | Secrets-redact email bodies (reuses the document-path `SecretsRedactor`) before storing in LanceDB. Set `false` to store bodies raw. |

---

## 5c. Provenance Spotlighting

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `ATOM_KNOWLEDGE_SPOTLIGHT_ENABLED` | `true` | — | Render retrieved knowledge (memory assembler knowledge leg + agents' RELEVANT KNOWLEDGE sections) as delimited UNTRUSTED `<provenance>` blocks with per-hit source/staleness/sender markers. Set `false` to restore legacy bare-bullet rendering. |

## 6. AI Providers (BYOK)

Optional. The server boots without any LLM key — LLM features are disabled
until you configure at least one provider. You can also add keys via the
UI (Settings > AI) instead of setting env vars.

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `OPENAI_API_KEY` | unset | — | https://platform.openai.com/api-keys |
| `ANTHROPIC_API_KEY` | unset | — | https://console.anthropic.com/ |
| `DEEPSEEK_API_KEY` | unset | — | https://platform.deepseek.com/ |
| `GOOGLE_API_KEY` | unset | — | https://aistudio.google.com/ |
| `GLM_API_KEY` | unset | — | Z.ai platform (GLM-5.2). |
| `MOONSHOT_API_KEY` | unset | — | https://platform.moonshot.cn/ (Kimi K2). |
| `OPENROUTER_API_KEY` | unset | — | https://openrouter.ai/keys (unified gateway). |
| `OPENCODE_API_KEY` | unset | — | https://opencode.ai/zen/v1 (low-cost subscription, recommended). |
| `MODEL_NAME` | `gpt-3.5-turbo` | — | Default model. |
| `MAX_TOKENS` | `2048` | — | Default max tokens. |
| `TEMPERATURE` | `0.7` | — | Default sampling temperature. |

### Local LLM (Ollama / LM Studio / vLLM)

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `ATOM_LOCAL_ONLY` | `false` | — | Block ALL cloud providers + integrations (fully offline). |
| `OLLAMA_HOST` | `http://localhost:11434` | — | Ollama host. |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | — | OpenAI-compatible Ollama endpoint. |
| `OLLAMA_MODEL` | `llama3:8b` | — | Default Ollama model. |
| `ALLOW_MOCK_AI` | `true` | — | Allow mock AI for tests/offline dev. |
| `USE_MOCK_DATA` | `true` | — | Return canned data when no provider configured. |
| `WORKFLOW_MOCK_ENABLED` | `false` | — | Use mock workflow executor. |

### Learning-based LLM router (Phase 3, default OFF)

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `ATOM_LEARNING_ROUTER` | `false` | — | Re-rank model candidates from observed outcomes. Master gate for the learning router singleton. |
| `ATOM_EMA_ROUTER_ENABLED` | `false` | — | When true (requires `ATOM_LEARNING_ROUTER=true`), blends an EMA (online telemetry) term into the score **alongside** the ML predictor — they are no longer mutually exclusive. EMA telemetry is always collected while the learning router is on; this flag only controls whether it influences the routing decision. Accepts `1`/`true`/`yes`/`on`. |
| `ATOM_EMA_ALPHA` | `0.2` | — | EMA smoothing factor in (0, 1]. Higher = more responsive to recent feedback; lower = more stable. |
| `ATOM_LLM_HEALER_ENABLED` | `false` | — | Enable the LLM-based fallback healer for provider 4xx errors. Rule-based healing is **always on**; this flag only enables the optional LLM-generated patch path (when no rule matches). See [Request Self-Healing](../architecture/REQUEST_SELF_HEALING.md). |
| `ATOM_COMPRESSION_ENABLED` | `true` | — | Master gate for token compression (RTK tool-output engine). See [Token Compression](../architecture/TOKEN_COMPRESSION.md). |
| `COMPRESS_RTK_ENABLED` | `true` | — | Enable the RTK engine (ANSI stripping, test-output compression, repeated-line collapse). Structured data (JSON/SQL) is never compressed. |
| `COMPRESS_RTK_MAX_SECTION_CHARS` | `8000` | — | Max chars per observation section before truncation (RTK). |
| `COMPRESS_SESSION_DEDUP_ENABLED` | `true` | — | Enable cross-turn exact-match dedup (replaces byte-identical repeated text with reference markers). Zero information loss. |
| `COMPRESS_DEDUP_MIN_CHUNK` | `200` | — | Minimum chunk size (chars) to index for session-dedup. |
| `COMPRESS_DEDUP_MAX_INDEX` | `500` | — | Max entries in the per-session dedup index (LRU eviction). |
| `ATOM_LKGP_ENABLED` | `true` | — | Enable Last-Known-Good-Path sticky routing (session continuity — prefers the provider/model that served the prior turn). See [Routing Strategies](ROUTING_STRATEGIES.md). |
| `ATOM_FUSION_ROUTING_ENABLED` | `true` | — | Enable fusion routing (panel+judge). Still requires `x-atom-strategy: fusion` header + COMPLEX tier + non-batch task. See [Routing Strategies](ROUTING_STRATEGIES.md). |
| `ATOM_FUSION_SAMPLES` | `3` | — | Number of parallel models in fusion routing. |
| `MCP_SERVER_ENABLED` | `true` | — | Enable the MCP (Model Context Protocol) server at `/mcp`. Exposes routing/compression/governance as MCP tools. See [MCP Server](../architecture/MCP_SERVER.md). |
| `ATOM_DAILY_BUDGET` | unset | — | Daily spend cap. Budget enforcement uses a rolling **daily window** (per calendar date): spend resets at the start of each day, so a breach today does not block generation tomorrow. |
| `ATOM_MONTHLY_BUDGET` | unset | — | Monthly spend cap. |

---

## 6a. Stage Router (Switchyard port — turn-level LLM routing)

Shadow-first per-turn model routing in the ReAct loop; calibrate per workload
before enforcing. See [`docs/architecture/SWITCHYARD_GAP_ANALYSIS.md`](../architecture/SWITCHYARD_GAP_ANALYSIS.md).

### Core flags

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `ATOM_STAGE_ROUTING_ENABLED` | `true` | — | Master switch. `true` = shadow (audit-only, no model override); `false` = kill switch (pre-stage-router loop). |
| `ATOM_STAGE_ROUTING_FORCE_ENFORCE` | `false` | — | `true` = live model-type override (efficient→fast, capable→quality). Only enable after per-workload calibration. |
| `ATOM_STAGE_ROUTING_PICKER` | `efficient_first` | — | Default arm picker when the router is ambiguous (`efficient_first` or `capable_first`). |
| `ATOM_STAGE_ROUTING_CONFIDENCE_THRESHOLD` | `0.5` | — | Corroborative signal score threshold for `dimensions` decision. |
| `ATOM_STAGE_ROUTING_WINDOW` | `3` | — | Number of recent turns scored per decision. |

### A/B harness (calibration)

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `ATOM_TRAFFIC_SPLIT` | `false` | — | A/B harness master switch. Forces weighted-random arm per turn for calibration. |
| `ATOM_STAGE_ROUTING_SPLIT` | _(empty)_ | — | JSON weights, e.g. `{"efficient": 0.7, "capable": 0.3}`. |
| `ATOM_STAGE_ROUTING_SPLIT_SEED` | _(empty)_ | — | Optional integer for reproducible splits. |

### Consent-gated automation

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `ATOM_STAGE_ROUTER_AUTO_ENFORCE` | `approve` | — | `off` \| `notify` \| `approve` \| `auto`. Escalation requires admin consent; revocation is always automatic. |
| `ATOM_STAGE_ROUTER_AUTO_INTERVAL_MIN` | `60` | — | Background certification cadence (minutes). |
| `ATOM_STAGE_ROUTER_AUTO_SUCCESS_GAP` | `0.03` | — | Min capable-arm success advantage to certify. |
| `ATOM_STAGE_ROUTER_AUTO_MAX_COST_RATIO` | `8.0` | — | Max capable/efficient cost ratio to certify. |
| `ATOM_STAGE_ROUTER_AUTO_REVOKE_GAP` | `0.02` | — | Capable-arm deficit that triggers automatic revocation. |
| `ATOM_STAGE_ROUTER_AUTO_NOTIFY_COOLDOWN_HOURS` | `24` | — | Min hours between admin notifications per agent (dedupe). |

---

## 6b. Background task model pins (planner / canvas editor / knowledge extraction)

Interactive calls can't always trust BPC's value ranking — tiny or bulk
structured calls pin one flash-class (provider, model) via
`generate_structured_response(provider_model=...)`, each with an unpinned
retry. Same convention as `ATOM_TOOL_PLANNER_MODEL` / `ATOM_CANVAS_EDITOR_MODEL`.

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `ATOM_KG_EXTRACTION_MODEL` | `qwen/qwen3.7-flash` | — | Model pinned for background knowledge-graph extraction (communication/document ingestion, ~800+ calls/6h observed). Flash-class: unpinned BPC routing sent this bulk workload to frontier models at ~26-30x the per-token cost (2026-09-05). |

## 6c. Multi-Agent Coordination (AgentRadio)

See [`docs/architecture/AGENT_RADIO.md`](../architecture/AGENT_RADIO.md).

Lateral (peer-to-peer) coordination layer. Additive and ON by default; a
fixed multi-agent team is **never** the default — threads auto-attach to fleet
runs only when a task crosses a responsibility breakpoint. Setting the master
switch to `false` restores pre-radio behavior on every path.

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `ATOM_RADIO_ENABLED` | `true` | — | Master kill switch for the lateral messaging layer. `false` disables the 3 `radio.*` actions and the passive inbox drain (graceful `success:false` / no-op). |
| `ATOM_RADIO_TEAM_BUDGET_USD` | `0.20` | — | Per-thread cumulative message-cost ceiling. When exhausted, `radio.send_message` returns `budget_exceeded`. |
| `ATOM_RADIO_INBOX_CAP` | `10` | — | Max pending mentions surfaced to an agent per inbox drain (attention cap). |
| `ATOM_RADIO_BACKLOG_TTL_MIN` | `30` | — | Messages older than this are treated as stale and dropped from the drain. |
| `ATOM_RADIO_WAIT_TIMEOUT_SECONDS` | `30` | — | Hard cap on agent-initiated `wait_for_mention` (never system-imposed; agents keep working by default). |
| `ATOM_RADIO_BREAKPOINT_GATE` | `true` | — | When `true`, a lateral thread is auto-attached to a recruited fleet ONLY for responsibility-breakpoint tasks. `false` disables auto-attachment entirely. |

---

## 7. Per-Turn Fact Extraction (Hermes-style memory)

See [`docs/architecture/CONTEXT_MEMORY.md`](../architecture/CONTEXT_MEMORY.md).

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `TURN_FACT_EXTRACTION_ENABLED` | `true` | — | Per-turn LLM extraction (1 fast-model call/turn). Default flipped ON in R72 Workstream D. |
| `TURN_FACT_PRE_COMPRESS_ENABLED` | `true` | — | Pre-truncation queue (free, additive). |
| `TURN_FACT_VECTOR_RECALL_ENABLED` | `true` | — | LanceDB-backed semantic recall. Default flipped ON in R72 Workstream D. |
| `TURN_FACT_MAX_PER_TURN` | `5` | — | Cap facts persisted per turn. |
| `TURN_FACT_EXTRACTION_SAMPLE_RATE` | `1.0` | — | Dial down in cost crunch (0.0 = off). |
| `TURN_FACT_QUEUE_MAXSIZE` | `100` | — | Queue capacity (overflow drops, never blocks). |

---

## 7b. R72 Reasoning-Loop Upgrades

All deterministic reasoning-loop gains from R72 default **ON**; the LLM
ActionJudge stays opt-in (`ATOM_SANDBOX_JUDGE_ENABLED`). Flags live in
`core/hallucination_config.py`.

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `ATOM_KNOWLEDGE_VFS_ENABLED` | `true` | — | Agent-native knowledge VFS: `documents.ls`/`cat`/`grep` with line-numbered content (W1). `false` = legacy ILIKE-only `documents.search`. |
| `ATOM_HYBRID_VECTOR_LEG_ENABLED` | `true` | — | Documents hybrid search (`documents.search`): enable the LanceDB vector leg (1536-dim). `false` = BM25/ILIKE lexical-only hybrid (`lexical_only` label). |
| `ATOM_ORACLE_VERIFIER_ENABLED` | `true` | — | Postcondition oracle: independently re-derives success against the system of record (W2). The oracle audits alongside self-report; set the force-enforce companion to override. |
| `ATOM_OBJECTIVE_LOOP_ENABLED` | `true` | — | Goal-driven ReAct loop: terminate early when an Objective's `definition_of_done` is satisfied (W5). `false` = `max_steps` bound only (also disables the utility-delta injection and the stuck-detector — P5b/P5c). |
| `ATOM_TEMPORALITY_ENABLED` | `true` | — | Temporal Evolution: ingestion-side date-anchor extraction (`temporal_entities`/`as_of`/`temporal_axis` on ingested records) feeding the bi-temporal graph reads (`edges_as_of`, expansion cutoffs, community windows, `local_search`/`global_search` `as_of`). See docs/architecture/TEMPORAL_EVOLUTION.md. |
| `ATOM_REVIEWER_LOOP_ENABLED` | `false` | — | Reviewer re-delegation loop (W3/P4c): a REVIEW rejection re-delegates the step to the originating specialist with feedback (parking the workflow RUNNING→WAITING) instead of folding into the voting fallback. |
| `ATOM_MOA_DIVERSITY_ENABLED` | `false` | — | Diversity-aware MoA init (W3/P4a): rotate per-sample perspective overlays and modulate the aggregator instruction by cross-sample agreement. Off = legacy byte-identical aggregator prompt. |
| `ATOM_FLEET_ROUTING_ENABLED` | `true` | — | Route TASK intents through the governed fleet path (`route_with_governance` → `FleetAdmiral`). Default ON since 2026-08-21 in **shadow** mode: recruitment + audit run on every eligible TASK, responses still come from Queen→ReAct. Set `false` for full kill-switch parity with pre-fleet behavior. |
| `ATOM_FLEET_ROUTING_FORCE_ENFORCE` | `false` | — | Live-mode for fleet routing: when true, return the recruitment summary directly instead of falling through to Queen→ReAct. When false (default), telemetry-only. |
| `ATOM_MOA_ENABLED` | `true` | — | Mixture-of-Agents on hard structured tasks (Workstream F). |
| `ATOM_MOA_SAMPLES` | `3` | — | Samples drawn per MoA vote (min 2). |
| `ATOM_PARALLEL_TOOLS` | `true` | — | In-loop parallel tool execution (Workstream G). |
| `ATOM_MAX_PARALLEL_TOOLS` | `4` | — | Max tools in a single parallel batch (Workstream G). |
| `ATOM_SKILL_INJECTION_ENABLED` | `true` | — | Prompt-time skill auto-injection (Workstream C). |
| `ATOM_TOOL_CACHE_ENABLED` | `true` | — | Read-only tool-result memoization (Workstream H). |
| `ATOM_TOOL_CACHE_TTL` | `30` | — | Cache TTL in seconds (Workstream H). |

---

## 8. API Behavior

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `RATE_LIMIT` | `100` | — | Requests per minute. |
| `REQUEST_TIMEOUT` | `30` | — | Request timeout (seconds). |
| `MAX_REQUEST_SIZE` | `10485760` (10 MB) | — | Max request body size. |
| `PAGINATION_SIZE` | `50` | — | Default page size. |

---

## 9. Logging

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `LOG_LEVEL` | `INFO` | — | Log level. |
| `LOG_FILE` | `./logs/atom.log` | — | Log file path. |
| `LOG_MAX_BYTES` | `10485760` (10 MB) | — | Rotation size. |
| `LOG_BACKUP_COUNT` | `5` | — | Rotated files to keep. |

---

## 10. Search & Web

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `TAVILY_API_KEY` | unset | — | https://tavily.com/ (agent web-search tool). |
| `BRAVE_SEARCH_API_KEY` | unset | — | https://brave.com/search/api/ |
| `NODE_ENGINE_URL` | `http://localhost:3003` | — | Node.js piece-engine URL (only if running that service). |

---

## 11. Marketplace (commercial service — atomagentos.com)

Two equivalent prefixes are read by the code: `ATOM_SAAS_*` and `MARKETPLACE_*`.
They are aliases — setting either works. Marketplace features degrade gracefully
to no-ops when no token is set.

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `MARKETPLACE_ENABLED` | `true` | — | Enable/disable marketplace. |
| `ATOM_SAAS_API_URL` / `MARKETPLACE_API_URL` | `https://atomagentos.com/api/v1/marketplace` | — | Marketplace API URL. |
| `ATOM_SAAS_API_TOKEN` / `MARKETPLACE_API_TOKEN` | unset | — | API token (https://atomagentos.com/settings/api-tokens). |
| `ATOM_SAAS_SYNC_INTERVAL_MINUTES` / `MARKETPLACE_SYNC_INTERVAL_MINUTES` | `15` | — | Skill/category sync interval. |
| `ATOM_SAAS_RATING_SYNC_INTERVAL_MINUTES` / `MARKETPLACE_RATING_SYNC_INTERVAL_MINUTES` | `30` | — | Rating sync interval. |
| `ATOM_SAAS_CONFLICT_STRATEGY` / `MARKETPLACE_CONFLICT_STRATEGY` | `remote_wins` | — | `remote_wins` \| `local_wins` \| `merge` \| `manual`. |
| `ATOM_SAAS_WS_URL` / `MARKETPLACE_WS_URL` | `wss://api.atomsaas.com/ws` | — | WebSocket URL. |
| `ATOM_SAAS_WS_RECONNECT_ATTEMPTS` / `MARKETPLACE_WS_RECONNECT_ATTEMPTS` | `10` | — | WS reconnect attempts. |
| `ATOM_SAAS_WS_HEARTBEAT_INTERVAL` / `MARKETPLACE_WS_HEARTBEAT_INTERVAL` | `30` | — | WS heartbeat (seconds). |
| `MARKETPLACE_SYNC_ENABLED` | `false` | — | Opt-in sync (privacy default off). |

---

## 12. Governance / Federation / Feature Flags

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `ADMIN_GOVERNANCE_ENABLED` | `true` | — | Admin governance UI. |
| `AGENT_GUIDANCE_ENABLED` | `true` | — | Agent guidance system. |
| `AGENT_REQUESTS_ENABLED` | `true` | — | Agent request endpoints. |
| `AI_WORKFLOW_ENABLED` | `true` | — | Enhanced workflow automation. |
| `ENHANCED_MONITORING_ENABLED` | `true` | — | Enhanced monitoring. |
| `CROSS_SERVICE_ORCHESTRATION_ENABLED` | `true` | — | Cross-service orchestration. |
| `WORKFLOW_OPTIMIZATION_ENABLED` | `true` | — | Workflow optimization. |
| `COMMISSION_AUTO_CALCULATE` | `true` | — | Auto-commission calculation. |
| `FEDERATION_API_KEY` | unset | — | Cross-instance agent sharing. |
| `ATOM_ORACLE_ENFORCE` | `true` | — | Postcondition oracle stamps tool outcomes (refuted self-reports marked UNVERIFIED). `false` = pass-through. |
| `ATOM_OIDC_ISSUER` / `ATOM_OIDC_CLIENT_ID` / `ATOM_OIDC_CLIENT_SECRET` / `ATOM_OIDC_ENABLED` | unset | — | OIDC SSO env fallback (a DB config row via `PUT /api/auth/sso/oidc/config` takes precedence). |
| `ATOM_SCIM_TOKEN` | unset | — | Bearer token for SCIM v2 provisioning (`/api/scim/v2`). Unset = SCIM disabled (503). |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` | unset / `https://cloud.langfuse.com` | — | Enables async trace-span export to Langfuse (`/api/observability/spans` works without them). |

### Monitoring thresholds

`RESPONSE_TIME_WARNING_MS=1000`, `RESPONSE_TIME_CRITICAL_MS=5000`,
`SUCCESS_RATE_WARNING=0.95`, `SUCCESS_RATE_CRITICAL=0.90`,
`HEALTH_SCORE_WARNING=80`, `HEALTH_SCORE_CRITICAL=60`.

---

## 13. Package Scanning & Piece Engine

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `SAFETY_API_KEY` | unset | — | Safety commercial vuln DB key (https://pyup.io/safety/). |
| `PACKAGE_CACHE_TTL` | `60` | — | Package cache duration (seconds). |
| `PACKAGE_CACHE_MAX_SIZE` | `1000` | — | Max cache entries. |
| `PIECE_ENGINE_API_KEY` | unset | piece-engine | **Critical** — secures `/sys/install` + `/execute/action`. Generate: `openssl rand -base64 32`. |

---

## 14. Integration credentials (46+ services)

### BambooHR (HR)

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `BAMBOOHR_SUBDOMAIN` | unset | for BambooHR | Your BambooHR subdomain. |
| `BAMBOOHR_API_KEY` | unset | for BambooHR | API key (Basic auth). |

### Twitter / X

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `TWITTER_BEARER_TOKEN` | unset | for X API v2 | Bearer token for post/user-tweets/search. |

All optional. Each integration has `*_CLIENT_ID` / `*_CLIENT_SECRET` (OAuth) or
`*_API_KEY` / `*_ACCESS_TOKEN` patterns. The full list with sign-up URLs lives
in [`backend/.env.example`](../../backend/.env.example) §10–§20.

### Telegram IM (polling or webhook)

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `TELEGRAM_BOT_TOKEN` | unset | for Telegram IM | Bot token from @BotFather. Enables agent IM in either mode. |
| `TELEGRAM_POLLING_ENABLED` | `false` | — | Long-poll `getUpdates` instead of a webhook. **No public URL/domain/tunnel needed** — NAT-friendly, recommended for Personal Edition. Mutually exclusive with webhook mode; the worker deletes any registered webhook on startup. See [IM Adapter Setup](../integrations/IM_ADAPTER_SETUP.md). |
| `TELEGRAM_WEBHOOK_URL` | unset | webhook mode | Public HTTPS URL Telegram pushes updates to. |
| `ATOM_TELEGRAM_WEBHOOK_SECRET` | unset | webhook mode | Fail-closed shared secret; Telegram sends it as `X-Telegram-Bot-Api-Secret-Token`. Requests without a match are rejected. |
| `ATOM_MEMORY_PROMPT_SENSITIVITY_CEILING` | `confidential` | — | Recall ceiling for prompt assembly: facts above it (public < internal < confidential < restricted) never surface into prompts sent to LLM providers. `none` disables; invalid values fall back to the safe default. |
| `ATOM_MEMORY_POISON_TRIPWIRE` | `true` | — | Write-path governance for turn facts: a source superseding ≥5 facts within 10 min gets its writes quarantined (`status="quarantined"`, excluded from recall) for 30 min — memory-injection defense. `false` disables. |
| `DISCORD_GATEWAY_ENABLED` | `false` | worker mode | Real-time Discord ingestion: connects the gateway WebSocket (bot token required) and routes MESSAGE_CREATE through `ingest_message("discord", …)` — closes the interactions-only bridge gap. |
| `DISCORD_BOT_TOKEN` | unset | — | Discord bot token; also used by the gateway client (required when the gateway is enabled). |
| `ZENDESK_WEBHOOK_SECRET` | unset | webhook mode | Fail-closed HMAC key for `POST /webhooks/zendesk/events`: requests carry `X-Zendesk-Webhook-Signature` (base64 HMAC-SHA256 over the raw body). Unset → 503; mismatch → 401. Ticket comments flow to both memory pipelines via `ingest_message("zendesk", …)`. |
| `TELEGRAM_BOT_USERNAME` | unset | — | Bot @username, informational. |

### Turn-time memory retrieval (Memory Context Assembler)

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `MEMORY_CONTEXT_ASSEMBLY` | `true` | — | Fuse comm memory + GraphRAG + episodes + turn facts + all ingested `integration_*` records into one bounded `RELEVANT MEMORY` block injected before the LLM on every chat/IM surface. Legs are fault-isolated with per-leg timeouts; a startup warm-up preloads embedding models. See [Agent Memory Unification Plan](../architecture/AGENT_MEMORY_UNIFICATION_PLAN.md). |
| `MEMORY_CONVERSATIONS_LEG` | `true` | — | Include the communication memory store (email/Slack/WhatsApp/Teams/Telegram) as a leg in `documents.search` hybrid results (`source=communication`, bridged — never copied into documents). See [Agent Hybrid Search](../architecture/AGENT_HYBRID_SEARCH.md). |

For group chats, disable the bot's privacy mode via BotFather `/setprivacy`,
and remember bots can never DM a user first (each user must `/start` the bot).

Categories: **Communication** (Slack, Discord, WhatsApp, Telegram, Teams,
Twilio, SendGrid), **Google**, **Microsoft**, **Project Management** (Asana,
Jira, Linear, Notion, Monday, Trello, ClickUp, Airtable), **CRM** (Salesforce,
HubSpot, Zendesk, Intercom, Freshdesk), **Dev Tools** (GitHub, GitLab,
Bitbucket, Figma), **Finance** (Stripe, QuickBooks, Xero, Plaid), **Storage**
(Dropbox, Box, Zoho, Zoom), **Marketing** (Mailchimp, LinkedIn, Shopify),
**Audio/Video** (Deepgram, ElevenLabs), **Calendar** (Calendly), **Email/SMTP**.

---

## 15. Frontend (Next.js)

Set in `frontend-nextjs/.env.local`. See `frontend-nextjs/.env.example` for the
full list. The ones that matter most:

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8001` | yes | Backend URL the browser calls. |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | — | Alternate backend URL var. |
| `NEXTAUTH_URL` | `http://localhost:3000` | — | NextAuth canonical URL. |
| `NEXTAUTH_SECRET` | unset | production | NextAuth session secret. |
| `NODE_ENV` | `development` | — | `development` \| `production`. |

---

## 14. Execution Sandbox Layer (P9 — default-on)

The deterministic blast-radius controls are **default-on** for all dispatch
paths since P9 (Aug 2026). Each flag is a kill switch — set any to `false` to
restore the prior shadow/off behavior instantly. See
[../architecture/SANDBOX_LAYER.md](../architecture/SANDBOX_LAYER.md).

| Variable | Default (P9) | Description |
|----------|--------------|-------------|
| `ATOM_SANDBOX_ENABLED` | `true` | Master switch (Phase A+). `false` = layer off. |
| `ATOM_SANDBOX_FORCE_ENFORCE` | `true` | Enforce (block on violation) vs shadow (audit only). `false` = shadow. |
| `ATOM_SANDBOX_POLICY_TENANT_OVERRIDE` | `false` | Allow tenant metadata_json to override policy. |
| `ATOM_SANDBOX_FS_ENABLED` | `true` | Phase B — filesystem scope enforcement. |
| `ATOM_SANDBOX_WHITELIST_ENABLED` | `true` | Phase C — tool whitelist enforcement. |
| `ATOM_SANDBOX_TRIPWIRES_ENABLED` | `true` | Phase C — tripwire pattern enforcement. |
| `ATOM_SANDBOX_CAPS_ENABLED` | `true` | Phase C — resource cap enforcement. |
| `ATOM_SANDBOX_EGRESS_ENABLED` | `false` | Phase D — egress proxy (network isolation). **Stays opt-in.** |
| `ATOM_SANDBOX_PROVENANCE_ENABLED` | `true` | Phase E — provenance tagging in context assembly. |
| `ATOM_SANDBOX_JUDGE_ENABLED` | `false` | Phase E — LLM ActionJudge for irreversible actions. **Stays opt-in (R72).** |

Caps: `ATOM_SANDBOX_MAX_TOOL_CALLS=200`, `ATOM_SANDBOX_MAX_EXEC_SECONDS=600`,
`ATOM_SANDBOX_MAX_BYTES_WRITTEN=104857600`, `ATOM_SANDBOX_MAX_COST_USD=5.0`.
Runtime: `ATOM_SANDBOX_RUNTIME=docker|firecracker|e2b`.

> **Fastest kill switch:** `ATOM_SANDBOX_FORCE_ENFORCE=false` returns the whole
> layer to shadow mode (policy still computed + audited, nothing blocked).

---

## Quick default-on summary

For a brand-new user copying `backend/.env.example` → `backend/.env`, the app
boots with **everything defaulted** except:
- `SECRET_KEY` (set one for persistent logins)

LLM keys are optional — the server boots without any. All 46+ integrations,
marketplace, federation, Redis, scheduler, and feature flags have safe defaults
and stay dormant until you configure them.

> Note (P0/P9): OAuth integration tokens are encrypted at rest with
> `BYOK_ENCRYPTION_KEY` (fail-closed in production), and the execution sandbox
> enforces by default — both safe out of the box. See
> [DATA_PROTECTION.md](../security/DATA_PROTECTION.md) and
> [SANDBOX_LAYER.md](../architecture/SANDBOX_LAYER.md).

## Agent journey learning knobs (R81j, Aug 2026)

| Variable | Default | Purpose |
|---|---|---|
| `ATOM_POSITIVE_RATING_BOOST_ENABLED` | `true` | Trusted-user star ratings ≥4 give a tiny confidence nudge to the rated agent. Explicit ratings are a high-precision but low-volume/extremes-biased signal, so the nudge is half the outcome drip and promotions remain gated on outcome evidence + exams. |
| `ATOM_POSITIVE_RATING_BOOST_MAGNITUDE` | `0.005` | Confidence delta per applied rating boost. |
| `ATOM_POSITIVE_RATING_BOOST_DAILY_CAP` | `3` | Max boosts per (agent, user) per day — anti-farming / diminishing returns. Ledger is written into `AgentFeedback.ai_reasoning` (`[rating_boost_applied]` / `[rating_boost_skipped_daily_cap]`). |
| `ATOM_EPISODE_LIFECYCLE_MAINTENANCE_ENABLED` | `false` | Opt-in daily worker: episode recency decay (`days_threshold=90`) + per-agent similarity consolidation via `EpisodeLifecycleService.run_daily_maintenance`. Manual alternatives: `POST /api/episodes/lifecycle/{decay,consolidate}`. |


---

*Last Updated: August 21, 2026*

## Trust Calibration Gateway (R81l–p, Aug 2026)

| Variable | Default | Purpose |
|---|---|---|
| `ATOM_TRUST_CALIBRATION_ENABLED` | `false` | Master switch; true = SHADOW recording at both ask-paths (`_step_act` HITL pauses + `_check_hitl_policy` interventions). Routes answer 503 when off. |
| `ATOM_TRUST_CALIBRATION_AUTO_ENFORCE` | `off` | Consent-gated automation: off\|notify\|approve\|auto. Auto applies certified enable verdicts and ALWAYS auto-revokes on regression. |
| `ATOM_TRUST_CALIBRATION_AUTO_INTERVAL_MIN` | `60` | Automation worker cadence (lifespan loop). |
| `ATOM_TRUST_CALIBRATION_FORCE_ENFORCE` | `false` | Env hard-switch overriding the action ledger for `resolved_trust_enforce()`. |
| `ATOM_TRUST_CALIBRATION_HALF_LIFE_DAYS` | `30` | k_time decay half-life (stale decisions down-weighted + noisier). |
| `ATOM_TRUST_CALIBRATION_MAX_OBS` | `400` | Most-recent decisions per posterior refit. |
| `ATOM_TRUST_CALIBRATION_REFIT_TTL` | `300` | Posterior cache seconds between refits. |
| `ATOM_TRUST_CALIBRATION_TAU_LOW` | `0.35` | p_approve below → **block** (confident denial, don't ask). |
| `ATOM_TRUST_CALIBRATION_TAU_UNCERTAIN` | `0.15` | σ² above → **ask** (ASK band entry). |
| `ATOM_TRUST_CALIBRATION_MIN_OBS` | `10` | Resolved observations before any non-ask recommendation. |

Certification gate: `scripts/calibrate_trust_gateway.py` (exit 0=certified,
1=not certified, 2=setup error) — temporal holdout Brier ≤ 0.25 AND
denial-coverage ≥ 0.7 AND n ≥ 30. See
[TRUST_CALIBRATION_PLAN.md](../architecture/TRUST_CALIBRATION_PLAN.md).

## Ontology Draft Promotion Automation (Aug 2026)

Promotes auto-discovered `EntityTypeDefinition` drafts (`is_active=False` —
integration-sync discovery, OpenIE discovery, single-entity linking) that
were otherwise invisible until a manual `PATCH {"is_active": true}`. See
[ONTOLOGY_DRAFT_AUTOMATION.md](../architecture/ONTOLOGY_DRAFT_AUTOMATION.md).

| Variable | Default | Purpose |
|---|---|---|
| `ATOM_ONTOLOGY_DRAFT_AUTO_ENFORCE` | `auto` | Consent-gated automation: off\|notify\|approve\|auto. Auto applies evidence-eligible promotions; revocation is ALWAYS automatic; manual decisions are never overridden. `off` = no pass, no worker loop. |
| `ATOM_ONTOLOGY_DRAFT_AUTO_INTERVAL_MIN` | `60` | Automation pass cadence (lifespan loop). |
| `ATOM_ONTOLOGY_DRAFT_AUTO_MIN_NODES` | `3` | Graph-usage evidence floor (matching graph node labels). |
| `ATOM_ONTOLOGY_DRAFT_AUTO_MIN_AGE_DAYS` | `2` | Minimum draft age to promote (one ingestion burst is not recurrence). |
| `ATOM_ONTOLOGY_DRAFT_AUTO_MIN_SAMPLES` | `3` | Discovery `sample_count` floor (applied only when that metadata is present). |
| `ATOM_ONTOLOGY_DRAFT_AUTO_REVOKE_STALE_DAYS` | `14` | Unused + undiscovered past this → automatic revoke. |
| `ATOM_ONTOLOGY_DRAFT_AUTO_NOTIFY_COOLDOWN_HOURS` | `24` | Notify-mode dedupe window. |

Admin surface: admin-gated `/api/v1/ontology-drafts/*` (`status`,
`automation`, `run-now`, `pending`, `approve/{id}`, `reject/{id}`).
