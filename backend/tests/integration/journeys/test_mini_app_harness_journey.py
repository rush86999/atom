"""Mini-app harness + user/bot journey — real-auth HTTP verification.

Walks the exact HTTP surface the frontend harness (``MiniAppHarness``) and the
agent chat loop use to author, test, publish, install, and run a mini-app:

    GET  /api/rpc/actions                       (13 mini_app_* actions exposed)
    POST /api/rpc/mini_app_scaffold             (draft app + blueprint canvas)
    GET/PUT /api/canvas/{blueprint}/logic       (harness Monaco save/load path)
    POST /api/rpc/mini_app_write_logic          (syntax-gated save + checkpoint)
    POST /api/rpc/mini_app_logic_history        (versioned checkpoints)
    POST /api/rpc/mini_app_revert_logic         (clean-state recovery)
    POST /api/rpc/mini_app_set_tests            (acceptance cases in manifest)
    POST /api/rpc/mini_app_status               (constraint probe)
    POST /api/rpc/mini_app_publish              (credential-stripped blueprint)
    POST /api/rpc/mini_app_install              (fresh immutable instance canvas)
    POST /api/rpc/mini_app_list / mini_app_get_state (dual-face reads)
    POST /api/rpc/mini_app_dev_run / mini_app_run    (fail-closed w/o Firecracker)

Uses REAL auth (register + login) against an isolated in-memory DB — no mocked
``get_current_user``. Firecracker execution is unavailable in this environment
(macOS), so dev-run/run correctly fail CLOSED with an actionable message while
every non-VM step completes.
"""
import uuid

MINI_APP_ACTIONS = {
    "mini_app_scaffold",
    "mini_app_write_logic",
    "mini_app_dev_run",
    "mini_app_publish",
    "mini_app_install",
    "mini_app_run",
    "mini_app_list",
    "mini_app_get_state",
    "mini_app_set_tests",
    "mini_app_run_tests",
    "mini_app_logic_history",
    "mini_app_revert_logic",
    "mini_app_status",
}

STARTER = (
    "state = dict(state or {})\n"
    "state['runs'] = state.get('runs', 0) + 1\n"
)

BAD_SYNTAX = "def broken(:"

# R87-R89 hardening (d7c297222) made the canvas-logic governance gate
# mandatory: PUT /api/canvas/{id}/logic requires an AUTONOMOUS agent id
# (check_governance(None) now raises — the round-06 journey predated that
# gate and its expectations decayed). The real harness (MiniAppHarness
# handleSave/handleDevRun) sends the operating agent's id with every save,
# so the journey must do the same — the gate stays exactly as production
# ships it, we just provide the agent it legitimately accepts.
def _autonomous_agent_for(email: str) -> str:
    """Create a real AUTONOMOUS AgentRegistry row owned by the given user.

    Mirrors how the production harness operates: the Monaco save/dev-run
    path runs under an AUTONOMOUS agent. Scratch rows only — in-memory
    journey DB.
    """
    from core.database import SessionLocal
    from core.models import AgentRegistry, User

    with SessionLocal() as s:
        uid = str(s.query(User).filter(User.email == email).first().id)
        agent = AgentRegistry(
            id=f"ag-{uuid.uuid4().hex[:12]}",
            name="Harness Authoring Agent",
            description="Scratch AUTONOMOUS authoring agent for the mini-app journey",
            category="Operations",
            module_path="journeys.miniapp_harness",
            class_name="HarnessAuthoringAgent",
            user_id=uid,
            status="AUTONOMOUS",
            enabled=True,
        )
        s.add(agent)
        s.commit()
        return str(agent.id)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _rpc(client, token, action, params=None, *, expected_success=True):
    """Call an action and assert the OUTER envelope either succeeded or failed.

    ``POST /api/rpc/{action}`` truthfully propagates an in-handler
    ``success=False`` to the outer envelope (``rpc_routes.py``). Intentional
    negative journeys must therefore say so explicitly instead of requiring
    ``success: true`` for every call; the returned ``data`` still carries the
    handler result (including its own ``success``/``error`` fields).
    """
    resp = client.post(f"/api/rpc/{action}", json={"params": params or {}}, headers=_auth(token))
    assert resp.status_code == 200, f"{action} -> {resp.status_code} {resp.text}"
    body = resp.json()
    assert body.get("success") is expected_success, (
        f"{action} outer success {body.get('success')!r} != expected "
        f"{expected_success!r}: {body}"
    )
    return body["data"]  # the handler result the harness consumes


class TestMiniAppHarnessJourney:
    def test_rpc_surface_exposes_all_13_mini_app_actions(self, real_auth_client, registered_user):
        _, _, _, token = registered_user
        resp = real_auth_client.get("/api/rpc/actions", headers=_auth(token))
        assert resp.status_code == 200
        names = {a["name"] for a in resp.json()["data"]}
        assert MINI_APP_ACTIONS <= names, f"missing: {MINI_APP_ACTIONS - names}"

    def test_unauth_scaffold_rejected(self, real_auth_client):
        resp = real_auth_client.post("/api/rpc/mini_app_scaffold", json={"params": {"name": "X"}})
        # Auth middleware rejects unauthenticated callers (401 or 403 depending on
        # how the token is missing). The harness RPC client maps both to an error.
        assert resp.status_code in (401, 403)

    def test_full_authoring_journey(self, real_auth_client, registered_user):
        client = real_auth_client
        _, _, _, token = registered_user
        # The harness save path runs under an AUTONOMOUS agent (R87-R89 gate).
        agent = _autonomous_agent_for(registered_user[1])

        # 1) Scaffold — draft app + blueprint canvas + starter logic
        scaf = _rpc(client, token, "mini_app_scaffold", {
            "name": "Expense Tracker",
            "declared_scopes": ["canvas_render"],
            "dependencies": [],
        })
        assert scaf["success"] is True, scaf
        app_id = scaf["app_id"]
        blueprint = scaf["canvas_id"]
        assert scaf["logic_source"]

        # 2) Harness save path — PUT/GET /api/canvas/{blueprint}/logic
        # (the real harness sends the operating agent's id — R87-R89 gate).
        save = client.put(
            f"/api/canvas/{blueprint}/logic",
            json={"source": STARTER, "language": "python", "agent_id": agent},
            headers=_auth(token),
        )
        assert save.status_code == 200, save.text
        loaded = client.get(f"/api/canvas/{blueprint}/logic", headers=_auth(token))
        assert loaded.status_code == 200
        assert loaded.json()["data"]["source"] == STARTER

        # 3) Agent path — mini_app_write_logic (syntax-gated + checkpointed)
        wl = _rpc(client, token, "mini_app_write_logic", {"app_id": app_id, "source": STARTER})
        assert wl["success"] is True
        assert wl["version"] == 1

        # Syntax gate rejects invalid source. This is an intentional negative:
        # the handler's success=False is propagated to the outer envelope, so
        # the expectation is explicit rather than waived.
        bad = _rpc(
            client, token, "mini_app_write_logic",
            {"app_id": app_id, "source": BAD_SYNTAX},
            expected_success=False,
        )
        assert bad["success"] is False
        assert "SyntaxError" in bad.get("error", "")

        # The rejected source was never persisted: the live controller source
        # is still the last valid save, and no checkpoint/version was appended.
        still_saved = client.get(f"/api/canvas/{blueprint}/logic", headers=_auth(token))
        assert still_saved.status_code == 200, still_saved.text
        assert still_saved.json()["data"]["source"] == STARTER

        # 4) Logic history + revert (clean-state recovery)
        hist = _rpc(client, token, "mini_app_logic_history", {"app_id": app_id})
        versions = [h["version"] for h in hist["history"]]
        assert versions == [1], versions  # BAD_SYNTAX appended no checkpoint
        assert hist["history"][0]["preview"] == STARTER
        rev = _rpc(client, token, "mini_app_revert_logic", {"app_id": app_id, "version": 1})
        assert rev["success"] is True

        # 5) Acceptance tests (generator-evaluator loop)
        st = _rpc(client, token, "mini_app_set_tests", {
            "app_id": app_id,
            "tests": [{"name": "runs increments", "inputs": {}, "expect_state": {"runs": 1}}],
        })
        assert st["success"] is True
        assert st["tests"] == 1

        # 6) Constraint probe
        status = _rpc(client, token, "mini_app_status", {"app_id": app_id})
        assert status["success"] is True
        assert "status" in status

        # 7) Dev-run — FAIL CLOSED without Firecracker (no VM on macOS).
        # The runtime funnel sanitizes the provisioning details out of the
        # response and keeps them server-side; the pointer stays actionable
        # (probe mini_app_status + host-setup doc), matching the shipped
        # run_stateful(RuntimeError) message.
        dev = _rpc(
            client, token, "mini_app_dev_run",
            {"app_id": app_id, "inputs": {}},
            expected_success=False,
        )
        assert dev["success"] is False
        assert "Mini-app runtime unavailable" in dev.get("error", "")
        assert "mini_app_status" in dev.get("error", "")

        # 7b) run_tests — the MINI-03 "receive test feedback" half. Without a
        # runtime the grading report still comes back, but every case fails
        # closed with the SAME explicit unavailable message (no fabricated
        # results, no stdout). This is the join the round-06 journey missed:
        # mini_app_run_tests was only in the surface set, never exercised.
        tests_run = client.post(
            "/api/rpc/mini_app_run_tests",
            json={"params": {"app_id": app_id}},
            headers=_auth(token),
        )
        assert tests_run.status_code == 200, tests_run.text
        tr_body = tests_run.json()
        assert tr_body.get("success") is True, tr_body  # the report surface ran
        tr = tr_body["data"]
        # The report surface itself succeeded even though every case failed.
        assert tr["success"] is True
        assert tr["total"] == 1 and tr["passed"] == 0 and tr["all_passed"] is False
        case = tr["results"][0]
        assert case["name"] == "runs increments"
        assert case["passed"] is False
        assert "Mini-app runtime unavailable" in case["error"]
        # No fabricated execution artifacts in the failed case.
        assert "stdout" not in case and "state" not in case

        # 8) Publish — no deps → no rootfs gate → succeeds; blueprint credential-stripped
        pub = _rpc(client, token, "mini_app_publish", {"app_id": app_id})
        assert pub["success"] is True, pub

        # 9) Install — fresh immutable instance canvas
        ins = _rpc(client, token, "mini_app_install", {"app_id": app_id})
        assert ins["success"] is True
        instance_canvas = ins["canvas_id"]
        assert instance_canvas != blueprint

        # 10) List + get_state (dual-face reads)
        listing = _rpc(client, token, "mini_app_list", {})
        assert any(a["id"] == app_id for a in listing["apps"])
        gs = _rpc(client, token, "mini_app_get_state", {"canvas_id": instance_canvas})
        assert gs["success"] is True
        # Install hydrates CanvasState at v1 with the published initial_state;
        # it has never been run, so state is the empty seed (no live data yet).
        assert gs["version"] == 1
        assert gs["state"] == {}

        # 11) Stateful run — FAIL CLOSED without Firecracker (same sanitized
        # funnel as step 7).
        run = _rpc(
            client, token, "mini_app_run",
            {"canvas_id": instance_canvas, "inputs": {}},
            expected_success=False,
        )
        assert run["success"] is False
        assert "Mini-app runtime unavailable" in run.get("error", "")

        # 12) Install-before-publish is rejected
        scaf2 = _rpc(client, token, "mini_app_scaffold", {"name": f"Unpublished {uuid.uuid4().hex[:6]}"})
        pre = _rpc(
            client, token, "mini_app_install",
            {"app_id": scaf2["app_id"]},
            expected_success=False,
        )
        assert pre["success"] is False
        assert "not published" in pre.get("error", "").lower()

    def test_canvas_logic_save_requires_access(self, real_auth_client, registered_user):
        """PUT /api/canvas/{id}/logic must not let a stranger overwrite logic on
        a private canvas (owner-gated), while collaborative canvases stay open
        to collaborators (mini-app blueprint/instance canvases are collaborative)."""
        client = real_auth_client
        _, email_a, _, token_a = registered_user

        # Register a second user B.
        email_b = f"journey_b_{uuid.uuid4().hex[:8]}@test.example.com"
        pw = "TestPass123!"
        r = client.post("/api/auth/register", json={
            "email": email_b, "password": pw, "first_name": "B", "last_name": "T",
        })
        assert r.status_code in (200, 201), r.text
        login_b = client.post("/api/auth/login", json={"username": email_b, "password": pw})
        assert login_b.status_code == 200, login_b.text
        token_b = login_b.json()["access_token"]

        # Create a private canvas (owned by A) and a collaborative one directly
        # in the shared in-memory DB so we control ownership + collaboration.
        from core.database import SessionLocal
        from core.models import Canvas, User

        agent = _autonomous_agent_for(email_a)

        priv_id = f"priv-{uuid.uuid4().hex}"
        collab_id = f"collab-{uuid.uuid4().hex}"
        with SessionLocal() as s:
            ua = s.query(User).filter(User.email == email_a).first()
            uid_a = str(ua.id)
            tenant_a = ua.tenant_id or "default"
            s.add(Canvas(id=priv_id, tenant_id=tenant_a, created_by=uid_a,
                         name="private", canvas_type="generic", is_collaborative=False, content={}))
            s.add(Canvas(id=collab_id, tenant_id=tenant_a, created_by=uid_a,
                         name="collab", canvas_type="generic", is_collaborative=True, content={}))
            s.commit()

        body = {"source": "x = 1", "language": "python", "agent_id": agent}
        # B cannot overwrite A's private canvas logic (403 is the ownership
        # refusal — the AUTONOMOUS gate passes and the access gate denies).
        denied = client.put(f"/api/canvas/{priv_id}/logic", json=body, headers=_auth(token_b))
        assert denied.status_code == 403, denied.text
        # A can write their own private canvas.
        owner_ok = client.put(f"/api/canvas/{priv_id}/logic", json=body, headers=_auth(token_a))
        assert owner_ok.status_code == 200, owner_ok.text
        # B can collaborate on a collaborative canvas (mini-app instances).
        collab_ok = client.put(f"/api/canvas/{collab_id}/logic", json=body, headers=_auth(token_b))
        assert collab_ok.status_code == 200, collab_ok.text
