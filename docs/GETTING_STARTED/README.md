# Getting Started

Quick start guides and installation for Atom.

## 📚 Quick Navigation

### Essential Guides
- **[Quick Start](QUICK_START.md)** - Get started in 15 minutes ⭐ START HERE
- **[Installation](INSTALLATION.md)** - Complete installation guide
- **[First Steps](FIRST_STEPS.md)** - Your first tasks with Atom
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions

## 🚀 Quick Start

### Option 1: Docker (5 minutes)
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
cd backend && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd ../frontend-nextjs && npm install
cp .env.personal .env
# Start backend: cd backend && python -m uvicorn main_api_app:app --reload
# Start frontend: cd frontend-nextjs && npm run dev
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
```

## 🎯 First Steps

1. **Explore the Dashboard**: Open http://localhost:8000
2. **Create Your First Agent**: Use the agent creation wizard
3. **Run a Workflow**: Try a simple automation task
4. **Explore Integrations**: Connect Slack, Gmail, or other services
5. **Check Documentation**: Visit [User Guide Index](../USER_GUIDE_INDEX.md)

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
```

### Marketplace Connection (Optional)
```bash
# Add to .env
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

## 📖 Related Documentation

- **[Installation Options](../getting-started/installation-options.md)** - Installation variants
- **[Mac Mini Install](../getting-started/mac-mini-install.md)** - Mac mini setup
- **[Install Script Guide](../getting-started/install-script.md)** - Automated installation

---

*Last Updated: April 12, 2026*
