# ATOM (Advanced Task Orchestration & Management)

This workspace contains a TypeScript React frontend (Vite) and a Flask-based Python backend with Socket.IO and PostgreSQL support.

Quick start (local development):

Prerequisites:

- Node.js (16+)
- Python 3.9+
- PostgreSQL
- Redis (optional for websockets/celery)

Frontend (run from repository root):

```powershell
npm install
npm run dev
```

Backend (run from repository root):

```powershell
# from repo root
cd backend\python-api-service
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# configure DATABASE_URL and other vars in .env
python app.py
```

Notes:

- Frontend dev server runs on port `3000` by default (Vite). The React app expects the backend Socket.IO server at `ws://localhost:3001` unless overridden via environment variables.
- Backend Socket.IO server listens on port `3001` by default.
- See `backend/python-api-service/README.md` for more backend details.
