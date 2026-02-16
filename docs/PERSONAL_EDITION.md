# Atom Personal Edition - Quick Start Guide

> **Run Atom on your local computer for personal automation and AI agent experimentation**

The Personal Edition is a simplified, streamlined version of Atom optimized for:
- Personal productivity automation
- AI agent experimentation and learning
- Local development and testing
- Privacy-focused automation (data never leaves your machine)

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (5 minutes)](#quick-start-5-minutes)
3. [Setup Instructions](#setup-instructions)
4. [Accessing Atom](#accessing-atom)
5. [Common Tasks](#common-tasks)
6. [Troubleshooting](#troubleshooting)
7. [Personal vs Full Edition](#personal-vs-full-edition)
8. [Next Steps](#next-steps)

---

## Prerequisites

### Required Software

- **Docker** (Desktop or Engine) - [Download Docker](https://www.docker.com/products/docker-desktop/)
- **Git** - [Download Git](https://git-scm.com/downloads)
- **At least one AI provider API key:**
  - [OpenAI](https://platform.openai.com/api-keys) (GPT-4/GPT-3.5) - **Recommended**
  - [Anthropic](https://console.anthropic.com/) (Claude 3.5 Sonnet) - **Best for complex tasks**
  - [DeepSeek](https://platform.deepseek.com/) (Affordable alternative)

### System Requirements

- **RAM:** 4GB minimum, 8GB recommended
- **Disk:** 10GB free space
- **OS:** macOS, Linux, or Windows 10/11 with WSL2

---

## Quick Start (5 minutes)

### 1. Clone and Configure

```bash
# Clone the repository
git clone https://github.com/rush86999/atom.git
cd atom

# Copy personal edition environment template
cp .env.personal .env

# Edit .env and add your API keys
# At minimum, set: OPENAI_API_KEY or ANTHROPIC_API_KEY
nano .env  # or use your favorite editor
```

### 2. Generate Encryption Keys

```bash
# Generate secure encryption keys
openssl rand -base64 32

# Copy the output and set these in .env:
# BYOK_ENCRYPTION_KEY=<paste-output>
# JWT_SECRET_KEY=<run-again-and-paste-second-output>
```

### 3. Start Atom

```bash
# Start all services
docker-compose -f docker-compose-personal.yml up -d

# Wait for services to start (30-60 seconds)
# Check status:
docker-compose -f docker-compose-personal.yml ps
```

### 4. Access Atom

Open your browser: **http://localhost:3000**

That's it! 🎉 Atom is now running on your local machine.

### 5. (Optional) Verify Vector Embeddings

Test that vector embeddings are working properly:

```bash
# Run embeddings test
python3 test-embeddings.py
```

Expected output:
```
✅ Provider: fastembed
✅ Model: BAAI/bge-small-en-v1.5
✅ Generated 384-dimensional vector
✅ Semantic similarity working correctly!
✅ Vector storage ready
```

**Learn more:** [Vector Embeddings Guide](VECTOR_EMBEDDINGS.md)

---

## Setup Instructions

### Step 1: Install Docker

**macOS:**
```bash
# Download Docker Desktop for Mac
# https://www.docker.com/products/docker-desktop/
```

**Linux (Ubuntu/Debian):**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker
```

**Windows:**
- Download Docker Desktop for Windows
- Enable WSL2 in Docker settings
- Restart your computer

### Step 2: Get AI Provider API Keys

**Option A: OpenAI (Recommended)**
1. Visit https://platform.openai.com/api-keys
2. Sign up or log in
3. Click "Create new secret key"
4. Copy the key (starts with `sk-`)

**Option B: Anthropic (Best for complex tasks)**
1. Visit https://console.anthropic.com/
2. Sign up or log in
3. Go to API Keys section
4. Create new key and copy it

**Option C: DeepSeek (Affordable)**
1. Visit https://platform.deepseek.com/
2. Sign up for free account
3. Get API key from dashboard

### Step 3: Configure Environment

```bash
# Navigate to Atom directory
cd atom

# Copy personal edition template
cp .env.personal .env

# Edit .env file
nano .env
```

**Minimum required settings in `.env`:**
```bash
# Set at least one AI provider key
OPENAI_API_KEY=sk-your-key-here
# OR
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Set encryption keys (generate with: openssl rand -base64 32)
BYOK_ENCRYPTION_KEY=your-32-char-key-here
JWT_SECRET_KEY=your-different-32-char-key-here
```

### Step 4: Start Services

```bash
# Create data directory for persistence
mkdir -p data

# Start Atom Personal Edition
docker-compose -f docker-compose-personal.yml up -d

# Watch logs (optional, Ctrl+C to exit log view)
docker-compose -f docker-compose-personal.yml logs -f
```

**Expected output:**
```
✅ atom-personal-backend - Up (healthy)
✅ atom-personal-frontend - Up
✅ atom-personal-browser - Up
```

---

## Accessing Atom

### Web Dashboard

Open your browser and navigate to:

- **Main Dashboard:** http://localhost:3000
- **API Documentation:** http://localhost:8000/docs
- **ReDoc Documentation:** http://localhost:8000/redoc

### Default Features Available

1. **Agent Chat** - Talk to AI agents with natural language
2. **Workflow Builder** - Create visual automation workflows
3. **Canvas Presentations** - Rich interactive presentations
4. **Browser Automation** - Web scraping and form filling
5. **Episodic Memory** - Agents remember past interactions
6. **Agent Governance** - Agents progress from Student → Autonomous

---

## Common Tasks

### View Logs

```bash
# All services
docker-compose -f docker-compose-personal.yml logs -f

# Specific service
docker-compose -f docker-compose-personal.yml logs -f atom-backend
docker-compose -f docker-compose-personal.yml logs -f atom-frontend
```

### Stop Atom

```bash
# Stop all services
docker-compose -f docker-compose-personal.yml down

# Stop and remove all data (clean slate)
docker-compose -f docker-compose-personal.yml down -v
rm -rf data/
```

### Restart Atom

```bash
# Restart all services
docker-compose -f docker-compose-personal.yml restart

# Restart specific service
docker-compose -f docker-compose-personal.yml restart atom-backend
```

### Update Atom

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose -f docker-compose-personal.yml up -d --build

# View logs during update
docker-compose -f docker-compose-personal.yml logs -f
```

### Access Database

```bash
# SQLite database location
./data/atom.db

# Query with sqlite3
sqlite3 data/atom.db
> .tables
> .schema agents
> SELECT * FROM agents LIMIT 10;

# Or use DB Browser for SQLite (GUI)
# https://sqlitebrowser.org/
```

### Backup Your Data

```bash
# Create backup
tar -czf atom-backup-$(date +%Y%m%d).tar.gz data/

# Restore from backup
tar -xzf atom-backup-20240216.tar.gz
```

---

## Troubleshooting

### Issue: Port Already in Use

**Error:** `Bind for 0.0.0.0:3000 failed: port is already allocated`

**Solution:**
```bash
# Check what's using the port
lsof -i :3000  # macOS/Linux
netstat -ano | findstr :3000  # Windows

# Change ports in docker-compose-personal.yml
# Edit line: "3000:3000" → "3001:3000"
```

### Issue: API Key Not Working

**Error:** `401 Unauthorized` or `Invalid API key`

**Solution:**
1. Verify your API key is correct (no extra spaces)
2. Check API key hasn't expired
3. Ensure you have credits/balance on your AI provider account
4. Restart services: `docker-compose -f docker-compose-personal.yml restart`

### Issue: Services Not Starting

**Error:** Container exits immediately

**Solution:**
```bash
# Check logs
docker-compose -f docker-compose-personal.yml logs atom-backend

# Common issues:
# 1. Missing .env file → Copy from .env.personal
# 2. Invalid encryption keys → Regenerate with openssl
# 3. Port conflicts → Change ports in docker-compose-personal.yml
```

### Issue: Database Locked

**Error:** `database is locked`

**Solution:**
```bash
# Stop all services
docker-compose -f docker-compose-personal.yml down

# Wait 5 seconds
sleep 5

# Restart
docker-compose -f docker-compose-personal.yml up -d
```

### Issue: Out of Memory

**Error:** Container killed due to OOM

**Solution:**
1. Increase Docker memory limit (Docker Desktop → Settings → Resources → Memory)
2. Reduce concurrent agents in `.env`: `MAX_CONCURRENT_AGENTS=2`
3. Disable browser service if not needed (comment out in docker-compose-personal.yml)

---

## Personal vs Full Edition

| Feature | Personal Edition | Full Edition |
|---------|-----------------|--------------|
| **Database** | SQLite (simpler, no external DB) | PostgreSQL (production-ready) |
| **Setup Time** | 5-10 minutes | 15-30 minutes |
| **Services** | Backend, Frontend, Browser (optional) | All services including monitoring |
| **Use Case** | Personal use, development | Production deployment |
| **Scalability** | Single user, light usage | Multi-user, enterprise |
| **Data Storage** | Local `./data` directory | Docker volumes with backups |
| **Configuration** | `.env.personal` template | Full `.env.example` |

**When to use Personal Edition:**
- ✅ Personal productivity automation
- ✅ Learning and experimentation
- ✅ Local development
- ✅ Privacy-focused automation
- ✅ Testing before production deployment

**When to use Full Edition:**
- ✅ Multi-user environment
- ✅ Production deployment
- ✅ Enterprise features (monitoring, metrics)
- ✅ High-scale automation
- ✅ Team collaboration

---

## Next Steps

### 1. Create Your First Agent

1. Open http://localhost:3000
2. Click "Create Agent"
3. Name your agent (e.g., "Personal Assistant")
4. Set maturity level to "STUDENT" (for learning)
5. Add capabilities: "General assistance, web search, email"
6. Click "Create"

### 2. Try Example Workflows

**Email Triage Workflow:**
1. Go to Workflows → Create New
2. Add trigger: "New email in Gmail"
3. Add action: "Analyze sentiment and urgency"
4. Add action: "Flag high-priority emails"
5. Enable workflow

**Web Research Workflow:**
1. Go to Workflows → Create New
2. Add manual trigger
3. Add action: "Search web for topic"
4. Add action: "Summarize findings"
5. Add action: "Create markdown report"

### 3. Explore Features

- **Agent Chat:** Talk to your agents in natural language
- **Canvas:** View rich presentations with charts and forms
- **Browser Automation:** Automate web tasks (scraping, form filling)
- **Episodic Memory:** Agents remember and learn from past interactions
- **Agent Graduation:** Promote agents as they demonstrate reliability

### 4. Integrate Your Services

**Gmail:**
1. Go to Integrations → Gmail
2. Click "Connect"
3. Authorize with Google
4. Grant permissions

**Slack:**
1. Go to Integrations → Slack
2. Create Slack app (link provided)
3. Install app to workspace
4. Add bot token and OAuth credentials

**More integrations:** HubSpot, Salesforce, Asana, Jira, and 40+ more

---

## Advanced Configuration

### Enable Host Shell Access (Advanced)

⚠️ **WARNING:** This gives agents access to your local filesystem. Only enable if you understand the risks.

```bash
# Edit .env
ATOM_HOST_MOUNT_ENABLED=true

# Restart services
docker-compose -f docker-compose-personal.yml restart
```

**Safety features:**
- ✅ AUTONOMOUS maturity gate required
- ✅ Command whitelist (ls, cat, grep, git, etc.)
- ✅ Blocked commands (rm, mv, chmod, kill, sudo, etc.)
- ✅ 5-minute timeout enforcement
- ✅ Full audit trail

### Adjust Resource Limits

Edit `docker-compose-personal.yml`:

```yaml
services:
  atom-backend:
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
```

### Enable Development Mode

For faster development with hot reload:

```yaml
command: uvicorn main_api_app:app --host 0.0.0.0 --port 8000 --reload --log-level debug
```

---

## Getting Help

### Documentation

- [Full Documentation](./README.md)
- [API Documentation](./docs/API_DOCUMENTATION.md)
- [Development Guide](./docs/DEVELOPMENT.md)
- [Architecture](./docs/ARCHITECTURE.md)

### Community

- GitHub Issues: https://github.com/rush86999/atom/issues
- Discussions: https://github.com/rush86999/atom/discussions

### Troubleshooting Tips

1. **Check logs first:** `docker-compose logs -f`
2. **Verify .env file:** Ensure no typos in API keys
3. **Restart services:** Often fixes transient issues
4. **Clean restart:** `docker-compose down -v && docker-compose up -d`
5. **Check Docker resources:** Ensure enough memory allocated

---

## Summary

**You now have Atom running locally!** 🎉

- **Dashboard:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **Data stored in:** `./data/`
- **Configuration:** `.env`

**Quick commands:**
```bash
# Start
docker-compose -f docker-compose-personal.yml up -d

# View logs
docker-compose -f docker-compose-personal.yml logs -f

# Stop
docker-compose -f docker-compose-personal.yml down

# Restart
docker-compose -f docker-compose-personal.yml restart
```

Enjoy automating with AI agents on your local machine! 🚀
