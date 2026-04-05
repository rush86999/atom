# Atom - Mac Mini Installation Guide

> **Install Atom on your Mac mini in 5 minutes with simple commands**

This guide is specifically written for Mac mini users running macOS (Monterey, Ventura, Sonoma, or Sequoia). Atom Personal Edition runs entirely on your Mac mini using Docker, keeping all data local and private.

---

## Table of Contents

1. [Quick Start (5 minutes)](#quick-start-5-minutes)
2. [Prerequisites](#prerequisites)
3. [Step-by-Step Installation](#step-by-step-installation)
4. [Accessing Atom](#accessing-atom)
5. [Managing Atom](#managing-atom)
6. [Troubleshooting Mac-Specific Issues](#troubleshooting-mac-specific-issues)
7. [Optimizing for Mac mini](#optimizing-for-mac-mini)

---

## Quick Start (5 minutes)

### Prerequisites Check

Open **Terminal** (Command + Space, type "Terminal", press Enter) and run:

```bash
# Check if you have Docker installed
docker --version

# If you see "Docker version XX.XX.X", continue to Step 1
# If you see "command not found", install Docker Desktop first
```

**If Docker is not installed:** Download [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/) (Apple Silicon or Intel chip based on your Mac mini).

### Three Commands to Install Atom

```bash
# 1. Clone Atom repository
git clone https://github.com/rush86999/atom.git
cd atom

# 2. Copy environment template and configure
cp .env.personal .env

# 3. Edit the configuration file (required steps below)
nano .env
```

**In the `.env` file, you MUST set these minimum values:**

```bash
# Replace with your actual API key (get one from https://platform.openai.com/api-keys)
OPENAI_API_KEY=sk-your-actual-openai-key-here

# Generate two secure keys (run this command in Terminal)
openssl rand -base64 32
# Run it twice, copy each output to the values below:

BYOK_ENCRYPTION_KEY=paste-first-openssl-output-here
JWT_SECRET_KEY=paste-second-openssl-output-here
```

**Save and exit** (Control + O, Enter, Control + X)

### Start Atom

```bash
# Start all services
docker-compose -f docker-compose-personal.yml up -d

# Wait 30-60 seconds, then check status
docker-compose -f docker-compose-personal.yml ps
```

**Expected output:**
```
✅ atom-personal-backend    Up (healthy)
✅ atom-personal-frontend    Up
✅ atom-personal-valkey      Up (healthy)
✅ atom-personal-browser     Up
```

### Access Atom

Open Safari or Chrome: **http://localhost:3000**

That's it! Atom is now running on your Mac mini.

---

## Prerequisites

### System Requirements

- **Mac mini** (2018 or newer recommended)
- **macOS:** Monterey (12.x), Ventura (13.x), Sonoma (14.x), or Sequoia (15.x)
- **RAM:** 4GB minimum, 8GB recommended
- **Storage:** 10GB free space
- **Internet:** Required for AI provider API calls

### Required Software

1. **Docker Desktop for Mac**
   ```bash
   # Check if installed
   docker --version
   ```
   - Download: https://www.docker.com/products/docker-desktop/
   - Choose **Apple Silicon** (M1/M2/M3/M4) or **Intel Chip** based on your Mac
   - Install and **start Docker Desktop** from Applications

2. **Git** (usually pre-installed on macOS)
   ```bash
   # Check if installed
   git --version
   ```
   - If not installed: `xcode-select --install`

3. **AI Provider API Key** (at least one required)
   - **OpenAI** (Recommended): https://platform.openai.com/api-keys
   - **Anthropic** (Best for complex tasks): https://console.anthropic.com/
   - **DeepSeek** (Affordable): https://platform.deepseek.com/

---

## Step-by-Step Installation

### Step 1: Install Docker Desktop

1. Download Docker Desktop for Mac from https://www.docker.com/products/docker-desktop/
2. Open the downloaded `.dmg` file
3. Drag Docker to Applications
4. Open Docker from Applications
5. Wait for "Docker is running" in menu bar

**Verify Docker is running:**
```bash
docker --version
docker info
```

### Step 2: Clone Atom Repository

```bash
# Navigate to your preferred directory (optional)
cd ~/Documents  # or ~/Desktop, or ~/Projects

# Clone the repository
git clone https://github.com/rush86999/atom.git

# Enter the directory
cd atom
```

### Step 3: Configure Environment

```bash
# Copy the Personal Edition template
cp .env.personal .env

# Edit with nano (or use VS Code, TextEdit, etc.)
nano .env
```

**Minimum required configuration:**

```bash
# ============================================================================
# REQUIRED: AI Provider API Key (at least one)
# ============================================================================
# Get your key from: https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-proj-abc123xyz789  # Replace with your actual key

# OR use Anthropic (Claude): https://console.anthropic.com/
# ANTHROPIC_API_KEY=sk-ant-abc123xyz789

# ============================================================================
# REQUIRED: Encryption Keys (generate secure keys)
# ============================================================================
# Run this command TWICE in Terminal: openssl rand -base64 32
# Paste each output below:

BYOK_ENCRYPTION_KEY=your-first-openssl-output-32-chars
JWT_SECRET_KEY=your-second-openssl-output-32-chars
```

**Optional but recommended:**

```bash
# Enable local-only mode (blocks all cloud services except AI providers)
# Perfect for privacy-focused users
ATOM_LOCAL_ONLY=false  # Set to 'true' to block Spotify, Notion, etc.

# Adjust logging
LOG_LEVEL=INFO  # Options: DEBUG, INFO, WARNING, ERROR
```

**Save the file** (nano: Control + O, Enter, Control + X)

### Step 4: Generate Encryption Keys

Open a **new Terminal window** and run:

```bash
# Generate first key (for BYOK_ENCRYPTION_KEY)
openssl rand -base64 32
# Copy the entire output

# Generate second key (for JWT_SECRET_KEY)
openssl rand -base64 32
# Copy the entire output
```

Paste these into your `.env` file at the appropriate lines.

### Step 5: Start Atom Services

```bash
# Make sure you're in the atom directory
cd ~/Documents/atom  # or wherever you cloned it

# Start all services
docker-compose -f docker-compose-personal.yml up -d

# Watch the logs (optional, see services starting)
docker-compose -f docker-compose-personal.yml logs -f
```

**Press Control + C** to stop watching logs (services keep running)

### Step 6: Verify Installation

```bash
# Check all services are running
docker-compose -f docker-compose-personal.yml ps
```

**Expected output:**
```
NAME                      STATUS              PORTS
atom-personal-backend     Up (healthy)        0.0.0.0:8000->8000/tcp
atom-personal-frontend    Up                  0.0.0.0:3000->3000/tcp
atom-personal-valkey      Up (healthy)        0.0.0.0:6379->6379/tcp
atom-personal-browser     Up                  0.0.0.0:3001->3000/tcp
```

**Check health status:**
```bash
# Backend health check
curl http://localhost:8000/health/live

# Should return: {"status":"healthy"}
```

---

## Accessing Atom

### Web Dashboard

Open your browser and navigate to:

- **Main Dashboard:** http://localhost:3000
- **API Documentation:** http://localhost:8000/docs
- **ReDoc Documentation:** http://localhost:8000/redoc

### What's Included

Atom Personal Edition on Mac mini includes:

1. **Agent Chat** - Talk to AI agents in natural language
2. **Workflow Builder** - Create visual automation workflows
3. **Canvas Presentations** - Rich interactive presentations with charts
4. **Browser Automation** - Web scraping and form filling
5. **Episodic Memory** - Agents remember past interactions
6. **Agent Governance** - Agents progress from Student → Autonomous
7. **Community Skills** - Import 5,000+ OpenClaw/ClawHub skills
8. **Smart Home Control** - Philips Hue, Home Assistant integration
9. **Media Control** - Spotify, Sonos integration
10. **Vector Search** - Local semantic search with FastEmbed

---

## Managing Atom

### Start Atom

```bash
cd ~/Documents/atom  # or your installation directory
docker-compose -f docker-compose-personal.yml up -d
```

### Stop Atom

```bash
cd ~/Documents/atom
docker-compose -f docker-compose-personal.yml down
```

### View Logs

```bash
# All services
docker-compose -f docker-compose-personal.yml logs -f

# Specific service
docker-compose -f docker-compose-personal.yml logs -f atom-backend

# Last 100 lines
docker-compose -f docker-compose-personal.yml logs --tail=100
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
cd ~/Documents/atom
git pull origin main

# Rebuild and restart
docker-compose -f docker-compose-personal.yml up -d --build

# View logs during update
docker-compose -f docker-compose-personal.yml logs -f
```

### Backup Your Data

```bash
# Navigate to atom directory
cd ~/Documents/atom

# Create backup (includes database, embeddings, configs)
tar -czf atom-backup-$(date +%Y%m%d).tar.gz data/

# List backups
ls -lh atom-backup-*.tar.gz

# Restore from backup (if needed)
tar -xzf atom-backup-20240220.tar.gz
```

### Database Location

```bash
# SQLite database (all your agents, workflows, data)
~/Documents/atom/data/atom.db

# View with SQLite
sqlite3 ~/Documents/atom/data/atom.db
> .tables
> .schema agents
> SELECT * FROM agents LIMIT 10;
> .quit

# Or use DB Browser for SQLite (GUI app)
# Download from: https://sqlitebrowser.org/
```

---

## Troubleshooting Mac-Specific Issues

### Issue: "Command not found: docker"

**Solution:** Docker Desktop is not installed or not running.

```bash
# Install Docker Desktop for Mac
# Download from: https://www.docker.com/products/docker-desktop/

# After installation, start Docker Desktop from Applications
# Wait for Docker icon in menu bar to show "Docker is running"
```

### Issue: Port Already in Use (3000, 8000, or 6379)

**Error:** `Bind for 0.0.0.0:3000 failed: port is already allocated`

**Solution 1: Find what's using the port**
```bash
# Check what's using port 3000
lsof -i :3000

# Kill the process (replace PID with actual process ID)
kill -9 <PID>

# Or use the command directly
kill -9 $(lsof -t -i:3000)
```

**Solution 2: Change Atom's ports**

Edit `docker-compose-personal.yml`:
```yaml
# Change port mappings to avoid conflicts
ports:
  - "3001:3000"  # Access frontend at http://localhost:3001
  - "8001:8000"  # Access API at http://localhost:8001
```

Then restart:
```bash
docker-compose -f docker-compose-personal.yml up -d
```

### Issue: Docker "out of memory"

**Error:** Container killed due to OOM (Out of Memory)

**Solution:** Increase Docker memory limit

1. Open Docker Desktop
2. Go to **Settings** → **Resources** → **Advanced**
3. Increase **Memory** to at least 4GB (8GB recommended)
4. Click **Apply & Restart**

### Issue: Apple Silicon (M1/M2/M3/M4) Compatibility

**Solution:** Docker Desktop automatically detects your architecture. Atom runs natively on Apple Silicon.

```bash
# Verify architecture
docker info | grep "Architecture"
# Should show: aarch64 (Apple Silicon) or x86_64 (Intel)

# If issues occur, rebuild with platform specified
docker-compose -f docker-compose-personal.yml build --platform linux/arm64
```

### Issue: Services Not Starting (Container exits)

**Solution 1: Check logs**
```bash
docker-compose -f docker-compose-personal.yml logs atom-backend
```

**Solution 2: Verify `.env` file**
```bash
# Ensure no typos in API keys
cat .env | grep API_KEY

# Ensure encryption keys are set
cat .env | grep ENCRYPTION_KEY
```

**Solution 3: Clean restart**
```bash
# Stop all services
docker-compose -f docker-compose-personal.yml down

# Remove volumes (clears all data - only if needed!)
docker-compose -f docker-compose-personal.yml down -v
rm -rf data/

# Start fresh
docker-compose -f docker-compose-personal.yml up -d
```

### Issue: macOS Firewall Blocking Docker

**Error:** Cannot connect to Docker daemon

**Solution:**
1. Open **System Settings** → **Network** → **Firewall**
2. If Firewall is on, click **Options**
3. Ensure **Docker Desktop** is allowed to receive incoming connections
4. Or disable Firewall temporarily to test

### Issue: File System Events Not Working (Hot Reload)

**Symptom:** Code changes not reflected immediately

**Solution:** macOS file system events may be rate-limited

```bash
# Increase file system event limits
echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Or restart services manually
docker-compose -f docker-compose-personal.yml restart
```

---

## Optimizing for Mac mini

### Memory Optimization

If your Mac mini has limited RAM (4GB or less):

```bash
# Edit .env
nano .env

# Reduce concurrent agents
MAX_CONCURRENT_AGENTS=2

# Disable browser service if not needed
# Comment out 'browser-node' service in docker-compose-personal.yml
```

### Storage Optimization

```bash
# Check current storage usage
du -sh ~/Documents/atom/data/

# Clean up old Docker images
docker system prune -a

# Set log rotation
# Edit docker-compose-personal.yml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### Performance Tuning

```bash
# Give Docker more resources
# Docker Desktop → Settings → Resources
# - Memory: 4GB minimum
# - CPUs: 2 minimum
# - Disk: 20GB minimum

# Use fastembed for embeddings (already default in Personal Edition)
EMBEDDING_PROVIDER=fastembed  # Local, fast, free
```

### Auto-Start on Boot

**Option 1: Create a Launch Agent (macOS native)**

```bash
# Create Launch Agent plist
nano ~/Library/LaunchAgents/com.atom.personal.plist
```

Contents:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atom.personal</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/docker-compose</string>
        <string>-f</string>
        <string>/Users/YOUR_USERNAME/Documents/atom/docker-compose-personal.yml</string>
        <string>up</string>
        <string>-d</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/Documents/atom</string>
</dict>
</plist>
```

```bash
# Load the agent
launchctl load ~/Library/LaunchAgents/com.atom.personal.plist

# Unload (to stop auto-start)
launchctl unload ~/Library/LaunchAgents/com.atom.personal.plist
```

**Option 2: Docker Desktop Auto-Start**

1. Open Docker Desktop
2. Go to **Settings** → **General**
3. Enable **Start Docker Desktop when you log in**
4. Create a shell script to start Atom:

```bash
# Create startup script
nano ~/start-atom.sh
```

Contents:
```bash
#!/bin/bash
cd ~/Documents/atom
/usr/local/bin/docker-compose -f docker-compose-personal.yml up -d
```

```bash
# Make executable
chmod +x ~/start-atom.sh

# Add to Login Items
# System Settings → General → Login Items → + → select start-atom.sh
```

### Network Configuration

If your Mac mini is a headless server (remote access):

```bash
# Access Atom from other devices on your network
# Edit docker-compose-personal.yml

ports:
  - "0.0.0.0:3000:3000"  # Frontend
  - "0.0.0.0:8000:8000"  # API

# Find your Mac mini's IP address
ipconfig getifaddr en0  # Ethernet
ipconfig getifaddr en1  # Wi-Fi

# Access from other devices: http://YOUR_MAC_IP:3000
```

---

## Advanced Usage

### Enable Local Shell Access (Advanced)

⚠️ **WARNING:** This gives agents access to your Mac's filesystem. Only enable if you understand the risks.

```bash
# Edit .env
nano .env

# Add this line
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

### Local-Only Mode (Privacy)

Block all cloud services except AI providers:

```bash
# Edit .env
nano .env

# Enable local-only mode
ATOM_LOCAL_ONLY=true

# Restart services
docker-compose -f docker-compose-personal.yml restart
```

**Blocked services:** Spotify, Notion, Gmail, Slack
**Working services:** Hue, Home Assistant, Sonos, FFmpeg

### Monitor Resource Usage

```bash
# Check Docker container stats
docker stats

# Check disk usage
docker system df

# Check Mac mini resources
top -o cpu  # CPU usage
top -o mem  # Memory usage
df -h       # Disk usage
```

---

## Getting Help

### Documentation

- [Full Documentation](./README.md)
- [Personal Edition Guide](./PERSONAL_EDITION.md)
- [API Documentation](API_DOCUMENTATION_INDEX.md)
- [Troubleshooting](ERROR_HANDLING_GUIDELINES.md)

### Community

- **GitHub Issues:** https://github.com/rush86999/atom/issues
- **GitHub Discussions:** https://github.com/rush86999/atom/discussions

### Common Issues Quick Reference

| Issue | Solution |
|-------|----------|
| Docker not running | Open Docker Desktop from Applications |
| Port already in use | `lsof -i :3000` then `kill -9 <PID>` |
| Out of memory | Increase Docker memory in Settings → Resources |
| API key not working | Verify key in `.env`, restart services |
| Services not starting | Check logs: `docker-compose logs atom-backend` |
| Cannot access from network | Bind to `0.0.0.0` in docker-compose-personal.yml |

---

## Summary

**You now have Atom running on your Mac mini!** 🎉

- **Dashboard:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **Data stored in:** `~/Documents/atom/data/`
- **Configuration:** `~/Documents/atom/.env`

**Quick commands:**
```bash
# Start
cd ~/Documents/atom && docker-compose -f docker-compose-personal.yml up -d

# Stop
docker-compose -f docker-compose-personal.yml down

# View logs
docker-compose -f docker-compose-personal.yml logs -f

# Restart
docker-compose -f docker-compose-personal.yml restart
```

Enjoy automating with AI agents on your Mac mini! 🚀

---

*Last updated: March 20, 2026*
