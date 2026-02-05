import os
import sys
import types
from unittest.mock import MagicMock


# --- FORCE MOCKS ---
def mock_package(name):
    m = types.ModuleType(name)
    m.__path__ = []
    sys.modules[name] = m
    return m

np_mock = mock_package("numpy")
pd_mock = mock_package("pandas")
sys.modules["numpy.linalg"] = MagicMock()
sys.modules["numpy.core"] = MagicMock()
sys.modules["numpy._core"] = MagicMock()
sys.modules["numpy.core.multiarray"] = MagicMock()
sys.modules["numpy._core.multiarray"] = MagicMock()
sys.modules["numpy.lib"] = MagicMock()
sys.modules["networkx"] = MagicMock()
sys.modules["lancedb"] = MagicMock()

import logging
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ATOM_SAFE_MODE")

# Load Env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

app = FastAPI(title="ATOM API (SAFE MODE)", description="Minimal backend for Auth testing")

# CORS
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Auth Routes ONLY
try:
    from core.auth_endpoints import router as auth_router
    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    logger.info("✓ Auth Routes Loaded")
except ImportError as e:
    logger.error(f"Failed to load Auth routes: {e}")

# Load Agent Routes (Check if safe)
try:
    # We suspect agent routes crash, so maybe mock them or try to load
    # Use strict try-except
    from api.agent_routes import router as agent_router
    app.include_router(agent_router, prefix="/api/agents", tags=["agents"])
    logger.info("✓ Agent Routes Loaded (Attempted)")
except Exception as e:
    logger.warning(f"Failed to load Agent routes in safe mode: {e}")

@app.get("/")
def health_check():
    return {"status": "ok", "mode": "safe"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
