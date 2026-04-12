# 🚀 ATOM Quick Start Guide

## Get Up and Running in 5 Minutes

Welcome to ATOM! This guide will help you get started with the platform quickly and efficiently.

## 📋 Prerequisites

Before you begin, ensure you have:

- **Python 3.8+** installed
- **Git** for version control
- **Docker** (optional, for containerized deployment)
- **Node.js 16+** (for frontend development)

## 🛠️ Installation

### Option 1: Quick Setup (Recommended)

```bash
# Clone the repository
git clone https://github.com/rush86999/atom.git
cd atom

# Run the quick setup script
./QUICK_DEPLOY_NOW.sh
```

### Option 2: Manual Setup

```bash
# Clone the repository
git clone https://github.com/rush86999/atom.git
cd atom

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend-nextjs
npm install
```

## 🚀 Start the Platform

### Backend Server

```bash
# Start the backend API server
cd backend
python3 main_api_app.py
```

The backend will start on `http://localhost:8000` with API documentation available at `http://localhost:8000/docs`.

### Frontend (Optional)

```bash
# Start the frontend development server
cd frontend-nextjs
npm run dev
```

The frontend will be available at `http://localhost:3000`.

## 🎯 Your First Workflow

### Step 1: Access the Platform
1. Open your browser to `http://localhost:8000`
2. You should see the ATOM API welcome message

### Step 2: Test Basic Functionality

```bash
# Test the API health endpoint
curl http://localhost:8000/health

# Test enhanced workflow automation status
curl http://localhost:8000/workflows/enhanced/status
```

### Step 3: Create Your First Workflow

Use the enhanced workflow automation to create your first automated process:

```bash
# Generate a workflow from natural language
curl -X POST http://localhost:8000/workflows/enhanced/intelligence/generate \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "When I receive important emails, create tasks in Asana and notify the team on Slack",
    "context": {"user_id": "demo_user"},
    "optimization_strategy": "performance"
  }'
```

## 🔧 Connect Your First Integration

### Slack Integration Example

1. **Set up Slack App**:
   - Create a new Slack app at [api.slack.com](https://api.slack.com/apps)
   - Add OAuth scopes: `channels:read`, `chat:write`, `users:read`
   - Get your OAuth credentials

2. **Configure in ATOM**:
   ```bash
   # Set environment variables
   export SLACK_CLIENT_ID=your_client_id
   export SLACK_CLIENT_SECRET=your_client_secret
   export SLACK_SIGNING_SECRET=your_signing_secret
   ```

3. **Test the Integration**:
   ```bash
   # Test Slack connectivity
   curl http://localhost:8000/api/v1/slack/health
   ```

## 🤖 Enhanced Workflow Automation

ATOM's enhanced workflow automation provides AI-powered features:

### Key Features Available Immediately

1. **AI-Powered Service Detection**
   - Automatically identifies services from your natural language input
   - 85%+ accuracy in service detection

2. **Context-Aware Workflow Generation**
   - Creates optimized workflows based on your context
   - Suggests improvements and optimizations

3. **Real-time Monitoring**
   - Monitor workflow health and performance
   - Get alerts for issues

### Example Workflow Creation

```python
import requests

# Create an optimized workflow
response = requests.post(
    "http://localhost:8000/workflows/enhanced/intelligence/generate",
    json={
        "user_input": "Automatically create GitHub issues when Trello cards are completed",
        "context": {"user_id": "your_user_id"},
        "optimization_strategy": "hybrid"
    }
)

print(response.json())
```

## 📊 Verify Your Setup

### Check System Status

```bash
# Verify backend is running
curl http://localhost:8000/health

# Check enhanced workflow automation status
curl http://localhost:8000/workflows/enhanced/status

# Test service registry
curl http://localhost:8000/api/v1/services
```

### Expected Responses

- **Health Check**: `{"status": "healthy", "version": "1.0.0"}`
- **Workflow Status**: Should show enhanced components as available
- **Service Registry**: Should list available integrations

## 🚨 Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Find and kill process using port 8000
   lsof -ti:8000 | xargs kill -9
   ```

2. **Python Dependencies Issues**
   ```bash
   # Create virtual environment
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Database Connection Issues**
   ```bash
   # The system uses SQLite by default
   # Check if database file exists
   ls -la backend/atom.db
   ```

### Getting Help

- Check the [Troubleshooting Guide](TROUBLESHOOTING.md)
- Review [API Documentation](../ARCHITECTURE/API_REFERENCE.md)
- Visit [GitHub Issues](https://github.com/rush86999/atom/issues)

## 🎉 Next Steps

Congratulations! You've successfully set up ATOM. Here's what to do next:

1. **Explore Integrations**: Connect more services from the 25+ available options
2. **Create Workflows**: Use the enhanced automation to build complex workflows
3. **Monitor Performance**: Set up monitoring for your automated processes
4. **Scale Up**: Deploy to production for team or enterprise use

### Recommended Learning Path

1. **Basic Workflows** → **Integration Setup** → **Advanced Automation** → **Production Deployment**

### Additional Resources

- [Enhanced Workflow Guide](../WORKFLOW_AUTOMATION/ENHANCED_WORKFLOW_GUIDE.md) - Learn about AI-powered features
- [Integration Overview](../INTEGRATIONS/OVERVIEW.md) - Connect your favorite services
- [Production Deployment](../DEPLOYMENT/PRODUCTION_DEPLOYMENT.md) - Deploy to production

---

**Need immediate help?** Check our [Troubleshooting Guide](TROUBLESHOOTING.md) or create an issue in our [GitHub repository](https://github.com/rush86999/atom).

**Ready for more?** Explore the [Enhanced Workflow Automation](../WORKFLOW_AUTOMATION/ENHANCED_WORKFLOW_GUIDE.md) to unlock AI-powered features.