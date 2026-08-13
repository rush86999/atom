# First Steps After Install

> **You've launched the server — now what?** This walks through the first
> 5 things to do after step 6 of the
> [Quick Start](./quick-start.md).

---

## 1. Confirm you're authenticated

```bash
PWD_VAL=$(cat backend/logs/bootstrap_admin_password.txt)

TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin@example.com\",\"password\":\"$PWD_VAL\"}" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

curl http://localhost:8001/api/users/me -H "Authorization: Bearer $TOKEN"
# → {"email":"admin@example.com","role":"workspace_admin", ...}
```

Save `$TOKEN` somewhere — you'll reuse it. JWTs expire after 1 hour by
default (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).

## 2. Pick an LLM provider

At least one provider key is needed for agent features to do anything useful.
The server boots without one — LLM features are just disabled until you configure
a provider.

**Quick pick:**
| Goal | Provider | Setup |
|------|----------|-------|
| Free, local, private | **Ollama** | `OLLAMA_BASE_URL=http://localhost:11434/v1` + `ollama pull llama3:8b` |
| Lowest cost, high volume | **OpenCode Go** | `OPENCODE_API_KEY=sk-opencode-...` (subscription) |
| Best quality | **OpenAI** / **Anthropic** | `OPENAI_API_KEY=sk-...` |
| Model variety | **OpenRouter** | `OPENROUTER_API_KEY=...` |

**Full comparison & setup**: [LLM Providers Guide](../guides/LLM_PROVIDERS.md)

**Minimal config** (backend/.env):
```bash
DATABASE_URL=sqlite:///./atom_dev.db
SECRET_KEY=<openssl rand -base64 48>
# ONE of these:
OPENAI_API_KEY=sk-...                    # Cloud
# ATOM_LOCAL_ONLY=true + OLLAMA_BASE_URL=http://localhost:11434/v1  # Local
```

After editing, restart the server (`Ctrl+C` then re-run the launch command).

## 3. Create your first agent

```bash
curl -X POST http://localhost:8001/api/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "research-assistant",
    "display_name": "Research Assistant",
    "description": "Helps with research and summarization"
  }'
```

New agents start at **STUDENT** tier (read-only). They graduate to
INTERN → SUPERVISED → AUTONOMOUS as they accumulate clean executions.

## 4. Try a workflow

```bash
curl -X POST http://localhost:8001/api/agent/route \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"request": "Summarize the benefits of multi-agent governance in 3 bullets"}'
```

The router classifies your request (CHAT / WORKFLOW / TASK) and dispatches
to the right agent. For TASK intents, the Fleet Admiral recruits a
specialist.

## 5. Open the frontend UI

If you haven't already:
```bash
cd frontend-nextjs && npm run dev
```

Open http://localhost:3000 and sign in with `admin@example.com` + the
password from `backend/logs/bootstrap_admin_password.txt`.

The UI gives you:
- **Dashboard** — agents, runs, governance state
- **Canvas** — rich presentations (charts, markdown, forms) from agent output
- **Workflows** — visual workflow builder
- **Integrations** — connect Slack, Gmail, Notion, etc.

---

## What to read next

### Core Concepts
- [Documentation Index](../INDEX.md) — Complete navigation by topic
- [Architecture Overview](../architecture/README.md) — How the pieces fit
- [Agent Systems](../agents/overview.md) — Governance, maturity, intent types
- [Execution Sandbox](../architecture/SANDBOX_LAYER.md) — How blast radius is bounded
- [Makefile Reference](../../Makefile) — `make backend`, `make test`, `make setup`

### Features
- [LLM Providers Guide](../guides/LLM_PROVIDERS.md) — All providers, costs, routing
- [Canvas & Office Automation](../guides/ATOM_OFFICE_AUTOMATION_GUIDE.md) — Presentations, spreadsheets, co-editing
- [Mini-Apps](../architecture/MINI_APPS.md) — Agent-authored stateful apps

### Operations
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) — When something breaks
- [Production Readiness](../operations/production-readiness.md) — Pre-flight checklist
- [Monitoring](../operations/monitoring.md) — Prometheus, health checks, alerts

### Reference
- [Environment Variables](../reference/ENVIRONMENT_VARIABLES.md) — Complete reference
- [API Overview](../api/OVERVIEW.md) — All endpoints
- `CLAUDE.md` (repo root) — Engineering reference (comprehensive)

---

**Last Updated**: August 2026
