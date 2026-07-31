"""
Round 47 — Missing get_current_tenant: tenant-scoped BYOK endpoints broken
(Red-Green-Refactor).

api/byok_routes.py imports get_current_tenant with a silent fallback:

    try:
        from core.auth import get_current_tenant
    except ImportError:
        get_current_tenant = None

core.auth has never exported get_current_tenant, so the fallback fires and
`Depends(None)` makes FastAPI treat the tenant parameter as a REQUIRED QUERY
PARAM — every tenant-scoped endpoint (/api/ai/providers, /api/ai/providers/{id},
/api/ai/providers/{id}/keys, /api/ai/usage/track, /api/ai/pdf/optimize) returns
422 "Field required" on every call, authenticated or not.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import jwt as pyjwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.auth import ALGORITHM, SECRET_KEY
from core.database import get_db


def make_token(user_id: str) -> str:
    import core.auth as auth_mod

    return pyjwt.encode(
        {
            "sub": user_id,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "jti": "r47-jti",
        },
        auth_mod.SECRET_KEY,
        algorithm=ALGORITHM,
    )


def make_db():
    """db mock: User resolves to an active user; Tenant resolves to a row."""
    db = MagicMock()

    def query_side_effect(model, *a, **k):
        q = MagicMock()
        name = getattr(model, "__name__", str(model))
        if name == "User":
            u = MagicMock()
            u.id = "u-1"
            u.status = "active"
            u.tenant_id = "t-1"
            q.filter.return_value.first.return_value = u
        elif name == "Tenant":
            t = MagicMock()
            t.id = "t-1"
            t.ai_mode = "auto"
            q.filter.return_value.first.return_value = t
        else:
            q.filter.return_value.first.return_value = None
            q.filter.return_value.all.return_value = []
        return q

    db.query.side_effect = query_side_effect
    return db


def make_client():
    from api.byok_routes import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: make_db()
    return TestClient(app, raise_server_exceptions=False)


class TestByokTenantDependency:
    def _auth(self):
        return {"Authorization": f"Bearer {make_token('u-1')}"}

    def test_get_ai_providers_returns_200(self):
        resp = make_client().get("/api/ai/providers", headers=self._auth())
        assert resp.status_code == 200, resp.text

    def test_get_ai_provider_returns_200(self):
        resp = make_client().get("/api/ai/providers/openai", headers=self._auth())
        assert resp.status_code == 200, resp.text

    def test_store_api_key_returns_200(self):
        resp = make_client().post(
            "/api/ai/providers/openai/keys",
            params={"api_key": "sk-test-123", "key_name": "default"},
            headers=self._auth(),
        )
        assert resp.status_code == 200, resp.text
