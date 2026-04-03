# Atom Personal Edition - One-Command Start

> **Start Atom with a single command - no configuration needed!**

---

## 🚀 Quick Start (One Command)

### macOS / Linux

```bash
./start.sh
```

### Windows

```batch
start.bat
```

That's it! Atom will start automatically. Open your browser to:

**http://localhost:3000**

---

## What This Script Does

The `start.sh` (or `start.bat`) script automatically:

1. ✅ **Checks prerequisites** - Python, Node.js, npm
2. ✅ **Installs if needed** - Runs `install-native.sh` if first time
3. ✅ **Starts backend** - On port 8000 (or 8001 if occupied)
4. ✅ **Starts frontend** - On port 3000 (or 3001 if occupied)
5. ✅ **Shows access URLs** - Dashboard, API, documentation
6. ✅ **Handles cleanup** - Stops both services when you press Ctrl+C

---

## 📋 What You'll See

```
╔════════════════════════════════════════════════════════════╗
║  🚀 Atom Personal Edition - Starting...                       ║
╚════════════════════════════════════════════════════════════╝

📊 Starting backend...
✅ Backend starting on port 8000

🎨 Starting frontend...
✅ Frontend starting on port 3000

╔════════════════════════════════════════════════════════════╗
║  ✅ Atom is Running!                                         ║
╚════════════════════════════════════════════════════════════╝

🌐 Dashboard:      http://localhost:3000
🔌 Backend API:    http://localhost:8000
📚 API Docs:      http://localhost:8000/docs
```

---

## 🛑 How to Stop

Just press **Ctrl+C** in the terminal. The script will automatically stop both backend and frontend services.

---

## 📝 First Time Setup

If this is your first time running Atom, the script will automatically run the installer:

```bash
./start.sh
# Will detect that installation is needed and run install-native.sh
```

The installer will:
- Create Python virtual environment
- Install all dependencies (FastAPI, FastEmbed, LanceDB, etc.)
- Configure environment (.env file)
- Generate encryption keys
- Run database migrations
- Create admin user

This takes about **5 minutes** on first run.

---

## ⚙️ Configuration

### Before First Run

Add your AI provider API key to `.env`:

```bash
# Edit .env file
nano .env

# Add your API key:
OPENAI_API_KEY=sk-your-key-here
# OR
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**Get API Key:**
- OpenAI: https://platform.openai.com/api-keys
- Anthropic: https://console.anthropic.com/

### Optional Configuration

If you want to customize ports or other settings:

```bash
# Edit start.sh
nano start.sh

# Change these lines if needed:
# PORT=8001  # Backend port
# FRONTEND_PORT=3001  # Frontend port
```

---

## 🔍 Troubleshooting

### Port Already in Use

**Error:** `address already in use`

**Solution:** The script automatically detects port conflicts and uses:
- Backend: 8001 (if 8000 is busy)
- Frontend: 3001 (if 3000 is busy)

### Backend Won't Start

**Error:** Backend exits immediately

**Solution:** Check logs:
```bash
tail -f /tmp/atom-backend.log
```

Common issues:
- Missing API key in `.env`
- Port conflicts
- Dependencies not installed (run `./install-native.sh`)

### Frontend Won't Start

**Solution:** Check frontend terminal or reinstall dependencies:
```bash
cd frontend-nextjs
npm install
```

---

## 📊 What's Included

**With the one-command start, you get:**

✅ **Full AI Automation Platform**
- Multi-agent system with governance
- **AI Workflow Generator**: Create complex automations by simply describing them to the agent. ✨ NEW
- **Intelligent request routing**: Automatic classification and task delegation. ✨ NEW
- Workflow builder with visual editor
- Browser automation
- Device capabilities

✅ **Community Skills** ✨ NEW
- 5,000+ OpenClaw/ClawHub skills
- Import via GitHub URL
- Enterprise security with sandboxed execution
- Automatic governance integration

✅ **Vector Embeddings**
- Local generation (FastEmbed, 10-20ms)
- Semantic search
- Episodic memory
- LanceDB vector database

✅ **Integrations**
- 46+ pre-built integrations
- Slack, Gmail, HubSpot, Salesforce, etc.
- OAuth flows configured

✅ **All Data Local**
- SQLite database in `./data/`
- LanceDB vectors in `./data/lancedb/`
- 100% private, nothing leaves your machine

---

## 🎯 Alternative: Docker Start

If you prefer Docker (even simpler setup):

```bash
docker-compose -f docker-compose-personal.yml up -d
```

Then access at: **http://localhost:3000**

---

## 📚 Documentation

- [PERSONAL_EDITION.md](docs/PERSONAL_EDITION.md) - Full Docker guide
- [NATIVE_SETUP.md](docs/NATIVE_SETUP.md) - Detailed native setup
- [VECTOR_EMBEDDINGS.md](docs/VECTOR_EMBEDDINGS.md) - Embeddings guide
- [INSTALLATION_OPTIONS.md](docs/INSTALLATION_OPTIONS.md) - Method comparison

---

## 🎉 Summary

**One command is all you need:**

```bash
./start.sh  # macOS/Linux
start.bat    # Windows
```

**Then open:** http://localhost:3000

**Features ready:**
- ✅ Multi-agent automation
- ✅ 5,000+ community skills (OpenClaw/ClawHub)
- ✅ Semantic search
- ✅ Vector embeddings
- ✅ Episodic memory
- ✅ 46+ integrations
- ✅ All data local
- ✅ Zero cloud costs

**That's it!** 🚀
