# Atom Personal Edition - User Guide

> **Complete guide to running Atom on your local computer for personal automation**

The Atom Personal Edition brings AI-powered automation to your home computer with privacy-first design, local-only operation, and comprehensive integrations for music, smart home, productivity, and creative workflows.

---

## Table of Contents

1. [Quick Start (5 Minutes)](#quick-start-5-minutes)
2. [Configuration](#configuration)
3. [Local-Only Mode]((#local-only-mode-privacy))
4. [Agent Commands]((#agent-commands))
5. [Troubleshooting]((#troubleshooting))
6. [Advanced Configuration]((#advanced-configuration))
7. [Security Best Practices]((#security-best-practices))
8. [Getting Help]((#getting-help))

---

## Quick Start (5 Minutes)

### 1. Install Prerequisites

**Required:**
- **Docker Desktop:** https://www.docker.com/products/docker-desktop
- **Git:** https://git-scm.com/downloads

**At least one AI provider (choose one):**
- OpenAI: https://platform.openai.com/api-keys (Recommended)
- Anthropic: https://console.anthropic.com/ (Best for complex tasks)
- DeepSeek: https://platform.deepseek.com/ (Affordable)

### 2. Clone and Start

```bash
# Clone the repository
git clone https://github.com/your-org/atom.git
cd atom

# Copy personal edition environment template
cp .env.personal .env

# Edit .env and add at least one AI provider key
nano .env
```

**Minimum .env configuration:**
```bash
# Required: One AI provider
OPENAI_API_KEY=sk-your-key-here
# OR
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Required: Encryption keys (generate with: openssl rand -base64 32)
BYOK_ENCRYPTION_KEY=your-32-char-key-here
JWT_SECRET_KEY=your-32-char-key-here

# Optional: Enable local-only mode for privacy
ATOM_LOCAL_ONLY=false
```

### 3. Start Atom

```bash
# Start all services
docker-compose -f docker-compose-personal.yml up -d

# Wait 30-60 seconds for services to start
docker-compose -f docker-compose-personal.yml ps
```

**Expected output:**
```
✅ atom-personal-backend - Up (healthy)
✅ atom-personal-frontend - Up
✅ atom-personal-valkey - Up (healthy)
✅ atom-personal-browser - Up
```

### 4. Access Atom

- **Frontend:** http://localhost:3000
- **API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

### 5. Stop Atom

```bash
docker-compose -f docker-compose-personal.yml down
```

---

## Configuration

### Required Settings

**AI Provider (at least one):**
```bash
# OpenAI (recommended)
OPENAI_API_KEY=sk-your-key-here

# Anthropic (best for complex tasks)
ANTHROPIC_API_KEY=sk-ant-your-key-here

# DeepSeek (affordable)
DEEPSEEK_API_KEY=your-deepseek-key
```

**Encryption Keys:**
```bash
# Generate with: openssl rand -base64 32
BYOK_ENCRYPTION_KEY=your-32-char-key-here
JWT_SECRET_KEY=your-32-char-key-here
```

### Optional Integrations

#### Music Control (Spotify)

**Setup:**
1. Create Spotify app: https://developer.spotify.com/dashboard
2. Create app, set Redirect URI: `http://localhost:8000/integrations/spotify/callback`
3. Set scopes: `user-read-playback-state`, `user-modify-playback-state`, `user-read-currently-playing`
4. Copy Client ID and Client Secret

**Configuration:**
```bash
SPOTIFY_CLIENT_ID=your-client-id
SPOTIFY_CLIENT_SECRET=your-client-secret
SPOTIFY_REDIRECT_URI=http://localhost:8000/integrations/spotify/callback
```

**Authorize in UI:**
1. Open http://localhost:3000
2. Navigate to Settings → Integrations → Spotify
3. Click "Authorize"
4. Grant permissions on Spotify page

**Agent Commands:**
- "Pause the music"
- "Play my focus playlist"
- "Skip this track"
- "Volume to 50%"
- "What's playing?"

#### Smart Home (Philips Hue)

**Setup:**
1. Find your Hue bridge IP (check router or Hue app)
2. Generate API key: Hue app → Settings → Hue Bridge → Local API
3. Or press link button on bridge and use automation tools

**Configuration:**
```bash
HUE_BRIDGE_IP=192.168.1.50
HUE_API_KEY=your-api-key-here
```

**Agent Commands:**
- "Turn on the living room light"
- "Set bedroom to blue"
- "Activate movie scene"
- "What's the thermostat set to?"
- "Turn off all lights"

**Auto-discovery:**
Hue bridges on local network are auto-discovered via mDNS. If discovery fails (common in Docker), set `HUE_BRIDGE_IP` manually.

#### Smart Home (Home Assistant)

**Setup:**
1. Create long-lived token: Home Assistant → Settings → Profile → Long-Lived Access Tokens
2. For Docker networking, use `host.docker.internal` to access HA on host machine

**Configuration:**
```bash
HOME_ASSISTANT_URL=http://host.docker.internal:8123
HOME_ASSISTANT_TOKEN=your-long-lived-token-here
```

**Agent Commands:**
- "Turn on the office fan"
- "Set thermostat to 72 degrees"
- "Trigger good night automation"
- "What's the living room temperature?"
- "Is the garage door open?"

#### Productivity (Notion)

**Option 1: OAuth (recommended)**
1. Create integration: https://www.notion.so/my-integrations
2. Set OAuth redirect: `http://localhost:8000/integrations/notion/callback`

**Configuration:**
```bash
NOTION_CLIENT_ID=your-client-id
NOTION_CLIENT_SECRET=your-client-secret
NOTION_REDIRECT_URI=http://localhost:8000/integrations/notion/callback
```

**Option 2: API Key (simpler)**
1. Create integration: https://www.notion.so/my-integrations
2. Copy "Internal Integration Token"

**Configuration:**
```bash
NOTION_API_KEY=secret_your-api-key-here
```

**Agent Commands:**
- "Create a task for tomorrow's meeting"
- "Search for pages about project X"
- "Add this to my todo list"
- "Show me tasks due this week"
- "Mark the meeting task as complete"

#### Creative Tools (FFmpeg)

FFmpeg is pre-installed in the Docker image. No configuration needed!

**Agent Commands:**
- "Trim the screencast from 5:00 to 10:00"
- "Extract audio from the meeting recording"
- "Generate thumbnails for my videos"
- "Convert this video to WebM"
- "Normalize the audio volume"

**Allowed Directories:**
```bash
# Default (in .env.personal):
FFMPEG_ALLOWED_DIRS=/app/data/media,/app/data/exports

# Custom paths:
FFMPEG_ALLOWED_DIRS=/app/data/media,/app/data/exports,/Users/username/Videos
```

**Note:** FFmpeg operations require AUTONOMOUS agent maturity level for safety.

---

## Local-Only Mode (Privacy)

Enable local-only mode to block all cloud services for maximum privacy.

### Enable Local-Only Mode

```bash
# In .env
ATOM_LOCAL_ONLY=true
```

### What Works in Local-Only Mode

✅ **Local Network Services:**
- Sonos speakers (local network control)
- Philips Hue lights (local API)
- Home Assistant (local instance)
- FFmpeg video/audio processing (local)

### What's Blocked in Local-Only Mode

❌ **Cloud Services:**
- Spotify (requires cloud API)
- Notion (requires cloud API)
- Any OAuth-based external service

### Privacy Guarantees

- **All tokens stored encrypted** in database (AES-256-GCM)
- **Audit logs track all device/media actions** (`data/logs/audit.log`)
- **No telemetry or metrics** sent to external servers
- **Docker network isolation** prevents data leaks
- **Local-only mode enforcement** at application level

### Switching Modes

```bash
# Disable local-only mode to use cloud services
atomoset ATOM_LOCAL_ONLY=false

# Restart services
docker-compose -f docker-compose-personal.yml restart backend
```

---

## Agent Commands

### Music Control

- "Pause the music"
- "Play my focus playlist"
- "Skip this track"
- "Previous track"
- "Volume to 50%"
- "Volume up"
- "Volume down"
- "What's playing?"
- "Show me my playlists"
- "Play artist Radiohead"

### Smart Home

- "Turn on the living room light"
- "Turn off all lights"
- "Set bedroom to blue"
- "Set brightness to 50%"
- "Activate movie scene"
- "Activate reading scene"
- "What's the thermostat set to?"
- "Set thermostat to 72 degrees"
- "Turn on the fan"
- "Is the garage door open?"

### Productivity

- "Create a task for tomorrow's meeting"
- "Create a task 'Buy groceries' in todo list"
- "Search for pages about project X"
- "Show me all tasks"
- "Show me tasks due this week"
- "Add meeting notes to project page"
- "Mark task as complete"
- "What's on my calendar today?"

### Creative Tools

- "Trim the screencast from 5:00 to 10:00"
- "Trim video from 1:30 to 5:00"
- "Extract audio from the meeting recording"
- "Extract audio as MP3"
- "Generate thumbnail at 30 seconds"
- "Generate 10 thumbnails for video"
- "Convert this video to WebM"
- "Convert to MP4 format"
- "Normalize the audio volume"

---

## Troubleshooting

### Port Already in Use

**Problem:** Ports 8000, 3000, or 6379 already in use.

**Solution:**
```bash
# Check what's using the port
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill the process OR change port in docker-compose-personal.yml
```

### Hue Bridge Not Found

**Problem:** mDNS discovery fails in Docker.

**Solution:**
```bash
# Set bridge IP manually in .env
HUE_BRIDGE_IP=192.168.1.50

# Find bridge IP:
# - Check router admin → DHCP clients
# - Use Hue app → Settings → Hue Bridge → Network Info
```

### Home Assistant Connection Failed

**Problem:** Backend can't reach Home Assistant.

**Solution:**
```bash
# Use host.docker.internal for Docker containers
HOME_ASSISTANT_URL=http://host.docker.internal:8123

# Verify HA is running:
curl http://localhost:8123/api/states

# Check token is valid long-lived access token (not normal token)
```

### FFmpeg Not Found

**Problem:** FFmpeg command fails.

**Solution:**
```bash
# FFmpeg is pre-installed in Docker image. Verify:
docker exec -it atom-personal-backend which ffmpeg

# If missing, rebuild image:
docker-compose -f docker-compose-personal.yml build backend
docker-compose -f docker-compose-personal.yml up -d
```

### Spotify Authorization Fails

**Problem:** OAuth callback fails or redirect URI mismatch.

**Solution:**
```bash
# Verify Redirect URI matches exactly in Spotify dashboard:
SPOTIFY_REDIRECT_URI=http://localhost:8000/integrations/spotify/callback

# Common issues:
# - Missing http:// or https://
# - Wrong port (must be 8000, not 3000)
# - Trailing slash (/) mismatch
# - Spelling or capitalization

# Ensure Client ID and Secret are correct (no extra spaces)
```

### Database Locked

**Problem:** SQLite database is locked.

**Solution:**
```bash
# Reset database (CAUTION: loses all data)
docker-compose -f docker-compose-personal.yml down
rm data/atom.db
docker-compose -f docker-compose-personal.yml up -d
```

### Out of Memory

**Problem:** Container crashes due to memory.

**Solution:**
```bash
# Increase Docker memory limit:
# Docker Desktop → Settings → Resources → Memory → 8GB

# Or reduce worker processes in .env:
WORKERS=1  # Reduce from default 4
```

---

## Advanced Configuration

### Custom FFmpeg Directories

**Default directories:**
```bash
FFMPEG_ALLOWED_DIRS=/app/data/media,/app/data/exports
```

**Add custom paths:**
```bash
# In .env
FFMPEG_ALLOWED_DIRS=/app/data/media,/app/data/exports,/custom/path
```

**Mount host directory:**
```yaml
# In docker-compose-personal.yml
services:
  backend:
    volumes:
      - ./my-videos:/app/data/custom:rw  # Add this line
```

### Audit Log Retention

**Default:** 90 days

**Custom retention:**
```bash
# In .env
AUDIT_LOG_RETENTION_DAYS=365  # Keep for 1 year
```

**View audit logs:**
```bash
# View logs
tail -f data/logs/audit.log

# Search logs
grep "spotify" data/logs/audit.log
```

### Database Migration

**Run migrations:**
```bash
# Enter backend container
docker exec -it atom-personal-backend bash

# Run migrations
alembic upgrade head

# Check migration status
alembic current

# View migration history
alembic history
```

### Backup Data

**Backup all data:**
```bash
# Stop services first
docker-compose -f docker-compose-personal.yml down

# Backup data directory
cp -r data data-backup-$(date +%Y%m%d)

# Restart services
docker-compose -f docker-compose-personal.yml up -d
```

**Restore from backup:**
```bash
# Stop services
docker-compose -f docker-compose-personal.yml down

# Restore data
rm -rf data
cp -r data-backup-20260220 data

# Restart services
docker-compose -f docker-compose-personal.yml up -d
```

### Enable Debug Logging

**Temporary (current session):**
```bash
# View backend logs
docker-compose -f docker-compose-personal.yml logs -f backend

# With timestamps
docker-compose -f docker-compose-personal.yml logs -f --timestamps backend
```

**Permanent (all sessions):**
```bash
# In .env
LOG_LEVEL=DEBUG
```

### Performance Tuning

**Reduce memory usage:**
```bash
# In .env
WORKERS=1  # Reduce CPU workers
MAX_UPLOAD_SIZE=10485760  # 10MB max upload
```

**Increase performance:**
```bash
# In docker-compose-personal.yml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G
```

---

## Security Best Practices

### 1. Generate Strong Encryption Keys

```bash
# Generate 32-byte (256-bit) keys
openssl rand -base64 32

# Use different keys for BYOK_ENCRYPTION_KEY and JWT_SECRET_KEY
```

### 2. Never Commit .env File

```bash
# .env is in .gitignore for your protection
git status  # Should NOT show .env file

# If accidentally committed, rotate keys immediately
openssl rand -base64 32  # Generate new keys
```

### 3. Use Long-Lived Tokens for Local Services

- **Hue:** Use local API key (not cloud account)
- **Home Assistant:** Use long-lived access token (not password)
- **Spotify/Notion:** OAuth tokens expire automatically (refreshed automatically)

### 4. Enable Local-Only Mode for Privacy

```bash
# Blocks all cloud services
ATOM_LOCAL_ONLY=true
```

**Use cases:**
- Sensitive data processing
- Offline environments
- Privacy-critical automation
- Testing without external dependencies

### 5. Review Audit Logs Regularly

**Location:** `data/logs/audit.log`

**What's logged:**
- All media control actions (Spotify play/pause, Sonos control)
- All smart home actions (Hue lights, Home Assistant automations)
- All FFmpeg operations (file paths, operations performed)
- All blocked local-only mode attempts
- Agent IDs and user IDs for accountability

**Example entry:**
```json
{
  "timestamp": "2026-02-20T12:34:56.789Z",
  "user_id": "user_123",
  "agent_id": "agent_autonomous_1",
  "action": "hue_set_light",
  "category": "smarthome",
  "service": "hue",
  "details": {"light_id": "1", "state": {"on": true, "brightness": 200}},
  "result": "success"
}
```

### 6. Network Security

**Docker network isolation:**
- All services run in isolated Docker network
- No exposed ports except 3000 (frontend) and 8000 (API)
- Valkey (Redis) not exposed to host machine

**Firewall recommendations:**
```bash
# Only allow local access (Linux)
sudo ufw deny 8000/tcp
sudo ufw allow from 127.0.0.1 to any port 8000
```

### 7. Regular Updates

```bash
# Update Atom code
git pull origin main

# Rebuild Docker images
docker-compose -f docker-compose-personal.yml build

# Restart services
docker-compose -f docker-compose-personal.yml up -d
```

---

## Getting Help

### Documentation

- **Main Docs:** https://docs.atom.ai
- **API Reference:** http://localhost:8000/docs (when running)
- **GitHub Issues:** https://github.com/your-org/atom/issues
- **Discord:** https://discord.gg/atom

### Debug Mode

**Enable debug logging:**
```bash
# View real-time logs
docker-compose -f docker-compose-personal.yml logs -f backend

# Check service health
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready

# View Prometheus metrics
curl http://localhost:8000/health/metrics
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Services won't start | Check Docker Desktop is running, verify ports not in use |
| Can't access frontend | Wait 60 seconds for services to start, check `docker-compose ps` |
| Agent not responding | Check API key is valid, verify LLM provider is accessible |
| Smart home not working | Verify device is on local network, check API token, test IP connectivity |
| FFmpeg operation fails | Check file path is in allowed directories, verify input file exists |

### Getting Support

1. **Check logs first:** `docker-compose logs backend`
2. **Search GitHub issues:** https://github.com/your-org/atom/issues
3. **Ask on Discord:** https://discord.gg/atom
4. **Create bug report:** Include logs, .env (with secrets redacted), system info

### System Information for Bug Reports

```bash
# Collect system info
docker-compose -f docker-compose-personal.yml ps > docker-ps.txt
docker-compose -f docker-compose-personal.yml logs --tail=100 backend > backend-logs.txt
docker version > docker-version.txt
uname -a > system-info.txt  # macOS/Linux
systeminfo > system-info.txt  # Windows
```

---

## Appendix

### Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | No* | - | OpenAI API key (one AI provider required) |
| `ANTHROPIC_API_KEY` | No* | - | Anthropic API key (one AI provider required) |
| `DEEPSEEK_API_KEY` | No* | - | DeepSeek API key (one AI provider required) |
| `BYOK_ENCRYPTION_KEY` | Yes | - | Encryption key for token storage (32 bytes) |
| `JWT_SECRET_KEY` | Yes | - | JWT signing key (32 bytes) |
| `ATOM_LOCAL_ONLY` | No | `false` | Enable local-only mode (blocks cloud services) |
| `SPOTIFY_CLIENT_ID` | No | - | Spotify OAuth client ID |
| `SPOTIFY_CLIENT_SECRET` | No | - | Spotify OAuth client secret |
| `HUE_BRIDGE_IP` | No | - | Hue bridge IP address (auto-discovery fallback) |
| `HUE_API_KEY` | No | - | Hue API v2 key |
| `HOME_ASSISTANT_URL` | No | - | Home Assistant URL |
| `HOME_ASSISTANT_TOKEN` | No | - | Home Assistant long-lived access token |
| `NOTION_API_KEY` | No | - | Notion integration token |
| `FFMPEG_ALLOWED_DIRS` | No | `/app/data/media,/app/data/exports` | FFmpeg allowed directories |
| `AUDIT_LOG_RETENTION_DAYS` | No | `90` | Audit log retention in days |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Docker Compose Services

| Service | Ports | Description |
|---------|-------|-------------|
| `backend` | 8000 | FastAPI backend with agent execution |
| `frontend` | 3000 | Next.js frontend web UI |
| `valkey` | - | Valkey (Redis-compatible) for agent communication |
| `browser` | - | Playwright browser for web automation |

### File Structure

```
atom/
├── .env.personal              # Personal Edition environment template
├── docker-compose-personal.yml # Personal Edition Docker services
├── backend/
│   ├── core/                  # Core services
│   ├── tools/                 # Agent tools (media, smarthome, etc.)
│   └── api/                   # API endpoints
├── frontend-nextjs/           # Web UI
├── data/                      # Data directory (created on first run)
│   ├── atom.db               # SQLite database
│   ├── logs/                 # Audit logs
│   ├── media/                # FFmpeg input/output
│   └── exports/              # FFmpeg exports
└── docs/                     # Documentation
    └── PERSONAL_EDITION_GUIDE.md  # This file
```

---

**Version:** 1.0.0
**Last Updated:** February 20, 2026
**For Atom Version:** Phase 66 (Personal Edition Enhancements)
