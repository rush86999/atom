# ATOM Development Setup Guide

## Quick Start

### Prerequisites
- **Python 3.8+** (Detected: Python 3.13.1 ✓)
- **Node.js 14+** (Detected: Node.js v22.14.0 ✓)
- **Git** (for cloning and version control)

### Starting the Application

#### Option 1: Start Both Services (Recommended)

Open **two separate terminal windows**:

**Terminal 1 - Backend:**
```powershell
cd c:\Users\Mannan Bajaj\atom
.\start-backend.ps1
```

**Terminal 2 - Frontend:**
```powershell
cd c:\Users\Mannan Bajaj\atom
.\start-frontend.ps1
```

#### Option 2: Manual Start

**Backend (Python/FastAPI):**
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main_api_app.py
```

**Frontend (Next.js):**
```powershell
cd frontend-nextjs
npm install --legacy-peer-deps
npm run dev
```

## What the Startup Scripts Do

### Backend Script (`start-backend.ps1`)
1. ✓ Checks Python installation
2. ✓ Creates virtual environment (if needed)
3. ✓ Activates virtual environment
4. ✓ Installs/updates dependencies from `requirements.txt`
5. ✓ Checks for `.env` configuration
6. ✓ Starts FastAPI server on port 5059

### Frontend Script (`start-frontend.ps1`)
1. ✓ Checks Node.js installation
2. ✓ Installs dependencies (if needed)
3. ✓ Creates `.env.local` with default settings
4. ✓ Starts Next.js dev server on port 3000

## Accessing the Application

Once both services are running:

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | http://localhost:3000 | Main application UI |
| **Backend API** | http://localhost:5059 | API server |
| **API Docs** | http://localhost:5059/docs | Interactive API documentation (Swagger UI) |
| **Health Check** | http://localhost:5059/health | Backend health status |

## Environment Configuration

### Backend Environment (`.env`)

The backend uses the root `.env` file located at `c:\Users\Mannan Bajaj\atom\.env`.

**Key settings for development:**
- `DATABASE_URL`: SQLite database (default) or PostgreSQL
- `OPENAI_API_KEY`: Required for AI features
- `USE_MOCK_DATA=true`: Use mock data for testing
- `ENABLE_OAUTH_DEMO=true`: Enable OAuth demo mode
- `PORT=5059`: Backend server port

### Frontend Environment (`.env.local`)

Auto-created by the startup script with:
```env
NEXT_PUBLIC_API_URL=http://localhost:5059
NEXT_PUBLIC_APP_NAME=ATOM Platform
```

## Troubleshooting

### Backend Issues

**Problem: "Module not found" errors**
```powershell
# Reinstall dependencies
cd backend
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt --force-reinstall
```

**Problem: Port 5059 already in use**
```powershell
# Find and kill the process
netstat -ano | findstr :5059
taskkill /PID <process_id> /F
```

**Problem: Database errors**
- Delete `atom_data.db` to reset the database
- Check `DATABASE_URL` in `.env`

### Frontend Issues

**Problem: TypeScript errors**
```powershell
cd frontend-nextjs
npm run type-check
```

**Problem: Port 3000 already in use**
- Next.js will automatically try port 3001, 3002, etc.
- Or manually kill the process using port 3000

**Problem: Module resolution errors**
```powershell
# Clean install
cd frontend-nextjs
Remove-Item -Recurse -Force node_modules
Remove-Item package-lock.json
npm install --legacy-peer-deps
```

### Common Issues

**Problem: PowerShell execution policy error**
```powershell
# Run as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Problem: Virtual environment activation fails**
```powershell
# Delete and recreate
cd backend
Remove-Item -Recurse -Force venv
python -m venv venv
```

## Development Workflow

### Making Changes

1. **Backend changes**: Edit Python files in `backend/`
   - FastAPI auto-reloads on file changes
   - Check terminal for errors

2. **Frontend changes**: Edit files in `frontend-nextjs/`
   - Next.js hot-reloads automatically
   - Check browser console for errors

### Running Tests

**Backend:**
```powershell
cd backend
.\venv\Scripts\Activate.ps1
pytest
```

**Frontend:**
```powershell
cd frontend-nextjs
npm test
```

### Type Checking

**Frontend TypeScript:**
```powershell
cd frontend-nextjs
npm run type-check
```

## Architecture Overview

```
ATOM Platform
├── backend/              # Python/FastAPI API server
│   ├── main_api_app.py  # Main entry point
│   ├── core/            # Core functionality
│   ├── integrations/    # Third-party integrations
│   └── requirements.txt # Python dependencies
│
└── frontend-nextjs/     # Next.js web application
    ├── pages/           # Next.js pages
    ├── components/      # React components
    ├── lib/             # Utilities
    └── package.json     # Node.js dependencies
```

## Next Steps

1. **Configure API Keys**: Update `.env` with your actual API keys
2. **Set up Database**: Configure PostgreSQL if needed (optional)
3. **Explore API**: Visit http://localhost:5059/docs
4. **Test Features**: Try creating workflows, integrations, etc.

## Getting Help

- Check the [API Documentation](http://localhost:5059/docs) when running
- Review error messages in terminal output
- Check browser console for frontend errors
- Refer to `DEPLOYMENT_GUIDE.md` for production setup

---

**Happy coding! 🚀**
