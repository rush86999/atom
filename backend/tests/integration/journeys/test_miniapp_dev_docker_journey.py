"""Mini-app DEV-ONLY docker-dev journey — full authoring + REAL dev-run.

Companion to ``test_mini_app_harness_journey.py`` (which proves dev-run/run
fail CLOSED without a runtime). This one proves the other half of the dev
story: with ``ATOM_MINIAAP_RUNTIME=docker-dev`` and a reachable Docker
daemon, the exact same HTTP surface the frontend harness uses EXECUTES the
app — scaffold → write logic → dev-run — inside a Docker container (same
guest agent + protocol as a Firecracker boot; see ``MiniAppDevRuntime``).

Skipped when Docker isn't reachable (e.g. CI without a daemon, or a MacBook
whose Docker Desktop is down — those cases are covered fail-closed by the
companion journey).
"""
import os
import subprocess

import pytest


def _docker_up() -> bool:
    try:
        return subprocess.run(
            ["docker", "info", "--format", "ok"],
            capture_output=True, timeout=10,
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


pytestmark = pytest.mark.skipif(not _docker_up(), reason="Docker daemon not reachable")


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _rpc(client, token, action, params=None):
    resp = client.post(f"/api/rpc/{action}", json={"params": params or {}}, headers=_auth(token))
    assert resp.status_code == 200, f"{action} -> {resp.status_code} {resp.text}"
    body = resp.json()
    assert body.get("success") is True, f"{action} top-level failed: {body}"
    return body["data"]


STARTER = (
    "state = dict(state or {})\n"
    "state['runs'] = state.get('runs', 0) + 1\n"
    "print('dev-run executed')\n"
)


class TestMiniAppDockerDevJourney:
    def test_author_then_dev_run_executes_in_container(self, real_auth_client, registered_user, monkeypatch):
        monkeypatch.setenv("ATOM_MINIAAP_RUNTIME", "docker-dev")
        monkeypatch.setenv("ENVIRONMENT", "development")

        client = real_auth_client
        _, _, _, token = registered_user

        # 1) Constraint probe reports the docker-dev mode BEFORE any run.
        scaf = _rpc(client, token, "mini_app_scaffold", {
            "name": "Dev Mode Counter",
            "declared_scopes": ["canvas_render"],
            "dependencies": [],
        })
        app_id = scaf["app_id"]

        status = _rpc(client, token, "mini_app_status", {"app_id": app_id})
        assert status["status"]["runtime"]["mode"] == "docker-dev"
        assert status["status"]["runtime"]["available"] is True

        # 2) Author logic (same path the harness Monaco editor saves through).
        wl = _rpc(client, token, "mini_app_write_logic", {"app_id": app_id, "source": STARTER})
        assert wl["success"] is True

        # 3) THE boundary: dev-run executes in a real container.
        run = _rpc(client, token, "mini_app_dev_run", {"app_id": app_id, "inputs": {}})
        assert run["success"] is True, run
        assert run["state"] == {"runs": 1}
        assert run["state_changed"] is True

        # 4) Second run is stateless (persist=False dry-run) but executes again.
        run2 = _rpc(client, token, "mini_app_dev_run", {"app_id": app_id, "inputs": {}})
        assert run2["success"] is True, run2
        assert run2["state"] == {"runs": 1}

    def test_dev_run_still_fails_closed_in_production(self, real_auth_client, registered_user, monkeypatch):
        """ENVIRONMENT=production refuses docker-dev outright — the dev mode
        cannot leak into a production deployment."""
        monkeypatch.setenv("ATOM_MINIAAP_RUNTIME", "docker-dev")
        monkeypatch.setenv("ENVIRONMENT", "production")

        client = real_auth_client
        _, _, _, token = registered_user

        scaf = _rpc(client, token, "mini_app_scaffold", {
            "name": "Prod Refused",
            "declared_scopes": ["canvas_render"],
            "dependencies": [],
        })
        app_id = scaf["app_id"]
        _rpc(client, token, "mini_app_write_logic", {"app_id": app_id, "source": STARTER})

        resp = client.post(
            "/api/rpc/mini_app_dev_run",
            json={"params": {"app_id": app_id, "inputs": {}}},
            headers=_auth(token),
        )
        assert resp.status_code == 200
        body = resp.json()
        # Fail-closed: either the action errors or carries a generic failure —
        # the run must NOT have executed.
        assert body.get("success") is not True or not body.get("data", {}).get("state")
