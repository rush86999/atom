# Atom Interactive Installation Script - Quick Guide

> **Install Atom on Mac mini with one interactive script**

## Quick Start

### Option 1: Clone and Run (Recommended)

```bash
# Clone repository
git clone https://github.com/rush86999/atom.git
cd atom

# Run interactive installer
bash install-mac-mini.sh
```

### Option 2: Download Script Only

```bash
# Download installer script
curl -O https://raw.githubusercontent.com/rush86999/atom/main/install-mac-mini.sh

# Make executable
chmod +x install-mac-mini.sh

# Run installer
bash install-mac-mini.sh
```

### Option 3: Troubleshooting Mode

If you already have Atom installed but need to troubleshoot:

```bash
# Navigate to atom directory
cd ~/Documents/atom  # or your installation directory

# Run troubleshooting mode
bash install-mac-mini.sh --troubleshoot
```

---

## What the Script Does

### Automatic Checks
- ✅ macOS version compatibility
- ✅ Mac architecture detection (Apple Silicon / Intel)
- ✅ Docker installation and running status
- ✅ Git installation
- ✅ Disk space availability (10GB required)
- ✅ Port availability (3000, 8000, 6379, 3001)

### Interactive Configuration
- 🔧 AI provider selection (OpenAI, Anthropic, DeepSeek)
- 🔧 API key input with validation
- 🔧 Automatic encryption key generation
- 🔧 Optional settings (local-only mode, log level)
- 🔧 Installation directory selection

### Service Management
- 🚀 Clone Atom repository
- 🚀 Create and configure .env file
- 🚀 Start all Docker services
- 🚀 Wait for services to be healthy
- 🚀 Verify installation

### Built-in Troubleshooting
- 🔍 Check service status
- 🔍 View service logs
- 🔍 Restart services
- 🔍 Check and resolve port conflicts
- 🔍 Verify .env configuration
- 🔍 Test API connectivity
- 🔍 Reset installation (clean slate)
- 🔍 Docker diagnostics

---

## Installation Flow

```
1. System Checks
   ├─ Check macOS version
   ├─ Check architecture (Apple Silicon/Intel)
   ├─ Check Docker installed and running
   ├─ Check Git installed
   ├─ Check disk space
   └─ Check port availability

2. Installation
   ├─ Select installation directory
   ├─ Clone repository
   └─ Verify clone

3. Configuration
   ├─ Select AI provider(s)
   ├─ Enter API key(s)
   ├─ Generate encryption keys
   └─ Configure optional settings

4. Start Services
   ├─ Create data directory
   ├─ Start Docker containers
   └─ Wait for health checks

5. Verification
   ├─ Check service status
   ├─ Test health endpoints
   └─ Verify frontend accessible

6. Complete
   ├─ Display access URLs
   ├─ Show quick commands
   ├─ Offer to open dashboard
   └─ Offer troubleshooting menu
```

---

## Troubleshooting Menu Options

### 1. Check Service Status
Shows detailed status of all Atom services:
- Backend (atom-personal-backend)
- Frontend (atom-personal-frontend)
- Valkey (atom-personal-valkey)
- Browser (atom-personal-browser)

### 2. View Service Logs
View logs from:
- Backend service (last 50 lines)
- Frontend service (last 50 lines)
- Valkey service (last 50 lines)
- Browser service (last 50 lines)
- All services (last 50 lines)

### 3. Restart Services
Restart options:
- All services
- Backend only
- Frontend only
- Valkey only

### 4. Check Port Conflicts
Automatically detects and helps resolve:
- Port 3000 conflicts
- Port 8000 conflicts
- Port 6379 conflicts
- Port 3001 conflicts

Offers to kill conflicting processes.

### 5. Verify .env Configuration
Checks:
- .env file exists
- API keys configured (at least one)
- Encryption keys set (not default values)
- Syntax errors

Shows current configuration with sensitive values hidden.

### 6. Test API Connectivity
Tests:
- Backend health endpoint
- Backend readiness endpoint
- Frontend accessibility

### 7. Reset Installation
⚠️ **Destructive action** that:
- Stops all services
- Removes Docker volumes
- Deletes data directory
- Removes .env file

Useful for starting from scratch.

### 8. Docker Diagnostics
Shows:
- Docker version
- System info
- Disk usage
- Running containers
- Resource limit recommendations

---

## Script Features

### Colored Output
- 🟢 Green: Success messages
- 🔴 Red: Error messages
- 🟡 Yellow: Warnings
- 🔵 Blue: Information
- �cyan Cyan: Headers

### Interactive Prompts
- Clear yes/no prompts
- Multiple choice options
- Default values shown
- Easy navigation

### Error Handling
- Exits on critical errors
- Offers retry options
- Provides helpful error messages
- Suggests solutions

### Progress Indicators
- Step-by-step progress
- Loading dots for long operations
- Success confirmations
- Detailed status output

---

## Example Installation Session

```bash
$ bash install-mac-mini.sh

=============================================================================
Atom Personal Edition - Mac mini Installer
=============================================================================

This script will guide you through installing Atom on your Mac mini.

Installation steps:
  1) System checks (macOS, Docker, Git, disk space)
  2) Clone Atom repository
  3) Configure environment (API keys, encryption)
  4) Start services
  5) Verify installation

Press Enter to start installation, or Ctrl+C to exit...

=============================================================================
SYSTEM CHECKS
============================================================================

→ Checking macOS version...
✓ macOS 14.5 detected

→ Checking Mac architecture...
✓ Apple Silicon (M1/M2/M3/M4) detected

→ Checking Docker installation...
✓ Docker 24.0.7 installed
✓ Docker is running

→ Checking Git installation...
✓ Git 2.39.3 installed

→ Checking disk space...
✓ 45GB disk space available

→ Checking port availability...
✓ All required ports are available

=============================================================================
INSTALLATION
============================================================================

→ Cloning Atom repository...

ℹ Where would you like to install Atom?
  1) ~/Documents/atom (default)
  2) ~/Desktop/atom
  3) ~/Projects/atom
  4) Custom location

Choose option [1-4]: 1

✓ Repository cloned to: /Users/john/Documents/atom

=============================================================================
CONFIGURATION
============================================================================

→ Configuring Atom environment...
✓ Created .env from template

=============================================================================
AI Provider Configuration
============================================================================

ℹ Atom requires at least one AI provider API key to function.

→ Select your AI provider:
  1) OpenAI (Recommended - GPT-4, GPT-3.5)
  2) Anthropic (Best for complex tasks - Claude 3.5 Sonnet)
  3) DeepSeek (Affordable alternative)
  4) Enter multiple keys

Choose option [1-4]: 1

ℹ OpenAI API Key
Get your key at: https://platform.openai.com/api-keys

Enter your OpenAI API key (or press Enter to skip): sk-proj-abc123...

✓ OpenAI API key configured

=============================================================================
Encryption Key Generation
============================================================================

ℹ Generating secure encryption keys...
✓ BYOK_ENCRYPTION_KEY generated
✓ JWT_SECRET_KEY generated
ℹ Keys stored in .env file

=============================================================================
Optional Configuration
============================================================================

Enable local-only mode? (Blocks Spotify, Notion, etc.) (y/n): n

ℹ Log level options:
  1) INFO (default - recommended)
  2) DEBUG (verbose logging)
  3) WARNING (less logging)

Choose log level [1-3]: 1

✓ Environment configured successfully

=============================================================================
STARTING SERVICES
============================================================================

→ Starting Atom services...
✓ Created data directory
ℹ Starting Docker containers...
✓ Docker containers started

→ Waiting for services to be healthy...
✓ All services are healthy

=============================================================================
VERIFICATION
============================================================================

→ Verifying installation...

ℹ Service Status:
NAME                      STATUS              PORTS
atom-personal-backend     Up (healthy)        0.0.0.0:8000->8000/tcp
atom-personal-frontend    Up                  0.0.0.0:3000->3000/tcp
atom-personal-valkey      Up (healthy)        0.0.0.0:6379->6379/tcp
atom-personal-browser     Up                  0.0.0.0:3001->3000/tcp

✓ Backend health check passed
✓ Frontend is accessible
✓ Installation completed successfully!

=============================================================================
INSTALLATION COMPLETE
=============================================================================

Atom is now running on your Mac mini!

Access Atom:
  Web Dashboard:  http://localhost:3000
  API Documentation: http://localhost:8000/docs

Quick Commands:
  View logs:     docker-compose -f docker-compose-personal.yml logs -f
  Stop Atom:     docker-compose -f docker-compose-personal.yml down
  Restart Atom:  docker-compose -f docker-compose-personal.yml restart

Installation Directory:
  /Users/john/Documents/atom

Configuration File:
  /Users/john/Documents/atom/.env

Data Location:
  /Users/john/Documents/atom/data/

Open Atom dashboard in browser? (y/n): y

✓ Thank you for installing Atom!
```

---

## Troubleshooting Mode Example

```bash
$ bash install-mac-mini.sh --troubleshoot

=============================================================================
ATOM TROUBLESHOOTING MODE
============================================================================

ℹ Current directory: /Users/john/Documents/atom

=============================================================================
TROUBLESHOOTING MENU
=============================================================================
  1) Check service status
  2) View service logs
  3) Restart services
  4) Check port conflicts
  5) Verify .env configuration
  6) Test API connectivity
  7) Reset installation (clean slate)
  8) Docker diagnostics
  9) Exit troubleshooting

Choose option [1-9]: 1

→ Checking service status...

ℹ Service Status:
NAME                      STATUS              PORTS
atom-personal-backend     Up (healthy)        0.0.0.0:8000->8000/tcp
atom-personal-frontend    Up                  0.0.0.0:3000->3000/tcp
atom-personal-valkey      Up (healthy)        0.0.0.0:6379->6379/tcp
atom-personal-browser     Up                  0.0.0.0:3001->3000/tcp

ℹ Detailed status:
✓ atom-personal-backend: running (healthy)
✓ atom-personal-frontend: running (no-healthcheck)
✓ atom-personal-valkey: running (healthy)
✓ atom-personal-browser: running (no-healthcheck)

Press Enter to continue...

[Returns to menu]
```

---

## Manual Commands Reference

If you prefer to manage Atom manually instead of using the script:

### Start Atom
```bash
cd ~/Documents/atom
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
```

### Restart Atom
```bash
docker-compose -f docker-compose-personal.yml restart
```

### Check Status
```bash
docker-compose -f docker-compose-personal.yml ps
```

### Health Check
```bash
curl http://localhost:8000/health/live
```

---

## System Requirements

- **macOS:** Monterey (12.x), Ventura (13.x), Sonoma (14.x), or Sequoia (15.x)
- **RAM:** 4GB minimum, 8GB recommended
- **Storage:** 10GB free space
- **Docker:** Docker Desktop for Mac (Apple Silicon or Intel)
- **Git:** Usually pre-installed on macOS
- **AI Provider:** At least one API key (OpenAI, Anthropic, or DeepSeek)

---

## Getting Help

### Documentation
- [Full Installation Guide](./MAC_MINI_INSTALL.md)
- [Personal Edition Guide](./PERSONAL_EDITION.md)
- [API Documentation](API_DOCUMENTATION_INDEX.md)

### Community
- **GitHub Issues:** https://github.com/rush86999/atom/issues
- **GitHub Discussions:** https://github.com/rush86999/atom/discussions

### Common Issues

| Issue | Solution |
|-------|----------|
| Docker not running | Open Docker Desktop from Applications |
| Port conflicts | Use troubleshooting option 4 |
| API key not working | Verify key in .env, use option 5 |
| Services not starting | Check logs with option 2 |
| Out of memory | Increase Docker memory limit |

---

## Advanced Usage

### Custom Installation Directory

The script lets you choose where to install Atom:

1. `~/Documents/atom` (default)
2. `~/Desktop/atom`
3. `~/Projects/atom`
4. Custom location

### Multiple AI Providers

You can configure multiple AI providers:
- Option 4 in AI provider menu
- Enter keys for OpenAI, Anthropic, and/or DeepSeek
- Atom will use the best provider for each task

### Local-Only Mode

Enable local-only mode during configuration:
- Blocks Spotify, Notion, Gmail, Slack
- Allows Hue, Home Assistant, Sonos, FFmpeg
- Perfect for privacy-focused users

### Log Level Options

Choose your log level:
- **INFO** (default): Normal logging
- **DEBUG**: Verbose logging for troubleshooting
- **WARNING**: Minimal logging

---

## Script Safety Features

- ✅ Exits on critical errors (prevents broken installations)
- ✅ Validates API key format
- ✅ Generates secure encryption keys automatically
- ✅ Confirms destructive actions (reset, kill processes)
- ✅ Shows what will happen before doing it
- ✅ Provides helpful error messages
- ✅ Offers retry options

---

## Summary

The interactive installation script provides:
- 🎯 **One-command installation** - Just run `bash install-mac-mini.sh`
- 🔍 **Built-in troubleshooting** - 8 diagnostic tools
- 🎨 **Colored, intuitive output** - Easy to follow
- ✅ **Automated checks** - Catches common issues
- 🔧 **Interactive configuration** - No manual file editing
- 🚀 **Quick start** - Get running in 5 minutes

**Perfect for:** Mac mini users who want an easy, guided installation with built-in troubleshooting support.

---

*Last updated: March 20, 2026*
