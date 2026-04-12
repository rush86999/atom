# Getting Started

Quick start guides, installation options, and first steps with Atom.

## 📚 Quick Navigation

### Essential Guides
- **[Installation](installation.md)** - Complete installation guide
- **[Installation Options](installation-options.md)** - Installation variants
- **[Mac Mini Install](mac-mini-install.md)** - Mac mini specific setup
- **[Install Script](install-script.md)** - Automated installation script

## 🚀 Quick Start

### Option 1: Docker (5 minutes) ⭐ RECOMMENDED
```bash
git clone https://github.com/rush86999/atom.git
cd atom
cp .env.personal .env
docker-compose -f docker-compose-personal.yml up -d
open http://localhost:8000
```

### Option 2: Native (10 minutes)
```bash
git clone https://github.com/rush86999/atom.git
cd atom

# Backend setup
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend setup
cd ../frontend-nextjs
npm install

# Configure environment
cp ../.env.personal ../.env

# Start services
# Terminal 1: cd backend && python -m uvicorn main:app --reload
# Terminal 2: cd frontend-nextjs && npm run dev
```

### Option 3: DigitalOcean (1 click)
[![Deploy to DO](https://www.deploytodo.com/do-btn-blue.svg)](https://cloud.digitalocean.com/apps/new?repo=https://github.com/rush86999/atom/tree/main&config=deploy/digitalocean/app.yaml)

## 📋 What You'll Need

### Requirements
- **Python**: 3.11+
- **Node.js**: 18+
- **Database**: SQLite (Personal) or PostgreSQL (Enterprise)
- **LLM API Key**: OpenAI, Anthropic, or compatible
- **Optional**: Docker for containerized deployment

### API Keys (Optional but Recommended)
```bash
# Add to .env file
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...
MINIMAX_API_KEY=...  # Optional: MiniMax M2.7 (204K context)
```

## 🎯 First Steps

### 1. Explore the Dashboard
Open http://localhost:8000 and explore the interface

### 2. Create Your First Agent
Use the agent creation wizard to set up a specialty agent

### 3. Run a Workflow
Try a simple automation task:
- Schedule a meeting
- Send an email
- Create a report

### 4. Explore Integrations
Connect your favorite services:
- Slack for notifications
- Gmail for email automation
- HubSpot for CRM workflows

### 5. Check Documentation
Visit [User Guide Index](../USER_GUIDE_INDEX.md) for comprehensive guides

## 🔧 Configuration

### Environment Variables
```bash
# Database (Personal Edition default)
DATABASE_URL=sqlite:///./atom_dev.db

# LLM Provider (at least one required)
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-...

# Application
PORT=8000
LOG_LEVEL=INFO

# Optional: Marketplace connection
MARKETPLACE_API_TOKEN=at_saas_your_token
```

## 📖 Next Steps

- **[User Guide Index](../USER_GUIDE_INDEX.md)** - Complete user documentation
- **[Agent System](../agents/README.md)** - Learn about agents
- **[Integrations](../INTEGRATIONS/README.md)** - Connect external services
- **[Operations](../operations/README.md)** - Deployment and monitoring

## ❓ Troubleshooting

### Port Already in Use
```bash
# Change port in .env
PORT=8001
```

### Database Connection Error
```bash
# Check DATABASE_URL in .env
# For Personal Edition, ensure SQLite file path is correct
```

### LLM API Error
```bash
# Verify API key is set
echo $OPENAI_API_KEY

# Test API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### Docker Issues
```bash
# Check Docker is running
docker ps

# Rebuild containers
docker-compose -f docker-compose-personal.yml up -d --build
```

## 📖 Related Documentation

- **[GETTING_STARTED (uppercase)](../GETTING_STARTED/README.md)** - Additional getting started docs
- **[Installation](../getting-started/installation.md)** - Detailed installation
- **[Development](../development/README.md)** - Development setup

> **Note**: This folder (lowercase `getting-started/`) contains quick start and installation guides. Additional getting started docs are in the `GETTING_STARTED/` (uppercase) folder.

---

*Last Updated: April 12, 2026*
