# Atom Project

## Setup
1. Copy `.env.example` to `.env` and configure values
2. Run services:
   - Python API: `cd backend && docker-compose up`
   - Frontend: `cd frontend-nextjs && npm run dev`
   - Desktop: `cd desktop && npm run tauri dev`

## Architecture
- Frontend: Next.js (port 3000)
- API: FastAPI (port 8000)
- Desktop: Tauri wrapper

## Environment Variables
See `config/env.example` for complete reference

## Project Structure
- `frontend-nextjs/` - Next.js web application
- `desktop/` - Tauri desktop application  
- `backend/` - Python FastAPI backend
- `config/` - Configuration files
- `scripts/` - Utility scripts
- `docs/` - Documentation
- `data/` - Data files
- `models/` - Machine learning models
- `tests/` - Test files