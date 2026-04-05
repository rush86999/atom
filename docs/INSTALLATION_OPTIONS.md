# Atom Installation Options - Quick Reference

> **Choose the installation method that works best for you**

---

## 🚀 Quick Comparison

| Method | Time | Difficulty | Best For | Isolation |
|--------|------|-----------|----------|-----------|
| **Docker** | 5 min | ⭐ Easy | Quick start, testing | ✅ Full |
| **Native (automated)** | 10 min | ⭐⭐ Medium | Development, performance | ❌ None |
| **Native (manual)** | 15 min | ⭐⭐⭐ Advanced | Full control, learning | ❌ None |
| **pip installer** | 2 min | ⭐ Easy | Personal use, simplicity | ❌ None |

---

## 🐳 Method 1: Docker (Recommended for Quick Start)

### Prerequisites
- Docker Desktop installed

### Steps
```bash
# Clone repository
git clone https://github.com/rush86999/atom.git
cd atom

# Copy environment template
cp .env.personal .env

# Edit .env and add your API keys
nano .env  # Set OPENAI_API_KEY or ANTHROPIC_API_KEY

# Start Atom
docker-compose -f docker-compose-personal.yml up -d
```

### Access
- Frontend: http://localhost:3000
- Backend: http://localhost:8000

### Documentation
[Full Docker Guide →](PERSONAL_EDITION.md)

---

## 💻 Method 2: Native Installation (Automated Script)

### Prerequisites
- Python 3.11+
- Node.js 18+
- Git

### Steps (macOS/Linux)
```bash
# Clone repository
git clone https://github.com/rush86999/atom.git
cd atom

# Run installation script
chmod +x install-native.sh
./install-native.sh

# Edit .env and add your API keys
nano .env

# Start Atom (Terminal 1)
cd backend
source venv/bin/activate
python -m uvicorn main_api_app:app --reload

# Start Atom (Terminal 2)
cd frontend-nextjs
npm run dev
```

### Steps (Windows)
```bash
# Clone repository
git clone https://github.com/rush86999/atom.git
cd atom

# Run installation script
install-native.bat

# Edit .env and add your API keys
notepad .env

# Start Atom (Terminal 1)
cd backend
venv\Scripts\activate
python -m uvicorn main_api_app:app --reload

# Start Atom (Terminal 2)
cd frontend-nextjs
npm run dev
```

### Access
- Frontend: http://localhost:3000
- Backend: http://localhost:8000

### Documentation
[Full Native Guide →](NATIVE_SETUP.md)

---

## 📦 Method 3: pip Installer (Fastest)

### Prerequisites
- Python 3.11+
- pip

### Steps
```bash
# Install Atom via pip
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

### Access
- Frontend: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Documentation
[CLI Documentation →](../backend/README.md)

---

## 🔧 Method 4: Native Installation (Manual)

### Prerequisites
- Python 3.11+
- Node.js 18+
- Git
- Familiarity with command line

### Steps
```bash
# Clone repository
git clone https://github.com/rush86999/atom.git
cd atom

# Backend setup
cd backend
python3 -m venv venv
source venv/bin/activate  # venv\Scripts\activate on Windows
pip install -r requirements.txt

# Frontend setup
cd ../frontend-nextjs
npm install

# Environment configuration
cd ..
cp .env.personal .env
nano .env  # Add your API keys

# Database initialization
cd backend
source venv/bin/activate
alembic upgrade head

# Start backend
cd backend
source venv/bin/activate
python -m uvicorn main_api_app:app --host 0.0.0.0 --port 8000 --reload

# Start frontend (new terminal)
cd frontend-nextjs
npm run dev
```

### Access
- Frontend: http://localhost:3000
- Backend: http://localhost:8000

### Documentation
[Full Manual Guide →](NATIVE_SETUP.md)

---

## 🎯 Which Method Should You Choose?

### Choose Docker if:
- ✅ You want the fastest setup
- ✅ You're not familiar with Python/Node.js
- ✅ You want full isolation from your system
- ✅ You might uninstall Atom later
- ✅ You're on macOS, Linux, or Windows with WSL2

### Choose Native (Automated) if:
- ✅ You don't have Docker
- ✅ You want better performance
- ✅ You're developing or customizing Atom
- ✅ You want direct file access
- ✅ You're comfortable with command line

### Choose pip Installer if:
- ✅ You want the absolute fastest setup
- ✅ You're using Atom for personal automation
- ✅ You don't need the frontend UI
- ✅ You prefer Python packages over containers

### Choose Native (Manual) if:
- ✅ You want full control over the installation
- ✅ You're learning how Atom works
- ✅ You need to customize dependencies
- ✅ You're an advanced user

---

## 📋 Common Setup Steps (All Methods)

### 1. Get AI Provider API Keys

You'll need at least one of these:

**OpenAI** (Recommended)
- Visit: https://platform.openai.com/api-keys
- Sign up and create API key
- Starts with: `sk-`

**Anthropic** (Best for complex tasks)
- Visit: https://console.anthropic.com/
- Sign up and create API key
- Starts with: `sk-ant-`

**DeepSeek** (Affordable)
- Visit: https://platform.deepseek.com/
- Sign up and get API key
- More budget-friendly for heavy usage

### 2. Generate Encryption Keys

```bash
# Generate two different keys
openssl rand -base64 32  # First key
openssl rand -base64 32  # Second key
```

### 3. Configure Environment

Edit `.env` file and add:

```bash
# AI Provider (at least one required)
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Encryption keys
BYOK_ENCRYPTION_KEY=<paste-first-key>
JWT_SECRET_KEY=<paste-second-key>
```

---

## 🧪 Verify Installation

After installation, verify Atom is running:

```bash
# Check health endpoint
curl http://localhost:8000/health/live

# Expected output:
# {"status":"alive"}

# Open API documentation
# http://localhost:8000/docs
```

---

## 📚 Next Steps

1. **Create your first agent** - Open the dashboard and create an agent
2. **Explore features** - Try browser automation, workflows, episodic memory
3. **Integrate services** - Connect Gmail, Slack, HubSpot, etc.
4. **Read documentation** - Learn about governance, graduation, canvas

**Documentation:**
- [Personal Edition Guide](PERSONAL_EDITION.md)
- [Native Setup Guide](NATIVE_SETUP.md)
- [Full Documentation](../README.md)
- [API Documentation](API_DOCUMENTATION_INDEX.md)

---

## 🆘 Troubleshooting

### Issue: Port already in use
```bash
# macOS/Linux
lsof -i :8000
kill -9 <PID>

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Issue: Module not found
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Docker container won't start
```bash
# Check Docker is running
docker ps

# View logs
docker-compose logs -f

# Restart containers
docker-compose restart
```

---

## 🎉 You're Ready!

Once Atom is running, you can:

- **Chat with AI agents** at http://localhost:3000
- **Build workflows** visually
- **Automate tasks** with browser automation
- **Integrate services** like Gmail, Slack, HubSpot
- **Monitor operations** with real-time visibility

Enjoy automating with Atom! 🚀
