# Run Atom with Ollama (Free, Local, No API Key)

Atom supports any OpenAI-compatible local LLM backend. [Ollama](https://ollama.ai)
is the easiest — install it, pull a model, and Atom handles the rest.

## Prerequisites

1. Install [Ollama](https://ollama.ai) (one download, runs on macOS/Linux/Windows)
2. Pull a model:
   ```bash
   ollama pull llama3:8b        # Fast, good for most tasks
   # or
   ollama pull qwen2.5:7b       # Good coding model
   # or
   ollama pull mixtral:8x7b     # Larger, more capable (needs ~26GB RAM)
   ```

## Option A: Quick Start Script

```bash
git clone https://github.com/rush86999/atom.git
cd atom
./scripts/quickstart.sh
# Edit backend/.env — set ATOM_LOCAL_ONLY=true
./scripts/dev.sh          # NOTE: launches minimal_app (smoke subset). For the
                          # full app, use: make backend
```

## Option B: Docker

```bash
git clone https://github.com/rush86999/atom.git
cd atom
cp .env.personal .env
# Edit .env — set:
#   ATOM_LOCAL_ONLY=true
#   OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
#   SECRET_KEY=<run: openssl rand -base64 32>
#   JWT_SECRET_KEY=<run: openssl rand -base64 32>
#   BYOK_ENCRYPTION_KEY=<run: openssl rand -base64 32>
docker compose -f docker-compose-personal.yml up -d --build
# Frontend: http://localhost:3001   Backend: http://localhost:8001
```

## Option C: Manual Setup

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure for local-only mode
export ATOM_LOCAL_ONLY=true
export OLLAMA_BASE_URL=http://localhost:11434/v1
export DATABASE_URL=sqlite:///./atom_dev.db
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")

# Start the FULL app (main_api_app:app) — from repo root
cd ..
PYTHONPATH=$PWD:$PWD/backend ./backend/venv/bin/python -m uvicorn main_api_app:app --reload --port 8001
```

## Verifying It Works

1. Open http://localhost:3000
2. Send a chat message: "Hello, what can you help me with?"
3. The response comes from your local Ollama model — no cloud, no API key, no cost

## Configuring Which Model Atom Uses

The cognitive tier system assigns local models to tiers. To customize which
Ollama model handles which task complexity:

1. Go to **Settings → Local Models** (`/settings/local-models`)
2. Register your Ollama endpoint (it's auto-detected if on localhost)
3. Click "Discover Models" — Atom finds all your Ollama models
4. Set capabilities (tools, vision, reasoning) per model

Atom's learning router will then re-rank candidates based on observed outcomes,
preferring the local model when it performs well — at zero cost.

## Privacy

With `ATOM_LOCAL_ONLY=true`, Atom:
- ✅ Never sends data to any cloud LLM API
- ✅ Never sends data to external pricing APIs
- ✅ Runs entirely on your machine
- ✅ Stores all data in a local SQLite database

Your prompts, responses, and learned routing data never leave your computer.
