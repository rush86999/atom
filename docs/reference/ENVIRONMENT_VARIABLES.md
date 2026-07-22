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
OPENAI_API_KEY=sk-...                      # OR ATOM_LOCAL_ONLY=true for Ollama
```

That's it. Everything below is optional.

---

## 1. Core / Runtime

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `ENVIRONMENT` | `development` | — | `development` \| `staging` \| `production`. Production enforces `SECRET_KEY` and disables dev escapes. |
| `HOST` | `0.0.0.0` | — | FastAPI bind host. |
| `PORT` | `8000` | — | FastAPI bind port (container). Dev launch uses `--port 8001`. |
| `WORKERS` | `1` | — | Uvicorn workers (production). Use `1` with `--reload`. |
| `DEBUG` | `false` | — | Enables debug logging / verbose errors. |
| `RELOAD` | `false` | — | Uvicorn auto-reload on file change. |
| `APP_URL` | `http://localhost:3000` | — | App's public URL (password-reset links, OAuth redirects). |
| `CORS_ORIGINS` | `http://localhost:3000,...:3001` | — | Comma-separated allowed browser origins. |
| `ALLOWED_ORIGINS` | (same as CORS_ORIGINS) | — | Read by `main_api_app.py` CORSMiddleware. |
| `DISABLE_AUTH_RATE_LIMIT` | unset | — | Set to `1` to lift register/login rate limits (dev/E2E only). |

---

## 2. Security & Secrets

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `SECRET_KEY` | random per restart (dev) | **Production** | Signs JWT sessions. Generate: `openssl rand -base64 48`. |
| `JWT_SECRET_KEY` | (falls back to SECRET_KEY) | Docker | Alternate JWT secret name; required by the Docker stacks. |
| `JWT_EXPIRATION` | `86400` (24h) | — | JWT lifetime in seconds. |
| `ENCRYPTION_KEY` | unset | — | Fernet-style general secrets encryption. Recommended. |
| `BYOK_ENCRYPTION_KEY` | unset | Docker | Encrypts stored provider API keys. Required by Docker stacks. |
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

## 6. AI Providers (BYOK)

Set **at least one** cloud key, OR set `ATOM_LOCAL_ONLY=true` for Ollama.

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `OPENAI_API_KEY` | unset | one of | https://platform.openai.com/api-keys |
| `ANTHROPIC_API_KEY` | unset | one of | https://console.anthropic.com/ |
| `DEEPSEEK_API_KEY` | unset | one of | https://platform.deepseek.com/ |
| `GOOGLE_API_KEY` | unset | one of | https://aistudio.google.com/ |
| `GLM_API_KEY` | unset | one of | Z.ai platform (GLM-5.2). |
| `MOONSHOT_API_KEY` | unset | one of | https://platform.moonshot.cn/ (Kimi K2). |
| `OPENROUTER_API_KEY` | unset | one of | https://openrouter.ai/keys (unified gateway). |
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
| `ATOM_LEARNING_ROUTER` | `false` | — | Re-rank model candidates from observed outcomes. |
| `ATOM_EMA_ROUTER_ENABLED` | `false` | — | EMA-smoothed router variant. |
| `ATOM_DAILY_BUDGET` | unset | — | Daily spend cap. |
| `ATOM_MONTHLY_BUDGET` | unset | — | Monthly spend cap. |

---

## 7. Per-Turn Fact Extraction (Hermes-style memory)

See [`docs/architecture/CONTEXT_MEMORY.md`](../architecture/CONTEXT_MEMORY.md).

| Variable | Default | Required? | Description |
|----------|---------|-----------|-------------|
| `TURN_FACT_EXTRACTION_ENABLED` | `false` | — | Per-turn LLM extraction (1 fast-model call/turn). |
| `TURN_FACT_PRE_COMPRESS_ENABLED` | `true` | — | Pre-truncation queue (free, additive). |
| `TURN_FACT_VECTOR_RECALL_ENABLED` | `false` | — | LanceDB-backed semantic recall. |
| `TURN_FACT_MAX_PER_TURN` | `5` | — | Cap facts persisted per turn. |
| `TURN_FACT_EXTRACTION_SAMPLE_RATE` | `1.0` | — | Dial down in cost crunch (0.0 = off). |
| `TURN_FACT_QUEUE_MAXSIZE` | `100` | — | Queue capacity (overflow drops, never blocks). |

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

All optional. Each integration has `*_CLIENT_ID` / `*_CLIENT_SECRET` (OAuth) or
`*_API_KEY` / `*_ACCESS_TOKEN` patterns. The full list with sign-up URLs lives
in [`backend/.env.example`](../../backend/.env.example) §10–§20.

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

## Quick default-on summary

For a brand-new user copying `backend/.env.example` → `backend/.env`, the app
boots with **everything defaulted** except:
- `SECRET_KEY` (set one for persistent logins)
- one LLM provider key (or `ATOM_LOCAL_ONLY=true`)

All 46+ integrations, marketplace, federation, Redis, scheduler, and feature
flags have safe defaults and stay dormant until you configure them.

---

*Last Updated: July 2026*
