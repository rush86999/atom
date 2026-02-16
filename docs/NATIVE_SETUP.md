# Atom Personal Edition - Native Installation (No Docker Required)

> **Run Atom directly on your computer without Docker - perfect for personal use and development**

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (5-10 minutes)](#quick-start-5-10-minutes)
3. [Installation Steps](#installation-steps)
4. [Running Atom](#running-atom)
5. [Managing Atom](#managing-atom)
6. [Troubleshooting](#troubleshooting)
7. [Native vs Docker](#native-vs-docker)

---

## Prerequisites

### Required Software

**Python 3.11+** (Required)
- macOS: `brew install python@3.11`
- Ubuntu/Debian: `sudo apt install python3.11 python3.11-venv`
- Windows: Download from [python.org](https://www.python.org/downloads/)
- Verify: `python3 --version` (should show 3.11 or higher)

**Node.js 18+** (Required for frontend)
- macOS: `brew install node`
- Ubuntu/Debian: `sudo apt install nodejs npm`
- Windows: Download from [nodejs.org](https://nodejs.org/)
- Verify: `node --version` (should show 18 or higher)

**Git** (Required)
- macOS: `brew install git`
- Ubuntu/Debian: `sudo apt install git`
- Windows: Download from [git-scm.com](https://git-scm.com/downloads/)
- Verify: `git --version`

**Optional but Recommended:**
- **pip** (Python package manager, comes with Python)
- **npm** (Node package manager, comes with Node.js)

### System Requirements

- **RAM:** 4GB minimum, 8GB recommended
- **Disk:** 5GB free space
- **OS:** macOS 10.15+, Ubuntu 20.04+, or Windows 10/11

---

## Quick Start (5-10 minutes)

### Option A: Using pip installer (Easiest)

```bash
# Install Atom directly via pip
pip3 install atom-os

# Generate encryption keys
openssl rand -base64 32  # Use for BYOK_ENCRYPTION_KEY
openssl rand -base64 32  # Use for JWT_SECRET_KEY

# Create .env file
mkdir -p ~/.atom
cat > ~/.atom/.env << EOF
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
BYOK_ENCRYPTION_KEY=<paste-first-key>
JWT_SECRET_KEY=<paste-second-key>
SQLITE_PATH=$HOME/.atom/data/atom.db
LANCEDB_PATH=$HOME/.atom/data/lancedb
EOF

# Start Atom
atom-os start --port 8000
```

**Access at:** http://localhost:8000

### Option B: From Source (More control)

```bash
# Clone repository
git clone https://github.com/rush86999/atom.git
cd atom

# Install backend dependencies
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Install frontend dependencies
cd ../frontend-nextjs
npm install

# Configure environment (see detailed steps below)
cd ..
cp .env.personal .env
# Edit .env and add your API keys

# Start backend
cd backend
source venv/bin/activate
python -m uvicorn main_api_app:app --host 0.0.0.0 --port 8000

# In another terminal, start frontend
cd frontend-nextjs
npm run dev
```

---

## Installation Steps

### Step 1: Clone Repository

```bash
# Clone Atom
git clone https://github.com/rush86999/atom.git
cd atom

# Verify Python version
python3 --version  # Should be 3.11 or higher
```

### Step 2: Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Verify installation
python -c "import fastapi; print('FastAPI installed')"
python -c "import sqlalchemy; print('SQLAlchemy installed')"
```

**Expected output:**
```
FastAPI installed
SQLAlchemy installed
```

### Step 3: Frontend Setup

```bash
# Navigate to frontend (new terminal)
cd frontend-nextjs

# Install dependencies
npm install

# Verify installation
npm run build  # Should complete without errors
```

### Step 4: Configure Environment

```bash
# Navigate to project root
cd ..

# Copy personal edition template
cp .env.personal .env

# Edit .env file
nano .env  # or use your favorite editor
```

**Minimum required settings:**
```bash
# AI Provider (at least one required)
OPENAI_API_KEY=sk-your-key-here
# OR
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Encryption keys (generate with: openssl rand -base64 32)
BYOK_ENCRYPTION_KEY=your-32-char-key-here
JWT_SECRET_KEY=your-different-32-char-key-here

# Database paths
SQLITE_PATH=./data/atom.db
LANCEDB_PATH=./data/lancedb
```

### Step 5: Initialize Database

```bash
# Create data directory
mkdir -p data

# Run database migrations
cd backend
source venv/bin/activate  # If not already activated
alembic upgrade head

# Verify database created
ls -la ../data/atom.db
```

---

## Running Atom

### Development Mode (Recommended for Personal Use)

**Terminal 1 - Backend:**
```bash
cd atom/backend
source venv/bin/activate
python -m uvicorn main_api_app:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Frontend:**
```bash
cd atom/frontend-nextjs
npm run dev
```

**Access:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Production Mode

**Using Python CLI:**
```bash
cd atom/backend
source venv/bin/activate
python -m cli.main start --port 8000 --workers 4
```

**Using gunicorn (more performant):**
```bash
cd atom/backend
source venv/bin/activate
pip install gunicorn
gunicorn main_api_app:app --workers 4 --bind 0.0.0.0:8000
```

### Background Service (Linux/macOS)

**Using systemd (Linux):**
```bash
# Create service file
sudo nano /etc/systemd/system/atom.service
```

**Content:**
```ini
[Unit]
Description=Atom AI Automation Platform
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/atom/backend
Environment="PATH=/home/your-username/atom/backend/venv/bin"
ExecStart=/home/your-username/atom/backend/venv/bin/gunicorn main_api_app:app --workers 4 --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable atom
sudo systemctl start atom
sudo systemctl status atom
```

**Using launchd (macOS):**
```bash
# Create plist file
nano ~/Library/LaunchAgents/com.atom.platform.plist
```

**Content:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atom.platform</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/your-username/atom/backend/venv/bin/gunicorn</string>
        <string>main_api_app:app</string>
        <string>--workers</string>
        <string>4</string>
        <string>--bind</string>
        <string>0.0.0.0:8000</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/your-username/atom/backend</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

**Load service:**
```bash
launchctl load ~/Library/LaunchAgents/com.atom.platform.plist
launchctl start com.atom.platform
```

---

## Managing Atom

### Start Atom

```bash
# Method 1: Using CLI (easiest)
cd atom/backend
source venv/bin/activate
python -m cli.main start

# Method 2: Direct uvicorn
cd atom/backend
source venv/bin/activate
python -m uvicorn main_api_app:app --host 0.0.0.0 --port 8000 --reload

# Method 3: Using gunicorn (production)
cd atom/backend
source venv/bin/activate
gunicorn main_api_app:app --workers 4 --bind 0.0.0.0:8000
```

### Stop Atom

```bash
# If using uvicorn with --reload, press Ctrl+C

# If using gunicorn
pkill -f gunicorn

# If using systemd
sudo systemctl stop atom

# If using launchd (macOS)
launchctl stop com.atom.platform
```

### Restart Atom

```bash
# systemd
sudo systemctl restart atom

# launchd
launchctl stop com.atom.platform
launchctl start com.atom.platform

# Manual
pkill -f "python.*main_api_app"
cd atom/backend
source venv/bin/activate
python -m uvicorn main_api_app:app --host 0.0.0.0 --port 8000
```

### View Logs

```bash
# If using systemd
sudo journalctl -u atom -f

# If using launchd
log stream --predicate 'process == "atom"'

# If running manually, logs are in terminal
# Or check backend logs
tail -f atom/backend/logs/atom.log
```

### Update Atom

```bash
# Navigate to project
cd atom

# Pull latest changes
git pull origin main

# Update backend dependencies
cd backend
source venv/bin/activate
pip install -r requirements.txt --upgrade

# Update frontend dependencies
cd ../frontend-nextjs
npm install

# Run migrations
cd ../backend
alembic upgrade head

# Restart Atom
# (use your preferred start method)
```

---

## Troubleshooting

### Issue: Port Already in Use

**Error:** `Address already in use`

**Solution:**
```bash
# Find process using port
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows

# Or use different port
python -m uvicorn main_api_app:app --port 8001
```

### Issue: Module Not Found

**Error:** `ModuleNotFoundError: No module named 'fastapi'`

**Solution:**
```bash
# Ensure virtual environment is activated
cd atom/backend
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate  # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Database Locked

**Error:** `sqlite3.OperationalError: database is locked`

**Solution:**
```bash
# Stop all Atom processes
pkill -f "python.*main_api_app"

# Wait 5 seconds
sleep 5

# Restart
cd atom/backend
source venv/bin/activate
python -m uvicorn main_api_app:app --host 0.0.0.0 --port 8000
```

### Issue: Frontend Can't Connect to Backend

**Error:** `Network error` or `Connection refused`

**Solution:**
1. Ensure backend is running: `curl http://localhost:8000/health/live`
2. Check frontend environment: `frontend-nextjs/.env.local`
3. Verify API URL: `NEXT_PUBLIC_API_URL=http://localhost:8000`

### Issue: Permission Denied

**Error:** `PermissionError: [Errno 13] Permission denied`

**Solution:**
```bash
# Check data directory permissions
ls -la data/

# Fix permissions
chmod 755 data/
chmod 644 data/atom.db

# Or run with correct user
python -m uvicorn main_api_app:app --port 8000
```

### Issue: Out of Memory

**Error:** `MemoryError` or process killed

**Solution:**
```bash
# Reduce workers
gunicorn main_api_app:app --workers 2 --bind 0.0.0.0:8000

# Or limit agent concurrency
# Edit .env:
MAX_CONCURRENT_AGENTS=2
```

---

## Native vs Docker

| Aspect | Native Installation | Docker Installation |
|--------|-------------------|-------------------|
| **Setup Complexity** | Medium (manual steps) | Low (one command) |
| **Performance** | Better (no container overhead) | Good (slight overhead) |
| **Isolation** | None (shared system) | Full (containerized) |
| **Portability** | System-specific | Platform-independent |
| **Resource Usage** | Lower | Higher |
| **Updates** | Manual (git pull) | Easy (docker pull) |
| **Development** | Easier (direct file access) | Requires volume mounts |
| **Production** | Requires more setup | Ready for deployment |

### When to Use Native Installation

✅ **Use Native when:**
- You don't have Docker installed
- You want maximum performance
- You're developing Atom itself
- You need direct file system access
- You're familiar with Python/Node.js
- You want to understand how Atom works

❌ **Use Docker when:**
- You want quick, easy setup
- You need full isolation
- You're deploying to production
- You want easy rollback
- You're not familiar with Python/Node.js

---

## Performance Optimization

### Backend Optimization

**1. Use gunicorn instead of uvicorn:**
```bash
# Development (uvicorn)
python -m uvicorn main_api_app:app --workers 1

# Production (gunicorn)
gunicorn main_api_app:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

**2. Enable caching:**
```bash
# Edit .env
ENABLE_GOVERNANCE_CACHE=true
CACHE_SIZE_MB=256
```

**3. Reduce logging:**
```bash
# Edit .env
LOG_LEVEL=WARNING  # Reduce log verbosity
```

### Frontend Optimization

**1. Build production bundle:**
```bash
cd frontend-nextjs
npm run build
npm run start  # Serve production build
```

**2. Enable compression:**
```bash
# Use nginx or Apache as reverse proxy
# Enable gzip compression
```

---

## Summary

**You're running Atom natively!** 🎉

- **Backend:** http://localhost:8000
- **Frontend:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **Data stored in:** `./data/`

**Quick Commands:**
```bash
# Start
cd backend && source venv/bin/activate && python -m uvicorn main_api_app:app --reload

# Stop
pkill -f "python.*main_api_app"

# Update
git pull && pip install -r requirements.txt --upgrade
```

**Advantages of Native Installation:**
- ✅ No Docker overhead
- ✅ Better performance
- ✅ Direct file access
- ✅ Easier debugging
- ✅ Lower resource usage

Enjoy running Atom directly on your system! 🚀
