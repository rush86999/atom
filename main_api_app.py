"""Local dev launcher (repo root).

Delegates to the real application in backend/main_api_app.py so
`uvicorn main_api_app:app --reload` keeps working from the repo root.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.join(_ROOT, "backend")
for _p in (_ROOT, _BACKEND):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.main_api_app import app  # noqa: E402,F401
