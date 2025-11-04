# 🚀 Atom Setup and Usage Guide

## 📋 Prerequisites

Before starting, ensure you have:
- Node.js 16+ installed
- Python 3.7+ installed
- npm or yarn package manager
- Git installed

## 🏗️ Architecture Overview

Atom consists of two main components:
1. **Frontend**: Next.js application (port 3000)
2. **Backend**: Python Flask API (port 5058)

## 🚀 Quick Start

### 1. Clone and Install Dependencies

```bash
# Clone the repository (if not already done)
git clone https://github.com/rush86999/atom.git
cd atom

# Install Node.js dependencies
npm install

# Install Python dependencies
cd backend/python-api-service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ../..
```

### 2. Start Development Environment

```bash
# Option A: Use the provided startup script
chmod +x start-dev.sh
./start-dev.sh

# Option B: Start services manually
# Terminal 1 - Frontend
cd frontend-nextjs
npm run dev

# Terminal 2 - Backend  
cd backend/python-api-service
source venv/bin/activate
python minimal_app.py
```

### 3. Access the Application

- **Frontend**: http://localhost:3000
- **API Documentation**: http://localhost:5058
- **Health Check**: http://localhost:5058/healthz

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the root directory with:

```env
# Database
DATABASE_URL=postgresql://username:password@localhost:5432/atom_db

# Flask
FLASK_SECRET_KEY=your-secret-key-here
PYTHON_API_PORT=5058

# Frontend
NEXT_PUBLIC_API_BASE_URL=http://localhost:5058
```

### API Key Management

API keys are passed from the frontend via headers. Supported headers:

```
X-OpenAI-API-Key: sk-your-openai-key
X-Google-Client-ID: your-google-client-id  
X-Google-Client-Secret: your-google-client-secret
X-Notion-API-Token: your-notion-token
X-Dropbox-Access-Token: your-dropbox-token
X-Trello-API-Key: your-trello-key
X-Trello-API-Secret: your-trello-secret
X-Asana-Access-Token: your-asana-token
```

## 📊 API Endpoints

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/healthz` | GET | Service health check |
| `/api/dashboard` | GET | Unified dashboard data |
| `/api/calendar/events` | GET | Calendar events |
| `/api/tasks` | GET | Task management |
| `/api/messages` | GET | Message inbox |
| `/api/integrations/status` | GET | Integration status |
| `/api/integrations/validate` | POST | Validate API keys |

### Example Usage

```bash
# Get dashboard data
curl http://localhost:5058/api/dashboard

# Validate API keys
curl -X POST http://localhost:5058/api/integrations/validate \
  -H "X-OpenAI-API-Key: sk-your-key" \
  -H "Content-Type: application/json"

# Health check
curl http://localhost:5058/healthz
```

## 🛠️ Development

### Project Structure

```
atom/
├── frontend-nextjs/          # Next.js frontend
│   ├── pages/               # React pages
│   ├── components/          # React components
│   └── lib/                 # Utility libraries
├── backend/python-api-service/ # Python backend
│   ├── minimal_app.py       # Main Flask application
│   ├── *.py                # Service handlers
│   └── requirements.txt    # Python dependencies
├── start-dev.sh            # Development startup script
└── SETUP_GUIDE.md         # This file
```

### Adding New Integrations

1. Create a new handler in `backend/python-api-service/`
2. Add API key header support in `minimal_app.py`
3. Register the blueprint in `main_api_app.py`
4. Update frontend components to use the new endpoint

### Database Setup

For production use, set up PostgreSQL:

```bash
# Install PostgreSQL (macOS)
brew install postgresql
brew services start postgresql

# Create database
createdb atom_db

# Update DATABASE_URL in .env
DATABASE_URL=postgresql://localhost:5432/atom_db
```

## 🧪 Testing

### Run Tests

```bash
# Frontend tests
cd frontend-nextjs
npm run test

# Backend tests  
cd backend/python-api-service
source venv/bin/activate
python -m pytest tests/

# Integration tests
npm run test:integration
```

### Manual Testing

```bash
# Test API endpoints
curl http://localhost:5058/healthz
curl http://localhost:5058/api/dashboard

# Test with API keys
curl -H "X-OpenAI-API-Key: test-key" http://localhost:5058/api/integrations/validate
```

## 🚀 Deployment

### Production Build

```bash
# Build frontend
cd frontend-nextjs
npm run build
npm start

# Build backend (using production WSGI server)
cd backend/python-api-service
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5058 minimal_app:app
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose -f backend/docker/docker-compose.yaml up --build
```

## 🔍 Troubleshooting

### Common Issues

1. **Port 3000 already in use**
   ```bash
   lsof -ti:3000 | xargs kill
   ```

2. **Port 5058 already in use**
   ```bash
   lsof -ti:5058 | xargs kill
   ```

3. **Python dependencies missing**
   ```bash
   cd backend/python-api-service
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Node modules missing**
   ```bash
   npm install
   cd frontend-nextjs && npm install
   ```

### Logs

- Frontend logs: Check browser console and terminal output
- Backend logs: Check `api.log` or terminal output
- Database logs: Check PostgreSQL logs

## 📞 Support

- Check existing issues on GitHub
- Review API documentation at `http://localhost:5058`
- Examine service health at `http://localhost:5058/healthz`

## 🎯 Next Steps

1. Configure real database connection
2. Set up authentication (JWT tokens)
3. Add API keys for services you want to use
4. Customize the dashboard for your needs
5. Set up production deployment

---

**Note**: This is a development setup. For production use, ensure proper security measures, environment configuration, and monitoring are in place.