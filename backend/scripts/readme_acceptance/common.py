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
WORLD_ROOT = Path(os.getenv("ATOM_README_WORLD_ROOT", str(TMP)))

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "ReadmeHarness!2026"
HARNESS_MARKER = ".atom-readme-acceptance-world"


class UnsafeWorldError(RuntimeError):
    """Raised before a destructive world operation when the path is unsafe."""


def _protected_paths() -> list[Path]:
    """Paths an acceptance reset must never target or delete as a parent."""
    protected = [
        Path("/"),
        Path("/Users"),
        Path("/private"),
        Path("/tmp"),
        Path.home(),
        REPO,
        BACKEND,
        TMP,
        WORLD_ROOT,
    ]
    # Resolve non-existent roots defensively; keep the literal path too.
    out: list[Path] = []
    for path in protected:
        out.append(path)
        try:
            out.append(path.resolve())
        except OSError:
            pass
    return out


def assert_safe_world(path: Path, *, allowed_root: Path | None = None) -> Path:
    """Validate a world path before creating, reusing, or deleting it.

    Rules (all fail closed):
      * the path itself must not be a symlink;
      * no existing component between the allowed root and the world may be
        a symlink;
      * the world must be a strict child of the allowed root (not the root);
      * the world must not equal or contain a protected path (home, repo,
        backend, temp root, filesystem root);
      * an existing world must carry the harness ownership marker.

    The marker is what distinguishes "a harness world we may replace" from
    "an arbitrary directory an operator pointed the env var at".
    """
    root = Path(allowed_root or WORLD_ROOT)
    try:
        resolved_root = root.resolve(strict=False)
        resolved = Path(path).resolve(strict=False)
    except OSError as exc:
        raise UnsafeWorldError(f"world path cannot be resolved: {path}: {exc}") from exc

    # The allowed root itself must not be a broad system/home/repo directory.
    forbidden_roots = {Path("/"), Path("/Users"), Path("/private"), Path("/tmp"),
                       Path.home(), REPO, BACKEND}
    if any(resolved_root == (p.resolve(strict=False) if p.exists() else p)
           for p in forbidden_roots):
        raise UnsafeWorldError(f"refusing protected allowed world root {resolved_root}")

    if Path(path).is_symlink():
        raise UnsafeWorldError(
            f"refusing a symlinked acceptance world: {path} -> {os.readlink(path)}"
        )
    if resolved_root == resolved:
        raise UnsafeWorldError(
            f"refusing to use the allowed world root itself as a world: {resolved}"
        )
    if resolved_root not in resolved.parents:
        raise UnsafeWorldError(
            f"world {resolved} is outside the allowed root {resolved_root}"
        )

    # Reject a symlinked component below the allowed root: deleting through
    # it could escape the sandbox even when the final resolved path is inside.
    raw_abs = Path(path).absolute()
    raw_root = root.absolute()
    cursor = raw_abs
    while cursor != raw_root and cursor != cursor.parent:
        if cursor.is_symlink():
            raise UnsafeWorldError(
                f"refusing a world under a symlinked component: {cursor}"
            )
        cursor = cursor.parent

    for protected in _protected_paths():
        try:
            protected_resolved = protected.resolve(strict=False)
        except OSError:
            protected_resolved = protected
        if resolved == protected_resolved:
            raise UnsafeWorldError(f"refusing to use protected path {protected}")
        if resolved in protected_resolved.parents:
            # This world is an ancestor of a protected path; deleting it
            # would delete /Users, the repo, the home directory, etc.
            raise UnsafeWorldError(
                f"refusing to delete/overwrite an ancestor of protected path {protected}"
            )

    if resolved.exists():
        if not resolved.is_dir():
            raise UnsafeWorldError(f"world path exists but is not a directory: {resolved}")
        marker = resolved / HARNESS_MARKER
        if not marker.is_file():
            raise UnsafeWorldError(
                f"existing world has no ownership marker ({HARNESS_MARKER}): {resolved}. "
                "Refusing to delete an unmarked directory. Remove it manually after "
                "verifying it is a harness world."
            )
    return resolved


def reset_world(path: Path | None = None, *, reset: bool = True,
                allowed_root: Path | None = None) -> Path:
    """Safely create or replace one marked acceptance world.

    The existing launcher storage guard runs first (it is a no-op unless the
    deployment configured it). Then the harness-specific marker/protected-path
    checks run before any rmtree.
    """
    world = Path(path or WORLD)
    try:
        from core.world_storage_guard import load_config, preflight

        cfg = load_config()
        if cfg.enabled:
            guard_root = cfg.root.resolve(strict=False)
            world_resolved = world.resolve(strict=False)
            if guard_root == world_resolved or guard_root in world_resolved.parents:
                # Only the deployment's own worlds root is governed by this
                # config. Applying it to an unrelated temp world would refuse
                # every run because that root may not exist.
                preflight(cfg)
    except Exception as exc:
        # A configured guard failure is a hard refusal, never a warning.
        raise UnsafeWorldError(f"world storage preflight refused the run: {exc}") from exc

    resolved = assert_safe_world(world, allowed_root=allowed_root)
    if reset and resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)
    (resolved / HARNESS_MARKER).write_text(
        "atom readme acceptance world\n"
        "This directory is disposable and owned by the README harness.\n"
    )
    return resolved


def prepare_world(reset: bool = True) -> None:
    reset_world(WORLD, reset=reset)
    (WORLD / "data").mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    os.environ.update({
        "ENVIRONMENT": "development",
        "SECRET_KEY": "readme-harness-secret",
        "JWT_SECRET_KEY": "readme-harness-jwt",
        "DATABASE_URL": f"sqlite:///{WORLD / 'atom.db'}",
        "ATOM_PRODUCT_PROFILE": os.getenv("ATOM_README_PRODUCT_PROFILE", "full"),
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
        "ATOM_MCP_ALLOWED_HOSTS": "127.0.0.1",
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
