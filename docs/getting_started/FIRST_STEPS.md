# First Steps After Install

> **You've launched the server — now what?** This walks through the first
> 5 things to do after step 6 of the
> [Quick Start](./quick-start.md).

---

## 1. Confirm you're authenticated

```bash
PWD_VAL=$(cat backend/logs/bootstrap_admin_password.txt)

TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin@example.com\",\"password\":\"$PWD_VAL\"}" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

curl http://localhost:8000/api/users/me -H "Authorization: Bearer $TOKEN"
# → {"email":"admin@example.com","role":"workspace_admin", ...}
```

Save `$TOKEN` somewhere — you'll reuse it. JWTs expire after 1 hour by
default (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).

## 2. Pick an LLM provider

At least one provider key is required for the agent features to do
anything useful. Edit `backend/.env`:

| Provider | Env var | Where to get a key |
|----------|---------|-------------------|
| OpenAI | `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| Anthropic | `ANTHROPIC_API_KEY` | https://console.anthropic.com/ |
| DeepSeek | `DEEPSEEK_API_KEY` | https://platform.deepseek.com/ |
| Google Gemini | `GEMINI_API_KEY` | https://aistudio.google.com/app/apikey |
| Zhipu GLM (5.2) | `GLM_API_KEY` | https://open.bigmodel.cn/usercenter/apikeys |
| MiniMax | `MINIMAX_API_KEY` | https://platform.minimaxi.com/ |
| Ollama (local, free) | `OLLAMA_BASE_URL` | https://ollama.ai (no key — local) |

After editing, restart the server (`Ctrl+C` then re-run the launch
command).

**Recommendation for first-run**: Ollama is free and fully local — set
`OLLAMA_BASE_URL=http://localhost:11434/v1` and `OLLAMA_MODEL=llama3:8b`
after running `ollama pull llama3:8b`.

## 3. Create your first agent

```bash
curl -X POST http://localhost:8000/api/agents \
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
curl -X POST http://localhost:8000/api/agent/route \
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

- [**TROUBLESHOOTING.md**](./TROUBLESHOOTING.md) — when something breaks
- [**Architecture overview**](../architecture/README.md) — how the pieces fit
- [**Agent governance**](../agents/governance.md) — maturity tiers explained
- [**Execution sandbox**](../architecture/SANDBOX_LAYER.md) — how blast radius is bounded
- [`CLAUDE.md`](../../CLAUDE.md) — the engineering reference (comprehensive)

---

**Last Updated**: June 30, 2026
