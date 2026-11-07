"""Mini-app runtime-boundary journey (MINI-03) — public RPC consumer controls.

The claim-inventory MINI-03 operation is ``RPC action mini_app_dev_run /
mini_app_run_tests`` — the surface the agent MCP loop AND the frontend RPC
client both use. Committed evidence for the fail-closed half exists as
``test_mini_app_harness_journey.py`` (real-auth HTTP walk). This file closes
the joins that evidence never covered, at the same public consumer, using the
production action registry → ``tools/mini_app_tool`` → ``core/mini_app_service``
→ the REAL ``get_miniapp_runtime`` factory (no mocks of those consumers):

1. dev_run on a harmless scaffold fail-closes on an unsupported host with the
   explicit actionable message (``mini_app_status`` probe + host-setup doc),
   never executes host-side, registers no instance, persists no state.
2. run_tests returns the per-case grading report with the same explicit
   unavailable feedback on every case (never fabricated results/stdout).
3. Cross-user authorization: dev_run / run_tests / status probe are owner-only
   (R54 identity — the requesting user, never a client-supplied actor).
4. Explicit docker-dev under ENVIRONMENT=production is refused outright at the
   SAME public consumer. The factory gate runs BEFORE any Docker daemon
   contact (``get_miniapp_runtime`` checks production first), so this control
   is deterministic on any host — no daemon, no images, no containers.
5. docker-dev in dev is fail-closed when no Docker daemon is reachable
   (skipped when a daemon IS up — the execution half is covered by
   ``test_miniapp_dev_docker_journey.py``).

Acceptance contract (CLAIM_INVENTORY MINI-03): "Runtime executes OR fails
closed with an explicit unavailable message". On this macOS host the second
half is the provable leg — asserted here end-to-end. MINI-04/MINI-05 remain
separate KVM requirements (not claimed here).

Scratch world: real-auth in-memory SQLite via journeys conftest; set
``LANCEDB_URI``/``MINIAPP_ROOTFS_DIR`` to a caller-provided scratch dir so
nothing outside the test sandbox is touched. No live model/provider/credential
calls — the runtime factory fails closed before any external contact.
"""
import subprocess
import uuid

import pytest


@pytest.fixture(autouse=True)
def no_runtime_execution(monkeypatch):
    """Fail immediately if a refusal accidentally dispatches guest/host work.

    The production factory and service stay real; these are unsafe external
    execution tripwires, not a replacement unavailable result.
    """
    from core.sandbox_runtime.firecracker_runner import FirecrackerRuntime
    from core.sandbox_runtime.miniapp_dev_runner import MiniAppDevRuntime

    async def forbidden_dispatch(*args, **kwargs):
        pytest.fail("Unavailable-runtime flow dispatched executable work")

    for runtime in (FirecrackerRuntime, MiniAppDevRuntime):
        monkeypatch.setattr(runtime, "execute_python", forbidden_dispatch)
        monkeypatch.setattr(runtime, "execute_command", forbidden_dispatch)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _rpc(client, token, action, params=None):
    """Successful-shape helper: top-level success must be true; return handler data."""
    resp = client.post(
        f"/api/rpc/{action}", json={"params": params or {}}, headers=_auth(token)
    )
    assert resp.status_code == 200, f"{action} -> {resp.status_code} {resp.text}"
    body = resp.json()
    assert body.get("success") is True, f"{action} top-level failed: {body}"
    return body["data"]


def _raw(client, token, action, params=None):
    """Raw RPC envelope. The route returns ``{"success": True, "data":
    <handler result>}`` — transport success is always true when dispatch
    works; the handler's own success/error live inside ``data`` (same shape
    the ``MiniAppHarness`` rpc client consumes)."""
    resp = client.post(
        f"/api/rpc/{action}", json={"params": params or {}}, headers=_auth(token)
    )
    assert resp.status_code == 200, f"{action} -> {resp.status_code} {resp.text}"
    return resp.json()["data"]  # the handler result


def _second_user(client):
    """Register+login a second real user (same pattern as the harness journey)."""
    email = f"boundary_b_{uuid.uuid4().hex[:8]}@test.example.com"
    pw = "TestPass123!"
    r = client.post(
        "/api/auth/register",
        json={"email": email, "password": pw, "first_name": "B", "last_name": "T"},
    )
    assert r.status_code in (200, 201), r.text
    login = client.post("/api/auth/login", json={"username": email, "password": pw})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


STARTER = (
    "state = dict(state or {})\n"
    "state['runs'] = state.get('runs', 0) + 1\n"
)

TESTS = [
    {"name": "runs increments", "inputs": {}, "expect_state": {"runs": 1}},
    {"name": "needs another run", "inputs": {}, "expect_state": {"runs": 2}},
]


def _scaffold_app(client, token, name="Boundary Counter"):
    scaf = _rpc(client, token, "mini_app_scaffold", {
        "name": name,
        "declared_scopes": ["canvas_render"],
        "dependencies": [],
    })
    wl = _rpc(client, token, "mini_app_write_logic", {"app_id": scaf["app_id"], "source": STARTER})
    assert wl["success"] is True
    return scaf["app_id"]


def _world_counts():
    """App / canvas / canvas-state rows in the scratch journey DB.

    Receipt of the side-effect tripwire: a fail-closed runtime boundary must
    register NO installed instance (no new canvases), NO CanvasState (nothing
    executed or committed), and leave the draft app untouched.
    """
    from core.database import SessionLocal
    from core.models import Canvas, CanvasState, MiniApp

    with SessionLocal() as s:
        return (
            s.query(MiniApp).count(),
            s.query(Canvas).count(),
            s.query(CanvasState).count(),
        )


def _status_runtime(client, token, app_id):
    st = _rpc(client, token, "mini_app_status", {"app_id": app_id})
    return st["status"]["runtime"]


class TestMiniAppRuntimeBoundaryJourney:
    def test_dev_run_fails_closed_actionable_no_side_effects(self, real_auth_client, registered_user):
        client, _, _, token = registered_user
        app_id = _scaffold_app(client, token)

        before = _world_counts()
        dev = _raw(client, token, "mini_app_dev_run", {"app_id": app_id, "inputs": {}})
        after = _world_counts()

        # Explicit, actionable fail-closed — no execution, no fake success.
        assert dev.get("success") is False, dev
        detail = dev.get("error", "")
        assert "Mini-app runtime unavailable" in detail
        # Actionable pointer: server-side probe + host setup doc (sanitized:
        # provisioning internals/env values stay out of the response).
        assert "mini_app_status" in detail
        assert "FIRECRACKER_HOST_SETUP" in detail
        # Owner-only status probe shows the concrete runtime reason.
        rt = _status_runtime(client, token, app_id)
        assert rt["available"] is False
        assert rt["reason"]
        # Side-effect tripwires: no instance registered, no state persisted,
        # app row untouched (persist=False dry-run never got to execute).
        assert after == before

    def test_run_tests_reports_unavailable_per_case(self, real_auth_client, registered_user):
        """MINI-03 'receive test feedback' half: the grading report still
        arrives, every case fails closed with the SAME explicit unavailable
        error — honest feedback, never fabricated results."""
        client, _, _, token = registered_user
        app_id = _scaffold_app(client, token)
        _rpc(client, token, "mini_app_set_tests", {"app_id": app_id, "tests": TESTS})

        before = _world_counts()
        tr = _raw(client, token, "mini_app_run_tests", {"app_id": app_id})
        after = _world_counts()

        assert tr.get("success") is True, tr  # the REPORT ran (feedback surface)
        assert tr["total"] == 2 and tr["passed"] == 0
        assert tr["all_passed"] is False
        for case, wanted in zip(tr["results"], TESTS):
            assert case["name"] == wanted["name"]
            assert case["passed"] is False
            assert "Mini-app runtime unavailable" in case["error"]
            assert "stdout" not in case and "state" not in case  # nothing executed
        assert after == before

    def test_dev_run_and_run_tests_are_owner_only(self, real_auth_client, registered_user):
        """Cross-user negative: R54 identity (context user, never a client
        actor) caps authoring through the public RPC consumer."""
        client, _, _, token_a = registered_user
        app_id = _scaffold_app(client, token_a)
        token_b = _second_user(client)

        for action in ("mini_app_dev_run", "mini_app_run_tests"):
            body = _raw(client, token_b, action, {"app_id": app_id})
            assert body.get("success") is False, body
            assert body["error"] == "Not the app owner"
            # B's own app — authorization failure, NOT a runtime failure.
            assert "runtime unavailable" not in body["error"].lower()
        # The status probe leaks nothing to strangers either.
        probe = _raw(client, token_b, "mini_app_status", {"app_id": app_id})
        assert probe["error"] == "Not the app owner"

    def test_production_refuses_explicit_docker_dev_at_public_rpc(
        self, real_auth_client, registered_user, monkeypatch
    ):
        """ENVIRONMENT=production refuses docker-dev outright, at the same
        public RPC consumer. The factory checks production BEFORE probing the
        daemon, so this needs no Docker contact and passes on any host."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ATOM_MINIAAP_RUNTIME", "docker-dev")

        client, _, _, token = registered_user
        app_id = _scaffold_app(client, token)
        before = _world_counts()

        def forbidden_daemon_probe():
            pytest.fail("Production docker-dev refusal contacted the daemon")

        monkeypatch.setattr(
            "core.sandbox_runtime.miniapp_dev_runner.is_available",
            forbidden_daemon_probe,
        )
        dev = _raw(client, token, "mini_app_dev_run", {"app_id": app_id, "inputs": {}})
        assert dev.get("success") is False, dev
        assert "Mini-app runtime unavailable" in dev["error"]
        assert _world_counts() == before

        # The owner-only probe is where the refused mode is named explicitly.
        rt = _status_runtime(client, token, app_id)
        assert rt["available"] is False
        assert "refused" in rt["reason"]
        assert "production" in rt["reason"]
        # No accidental instance/state registration while refused.
        assert _world_counts() == before

        # The same refusal applies to the acceptance-test path.
        _rpc(client, token, "mini_app_set_tests", {"app_id": app_id, "tests": TESTS[:1]})
        tr = _raw(client, token, "mini_app_run_tests", {"app_id": app_id})
        assert tr["passed"] == 0 and tr["total"] == 1
        assert "Mini-app runtime unavailable" in tr["results"][0]["error"]
        assert _world_counts() == before

    def test_docker_dev_fails_closed_without_daemon(self, real_auth_client, registered_user, monkeypatch):
        """Dev-mode docker-dev with an unreachable daemon fail-closes at the
        public consumer with the actionable dev hint. Skipped when a daemon
        IS reachable (the execution half belongs to
        test_miniapp_dev_docker_journey.py)."""
        try:
            daemon_up = subprocess.run(
                ["docker", "info", "--format", "ok"], capture_output=True, timeout=10
            ).returncode == 0
        except (OSError, subprocess.SubprocessError):
            daemon_up = False
        if daemon_up:
            pytest.skip("Docker daemon reachable — dev-mode execution covered elsewhere")

        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("ATOM_MINIAAP_RUNTIME", "docker-dev")

        client, _, _, token = registered_user
        app_id = _scaffold_app(client, token)

        dev = _raw(client, token, "mini_app_dev_run", {"app_id": app_id, "inputs": {}})
        assert dev.get("success") is False, dev
        assert dev["error"] == "Mini-app runtime unavailable on this host. Probe mini_app_status for the reason; host setup: docs/deployment/FIRECRACKER_HOST_SETUP.md"
        rt = _status_runtime(client, token, app_id)
        assert rt["available"] is False
        assert "docker-dev" in rt["reason"]
        assert "Docker" in rt["reason"]
