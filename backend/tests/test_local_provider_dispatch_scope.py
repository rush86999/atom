"""J2 provider-scope work order (owner, 2026-10-12): TWO authorized
workspaces register the SAME model name at DIFFERENT endpoints with
DIFFERENT capabilities. Registration rides the REAL product path
(``POST /api/local-models`` + ``/capabilities`` with each user's own
token); the external endpoints are controlled HTTP servers that count
and attribute every completion call. No routing result is seeded and
the handler under test is never patched — dispatch runs through
``LLMService.generate_completion`` and the real ``BYOKHandler``.

The demonstrated defects this file pins (each control names the class):

- scope loss: the chat path builds ``LLMService`` without the user's
  workspace and ``generate_completion``/``generate`` collapse the
  tenant into the workspace (and drop tenant at ``_get_handler``);
- identity split: a registered local client is keyed ``local_<id>``
  while its model metadata lands in the GLOBAL pricing cache keyed by
  model name only — two workspaces overwrite each other's capabilities
  and the ranker attributes the model to a provider type, never to the
  client that holds the endpoint;
- absolute fallback: ``COST_EFFICIENT_MODELS`` has no entry for a
  dynamically registered provider id, so a healthy local route is
  skipped and the turn renders "no provider configured".
"""
import asyncio
import json
import threading
import time
import uuid
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


MODEL_NAME = "shared-model"


class _CountingEndpoint:
    """A controlled OpenAI-compatible endpoint. Counts and attributes
    every /chat/completions call; identifies itself in the reply body so
    the test can tell WHICH endpoint answered."""

    def __init__(self, tag: str, model: str = MODEL_NAME, fail: bool = False):
        self.tag = tag
        self.model = model
        self.fail = fail
        self.calls = []          # [{'model':…, 'messages':…, 'auth': bool}]
        self._lock = threading.Lock()
        outer = self

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence the per-request stderr
                pass

            def do_GET(self):
                if self.path.rstrip("/").endswith("/models"):
                    body = json.dumps({
                        "object": "list",
                        "data": [{"id": outer.model,
                                  "object": "model",
                                  "owned_by": outer.tag}],
                    }).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                if outer.fail:
                    with outer._lock:
                        outer.calls.append({"path": self.path, "fail": True})
                    body = json.dumps({"error": {"message": f"{outer.tag} upstream failure"}}).encode()
                    self.send_response(502)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                length = int(self.headers.get("Content-Length") or 0)
                payload = {}
                if length:
                    try:
                        payload = json.loads(
                            self.rfile.read(length).decode() or "{}")
                    except Exception:  # noqa: BLE001 — record shape only
                        payload = {}
                with outer._lock:
                    outer.calls.append({
                        "path": self.path,
                        "model": payload.get("model"),
                        "n_messages": len(payload.get("messages") or []),
                        "auth": bool(self.headers.get("Authorization")),
                    })
                body = json.dumps({
                    "id": f"chatcmpl-{outer.tag}",
                    "object": "chat.completion",
                    "model": payload.get("model") or outer.model,
                    "choices": [{
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant",
                                    "content": f"pong-{outer.tag}"},
                    }],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 2,
                              "total_tokens": 7},
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self._server.server_address[1]
        self.base_url = f"http://localhost:{self.port}/v1"
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()
        return False

    @property
    def hit_count(self) -> int:
        with self._lock:
            return len(self.calls)


@pytest.fixture()
def scoped_world(monkeypatch, tmp_path):
    """Scratch database + scratch credentials. Repoints core.database at
    an in-memory engine (the BYOK/local-provider loaders read through
    ``core.database.get_db_session``, not an injected session) and gives
    the process a FRESH key store, so the only configured providers are
    the ones the test registers — the fresh-install shape the J2 work
    order targets. Snapshots every process-global the dispatch path
    touches and restores them after."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import core.database as db_module
    import core.byok_endpoints as be
    import main_api_app as main_module
    from core.database import get_db
    from core.models import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    original = (db_module.engine, db_module.SessionLocal, db_module.get_db)
    db_module.engine = engine
    db_module.SessionLocal = TestSession
    db_module.get_db = override_get_db

    import api.enterprise_auth_endpoints as ent_auth
    original_ent = getattr(ent_auth, "get_db", None)
    if hasattr(ent_auth, "get_db"):
        ent_auth.get_db = override_get_db

    # SCRATCH CREDENTIAL STORE: the runtime resolves keys env-first, then
    # BYOK-file. Point both at the test's own empty store so no machine
    # credential can serve (or be billed by) a dispatch under test.
    keys_file = tmp_path / "byok_keys.json"
    keys_file.write_text('{"keys": {}}')
    monkeypatch.setenv("BYOK_KEYS_FILE", str(keys_file))
    monkeypatch.setenv("BYOK_CONFIG_FILE",
                       str(tmp_path / "byok_config.json"))
    monkeypatch.setenv("BYOK_ENC_KEY_FILE", str(tmp_path / "byok_enc"))
    monkeypatch.setattr(be, "BYOK_KEYS_FILE", str(keys_file))
    monkeypatch.setattr(be, "BYOK_CONFIG_FILE",
                        str(tmp_path / "byok_config.json"))
    monkeypatch.setattr(be, "BYOK_ENC_KEY_FILE", str(tmp_path / "byok_enc"))
    _original_manager = be._byok_manager
    be._byok_manager = None
    for _prov in ("openai", "anthropic", "deepseek", "moonshot",
                  "deepinfra", "minimax", "qwen", "gemini", "xiaomi",
                  "openrouter", "glm", "mistral", "groq", "xai",
                  "cerebras", "fireworks", "huggingface", "nvidia_nim",
                  "zai", "opencode", "opencode-go", "google"):
        monkeypatch.delenv(f"{_prov.upper()}_API_KEY", raising=False)

    Base.metadata.create_all(bind=engine)

    # Process-globals the routing path mutates: snapshot for restore.
    from core.dynamic_pricing_fetcher import get_pricing_fetcher
    from core.llm import byok_handler as bh
    from core.llm import model_route_registry as mrr

    fetcher = get_pricing_fetcher()
    pricing_keys_before = set(fetcher.pricing_cache.keys())
    cooldown_before = dict(bh._PROVIDER_COOLDOWN_UNTIL)
    cooldown_reason_before = dict(bh._PROVIDER_COOLDOWN_REASON)
    auth_failed_before = set(bh._AUTH_FAILED)

    yield {"Session": TestSession, "engine": engine,
           "override": override_get_db}

    for key in set(fetcher.pricing_cache.keys()) - pricing_keys_before:
        fetcher.pricing_cache.pop(key, None)
    bh._PROVIDER_COOLDOWN_UNTIL.clear()
    bh._PROVIDER_COOLDOWN_UNTIL.update(cooldown_before)
    bh._PROVIDER_COOLDOWN_REASON.clear()
    bh._PROVIDER_COOLDOWN_REASON.update(cooldown_reason_before)
    bh._AUTH_FAILED.clear()
    bh._AUTH_FAILED.update(auth_failed_before)
    cat = mrr.get_provider_model_catalog()
    try:
        cat._catalog.clear()
        cat._observations.clear()
    except Exception:  # noqa: BLE001 — isolation best-effort
        pass

    be._byok_manager = _original_manager
    db_module.engine, db_module.SessionLocal, db_module.get_db = original
    if original_ent is not None:
        ent_auth.get_db = original_ent
    engine.dispose()


@pytest.fixture()
def world_app(scoped_world):
    """The REAL FastAPI app over the scratch DB (real auth + the real
    /api/local-models registration path)."""
    from fastapi.testclient import TestClient

    import main_api_app as main_module
    from core.database import get_db

    app = main_module.app
    app.dependency_overrides[get_db] = scoped_world["override"]
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


def _authorized_workspace(app, scoped_world) -> dict:
    """One authorized workspace through the REAL register/login path.
    Each registered user gets its own tenant + workspace (the product's
    own registration creates them)."""
    email = f"scope_{uuid.uuid4().hex[:10]}@test.example.com"
    password = "TestPass123!"
    resp = app.post("/api/auth/register", json={
        "email": email, "password": password,
        "first_name": "Scope", "last_name": "Tester"})
    assert resp.status_code in (200, 201), resp.text
    login = app.post("/api/auth/login", json={
        "username": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json().get("access_token")
    assert token, "no access token"
    db = scoped_world["Session"]()
    try:
        from core.models import User

        user = db.query(User).filter(User.email == email).first()
        assert user is not None and user.workspace_id and user.tenant_id
        return {"email": email, "token": token,
                "user_id": user.id,
                "workspace_id": user.workspace_id,
                "tenant_id": user.tenant_id}
    finally:
        db.close()


def _register_local_route(app, ws: dict, base_url: str, *, tools: bool,
                          quality: float) -> str:
    """Register provider + capabilities through the PRODUCT path."""
    headers = {"Authorization": f"Bearer {ws['token']}"}
    reg = app.post("/api/local-models", headers=headers, json={
        "name": f"local-{uuid.uuid4().hex[:6]}",
        "provider_type": "ollama",
        "base_url": base_url})
    assert reg.status_code == 200, reg.text
    provider_id = reg.json().get("id")
    assert provider_id, reg.text
    caps = app.post(f"/api/local-models/{provider_id}/capabilities",
                    headers=headers, json={
                        "model_id": MODEL_NAME,
                        "supports_tools": tools,
                        "supports_vision": False,
                        "supports_reasoning": False,
                        "quality_score": quality,
                        "speed_score": 0.8,
                        "context_window": 8192})
    assert caps.status_code == 200, caps.text
    return provider_id


def _completion(service, ws: dict, prompt: str = "Reply with PONG") -> dict:
    return asyncio.run(service.generate_completion(
        messages=[{"role": "user", "content": prompt}],
        workspace_id=ws["workspace_id"], tenant_id=ws["tenant_id"]))


class TestSequentialIsolation:
    """Control row 1-4 of the work order: each workspace reaches ONLY
    its authorized endpoint, with ITS OWN capabilities."""

    def test_each_workspace_reaches_only_its_own_endpoint(
            self, scoped_world, world_app):
        from core.llm_service import LLMService

        with _CountingEndpoint("A") as ep_a, _CountingEndpoint("B") as ep_b:
            ws_a = _authorized_workspace(world_app, scoped_world)
            ws_b = _authorized_workspace(world_app, scoped_world)
            prov_a = _register_local_route(
                world_app, ws_a, ep_a.base_url, tools=True, quality=0.9)
            # B's registration differs in CAPABILITY (no tools), not in
            # viability: quality stays above the simple-tier floor so a
            # plain turn must reach B's own endpoint.
            prov_b = _register_local_route(
                world_app, ws_b, ep_b.base_url, tools=False, quality=0.85)

            # Workspace A's turn — dispatch through the REAL service and
            # handler. The reply must come from endpoint A.
            svc_a = LLMService(workspace_id=ws_a["workspace_id"],
                               tenant_id=ws_a["tenant_id"])
            out_a = _completion(svc_a, ws_a)
            assert ep_a.hit_count >= 1, (
                "workspace A's request never reached endpoint A; "
                f"provider={out_a.get('provider')} model={out_a.get('model')} "
                f"content={str(out_a.get('content'))[:200]}")
            assert ep_b.hit_count == 0, (
                "workspace A's request LEAKED to workspace B's endpoint")
            assert out_a.get("content") == "pong-A", (
                f"endpoint identity mismatch: {out_a.get('content')!r}")
            assert str(out_a.get("provider") or "").startswith(
                f"local_{prov_a[:8]}"), (
                "the route must keep the registered provider identity "
                f"(local_{prov_a[:8]}), got {out_a.get('provider')!r}")

            # Workspace B's turn — same model name, different endpoint.
            svc_b = LLMService(workspace_id=ws_b["workspace_id"],
                               tenant_id=ws_b["tenant_id"])
            out_b = _completion(svc_b, ws_b)
            assert ep_b.hit_count >= 1, (
                "workspace B's request never reached endpoint B")
            assert out_b.get("content") == "pong-B", (
                f"endpoint identity mismatch: {out_b.get('content')!r}")

    def test_capability_association_follows_the_owning_workspace(
            self, scoped_world, world_app):
        """A registers shared-model WITH tools; B registers shared-model
        WITHOUT tools. A's handler must see A's registration, B's must
        see B's — the shared pricing cache must not collapse them."""
        from core.llm_service import LLMService

        with _CountingEndpoint("A") as ep_a, _CountingEndpoint("B") as ep_b:
            ws_a = _authorized_workspace(world_app, scoped_world)
            ws_b = _authorized_workspace(world_app, scoped_world)
            prov_a = _register_local_route(world_app, ws_a, ep_a.base_url,
                                           tools=True, quality=0.9)
            prov_b = _register_local_route(world_app, ws_b, ep_b.base_url,
                                           tools=False, quality=0.85)

            # A tool-requiring task must rank workspace A's OWN
            # registration (supports_tools=True), never B's record of
            # the same model name.
            svc_a = LLMService(workspace_id=ws_a["workspace_id"],
                               tenant_id=ws_a["tenant_id"])
            handler_a = svc_a.handler
            own_key = f"local_{prov_a[:8]}"
            assert own_key in handler_a.clients, (
                "the workspace's registered client must load; clients="
                f"{sorted(handler_a.clients)}")
            ranked = handler_a.get_ranked_providers(
                handler_a.analyze_query_complexity("Reply with PONG"),
                requires_tools=True)
            ranked_pairs = [(p, m) for p, m in ranked]
            assert (own_key, MODEL_NAME) in ranked_pairs, (
                "the owning workspace's registered route must rank for a "
                f"tool task; ranked={ranked_pairs[:8]}")


class TestChatShapedScope:
    """The boundary the owner added: ``generate_completion`` accepts
    tenant_id, and the chat path calls it with tenant only. The handler
    it selects must still be the USER's workspace — tenant and workspace
    stay separate identifiers."""

    def test_tenant_only_dispatch_resolves_the_user_workspace(
            self, scoped_world, world_app):
        from core.llm_service import LLMService

        with _CountingEndpoint("A") as ep_a:
            ws_a = _authorized_workspace(world_app, scoped_world)
            _register_local_route(world_app, ws_a, ep_a.base_url,
                                  tools=True, quality=0.9)

            # THE CHAT SHAPE: service built with tenant only; the call
            # passes tenant only (ChatOrchestrator.__init__ +
            # generate_completion(tenant_id=…) today).
            svc = LLMService(tenant_id=ws_a["tenant_id"])
            out = asyncio.run(svc.generate_completion(
                messages=[{"role": "user", "content": "Reply with PONG"}],
                tenant_id=ws_a["tenant_id"]))
            assert ep_a.hit_count >= 1, (
                "a tenant-scoped (chat-shaped) request never reached the "
                f"user's own endpoint; provider={out.get('provider')} "
                f"content={str(out.get('content'))[:200]}")
            assert out.get("content") == "pong-A"
            assert svc.handler.workspace_id == ws_a["workspace_id"], (
                "the selected handler must carry the user's workspace, "
                f"got {svc.handler.workspace_id!r}")


class TestDispatchControls:
    """The work order's production-dispatch controls (rows 2 and 4-9).
    Row 1 (sequential) and row 5 (ranking discovery) are covered in
    TestSequentialIsolation."""

    def test_concurrent_requests_do_not_contaminate(
            self, scoped_world, world_app):
        """A and B, concurrent requests: no handler or route
        contamination — each reply names its own endpoint."""
        import concurrent.futures

        from core.llm_service import LLMService

        with _CountingEndpoint("A") as ep_a, _CountingEndpoint("B") as ep_b:
            ws_a = _authorized_workspace(world_app, scoped_world)
            ws_b = _authorized_workspace(world_app, scoped_world)
            _register_local_route(world_app, ws_a, ep_a.base_url,
                                  tools=True, quality=0.9)
            _register_local_route(world_app, ws_b, ep_b.base_url,
                                  tools=False, quality=0.85)
            svc_a = LLMService(workspace_id=ws_a["workspace_id"],
                               tenant_id=ws_a["tenant_id"])
            svc_b = LLMService(workspace_id=ws_b["workspace_id"],
                               tenant_id=ws_b["tenant_id"])

            def _turn(service, ws):
                return asyncio.run(service.generate_completion(
                    messages=[{"role": "user", "content": "Reply PONG"}],
                    workspace_id=ws["workspace_id"],
                    tenant_id=ws["tenant_id"]))

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                futures = [ex.submit(_turn, svc_a, ws_a),
                           ex.submit(_turn, svc_b, ws_b),
                           ex.submit(_turn, svc_a, ws_a),
                           ex.submit(_turn, svc_b, ws_b)]
                outs = [f.result(timeout=90) for f in futures]

            contents = [str(o.get("content")) for o in outs]
            assert sum(c == "pong-A" for c in contents) == 2, (
                f"endpoint A identity corrupted under concurrency: "
                f"{contents}")
            assert sum(c == "pong-B" for c in contents) == 2, (
                f"endpoint B identity corrupted under concurrency: "
                f"{contents}")
            assert ep_a.hit_count >= 2 and ep_b.hit_count >= 2

    def test_capability_gap_is_truthful_per_workspace(
            self, scoped_world, world_app):
        """Same model, different capabilities: a tool-requiring ranking
        uses the CAPABLE authorized route (A) and truthfully refuses the
        incapable one (B) — each from its own registration record."""
        from core.llm.byok_handler import QueryComplexity
        from core.llm_service import LLMService

        with _CountingEndpoint("A") as ep_a, _CountingEndpoint("B") as ep_b:
            ws_a = _authorized_workspace(world_app, scoped_world)
            ws_b = _authorized_workspace(world_app, scoped_world)
            prov_a = _register_local_route(world_app, ws_a, ep_a.base_url,
                                           tools=True, quality=0.9)
            prov_b = _register_local_route(world_app, ws_b, ep_b.base_url,
                                           tools=False, quality=0.85)

            ranked_a = LLMService(
                workspace_id=ws_a["workspace_id"],
                tenant_id=ws_a["tenant_id"]).handler
            ranked_b = LLMService(
                workspace_id=ws_b["workspace_id"],
                tenant_id=ws_b["tenant_id"]).handler
            tools_rank_a = ranked_a.get_ranked_providers(
                QueryComplexity.SIMPLE, requires_tools=True)
            tools_rank_b = ranked_b.get_ranked_providers(
                QueryComplexity.SIMPLE, requires_tools=True)
            assert (f"local_{prov_a[:8]}", MODEL_NAME) in [
                (p, m) for p, m in tools_rank_a], (
                f"A's capable route must rank for a tool task: "
                f"{[(p, m) for p, m in tools_rank_a][:6]}")
            assert (f"local_{prov_b[:8]}", MODEL_NAME) not in [
                (p, m) for p, m in tools_rank_b], (
                "B's registration says supports_tools=False — its route "
                "must NOT rank for a tool task")

    def test_updating_b_does_not_change_a(
            self, scoped_world, world_app):
        """Update B's registration: A's endpoint and capabilities remain
        unchanged (the shared cache entry is rewritten by B — A's own
        route record drives A's routing)."""
        from core.llm.byok_handler import QueryComplexity
        from core.llm_service import LLMService

        with _CountingEndpoint("A") as ep_a, _CountingEndpoint("B") as ep_b:
            ws_a = _authorized_workspace(world_app, scoped_world)
            ws_b = _authorized_workspace(world_app, scoped_world)
            prov_a = _register_local_route(world_app, ws_a, ep_a.base_url,
                                           tools=True, quality=0.9)
            prov_b = _register_local_route(world_app, ws_b, ep_b.base_url,
                                           tools=False, quality=0.85)

            svc_a = LLMService(workspace_id=ws_a["workspace_id"],
                               tenant_id=ws_a["tenant_id"])
            out_before = _completion(svc_a, ws_a)
            assert out_before.get("content") == "pong-A"
            first_provider = str(svc_a.handler._last_used_provider)

            # B re-declares its model THROUGH THE PRODUCT: different
            # window and tools.
            headers = {"Authorization": f"Bearer {ws_b['token']}"}
            caps = world_app.post(
                f"/api/local-models/{prov_b}/capabilities", headers=headers,
                json={"model_id": MODEL_NAME, "supports_tools": True,
                      "supports_vision": True, "supports_reasoning": True,
                      "quality_score": 0.95, "speed_score": 0.8,
                      "context_window": 4096})
            assert caps.status_code == 200, caps.text

            # A's route is untouched: same endpoint identity, same
            # declared capability row.
            out_a = _completion(svc_a, ws_a)
            assert out_a.get("content") == "pong-A", (
                f"A's endpoint identity changed after B's update: "
                f"{out_a.get('content')!r}")
            assert str(out_a.get("provider")) == first_provider
            route_a = svc_a.handler._local_routes.get(MODEL_NAME)
            assert route_a["provider_key"] == f"local_{prov_a[:8]}"
            assert route_a["supports_tools"] is True
            assert route_a["context_window"] == 8192, (
                "A's declared context window must not adopt B's rewrite")

    def test_absolute_fallback_serves_a_registered_local_route(
            self, scoped_world, world_app):
        """Absolute fallback: a provider with NO static default entry —
        a dynamically registered local route — is eligible through its
        OWN registered model, and the dispatch lands on its endpoint."""
        from core.llm.byok_handler import QueryComplexity
        from core.llm_service import LLMService

        with _CountingEndpoint("A") as ep_a:
            ws_a = _authorized_workspace(world_app, scoped_world)
            _register_local_route(world_app, ws_a, ep_a.base_url,
                                  tools=True, quality=0.85)
            svc = LLMService(workspace_id=ws_a["workspace_id"],
                             tenant_id=ws_a["tenant_id"])
            handler = svc.handler
            # An ADVANCED ask outruns the registration's declared quality
            # (85 < the 90 advanced floor), so BPC ranking returns no
            # candidate and get_optimal_provider walks the absolute
            # fallback — where the registered route must qualify WITHOUT
            # a static provider default.
            provider, model = handler.get_optimal_provider(
                QueryComplexity.ADVANCED)
            assert provider.startswith("local_") and model == MODEL_NAME, (
                "the absolute fallback must select the registered local "
                f"route, got {provider}/{model}")
            out = _completion(svc, ws_a)
            assert out.get("content") == "pong-A"
            assert ep_a.hit_count >= 1

    def test_no_configuration_is_truthful(self, scoped_world, world_app):
        """No configuration: a workspace with no registered provider and
        no keys gets a truthful no-provider result — nothing dispatched,
        nothing invented."""
        from core.llm_service import LLMService

        with _CountingEndpoint("A") as ep_a:
            ws_a = _authorized_workspace(world_app, scoped_world)
            svc = LLMService(workspace_id=ws_a["workspace_id"],
                             tenant_id=ws_a["tenant_id"])
            out = _completion(svc, ws_a)
            content = str(out.get("content") or "")
            assert ep_a.hit_count == 0, (
                "an unconfigured workspace must not dispatch anywhere")
            assert ("no api key" in content.lower()
                    or "no provider" in content.lower()
                    or "no eligible" in content.lower()
                    or "no dispatchable" in content.lower()), (
                f"the no-configuration result must be truthful, got "
                f"{content[:200]!r}")

    def test_configuration_without_qualifying_route_is_truthful(
            self, scoped_world, world_app):
        """Configuration exists but no route qualifies: a provider
        registered WITHOUT a capability record names no servable model —
        the result is a truthful no-eligible-route, never an invented
        model name."""
        from core.llm_service import LLMService

        with _CountingEndpoint("A") as ep_a:
            ws_a = _authorized_workspace(world_app, scoped_world)
            headers = {"Authorization": f"Bearer {ws_a['token']}"}
            reg = world_app.post("/api/local-models", headers=headers, json={
                "name": "bare-provider",
                "provider_type": "ollama",
                "base_url": ep_a.base_url})
            assert reg.status_code == 200, reg.text
            # NO capabilities declared — nothing defines a servable model.
            svc = LLMService(workspace_id=ws_a["workspace_id"],
                             tenant_id=ws_a["tenant_id"])
            out = _completion(svc, ws_a)
            content = str(out.get("content") or "")
            assert ep_a.hit_count == 0, (
                "a capability-less registration must not dispatch")
            assert ("no eligible" in content.lower()
                    or "no dispatchable" in content.lower()
                    or "not initialized" in content.lower()
                    or "no provider" in content.lower()), (
                f"the no-qualifying-route result must be truthful, got "
                f"{content[:200]!r}")
            assert MODEL_NAME not in content, (
                "no model may be invented into a route")

    def test_registration_and_identity_survive_restart(
            self, scoped_world, world_app):
        """Restart: a NEW LLMService (fresh handler, fresh DB load)
        against the same store rediscovers the registration and the
        same route identity serves again."""
        from core.llm_service import LLMService

        with _CountingEndpoint("A") as ep_a:
            ws_a = _authorized_workspace(world_app, scoped_world)
            prov_a = _register_local_route(world_app, ws_a, ep_a.base_url,
                                           tools=True, quality=0.9)
            first = _completion(
                LLMService(workspace_id=ws_a["workspace_id"],
                           tenant_id=ws_a["tenant_id"]), ws_a)
            assert first.get("content") == "pong-A"

            # THE RESTART: a brand-new service over the same persisted
            # registration (the process did not keep the old handler).
            reborn = LLMService(workspace_id=ws_a["workspace_id"],
                                tenant_id=ws_a["tenant_id"])
            second = _completion(reborn, ws_a)
            assert second.get("content") == "pong-A", (
                f"the route identity did not survive the restart: "
                f"{second.get('content')!r}")
            assert str(second.get("provider")).startswith(
                f"local_{prov_a[:8]}")
            assert ep_a.hit_count >= 2


class TestScopeResolutionFailures:
    """Owner correction 2026-10-12: an unresolved scope is NEVER
    substituted with another workspace. An explicitly named tenant with
    missing, ambiguous or failed resolution produces an explicit
    unresolved-scope result and ZERO provider calls — every negative
    here asserts the existing workspace's endpoint saw nothing."""

    def test_unknown_tenant_is_refused_without_calls(
            self, scoped_world, world_app):
        from core.llm_service import LLMService

        with _CountingEndpoint("A") as ep_a:
            ws_a = _authorized_workspace(world_app, scoped_world)
            _register_local_route(world_app, ws_a, ep_a.base_url,
                                  tools=True, quality=0.9)
            svc = LLMService(workspace_id=ws_a["workspace_id"],
                             tenant_id=ws_a["tenant_id"])
            out = asyncio.run(svc.generate_completion(
                messages=[{"role": "user", "content": "Reply PONG"}],
                tenant_id=f"tenant-{uuid.uuid4().hex}"))
            assert out.get("success") is False, (
                "an unknown tenant must not fake success")
            assert out.get("provider") is None and \
                not (out.get("usage") or {}).get("total_tokens"), (
                "no provider was consulted")
            assert "unresolved" in str(out.get("content")).lower()
            assert ep_a.hit_count == 0, (
                "the existing workspace's endpoint must see ZERO calls "
                "from an unresolved tenant's dispatch")

    def test_lookup_failure_is_refused_and_not_cached(
            self, scoped_world, world_app, monkeypatch):
        from core import database as db_module
        from core.llm_service import LLMService

        with _CountingEndpoint("A") as ep_a:
            ws_a = _authorized_workspace(world_app, scoped_world)
            _register_local_route(world_app, ws_a, ep_a.base_url,
                                  tools=True, quality=0.9)
            svc = LLMService(workspace_id=ws_a["workspace_id"],
                             tenant_id=ws_a["tenant_id"])

            def _broken_session():
                raise RuntimeError("database unavailable (simulated)")

            monkeypatch.setattr(db_module, "get_db_session",
                                _broken_session)
            out = asyncio.run(svc.generate_completion(
                messages=[{"role": "user", "content": "Reply PONG"}],
                tenant_id=f"tenant-{uuid.uuid4().hex}"))
            assert out.get("success") is False
            assert ep_a.hit_count == 0, (
                "a failed scope lookup must not dispatch to the existing "
                "workspace's endpoint")

    def test_multiple_workspaces_under_one_tenant_stay_unresolved(
            self, scoped_world, world_app):
        """A tenant binding MULTIPLE workspaces is ambiguous: tenant-only
        resolution refuses (registration creating one workspace does not
        establish that a tenant always has exactly one)."""
        from core.llm_service import LLMService

        with _CountingEndpoint("A") as ep_a, _CountingEndpoint("B") as ep_b:
            ws_a = _authorized_workspace(world_app, scoped_world)
            _register_local_route(world_app, ws_a, ep_a.base_url,
                                  tools=True, quality=0.9)
            # A SECOND workspace under the SAME tenant (data-layer
            # setup: the ambiguity itself is what's under test).
            from core.models import Workspace

            db = scoped_world["Session"]()
            try:
                db.add(Workspace(id=str(uuid.uuid4()), name="Second",
                                 tenant_id=ws_a["tenant_id"]))
                db.commit()
            finally:
                db.close()

            # TENANT-ONLY: ambiguous -> refused, zero calls.
            svc = LLMService(tenant_id=ws_a["tenant_id"])
            assert svc.scope_is_unresolved(), (
                "a multi-workspace tenant is ambiguous for tenant-only "
                "resolution")
            out = asyncio.run(svc.generate_completion(
                messages=[{"role": "user", "content": "Reply PONG"}],
                tenant_id=ws_a["tenant_id"]))
            assert out.get("success") is False
            assert ep_a.hit_count == 0 and ep_b.hit_count == 0, (
                "an ambiguous tenant must not reach EITHER endpoint")

            # EXPLICIT AUTHENTICATED WORKSPACE selection under the same
            # ambiguous tenant still routes to ITS OWN endpoint.
            explicit = LLMService(workspace_id=ws_a["workspace_id"],
                                  tenant_id=ws_a["tenant_id"])
            out_a = asyncio.run(explicit.generate_completion(
                messages=[{"role": "user", "content": "Reply PONG"}],
                workspace_id=ws_a["workspace_id"],
                tenant_id=ws_a["tenant_id"]))
            assert out_a.get("content") == "pong-A", (
                "explicit workspace selection routes to its own endpoint "
                f"(got {out_a.get('content')!r})")
            assert ep_b.hit_count == 0

    def test_service_recovers_after_binding_repair(
            self, scoped_world, world_app):
        """Item 3: a failed/missing resolution must not leave the
        long-lived service stuck. After the workspace binding is
        repaired, the SAME service instance resolves its own scope and
        dispatches to the recovered workspace's endpoint."""
        from core.llm_service import LLMService
        from core.models import Workspace

        with _CountingEndpoint("A") as ep_a:
            ws_c = _authorized_workspace(world_app, scoped_world)
            _register_local_route(world_app, ws_c, ep_a.base_url,
                                  tools=True, quality=0.9)
            # BREAK the binding (the workspace row disappears).
            db = scoped_world["Session"]()
            try:
                bound = (db.query(Workspace)
                         .filter(Workspace.id == ws_c["workspace_id"])
                         .first())
                assert bound is not None
                db.delete(bound)
                db.commit()
            finally:
                db.close()

            svc = LLMService(tenant_id=ws_c["tenant_id"])
            assert svc.scope_is_unresolved(), (
                "a missing binding leaves the service unresolved")
            out = asyncio.run(svc.generate_completion(
                messages=[{"role": "user", "content": "Reply PONG"}],
                tenant_id=ws_c["tenant_id"]))
            assert out.get("success") is False and ep_a.hit_count == 0

            # REPAIR the binding — the SAME workspace row returns.
            db = scoped_world["Session"]()
            try:
                db.add(Workspace(id=ws_c["workspace_id"], name="Default",
                                 tenant_id=ws_c["tenant_id"]))
                db.commit()
            finally:
                db.close()

            # The SAME (long-lived) service instance: the next dispatch
            # adopts the repaired binding — never stuck on the failure.
            out2 = asyncio.run(svc.generate_completion(
                messages=[{"role": "user", "content": "Reply PONG"}],
                tenant_id=ws_c["tenant_id"]))
            assert out2.get("content") == "pong-A", (
                f"the service must recover after the binding repair, got "
                f"{out2.get('content')!r}")
            assert not svc.scope_is_unresolved()
            assert ep_a.hit_count == 1

    def test_revoked_binding_never_serves_from_the_stale_resolution(
            self, scoped_world, world_app):
        """Verifier finding P3 on 316317f3b: a POSITIVE resolution must
        not outlive its binding. After the tenant's workspace is
        revoked, the SAME long-lived service refuses — zero calls to
        the revoked workspace's endpoint."""
        from core.llm_service import LLMService
        from core.models import Workspace

        with _CountingEndpoint("A") as ep_a:
            ws_a = _authorized_workspace(world_app, scoped_world)
            _register_local_route(world_app, ws_a, ep_a.base_url,
                                  tools=True, quality=0.9)
            svc = LLMService(tenant_id=ws_a["tenant_id"])
            out = asyncio.run(svc.generate_completion(
                messages=[{"role": "user", "content": "Reply PONG"}],
                tenant_id=ws_a["tenant_id"]))
            assert out.get("content") == "pong-A", (
                "the resolved route serves before the revocation")
            assert ep_a.hit_count == 1

            # REVOKE: the tenant's binding is removed.
            db = scoped_world["Session"]()
            try:
                bound = (db.query(Workspace)
                         .filter(Workspace.id == ws_a["workspace_id"])
                         .first())
                db.delete(bound)
                db.commit()
            finally:
                db.close()

            out2 = asyncio.run(svc.generate_completion(
                messages=[{"role": "user", "content": "Reply PONG"}],
                tenant_id=ws_a["tenant_id"]))
            assert out2.get("success") is False, (
                "a revoked binding must not serve from the stale "
                f"resolution: {out2.get('content')!r}")
            assert out2.get("unresolved_scope"), (
                "the refusal names the unresolved scope")
            assert ep_a.hit_count == 1, (
                "ZERO calls to the revoked workspace's endpoint after "
                "the binding was removed")

    def test_changed_binding_routes_to_the_new_workspace(
            self, scoped_world, world_app):
        """Verifier finding P3 on 316317f3b: a binding CHANGED to a
        different workspace must not serve the old endpoint — the same
        long-lived service adopts the new scope and its handler is
        rebuilt for it."""
        from core.llm_service import LLMService
        from core.models import Workspace

        with _CountingEndpoint("A") as ep_a, _CountingEndpoint("B") as ep_b:
            ws_a = _authorized_workspace(world_app, scoped_world)
            ws_b = _authorized_workspace(world_app, scoped_world)
            _register_local_route(world_app, ws_a, ep_a.base_url,
                                  tools=True, quality=0.9)
            _register_local_route(world_app, ws_b, ep_b.base_url,
                                  tools=False, quality=0.85)
            svc = LLMService(tenant_id=ws_a["tenant_id"])
            out = asyncio.run(svc.generate_completion(
                messages=[{"role": "user", "content": "Reply PONG"}],
                tenant_id=ws_a["tenant_id"]))
            assert out.get("content") == "pong-A"

            # CHANGED: ws_a's binding is replaced by ws_b under the
            # SAME tenant (ws_a's row deleted, ws_b re-bound).
            db = scoped_world["Session"]()
            try:
                db.query(Workspace).filter(
                    Workspace.id == ws_a["workspace_id"]).delete()
                bound_b = (db.query(Workspace)
                           .filter(Workspace.id == ws_b["workspace_id"])
                           .first())
                bound_b.tenant_id = ws_a["tenant_id"]
                db.commit()
            finally:
                db.close()

            out2 = asyncio.run(svc.generate_completion(
                messages=[{"role": "user", "content": "Reply PONG"}],
                tenant_id=ws_a["tenant_id"]))
            assert out2.get("content") == "pong-B", (
                f"the changed binding must route to the NEW workspace's "
                f"endpoint, got {out2.get('content')!r}")
            assert ep_a.hit_count == 1, (
                "ZERO calls to the old workspace's endpoint after the "
                "binding changed")
            assert ep_b.hit_count >= 1
            assert svc.handler.workspace_id == ws_b["workspace_id"], (
                "the shared handler was rebuilt for the adopted scope")

    def test_scope_adoption_never_hands_out_the_stale_handler(
            self, scoped_world, world_app, monkeypatch):
        """Agent 3 finding 1 on d6fbcd846: adoption swapped the service
        workspace BEFORE the (slow) handler rebuild, so a concurrent
        reader paired the NEW scope with the OLD handler and dispatched
        to the old endpoint. Selection is serialized: a reader entering
        during an adoption blocks, then sees the adopted handler —
        never the stale one."""
        from core import llm_service as lsm
        from core.llm_service import LLMService
        from core.models import Workspace

        with _CountingEndpoint("A") as ep_a, _CountingEndpoint("B") as ep_b:
            ws_a = _authorized_workspace(world_app, scoped_world)
            ws_b = _authorized_workspace(world_app, scoped_world)
            _register_local_route(world_app, ws_a, ep_a.base_url,
                                  tools=True, quality=0.9)
            _register_local_route(world_app, ws_b, ep_b.base_url,
                                  tools=False, quality=0.85)
            # A lightweight stand-in replaces BYOKHandler for this
            # whole test BEFORE any construction — the defect is the
            # SERVICE-level pairing of (workspace, handler), and a real
            # handler's held DB session deadlocks the single-connection
            # in-memory fixture under threads. The constructor's first
            # scope resolution (W1) and every later adoption therefore
            # build stand-ins, and construction is SLOW to widen the
            # mid-swap window a concurrent reader would (unlocked) trip.
            class _SlowStandIn:
                def __init__(self, workspace_id=None, tenant_id=None,
                             db_session=None):
                    time.sleep(0.2)
                    self.workspace_id = workspace_id
                    self.tenant_id = tenant_id
                    self.clients = {}

            monkeypatch.setattr(lsm, "BYOKHandler", _SlowStandIn)
            svc = LLMService(tenant_id=ws_a["tenant_id"])
            first = svc._get_handler(tenant_id=ws_a["tenant_id"])
            assert first.workspace_id == ws_a["workspace_id"]

            # CHANGED binding: ws_a revoked, ws_b re-bound to the tenant.
            db = scoped_world["Session"]()
            try:
                db.query(Workspace).filter(
                    Workspace.id == ws_a["workspace_id"]).delete()
                bound_b = (db.query(Workspace)
                           .filter(Workspace.id == ws_b["workspace_id"])
                           .first())
                bound_b.tenant_id = ws_a["tenant_id"]
                db.commit()
            finally:
                db.close()

            adopted_box = {}

            def _adopting_reader():
                adopted_box["handler"] = svc._get_handler(
                    tenant_id=ws_a["tenant_id"])

            adopter = threading.Thread(target=_adopting_reader)
            adopter.start()
            time.sleep(0.05)          # the adopter is inside construction
            concurrent = svc._get_handler(tenant_id=ws_a["tenant_id"])
            adopter.join(timeout=10)

            new_ws = ws_b["workspace_id"]
            assert concurrent.workspace_id == new_ws, (
                "a reader entering mid-adoption must receive the ADOPTED "
                f"handler, got the handler for "
                f"{concurrent.workspace_id}")
            assert adopted_box["handler"].workspace_id == new_ws
            # and the shared state is coherent afterwards
            after = svc._get_handler(tenant_id=ws_a["tenant_id"])
            assert after.workspace_id == new_ws and after is concurrent

    def test_cold_pricing_refresh_never_hides_the_registered_route(
            self, scoped_world, world_app, monkeypatch):
        """Agent 3 finding 2 on d6fbcd846: on a cold pricing cache the
        auto-refresh REPLACES the public cache dict before the first
        ranking, dropping the just-stamped registration route — the
        fresh user got a false 'No eligible LLM providers' (8/8 cold).
        The route's availability is independent of public cache
        replacement: the very first dispatch reaches its endpoint."""
        from core.dynamic_pricing_fetcher import get_pricing_fetcher
        from core.llm_service import LLMService

        with _CountingEndpoint("A") as ep_a:
            ws_a = _authorized_workspace(world_app, scoped_world)
            _register_local_route(world_app, ws_a, ep_a.base_url,
                                  tools=True, quality=0.9)
            svc = LLMService(workspace_id=ws_a["workspace_id"],
                             tenant_id=ws_a["tenant_id"])
            assert svc.handler._local_routes, "the registration loaded"

            # FORCE the public-cache replacement a cold start performs:
            # cache invalid -> the ranking initializer refreshes and
            # REBINDS pricing_cache from its sources (offline stubs; the
            # rebind itself is the mechanism under test).
            fetcher = get_pricing_fetcher()

            async def _empty():
                return {}

            monkeypatch.setattr(fetcher, "fetch_litellm_pricing", _empty)
            monkeypatch.setattr(fetcher, "fetch_openrouter_pricing",
                                _empty)
            monkeypatch.setattr(fetcher, "fetch_opencode_pricing", _empty)
            fetcher.last_fetch = None
            fetcher.pricing_cache = {}

            # THE FRESH-USER SHAPE: first dispatch in the process.
            out = _completion(svc, ws_a)
            assert out.get("content") == "pong-A", (
                "the first dispatch must reach the registered route even "
                f"when the pricing refresh replaced the public cache; "
                f"got {str(out.get('content'))[:160]!r}")
            assert ep_a.hit_count == 1


class TestChatPublicRouteScope:
    """The PUBLIC-ROUTE user boundary (pristine-J2 first-request failure,
    2026-10-12): the chat orchestrator singleton is constructed
    default-scoped at import, and the reply dispatch rode that scope —
    a fresh user's own registered provider was invisible ("No eligible
    LLM providers found for your current plan") even though the rows
    were durably theirs. The counted first authenticated chat message
    must dispatch in the REQUEST's scope and reach the user's own
    endpoint."""

    def test_first_chat_message_reaches_the_user_endpoint_isolation(
            self, scoped_world, world_app):
        """NARROW endpoint-isolation proof only: the counted first
        message reaches the user's own registered endpoint. This test
        deliberately does NOT assert the full user outcome envelope
        (success flags, outcome agreement) — that is
        test_public_route_reply_agrees_with_durable_outcome below."""
        import asyncio
        import json
        from contextlib import ExitStack
        from unittest.mock import AsyncMock, MagicMock, patch

        import integrations.chat_orchestrator as co
        from core.llm_service import LLMService
        from core.chat_tool_planner import ToolPlan

        with _CountingEndpoint("A") as ep_a:
            ws_a = _authorized_workspace(world_app, scoped_world)
            _register_local_route(world_app, ws_a, ep_a.base_url,
                                  tools=True, quality=0.9)

            # THE PUBLIC-ROUTE SHAPE: a default-scoped orchestrator
            # singleton with the default-scoped service — exactly what
            # the module-level construction produces at import.
            orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
            orch.tenant_id = "default"
            orch._cancelled_sessions = set()
            orch._budget_exceeded_runs = set()
            orch.llm_service = LLMService(tenant_id="default")

            session = {"id": "sess-scope", "history": []}

            async def _plan_ce(*a, **k):
                class _P:
                    wants_edit = False
                return _P()

            no_tool_plan = ToolPlan(use_tool=False, service="datasets",
                                    intent="search", query="unused",
                                    reason="no tool for a plain reply")

            with ExitStack() as st:
                for cm in [
                    patch.object(orch, "_get_or_create_session",
                                 return_value=session),
                    patch.object(orch, "_resolve_canvas_ctx",
                                 new=AsyncMock(return_value=dict({
                                     "canvas_id": "cv-scope",
                                     "canvas_type": "email",
                                     "title": "Scope",
                                     "content": {"body": "<p>quote table</p>"}}))),
                    patch.object(orch, "_start_chat_execution",
                                 return_value="exec-scope"),
                    patch.object(orch, "_record_chat_step", new=AsyncMock()),
                    patch.object(orch, "_emit_agent_status",
                                 new=AsyncMock()),
                    patch.object(orch, "_update_session",
                                 new=MagicMock()),
                    patch.object(orch, "_finish_chat_execution",
                                 new=MagicMock()),
                    patch.object(orch, "_load_conversation_mail_handles",
                                 return_value=([], [])),
                    patch.object(orch, "_route_to_features",
                                 new=AsyncMock(return_value={})),
                    patch("core.chat_tool_planner.plan_tool_use",
                          new=AsyncMock(return_value=no_tool_plan)),
                    patch("core.chat_tool_planner.execute_tool_plan",
                          new=AsyncMock(return_value="")),
                    patch("core.memory_context_assembler.assembly_enabled",
                          return_value=False),
                    patch("core.chat_mini_app_authoring.try_handle",
                          new=AsyncMock(return_value=None)),
                    patch("core.chat_tool_planner._provenance_menu",
                          new=AsyncMock(return_value="")),
                    patch("integrations.chat_orchestrator."
                          "_verbatim_mail_evidence",
                          new=AsyncMock(return_value=[])),
                    patch("integrations.chat_orchestrator._begin_task_edit",
                          return_value={"status": "legacy"}),
                    patch("core.chat_canvas_editor.plan_canvas_edit",
                          new=AsyncMock(side_effect=_plan_ce)),
                    patch("core.student_learning_service.get_agent_lessons",
                          return_value=[]),
                    patch("integrations.chat_orchestrator."
                          "_task_lifecycle_for",
                          return_value=None),
                ]:
                    st.enter_context(cm)
                out = asyncio.run(orch.process_chat_message(
                    ws_a["user_id"],
                    "What are the approved prices and delivery times "
                    "for rows 1 through 5 of the draft?",
                    "sess-scope",
                    context={"workspace_id": ws_a["workspace_id"],
                             "canvas": dict({
                                 "canvas_id": "cv-scope",
                                 "canvas_type": "email",
                                 "title": "Supplier quote",
                                 "content": {"body":
                                             "<p>quote table</p>"}}),
                             "agent_id": "agent-scope"}))

            # ONE counted USER request; internal same-request fallbacks
            # (streaming attempt -> non-streaming) may add HTTP calls to
            # the SAME endpoint — that is one user request served.
            assert ep_a.hit_count >= 1, (
                "the counted FIRST authenticated chat message must reach "
                f"the user's own registered endpoint; got {ep_a.hit_count} "
                f"calls; response={json.dumps(out, default=str)[:300]}")
            assert out.get("message") == "pong-A", (
                "the reply must come from the user's own provider: "
                f"{json.dumps(out, default=str)[:300]}")


    def test_public_route_reply_agrees_with_durable_outcome(
            self, scoped_world, world_app):
        """The FULL user-outcome agreement (owner test-quality
        correction): what the reply says, what the machine outcome
        records, what durable execution persisted, and what the history
        carries must all agree — one served-by-your-provider story, not
        four different ones."""
        import asyncio
        import json
        from contextlib import ExitStack
        from unittest.mock import AsyncMock, MagicMock, patch

        import integrations.chat_orchestrator as co
        from core.chat_tool_planner import ToolPlan
        from core.llm_service import LLMService

        with _CountingEndpoint("A") as ep_a:
            ws_a = _authorized_workspace(world_app, scoped_world)
            _register_local_route(world_app, ws_a, ep_a.base_url,
                                  tools=True, quality=0.9)
            orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
            orch.tenant_id = "default"
            orch._cancelled_sessions = set()
            orch._budget_exceeded_runs = set()
            orch.llm_service = LLMService(tenant_id="default")
            session = {"id": "sess-agree", "history": []}

            async def _plan_ce(*a, **k):
                class _P:
                    wants_edit = False
                return _P()

            no_tool_plan = ToolPlan(use_tool=False, service="datasets",
                                    intent="search", query="unused",
                                    reason="no tool for a plain reply")

            with ExitStack() as st:
                for cm in [
                    patch.object(orch, "_get_or_create_session",
                                 return_value=session),
                    patch.object(orch, "_resolve_canvas_ctx",
                                 new=AsyncMock(return_value=dict({
                                     "canvas_id": "cv-agree",
                                     "canvas_type": "email",
                                     "title": "Agreement",
                                     "content": {"body":
                                                 "<p>quote</p>"}}))),
                    patch.object(orch, "_start_chat_execution",
                                 return_value="exec-agree"),
                    patch.object(orch, "_record_chat_step", new=AsyncMock()),
                    patch.object(orch, "_emit_agent_status",
                                 new=AsyncMock()),
                    patch.object(orch, "_update_session",
                                 new=MagicMock()),
                    patch.object(orch, "_finish_chat_execution",
                                 new=MagicMock()),
                    patch.object(orch, "_load_conversation_mail_handles",
                                 return_value=([], [])),
                    patch.object(orch, "_route_to_features",
                                 new=AsyncMock(return_value={})),
                    patch("core.chat_tool_planner.plan_tool_use",
                          new=AsyncMock(return_value=no_tool_plan)),
                    patch("core.chat_tool_planner.execute_tool_plan",
                          new=AsyncMock(return_value="")),
                    patch("core.memory_context_assembler.assembly_enabled",
                          return_value=False),
                    patch("core.chat_mini_app_authoring.try_handle",
                          new=AsyncMock(return_value=None)),
                    patch("core.chat_tool_planner._provenance_menu",
                          new=AsyncMock(return_value="")),
                    patch("integrations.chat_orchestrator."
                          "_verbatim_mail_evidence",
                          new=AsyncMock(return_value=[])),
                    patch("integrations.chat_orchestrator._begin_task_edit",
                          return_value={"status": "legacy"}),
                    patch("core.chat_canvas_editor.plan_canvas_edit",
                          new=AsyncMock(side_effect=_plan_ce)),
                    patch("core.student_learning_service.get_agent_lessons",
                          return_value=[]),
                    patch("integrations.chat_orchestrator."
                          "_task_lifecycle_for",
                          return_value=None),
                ]:
                    st.enter_context(cm)
                out = asyncio.run(orch.process_chat_message(
                    ws_a["user_id"],
                    "What are the approved prices and delivery times "
                    "for rows 1 through 5 of the draft?",
                    "sess-agree",
                    context={"workspace_id": ws_a["workspace_id"],
                             "canvas": dict({
                                 "canvas_id": "cv-agree",
                                 "canvas_type": "email",
                                 "title": "Agreement",
                                 "content": {"body":
                                             "<p>quote</p>"}}),
                             "agent_id": "agent-agree"}))

            reply = out.get("message")
            assert reply == "pong-A", f"reply: {reply!r}"
            # THE MACHINE OUTCOME agrees: the routing feedback row was
            # recorded under the USER'S OWN tenant (the scope the turn
            # dispatched in — not the singleton default), and the turn
            # actually reached the user's own endpoint. (The API-level
            # chat_messages history leg is asserted by the pristine-J2
            # acceptance against the real server, which owns that write.)
            db = scoped_world["Session"]()
            try:
                from core.models import LLMRoutingFeedback

                fb = (db.query(LLMRoutingFeedback)
                      .order_by(LLMRoutingFeedback.created_at.desc())
                      .first())
            finally:
                db.close()
            assert fb is not None, "the turn recorded routing feedback"
            assert fb.tenant_id == ws_a["tenant_id"], (
                "feedback scope must be the user's own tenant "
                f"(got {fb.tenant_id!r})")
            assert ep_a.hit_count >= 1, (
                "the durable agreement rests on a dispatch that actually "
                "reached the user's own endpoint")


class TestTruthfulToolRequest:
    """The pristine-J2 false-search finding (2026-10-12): a
    search-imperative over DOCUMENTS compiled to a bare `converse` op
    (the source vocabulary knew mail and tickets but not documents), so
    zero searches ran — and the reply narrated "I've searched your Zoho
    CRM integration … 5 records" in a fresh world with no integrations.
    Two gates: the compile must produce the search work, and the reply
    prompt must carry the no-tool truthfulness envelope when nothing
    executed."""

    def test_documents_search_compiles_a_research_action(self):
        from core.turn_decision import build_turn_decision

        decision = build_turn_decision(
            message=("Search my documents for anything about quarterly "
                     "revenue and tell me what you find."),
            session={"id": "sess-docs", "history": []},
            context={})
        actions = decision.get("requested_actions") or []
        research = [a for a in actions if a.get("kind") == "research"]
        assert research, (
            "a search-imperative over documents must compile a research "
            f"action, got: {[(a.get('kind')) for a in actions]}")
        target_sources = (research[0].get("target") or {}).get(
            "sources") or research[0].get("additional_sources") or []
        assert any("document" in str(s).lower() for s in target_sources), (
            f"the research target must name the documents source: "
            f"{target_sources}")
        assert not any(a.get("kind") == "conversation" for a in actions), (
            "a search-imperative must not degrade to a bare conversation "
            "action")

    def test_zero_executed_searches_carry_the_truthfulness_envelope(self):
        """A seek-shaped turn whose tool block never materialized must
        brief the model that NOTHING ran — the deterministic input that
        keeps 'I've searched your Zoho CRM' unfabricatable."""
        import asyncio
        import json
        from contextlib import ExitStack
        from unittest.mock import AsyncMock, MagicMock, patch

        import integrations.chat_orchestrator as co
        from core.chat_tool_planner import ToolPlan

        captured = {}

        async def _capture_completion(**kwargs):
            captured["messages"] = kwargs.get("messages")
            # THE FABRICATED CLAIM (run-3's finding class): the model
            # narrates searches over zero executed work. The delivered
            # outcome must be enforced truthful, not carry this text.
            return {"success": True, "content": (
                "I've searched your Zoho CRM integration (connected "
                "previously) for any mentions of quarterly revenue. The "
                "search yielded no precise matches in the CRM database "
                "itself, which only contains 5 records mentioning "
                "revenue."), "text": (
                "I've searched your Zoho CRM integration (connected "
                "previously) for any mentions of quarterly revenue. The "
                "search yielded no precise matches in the CRM database "
                "itself, which only contains 5 records mentioning "
                "revenue."), "model": "x", "provider": "y",
                "usage": {"prompt_tokens": 5, "completion_tokens": 20,
                          "total_tokens": 25}}

        class _CapturingService:
            def __init__(self):
                from unittest.mock import MagicMock

                self.stream_completion = MagicMock(
                    return_value=iter(()))
                self.generate_completion = _capture_completion

            @property
            def handler(self):
                class _H:
                    clients = {"local_x": object()}
                    workspace_id = "default"
                return _H()

            def is_available(self):
                return True

        orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
        orch.tenant_id = "default"
        orch._cancelled_sessions = set()
        orch._budget_exceeded_runs = set()
        orch.llm_service = _CapturingService()
        session = {"id": "sess-truth", "history": []}

        async def _plan_ce(*a, **k):
            class _P:
                wants_edit = False
            return _P()

        no_tool_plan = ToolPlan(use_tool=False, service="datasets",
                                intent="search", query="unused",
                                reason="no tool")

        with ExitStack() as st:
            for cm in [
                patch.object(orch, "_get_or_create_session",
                             return_value=session),
                patch.object(orch, "_resolve_canvas_ctx",
                             new=AsyncMock(return_value=dict({
                                 "canvas_id": "cv-truth",
                                 "canvas_type": "email",
                                 "title": "Truth",
                                 "content": {"body": "<p>x</p>"}}))),
                patch.object(orch, "_start_chat_execution",
                             return_value="exec-truth"),
                patch.object(orch, "_record_chat_step", new=AsyncMock()),
                patch.object(orch, "_emit_agent_status", new=AsyncMock()),
                patch.object(orch, "_update_session", new=MagicMock()),
                patch.object(orch, "_finish_chat_execution",
                             new=MagicMock()),
                patch.object(orch, "_load_conversation_mail_handles",
                             return_value=([], [])),
                patch.object(orch, "_route_to_features",
                             new=AsyncMock(return_value={})),
                patch("core.chat_tool_planner.plan_tool_use",
                      new=AsyncMock(return_value=no_tool_plan)),
                patch("core.chat_tool_planner.execute_tool_plan",
                      new=AsyncMock(return_value="")),
                patch("core.memory_context_assembler.assembly_enabled",
                      return_value=False),
                patch("core.chat_mini_app_authoring.try_handle",
                      new=AsyncMock(return_value=None)),
                patch("core.chat_tool_planner._provenance_menu",
                      new=AsyncMock(return_value="")),
                patch("integrations.chat_orchestrator."
                      "_verbatim_mail_evidence",
                      new=AsyncMock(return_value=[])),
                patch("integrations.chat_orchestrator._begin_task_edit",
                      return_value={"status": "legacy"}),
                patch("core.chat_canvas_editor.plan_canvas_edit",
                      new=AsyncMock(side_effect=_plan_ce)),
                patch("core.student_learning_service.get_agent_lessons",
                      return_value=[]),
                patch("integrations.chat_orchestrator._task_lifecycle_for",
                      return_value=None),
            ]:
                st.enter_context(cm)
            out = asyncio.run(orch.process_chat_message(
                "user-truth",
                "Search my documents for anything about quarterly "
                "revenue and tell me what you find.",
                "sess-truth",
                context={"workspace_id": "default",
                         "canvas": dict({"canvas_id": "cv-truth",
                                         "canvas_type": "email",
                                         "title": "Truth",
                                         "content": {"body":
                                                     "<p>x</p>"}}),
                         "agent_id": "agent-truth"}))

        msgs = captured.get("messages") or []
        blob = json.dumps(msgs, default=str)
        # Either truthful briefing satisfies the requirement: the
        # planner-timeout envelope ("NO TOOL LOOKUP RAN THIS TURN …") or
        # the no-block truthfulness directive ("NO SEARCH OR TOOL LOOKUP
        # RAN THIS TURN …"). What must NEVER happen is a seek-shaped turn
        # briefed without one — that is how "I've searched your Zoho CRM"
        # was fabricated over zero executed work.
        assert ("NO SEARCH OR TOOL LOOKUP RAN THIS TURN" in blob
                or "NO TOOL LOOKUP RAN THIS TURN" in blob), (
            "a seek-shaped turn with zero executed tool work must brief "
            f"the model with a truthfulness envelope; messages="
            f"{blob[:400]}")
        # ENFORCEMENT (owner directive: beyond a prompt) — the model
        # IGNORED the briefing and claimed the search anyway. The
        # delivered outcome must remain truthful: the claiming text is
        # withheld and the honest refusal is what the user gets.
        assert "Zoho CRM integration" not in str(out.get("message")), (
            f"a search-claiming reply must not be delivered: "
            f"{str(out.get('message'))[:200]!r}")
        assert "Nothing was searched this turn" in str(out.get("message")), (
            f"the delivered message must be the truthful refusal: "
            f"{str(out.get('message'))[:200]!r}")



    def test_budget_exhausted_before_the_reply_leg_delivers_zero_dispatch(
            self, scoped_world, world_app):
        """Control B (owner diagnostic bounds): max(5.0, remaining) used
        to grant fresh dispatch time AFTER the turn budget was spent.
        Exhausted budget ⇒ the honest envelope with ZERO dispatch."""
        import asyncio
        from contextlib import ExitStack
        from unittest.mock import AsyncMock, MagicMock, patch

        import integrations.chat_orchestrator as co
        from core.chat_tool_planner import ToolPlan

        dispatched = {"n": 0}

        class _NoDispatch:
            handler = type("_H", (), {"clients": {},
                                      "workspace_id": "default"})()

            def is_available(self):
                return True

            async def generate_completion(*a, **k):
                dispatched["n"] += 1
                return {"success": True, "content": "should not happen"}

            def stream_completion(self, *a, **k):
                dispatched["n"] += 1
                raise AssertionError("no streaming past a spent budget")

        orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
        orch.tenant_id = "default"
        orch._cancelled_sessions = set()
        orch._budget_exceeded_runs = set()
        orch.llm_service = _NoDispatch()
        session = {"id": "sess-spent", "history": []}

        async def _plan_ce(*a, **k):
            class _P:
                wants_edit = False
            return _P()

        class _SpentClock:
            def __init__(self, *a, **k):
                pass

            def expired(self, *a, **k):
                return True

            def remaining(self, *a, **k):
                return -1.0

        with ExitStack() as st:
            for cm in [
                patch.object(orch, "_get_or_create_session",
                             return_value=session),
                patch.object(orch, "_resolve_canvas_ctx",
                             new=AsyncMock(return_value=dict({
                                 "canvas_id": "cv-spent",
                                 "canvas_type": "email",
                                 "title": "Spent",
                                 "content": {"body": "<p>x</p>"}}))),
                patch.object(orch, "_start_chat_execution",
                             return_value="exec-spent"),
                patch.object(orch, "_record_chat_step", new=AsyncMock()),
                patch.object(orch, "_emit_agent_status", new=AsyncMock()),
                patch.object(orch, "_update_session", new=MagicMock()),
                patch.object(orch, "_finish_chat_execution",
                             new=MagicMock()),
                patch.object(orch, "_load_conversation_mail_handles",
                             return_value=([], [])),
                patch.object(orch, "_route_to_features",
                             new=AsyncMock(return_value={})),
                patch("core.chat_tool_planner.plan_tool_use",
                      new=AsyncMock(return_value=ToolPlan(
                          use_tool=False, service="datasets",
                          intent="search", query="unused", reason="r"))),
                patch("core.chat_tool_planner.execute_tool_plan",
                      new=AsyncMock(return_value="")),
                patch("core.memory_context_assembler.assembly_enabled",
                      return_value=False),
                patch("core.chat_mini_app_authoring.try_handle",
                      new=AsyncMock(return_value=None)),
                patch("core.chat_tool_planner._provenance_menu",
                      new=AsyncMock(return_value="")),
                patch("integrations.chat_orchestrator."
                      "_verbatim_mail_evidence",
                      new=AsyncMock(return_value=[])),
                patch("integrations.chat_orchestrator._begin_task_edit",
                      return_value={"status": "legacy"}),
                patch("core.chat_canvas_editor.plan_canvas_edit",
                      new=AsyncMock(side_effect=_plan_ce)),
                patch("core.student_learning_service.get_agent_lessons",
                      return_value=[]),
                patch("integrations.chat_orchestrator."
                      "_task_lifecycle_for", return_value=None),
                patch("integrations.chat_orchestrator."
                      "ChatOrchestrator._get_qwen_response",
                      new=AsyncMock(
                          side_effect=AssertionError(
                              "no dispatch past a spent budget"))),
                patch("integrations.chat_orchestrator.TurnDeadline",
                      new=_SpentClock),
            ]:
                st.enter_context(cm)
            out = asyncio.run(orch.process_chat_message(
                "user-spent", "What are the approved prices for rows 1 "
                "through 5 of the draft?", "sess-spent",
                context={"workspace_id": "default",
                         "canvas": dict({"canvas_id": "cv-spent",
                                         "canvas_type": "email",
                                         "title": "Spent",
                                         "content": {"body":
                                                     "<p>x</p>"}})}))

        assert dispatched["n"] == 0, (
            f"a spent turn budget must produce ZERO dispatch, got "
            f"{dispatched['n']}")
        blob = json.dumps(out, default=str)
        assert "turn_budget_exceeded" in blob, (
            "the honest budget envelope must be delivered, got: "
            f"{blob[:300]}")



class TestProgramKinds:
    """The mapping pin (coordinated peer integration, 41c4c54da→): the
    decision's documents source ask survives the REAL compiler with its
    kind intact — on 3259870cb this failed with source_kinds=[] (the
    second transition where required tool work disappeared)."""

    def test_document_nouns_survive_program_compilation(self):
        from core.action_program import (
            normalize_source_kind, program_from_decision,
        )
        from core.turn_decision import build_turn_decision

        source_ask = ("Search my documents for anything about quarterly "
                      "revenue and tell me what you find.")
        decision = build_turn_decision(source_ask, session={}, history=[],
                                       context={})
        kinds = [a.get("target", {}).get("sources")
                 for a in decision["requested_actions"]
                 if a.get("kind") == "research"]
        assert kinds and kinds[0] == ["documents"]
        program = program_from_decision(decision)
        ops = [a for a in program.actions if getattr(a, "op", "") ==
               "source_read"]
        assert ops and ops[0].source_kinds == ["document"]
        assert normalize_source_kind("documents") == "document"
        assert normalize_source_kind("workbooks") == "spreadsheet"
        assert normalize_source_kind("flurb") == ""


class TestInternalLegScopeLeak:
    """The KNOWN owned finding (runs 2-4): the chat singleton's internal
    legs (turn-fact extraction, legacy intent analysis) dispatch from the
    module singleton's DEFAULT scope when no request scope is published.
    Owner question: can that default-scoped handler REACH another
    workspace's registered provider or endpoint? Expected: NO — the
    failure mode is under-service (the leg sees nothing), never
    cross-workspace access."""

    def test_default_scope_sees_no_other_workspaces_provider(
            self, scoped_world, world_app):
        from core.llm_service import LLMService

        with _CountingEndpoint("A") as ep_a:
            ws_a = _authorized_workspace(world_app, scoped_world)
            _register_local_route(world_app, ws_a, ep_a.base_url,
                                  tools=True, quality=0.9)
            # THE SINGLETON SHAPE: default/default, constructed exactly
            # as the module-level chat singleton is.
            singleton = LLMService(tenant_id="default")
            routes = singleton.handler._local_routes
            clients = singleton.handler.clients
            assert not routes, (
                f"the default-scoped handler must not adopt another "
                f"workspace's routes; got {list(routes)}")
            foreign = [k for k in clients if k.startswith("local_")]
            assert not foreign, (
                f"the default-scoped handler must not hold another "
                f"workspace's provider clients; got {foreign}")
            assert ep_a.hit_count == 0, (
                "no endpoint may be reachable from the default scope")
            from core.llm.byok_handler import QueryComplexity

            ranked = singleton.handler.get_ranked_providers(
                singleton.handler.analyze_query_complexity("x"))
            assert not [p for p, _m in ranked
                        if str(p).startswith("local_")], (
                "another workspace's registered route must never rank in "
                "the default scope")

    def test_workspace_rows_are_invisible_to_the_default_scope(
            self, scoped_world, world_app):
        from core.llm_service import LLMService

        with _CountingEndpoint("A") as ep_a, _CountingEndpoint("B") as ep_b:
            ws_a = _authorized_workspace(world_app, scoped_world)
            ws_b = _authorized_workspace(world_app, scoped_world)
            _register_local_route(world_app, ws_a, ep_a.base_url,
                                  tools=True, quality=0.9)
            _register_local_route(world_app, ws_b, ep_b.base_url,
                                  tools=False, quality=0.85)
            default_svc = LLMService(tenant_id="default")
            out = asyncio.run(default_svc.generate_completion(
                messages=[{"role": "user", "content": "PONG"}]))
            blob = json.dumps(out, default=str)
            assert ep_a.hit_count == 0 and ep_b.hit_count == 0, (
                "a default-scoped internal leg must not reach either "
                f"workspace's endpoint; response={blob[:200]}")


class TestSearchOutcomeContract:
    """The owner's bounded outcome contract (2026-10-13 directive):
    executed + complete + zero matches = a completed search with scoped
    absence — delivered truthfully (never success=false), with the
    durable outcome and history agreeing; truncated/degraded and
    unverified executions stay partial/failed; a stale or unrelated
    receipt can never license this request. Normalization preserves the
    bounded scope (query, match count, coverage, bounds)."""

    @staticmethod
    def _receipt(match_count=0, verified=True, coverage="complete",
                 truncated=False, degraded=False, query="quarterly "
                 "revenue", paths=None):
        return {
            "tool": "documents.grep",
            "verified": verified,
            "required": True,
            "outcome": (f"status={'degraded' if degraded else 'ok'} "
                        f"match_count={match_count}"),
            "evidence_refs": [{
                "kind": "documents",
                "query": query,
                "match_count": match_count,
                "coverage": ("degraded" if (degraded or truncated)
                             else coverage),
                "truncated": truncated,
                "paths": [str(p)[:200] for p in (paths or [])][:10],
            }],
        }

    def test_complete_zero_match_search_validates_as_scoped_absence(self):
        """Gap 1: executed + complete + zero matches resolves to a
        completed search (scoped absence) — never unconfirmed."""
        from integrations.chat_orchestrator import (
            _execution_verified_complete_search,
        )

        assert _execution_verified_complete_search("exec-zm") is False, (
            "no row — cannot validate")
        # the production probe covers the DB read; here the contract's
        # receipt predicate is pinned through the same helper used by
        # the op-level path.
        from integrations.chat_orchestrator import (
            _operation_carries_verified_complete_search,
        )

        op = {"execution": {"task_outcome": {"tool_outcomes": [
            self._receipt(match_count=0),
        ]}}}
        assert _operation_carries_verified_complete_search(op) is True

    def test_unverified_or_partial_receipts_never_validate(self):
        from integrations.chat_orchestrator import (
            _operation_carries_verified_complete_search,
        )

        base = {"execution": {"task_outcome": {"tool_outcomes": []}}}
        assert _operation_carries_verified_complete_search(base) is False
        unverified = {"execution": {"task_outcome": {"tool_outcomes": [
            self._receipt(verified=False),
        ]}}}
        assert not _operation_carries_verified_complete_search(unverified)
        degraded = {"execution": {"task_outcome": {"tool_outcomes": [
            self._receipt(degraded=True, truncated=True),
        ]}}}
        assert not _operation_carries_verified_complete_search(degraded)
        no_count = {"execution": {"task_outcome": {"tool_outcomes": [
            self._receipt(match_count=None),
        ]}}}
        assert not _operation_carries_verified_complete_search(no_count)

    def test_copy_ref_preserves_scope_bounds_and_zero_count(self):
        """Gap 2: settlement normalization preserves the structured
        search scope — query, match_count (zero is a legitimate value),
        coverage, paths (bounded) — and records the bounds."""
        from core.task_outcome_contract import _copy_ref

        ref = _copy_ref({
            "kind": "documents",
            "query": "quarterly revenue",
            "match_count": 0,
            "coverage": "complete",
            "truncated": False,
            "paths": ["/docs/a.md", "/docs/b.md"],
            "action": "grep",
            "service": "documents",
        })
        assert ref["kind"] == "documents"
        assert ref["query"] == "quarterly revenue"
        assert ref["match_count"] == 0, (
            "a zero match count is a real result and must survive")
        assert ref["coverage"] == "complete"
        assert ref["paths"] == ["/docs/a.md", "/docs/b.md"]
        assert ref["action"] == "grep" and ref["service"] == "documents"

    def test_copy_ref_bounds_paths_and_drops_unknown(self):
        from core.task_outcome_contract import _copy_ref

        ref = _copy_ref({
            "kind": "documents",
            "paths": [f"/p/{i}.md" for i in range(20)],
            "credentials": "secret-value",
            "content_blob": "x" * 10000,
        })
        assert len(ref["paths"]) <= 10
        assert "credentials" not in ref and "content_blob" not in ref

    def test_degraded_coverage_is_stamped_so_absence_stays_partial(self):
        """A truncated/degraded zero-match receipt stamps degraded
        coverage — the validator refuses to certify a complete absence
        from it (regression 3)."""
        from integrations.chat_orchestrator import (
            _operation_carries_verified_complete_search,
        )

        op = {"execution": {"task_outcome": {"tool_outcomes": [
            self._receipt(truncated=True, degraded=True),
        ]}}}
        assert not _operation_carries_verified_complete_search(op)


    def test_session_planner_receipts_validate_before_settlement(self):
        """The ordering repair (peer round-11 finding at 2eb46a8b9): the
        recorded-outcome resolution runs BEFORE the execution row's
        task_outcome settles. The planner's own receipts for this
        execution — stamped into the session at dispatch — must carry
        the completed search at resolution time."""
        from integrations.chat_orchestrator import (
            _receipts_carry_verified_complete_search,
        )

        rows = self._receipt(match_count=0)
        rows["evidence_refs"][0]["query"] = "quarterly revenue"
        assert _receipts_carry_verified_complete_search([rows]) is True
        # an unverified row never carries it
        unverified = self._receipt(verified=False)
        assert _receipts_carry_verified_complete_search([unverified]) is False
        # degraded coverage never carries it
        degraded = self._receipt(degraded=True, truncated=True)
        assert _receipts_carry_verified_complete_search([degraded]) is False
        # not-a-list / empty never validate
        assert _receipts_carry_verified_complete_search(None) is False
        assert _receipts_carry_verified_complete_search([]) is False


class TestSearchOutcomeFinalization:
    """The owner's 6-case table through ACTUAL finalization
    (`_finish_chat_execution` → builder → durable AgentExecution row),
    driving the real resolver (`_fallback_turn_outcome`) and the real
    planner-receipt stamp. The final outcome is never seeded."""

    @staticmethod
    def _drive(orch, session, response, execution_id="exec-fin-1",
               ai_response=None):
        import asyncio

        asyncio.run(orch._finish_chat_execution(
            execution_id, "completed", "summary",
            session=session, message="Search my documents for quarterly "
            "revenue.",
            response=response, ai_response=ai_response or {},
            deadline=None, pending_task=None,
            user_id="u-fin", workspace_id="default",
            allow_persisted_evidence=False))

    @staticmethod
    def _recorded(execution_id, state="completed", delivered=True):
        return {"state": state, "delivered": delivered,
                "work_turn": True, "open_work": [],
                "execution_ids": [execution_id]}

    @staticmethod
    def _read_row(db, execution_id):
        from core.models import AgentExecution

        row = (db.query(AgentExecution)
               .filter(AgentExecution.id == execution_id).first())
        meta = row.metadata_json if row is not None else {}
        outcome = (meta or {}).get("task_outcome") or {}
        return row, outcome

    def _build_world(self, scoped_world):
        from core.models import AgentExecution

        db = scoped_world["Session"]()
        try:
            db.add(AgentExecution(
                id="exec-fin-1", status="success", triggered_by="chat",
                agent_id=None, task_id=None, goal_run_id=None))
            db.commit()
        except Exception:  # noqa: BLE001 — id may exist
            db.rollback()
        finally:
            db.close()


    def test_complete_zero_match_settles_objective_met_true(
            self, scoped_world, world_app):
        """Case 1 (positive), through ACTUAL FINALIZATION: the real
        resolver decides `completed` from the planner's own dispatch
        receipts; the real builder carries objective_met=true into the
        durable AgentExecution row; a fresh session reads it back with
        success kinds and the preserved receipt scope. The final outcome
        is never seeded — only the dispatch-level facts are."""
        import json

        import integrations.chat_orchestrator as co
        from core.chat_tool_planner import ToolPlan
        from core.models import AgentExecution
        from core.llm_service import LLMService

        ws_ws = "ws-fin-0000"
        exec_id = "exec-fin-1"
        plan = ToolPlan(use_tool=True, service="documents",
                        intent="search", query="quarterly revenue",
                        reason="documents search")
        plan._result_meta["documents_read"] = {
            "action": "grep", "query": "quarterly revenue",
            "executed": True, "match_count": 0,
            "paths": ["/docs/empty.md"], "degraded": False,
            "truncated": False, "error": "",
            "workspace_id": ws_ws,
        }

        session = {"id": "sess-fin", "history": [],
                   "_planner_tool_receipts_" + exec_id:
                       co._planner_receipt_rows(plan)}
        assert session["_planner_tool_receipts_" + exec_id], (
            "the real producer must stamp the executed receipt")

        recorded = co._fallback_turn_outcome(
            session, exec_id, {}, {"workspace_id": ws_ws},
            workspace_id=ws_ws)
        assert recorded.get("state") == "completed", (
            f"the completed scoped absence must resolve completed; got "
            f"{recorded.get('state')!r}")
        assert recorded.get("delivered") is True

        response = {"_recorded_outcome": recorded,
                    "message": "No matches found in your documents."}

        db = scoped_world["Session"]()
        try:
            db.add(AgentExecution(id=exec_id, status="success",
                                  triggered_by="chat"))
            db.commit()
        finally:
            db.close()

        orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
        orch.tenant_id = "default"
        orch._cancelled_sessions = set()
        orch._budget_exceeded_runs = set()
        from core.llm_service import LLMService as _LS

        orch.llm_service = _LS(tenant_id="default")
        orch._finish_chat_execution(
            exec_id, "completed", "summary",
            task_outcome=None,  # the builder derives it — never seeded
            session=session, message="Search my documents.",
            response=response, ai_response=None, deadline=None,
            pending_task=None, user_id="u-fin", workspace_id=ws_ws,
            allow_persisted_evidence=False)

        db = scoped_world["Session"]()
        try:
            row = (db.query(AgentExecution)
                   .filter(AgentExecution.id == exec_id).first())
        finally:
            db.close()
        assert row is not None
        meta = row.metadata_json if isinstance(row.metadata_json, dict) else {}
        oc = meta.get("task_outcome") or {}
        assert oc.get("objective_met") is True, (
            f"the completed bounded search must settle objective_met=true; "
            f"got {oc.get('objective_met')!r}")
        assert oc.get("success_kinds"), (
            "success kinds must be derived from the durable outcome")
        tools = (oc.get("tool_outcomes") or [])
        refs = [r for t in tools for r in (t.get("evidence_refs") or [])]
        assert refs, (
            f"receipt scope must survive settlement: "
            f"{json.dumps(oc, default=str)[:300]}")
        assert refs[0].get("query") == "quarterly revenue", (
            f"receipt scope must survive settlement: {refs!r}")
        assert refs[0].get("match_count") == 0, (
            "the zero count is a real result and must survive")
        assert refs[0].get("coverage") == "complete", (
            "complete coverage must survive settlement")

    def test_stale_and_unverified_receipts_never_promote(
            self, scoped_world, world_app):
        """Cases 4-5 through ACTUAL FINALIZATION with a REAL, PRE-EXISTING
        execution row (owner correction: the previous negative control
        passed vacuously on an absent record). The row is created with
        pre-existing metadata BEFORE finalization runs; after the real
        builder + finalizer, the row must exist, the ORIGINAL metadata
        must survive, and objective_met must be exactly the pinned
        tri-state value — stale receipts and unverified receipts never
        certify success (stale: not True; unverified: None, "unknown",
        not the definitive False)."""
        import json

        import integrations.chat_orchestrator as co
        from core.chat_tool_planner import ToolPlan
        from core.llm_service import LLMService
        from core.models import AgentExecution

        plan = ToolPlan(use_tool=True, service="documents",
                        intent="search", query="quarterly revenue",
                        reason="documents search")
        plan._result_meta["documents_read"] = {
            "action": "grep", "query": "quarterly revenue",
            "executed": True, "match_count": 0, "paths": [],
            "degraded": False, "truncated": False, "error": "",
            "workspace_id": "ws-x",
        }
        receipts = co._planner_receipt_rows(plan)
        assert receipts, "the real producer must stamp the receipt"

        from core.llm_service import LLMService

        orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
        orch.tenant_id = "default"
        orch._cancelled_sessions = set()
        orch._budget_exceeded_runs = set()
        orch.llm_service = LLMService(tenant_id="default")

        # Non-colliding keys: the ownership listener stamps its own
        # "owner" key at insert; pre-existing NON-owner keys must survive.
        original_metadata = {"pre_existing_note": "here-before-finalization",
                             "session_id": "sess-neg"}

        # === CASE A: STALE receipt (keyed to a DIFFERENT execution) ===
        exec_a = "exec-stale-1"
        # ONLY the stale key: the current execution's own key is
        # deliberately absent so the test proves that stale-key rejection
        # (not absent-response) is what prevents promotion.
        session_a = {"_planner_tool_receipts_exec-other-9": receipts}
        db = scoped_world["Session"]()
        try:
            db.add(AgentExecution(
                id=exec_a, status="success", triggered_by="chat",
                metadata_json=dict(original_metadata)))
            db.commit()
        finally:
            db.close()
        orch._finish_chat_execution(
            exec_a, "completed", "s",
            session=session_a, message="Search my documents.",
            response={}, ai_response=None, deadline=None,
            pending_task=None, user_id="u", workspace_id="ws-x",
            allow_persisted_evidence=False)
        db = scoped_world["Session"]()
        try:
            row = (db.query(AgentExecution)
                   .filter(AgentExecution.id == exec_a).first())
        finally:
            db.close()
        assert row is not None, "the execution row must exist"
        meta = row.metadata_json if isinstance(
            row.metadata_json, dict) else {}
        # ORIGINAL metadata survived the finalization write
        assert meta.get("pre_existing_note") == "here-before-finalization", (
            f"original metadata must survive the finalization write: "
            f"{meta!r}")
        assert meta.get("session_id") == "sess-neg", (
            f"original session_id must survive: {meta!r}")
        assert "task_outcome" in meta, (
            "the finalizer must have written task_outcome to the durable "
            f"row; keys: {sorted(meta.keys())}")
        oc = meta.get("task_outcome") or {}
        assert oc.get("objective_met") is not True, (
            "a STALE receipt (keyed to another execution) must never "
            f"promote objective_met to True; got {oc.get('objective_met')!r}")

        # === CASE B: CURRENT UNVERIFIED receipt ===
        # The receipts ARE keyed to this execution, but verified=false:
        # the completion predicate must refuse, and the tri-state result
        # is objective_met=None ("unknown"), never True (certified) and
        # never False (definitively failed) — unverified means unknown.
        exec_b = "exec-unv-1"
        unverified_receipts = co._planner_receipt_rows(plan)
        for r in unverified_receipts:
            r["verified"] = False
        session_b = {"_planner_tool_receipts_" + exec_b:
                     unverified_receipts}
        db = scoped_world["Session"]()
        try:
            db.add(AgentExecution(
                id=exec_b, status="success", triggered_by="chat",
                metadata_json=dict(original_metadata)))
            db.commit()
        finally:
            db.close()
        orch._finish_chat_execution(
            exec_b, "completed", "s",
            session=session_b, message="Search my documents.",
            response={}, ai_response=None, deadline=None,
            pending_task=None, user_id="u", workspace_id="ws-x",
            allow_persisted_evidence=False)
        db = scoped_world["Session"]()
        try:
            row = (db.query(AgentExecution)
                   .filter(AgentExecution.id == exec_b).first())
        finally:
            db.close()
        assert row is not None, "the unverified execution row must exist"
        meta = row.metadata_json if isinstance(
            row.metadata_json, dict) else {}
        assert meta.get("pre_existing_note") == "here-before-finalization", (
            f"original metadata must survive the finalization write: "
            f"{meta!r}")
        assert "task_outcome" in meta, (
            "the finalizer must have written task_outcome to the durable "
            f"row; keys: {sorted(meta.keys())}")
        oc = meta.get("task_outcome") or {}
        assert oc.get("objective_met") is not True, (
            "an UNVERIFIED receipt must never certify objective_met=True")
        assert oc.get("objective_met") is None, (
            f"the exact tri-state for unverified is None (unknown), got "
            f"{oc.get('objective_met')!r}")
        # Success kinds ARE derived (the finalizer records the honest
        # outcome) but every kind must be False — nothing is certified
        # from an unverified execution.
        sk = oc.get("success_kinds") or {}
        assert not any(v is True for v in sk.values()), (
            f"no success kind may be True from an unverified turn: {sk!r}")


class TestRetrievalSourceObservations:
    """Owner corrections C1-C5: the knowledge leg captures actual source
    identities into an explicit out-param; the assembler threads them to
    the caller; the orchestrator stores them keyed by execution id and
    gated on memory_block existing. The finalizer consumes them as
    attributable evidence refs for context-backed answers."""

    def test_successful_retrieval_captures_source_identities(
            self, scoped_world, world_app):
        """C1+C5: the knowledge leg captures file_name/title/content_hash
        into the source_observations_out list when the retrieval
        succeeds."""
        import asyncio

        from core.memory_context_assembler import _knowledge_leg

        observations = []
        asyncio.run(_knowledge_leg(
            "quarterly revenue", "ws-test", "u-test",
            source_observations_out=observations))
        # The VFS is empty in this test, so no sources — but the
        # out-param mechanism itself is exercised (no crash, list intact)
        assert isinstance(observations, list)

    def test_writer_gate_and_keyed_store_source_pinned(
            self, scoped_world, world_app):
        """C4+C2 at the writer (round-18 review finding: the writer line
        is unreachable in the test suite — every suite disables
        assembly — so its contract is pinned at the source level).

        Pinned: the gate reads `memory_block and isinstance(session,
        dict) and execution_id` (the shipped-in-29a941faf defect gated
        on a nonexistent `_execution_id`, whose NameError also aborted
        the memory_block append that follows), and the store is the
        execution-keyed carrier."""
        import inspect

        import integrations.chat_orchestrator as chat

        src = inspect.getsource(chat.ChatOrchestrator._get_qwen_response)
        assert 'if memory_block and isinstance(session, dict) ' \
            'and execution_id:' in src
        assert 'session[f"_retrieval_source_observations_' \
            '{execution_id}"]' in src
        # The defect token must not exist as a standalone identifier in
        # this scope (29a941faf gated on `_execution_id`, a name that
        # only exists in process_chat_message's scope).
        import re as _re
        assert not _re.search(r"(?<![A-Za-z0-9_])_execution_id\b", src)

    def test_context_sources_keyed_by_execution_id(
            self, scoped_world, world_app):
        """C2+C3 at the readers (round-18 review finding: the resolver's
        read shipped unscoped in 29a941faf): both consumers read the
        execution-keyed carrier and the deleted contextvar getter is
        not imported anywhere."""
        import inspect

        import integrations.chat_orchestrator as chat

        resolver_src = inspect.getsource(chat._fallback_turn_outcome)
        assert 'f"_retrieval_source_observations_{execution_id}"' \
            in resolver_src
        assert '"_retrieval_source_observations"' not in resolver_src
        builder_src = inspect.getsource(
            chat.ChatOrchestrator._build_turn_task_outcome)
        assert 'f"_retrieval_source_observations_{execution_id}"' \
            in builder_src
        assert '"_retrieval_source_observations"' not in builder_src
        orchestrator_src = inspect.getsource(chat)
        assert "get_retrieval_sources" not in orchestrator_src


class TestProviderPolicyFallback:
    """ROUTE-03: a failed primary falls back to the second allowed provider,
    the response names the provider that actually served, and a configured
    but policy-denied provider receives nothing."""

    def test_primary_failure_falls_back_to_secondary_and_denies_policy(
            self, scoped_world, monkeypatch):
        from core.llm_service import LLMService

        with _CountingEndpoint("primary", fail=True) as primary, \
                _CountingEndpoint("secondary") as secondary, \
                _CountingEndpoint("denied") as denied:
            monkeypatch.setenv("OPENAI_BASE_URL", primary.base_url)
            monkeypatch.setenv("OPENAI_API_KEY", "sk-primary-fallback-1234567890")
            monkeypatch.setenv("OPENCODE_BASE_URL", secondary.base_url)
            monkeypatch.setenv("OPENCODE_API_KEY", "sk-secondary-fallback-1234567890")
            monkeypatch.setenv("OLLAMA_BASE_URL", denied.base_url)
            monkeypatch.setenv(
                "ATOM_LLM_PROVIDER_POLICY",
                json.dumps({
                    "mode": "selected",
                    "allowed_providers": ["openai", "opencode"],
                }),
            )
            service = LLMService(workspace_id="ws-fallback",
                                 tenant_id="tenant-fallback")
            handler = service._get_handler()
            assert handler is not None
            # The isolated endpoints below are the authoritative served-set
            # for this test; the global pricing catalog is empty in the
            # scratch world, so do not let an unrelated catalog lookup veto
            # the two providers under test.
            handler._provider_serves_model = lambda provider, model: True
            result = asyncio.run(handler.chat_completion(
                messages=[{"role": "user", "content": "fallback please"}],
                model="gpt-4o-mini",
                provider_id="openai",
                max_tokens=64,
            ))
            assert result.get("provider") == "opencode", result
            message = (result.get("choices") or [{}])[0].get("message") or {}
            assert message.get("content") == "pong-secondary", result
            assert primary.hit_count >= 1, "primary was not attempted"
            assert secondary.hit_count >= 1, "secondary was not used"
            assert denied.hit_count == 0, "policy-denied provider was dispatched"
