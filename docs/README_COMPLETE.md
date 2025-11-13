# 🌟 ATOM Platform - Complete Autonomous AI System

ATOM is a comprehensive AI-powered automation platform that integrates with 50+ tools and services to provide intelligent workflow automation, data management, and productivity enhancement.

## 🚀 Quick Start

### Prerequisites
- **Python 3.8+** (for backend)
- **Node.js 16+** (for frontend and desktop)
- **Rust** (for desktop app, optional)

### 1. Clone and Setup
```bash
# Clone the repository
git clone <repository-url>
cd atom

# Make startup scripts executable (Linux/macOS)
chmod +x start_*.sh test_backend.py start_backend.py
```

### 2. Start the Platform

#### Option 1: Start Everything (Recommended)
```bash
# Starts backend, frontend, and optional desktop
./start_all.sh
```

#### Option 2: Individual Components
```bash
# Start backend only
python start_backend.py

# Start frontend only
./start_frontend.sh

# Start desktop only
./start_desktop.sh
```

### 3. Access the Platform
- **Frontend Web UI**: http://localhost:3000
- **Backend API**: http://localhost:5058
- **API Documentation**: http://localhost:5058/docs
- **Desktop App**: Opens automatically when started

### 4. Test the System
```bash
# Test backend functionality
python test_backend.py
```

## 📁 Project Structure

```
atom/
├── 🌐 Frontend Web App (Next.js)
│   └── frontend-nextjs/
│       ├── pages/              # All pages and integrations
│       ├── components/         # UI components
│       ├── api/              # API routes
│       └── public/           # Static assets
│
├── 🖥️  Desktop App (Tauri)
│   └── desktop/tauri/
│       ├── src/              # Desktop app source
│       ├── services/         # Desktop services
│       └── skills/           # AI skills
│
├── 📡 Backend API (FastAPI/Python)
│   └── backend/
│       ├── integrations/     # Service integrations
│       ├── core/           # Core services
│       ├── ai/             # AI/ML components
│       └── main_api_app.py # Main API
│
├── 🧠 Shared Components
│   ├── shared/            # Shared services
│   └── orchestration/    # Workflow orchestration
│
└── 🛠️  Scripts & Tools
    ├── start_*.sh        # Startup scripts
    ├── test_backend.py    # Backend testing
    └── scripts/          # Utility scripts
```

## 🔧 Available Services & Integrations

### 📊 Development & Project Management
- **GitHub** - Repository management, issues, PRs
- **GitLab** - GitLab integration
- **Jira** - Project tracking and issues
- **Asana** - Task management
- **Trello** - Kanban boards
- **Monday** - Project management
- **Linear** - Issue tracking

### 📧 Communication & Collaboration
- **Slack** - Team communication
- **Microsoft Teams** - Video meetings & chat
- **Discord** - Community communication
- **Gmail** - Email management
- **Outlook** - Email & calendar
- **Zoom** - Video conferencing

### 💾 Data & Storage
- **Google Drive** - Cloud storage
- **OneDrive** - Microsoft storage
- **Dropbox** - File storage
- **Box** - Enterprise storage

### 💰 Business & Finance
- **Stripe** - Payment processing
- **Salesforce** - CRM
- **HubSpot** - Marketing & sales
- **QuickBooks** - Accounting
- **Xero** - Accounting

### 🎨 Design & Creative
- **Figma** - Design collaboration
- **Notion** - Documentation & notes
- **Miro** - Whiteboard collaboration

### 📈 Analytics & Monitoring
- **Google Analytics** - Web analytics
- **Tableau** - Data visualization
- **Zendesk** - Customer support

## 🤖 AI & Automation Features

### Core AI Capabilities
- **Natural Language Processing** - Understand user requests
- **Workflow Automation** - Create and execute automated workflows
- **Data Intelligence** - Analyze and extract insights
- **Predictive Analytics** - Forecast trends and outcomes

### Available AI Skills
- **Content Creation** - Generate marketing copy, documents
- **Data Analysis** - Analyze datasets and create reports
- **Customer Support** - Automated ticket management
- **Finance Management** - Budget tracking, financial insights
- **Project Management** - Task automation and reporting
- **Research** - Gather and synthesize information

### Memory & Learning
- **Vector Database** - Store and retrieve information
- **Conversation Memory** - Remember past interactions
- **Learning System** - Improve from user feedback

## 🔌 Integration Setup

### 1. Configure Environment Variables
```bash
# Copy environment template
cp backend/.env.template backend/.env

# Edit with your API keys
nano backend/.env
```

### 2. Required API Keys
Set these in your `.env` file:

```env
# Core Services
DATABASE_URL=sqlite:///atom_data.db
SECRET_KEY=your-secret-key-here

# Google Services
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Microsoft Services
MICROSOFT_CLIENT_ID=your-microsoft-client-id
MICROSOFT_CLIENT_SECRET=your-microsoft-client-secret

# Development Tools
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret

# Communication
SLACK_BOT_TOKEN=your-slack-bot-token

# Storage Services
DROPBOX_APP_KEY=your-dropbox-app-key
DROPBOX_APP_SECRET=your-dropbox-app-secret

# Business Services
STRIPE_SECRET_KEY=your-stripe-secret-key
SALESFORCE_CLIENT_ID=your-salesforce-client-id
```

### 3. OAuth Callback URLs
For OAuth integrations, add these callback URLs:

```bash
# Development
http://localhost:5058/oauth/github/callback
http://localhost:5058/oauth/google/callback
http://localhost:5058/oauth/slack/callback

# Production
https://your-domain.com/oauth/github/callback
https://your-domain.com/oauth/google/callback
```

## 🎯 Usage Examples

### Basic Commands
```python
# Using the Python API
from backend.integrations.github_service import get_github_service

# Get GitHub service
github = get_github_service()

# Test connection
result = github.test_connection()
print(result)

# Get repositories
repos = github.get_user_repositories()
```

### API Examples
```bash
# Health check
curl http://localhost:5058/health

# Get system status
curl http://localhost:5058/system/status

# Get available integrations
curl http://localhost:5058/integrations/status
```

### Frontend Usage
1. Navigate to http://localhost:3000
2. Click on "Integrations" in the sidebar
3. Select an integration to configure
4. Follow the OAuth flow or enter API keys
5. Use the integration features

## 🛠️ Development

### Backend Development
```bash
cd backend
pip install -r requirements.txt
python main_api_app.py
```

### Frontend Development
```bash
cd frontend-nextjs
npm install
npm run dev
```

### Desktop Development
```bash
cd desktop/tauri
npm install
npm run tauri:dev
```

### Testing
```bash
# Test backend
python test_backend.py

# Test specific integrations
python backend/tests/test_github_integration.py

# Run all backend tests
cd backend && python -m pytest tests/
```

## 🔍 Troubleshooting

### Common Issues

#### Backend Won't Start
```bash
# Check Python version
python --version  # Should be 3.8+

# Install missing packages
pip install fastapi uvicorn requests pydantic

# Check database permissions
mkdir -p data
chmod 755 data
```

#### Frontend Won't Start
```bash
# Clear node_modules
cd frontend-nextjs
rm -rf node_modules package-lock.json
npm install
```

#### Integration Errors
```bash
# Check API keys
python -c "import os; print('DATABASE_URL:', os.getenv('DATABASE_URL'))"

# Test service connection
python test_backend.py
```

#### Memory/Vector Database Issues
```bash
# Install LanceDB
pip install lancedb

# Check memory directory
ls -la data/atom_memory/
```

### Logs
Check these log files for debugging:
- `logs/backend.log` - Backend server logs
- `logs/frontend.log` - Frontend server logs
- `logs/desktop.log` - Desktop app logs

### Port Conflicts
```bash
# Check what's using ports
lsof -i :5058  # Backend
lsof -i :3000  # Frontend

# Use different ports
export BACKEND_PORT=5059
export FRONTEND_PORT=3001
./start_all.sh
```

## 📚 API Documentation

### Core Endpoints
- `GET /health` - Health check
- `GET /system/status` - System status
- `GET /docs` - Swagger documentation
- `GET /integrations/status` - Integration status

### Integration Endpoints
- `GET /integrations/github/health` - GitHub status
- `POST /integrations/github/repo/{owner}/{name}` - Get repo info
- `GET /integrations/slack/channels` - Get Slack channels
- `POST /integrations/notion/pages` - Create Notion page

### Memory Endpoints
- `GET /memory/health` - Vector database status
- `POST /memory/search` - Search stored memories
- `POST /memory/store` - Store new memory

## 🚀 Deployment

### Production Setup
```bash
# Set production environment
export ENVIRONMENT=production

# Use production database
export DATABASE_URL=postgresql://user:pass@localhost/atom

# Enable SSL/HTTPS
export SSL_ENABLED=true

# Run production server
./start_all.sh
```

### Docker Deployment
```bash
# Build Docker image
docker build -t atom-platform .

# Run container
docker run -p 5058:5058 atom-platform
```

### Cloud Deployment
- **AWS**: Use ECS or Fargate
- **Google Cloud**: Use Cloud Run
- **Azure**: Use Container Instances
- **Vercel**: Frontend deployment
- **Heroku**: Full platform deployment

## 🤝 Contributing

### Development Workflow
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

### Code Style
- **Python**: Follow PEP 8
- **TypeScript**: Use Prettier + ESLint
- **Rust**: Use rustfmt
- **Comments**: Add docstrings for all functions

### Adding New Integrations
1. Create service file in `backend/integrations/`
2. Create API routes in `backend/integrations/{service}_routes.py`
3. Add frontend page in `frontend-nextjs/pages/integrations/`
4. Add tests in `backend/tests/`
5. Update documentation

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Get Help
- **Documentation**: Check this README and inline documentation
- **Issues**: Report bugs on GitHub Issues
- **Discussions**: Join GitHub Discussions for questions
- **Community**: Join our Discord/Slack communities

### Feature Requests
- Submit ideas on GitHub Issues with the "enhancement" label
- Discuss in GitHub Discussions
- Vote on existing requests

## 🎉 Acknowledgments

Thanks to all contributors and the open-source community for making ATOM possible!

---

**🌟 ATOM Platform - Transforming Work with AI Automation** 🌟