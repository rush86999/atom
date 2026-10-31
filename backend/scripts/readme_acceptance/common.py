"""Shared world/plumbing for the README feature acceptance harness.

The harness boots the *real* FastAPI application in-process (`TestClient`)
against a throwaway SQLite database + throwaway data root, with every
external integration tokenless and every scheduler off. Scenarios talk to the
same HTTP boundary a browser/API client uses; direct service calls are only
used where the product exposes no HTTP route (and that is stated in the
claim's evidence).

No real credentials, sends, deployments, or writes to connected systems.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BACKEND = REPO / "backend"
TMP = Path(os.getenv("ATOM_README_TMP", "/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode"))
WORLD = Path(os.getenv("ATOM_README_WORLD", str(TMP / "readme-feature-world")))
EVIDENCE = Path(os.getenv("ATOM_README_EVIDENCE", str(WORLD / "evidence")))

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "ReadmeHarness!2026"


def prepare_world(reset: bool = True) -> None:
    if reset and WORLD.exists():
        shutil.rmtree(WORLD)
    (WORLD / "data").mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    os.environ.update({
        "ENVIRONMENT": "development",
        "SECRET_KEY": "readme-harness-secret",
        "JWT_SECRET_KEY": "readme-harness-jwt",
        "DATABASE_URL": f"sqlite:///{WORLD / 'atom.db'}",
        "ATOM_PRODUCT_PROFILE": "full",
        "ADMIN_PASSWORD": ADMIN_PASSWORD,
        "ATOM_BOOTSTRAP_PASSWORD_FILE": str(WORLD / "bootstrap_admin_password.txt"),
        # Isolated world: no schedulers, pollers or outbound integration sync.
        "ENABLE_SCHEDULER": "false",
        "ENABLE_INGESTION_SYNC": "false",
        "ATOM_AGENT_EVOLUTION_ENABLED": "false",
        "ATOM_CHAT_STREAMING": "false",
        "BYPASS_RATE_LIMIT": "1",
        # TESTING=1 would force backend/test_integration.db and silently ignore
        # DATABASE_URL (core/database.py). TESTING=0 keeps the isolated
        # world's explicit DATABASE_URL authoritative.
        "TESTING": "0",
        "LOG_LEVEL": "ERROR",
        # Feature flags under test, all documented product flags.
        "ATOM_GATEWAY_ENABLED": "true",
        "ATOM_TRUST_CALIBRATION_ENABLED": "true",
        "ATOM_TRUST_CALIBRATION_AUTO_ENFORCE": "approve",
        "ATOM_KNOWLEDGE_VFS_ENABLED": "true",
        "TURN_FACT_VECTOR_RECALL_ENABLED": "true",
        "LANCEDB_URI_BASE": str(WORLD / "atom_memory"),
        "LANCEDB_URI": str(WORLD / "atom_memory" / "default"),
        "ATOM_RADIO_ENABLED": "true",
        "ATOM_OBJECTIVE_LOOP_ENABLED": "true",
        "ATOM_ORACLE_VERIFIER_ENABLED": "true",
        "ATOM_ORACLE_ENFORCE": "true",
        "ATOM_LEARNING_ROUTER": "true",
        "ATOM_STAGE_ROUTING": "shadow",
        "ATOM_LOCAL_ONLY": "true" if os.getenv("ATOM_README_LOCAL_ONLY") == "1" else "false",
        "OLLAMA_BASE_URL": os.getenv("ATOM_HARNESS_LLM_URL", "http://127.0.0.1:59999/v1"),
        "ATOM_DELEGATION_CONTRACTS_ENABLED": "true",
        "ATOM_ORG_TELEMETRY_ENABLED": "true",
        "ATOM_SCIM_TOKEN": "acceptance-scim-token",
        "ATOM_EPISODE_LIFECYCLE_MAINTENANCE_ENABLED": "false",
        "ATOM_INGESTION_PERSIST_STATE": "true",
        "ATOM_BYOK_DB_SYNC": "false",
        "ATOM_OFFICE_DIR": str(WORLD / "office"),
        "ATOM_ASSIGNMENT_OUTPUT_DIR": str(WORLD / "office" / "assignments"),
        # BYOK storage is anchored to backend/data unless these override it.
        "BYOK_CONFIG_FILE": str(WORLD / "byok_config.json"),
        "BYOK_KEYS_FILE": str(WORLD / "byok_keys.json"),
        "BYOK_ENC_KEY_FILE": str(WORLD / "byok_encryption_key"),
        "OPENAI_BASE_URL": os.getenv("ATOM_HARNESS_LLM_URL", "http://127.0.0.1:59999/v1"),
        # Fake local-upstream credential: never a real cloud key. Pre-seeding
        # it makes the provider available from process start (a key stored
        # after the LLM service is constructed is not picked up by the cached
        # service — that shared-service defect is reported, not worked around).
        "OPENAI_API_KEY": "sk-acceptance-local-upstream-000000",
    })


@dataclass
class Ctx:
    client: object
    headers: dict
    token: str
    admin_id: str
    tenant_id: str
    workspace_id: str
    world: Path
    evidence: Path
    results: list = field(default_factory=list)
    cache: dict = field(default_factory=dict)

    def db(self):
        from core.database import SessionLocal
        return SessionLocal()

    def get(self, path, **kw):
        return self.client.get(path, headers=self.headers, **kw)

    def post(self, path, **kw):
        return self.client.post(path, headers=self.headers, **kw)

    def put(self, path, **kw):
        return self.client.put(path, headers=self.headers, **kw)

    def patch(self, path, **kw):
        return self.client.patch(path, headers=self.headers, **kw)

    def delete(self, path, **kw):
        return self.client.delete(path, headers=self.headers, **kw)

    def save(self, name: str, payload) -> str:
        path = self.evidence / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(payload, (dict, list)):
            path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
        else:
            path.write_text(str(payload))
        return str(path)

    def record(self, claim_id: str, status: str, evidence: list | None = None,
               notes: str = "", blocker: str = "") -> None:
        self.results.append({
            "claim_id": claim_id,
            "status": status,
            "evidence": evidence or [],
            "notes": notes,
            "blocker": blocker,
        })


def login(ctx: Ctx) -> None:
    last = None
    for _ in range(3):
        r = ctx.client.post("/api/auth/login", json={
            "username": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        last = r
        if r.status_code == 200:
            body = r.json()
            ctx.token = body["access_token"]
            ctx.headers = {"Authorization": f"Bearer {ctx.token}"}
            me = ctx.client.get("/api/auth/me", headers=ctx.headers)
            if me.status_code == 200:
                ctx.admin_id = str(me.json().get("id") or me.json().get("user", {}).get("id"))
            return
        time.sleep(1)
    raise RuntimeError(f"login failed: {last.status_code} {last.text[:400]}")


def make_agent(ctx: Ctx, name: str, *, tier: str = "intern",
               complexity: int = 2, capabilities=None, status: str = "active",
               configuration=None) -> str:
    """Create a registry agent row (the product's Agents surface does this via
    POST /api/agents; direct model insert is used only to pin a tier that the
    create route doesn't expose)."""
    import uuid
    from core.models import AgentRegistry
    db = ctx.db()
    try:
        agent = AgentRegistry(
            id=str(uuid.uuid4()),
            name=name,
            display_name=name,
            description=f"acceptance fixture: {name}",
            category="acceptance",
            role="agent",
            type="personal",
            module_path="core.generic_agent",
            class_name="GenericAgent",
            status=tier.lower(),
            confidence_score=0.5,
            capabilities=capabilities or [],
            configuration=configuration or {},
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
        )
        db.add(agent)
        db.commit()
        return agent.id
    finally:
        db.close()


def parse(resp, label: str) -> dict:
    try:
        body = resp.json()
    except Exception:
        body = {"_text": resp.text[:800]}
    return {"label": label, "status": resp.status_code, "body": body}
