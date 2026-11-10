#!/usr/bin/env python3
"""No-browser self-test for the SSO harness capture and issuer gate.

Verifies, without launching a browser:

1. The atomic failure checkpoint retains the full safe matrix, false/unknown
   names, safe URL key names, header records, provider/restart state,
   navigation paths and screenshot reference.
2. Response headers are captured by method/path/status, not by response object
   identity, so redirect/landing responses cannot be silently dropped and a
   missing record is ``None`` (unknown), never a false product claim.
3. The owned controlled issuer's real ``/authorize`` 302 is actually held
   before it is written: the client gets no response until the gate is
   released, then receives the unchanged 302 with the real redirect code.
"""
from __future__ import annotations

import base64
import hashlib
import http.client
import importlib.util
import json
import socket
import sys
import tempfile
import threading
import urllib.parse
from pathlib import Path

HARNESS = Path("/private/tmp/root-web-sso-browser-harness-20261109.py")
BACKEND = Path("/private/tmp/atom-web-task-project-20261109/backend")


def load_harness():
    spec = importlib.util.spec_from_file_location("sso_harness", HARNESS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def check_checkpoint(module):
    world = Path(tempfile.mkdtemp(prefix="sso-capture-selftest-", dir="/private/tmp"))
    checks = {"a": True, "b": False, "c": None}
    required_failures = {"b": False, "c": None}
    payload = module.write_boundary_checkpoint(
        world,
        checks=checks,
        required_failures=required_failures,
        restart={"held": False, "extension_ok": False},
        final_pathname="/settings",
        final_query_keys=["sso"],
        settings={"exact_path_query": True},
        header_records={
            "GET /auth/sso/callback": [{
                "status": 200,
                "cache-control": "no-store",
                "referrer-policy": "no-referrer",
                "content-type": "text/html",
            }],
        },
        provider_counts={"authorize": 1, "token": 1},
        navigation=[{"method": "GET", "path": "/settings", "status": 200}],
        page_heading="Settings",
        failure_screenshot="failure-final.png",
        source="13409c7d3f31fcac4136cffc93672b6ecd41ca4b",
        harness_sha256="test-hash",
    )
    assert payload["checks"] == checks
    assert payload["false_checks"] == ["b"]
    assert payload["unknown_checks"] == ["c"]
    assert payload["required_failures"] == required_failures
    assert payload["final_pathname"] == "/settings"
    assert payload["final_query_keys"] == ["sso"]
    assert payload["provider"]["token"] == 1
    assert payload["navigation"][0]["path"] == "/settings"
    assert payload["failure_screenshot"] == "failure-final.png"
    stored = json.loads((world / "boundary-checks.private.json").read_text())
    assert stored["checks"]["c"] is None
    return stored


def check_header_capture(module):
    recorder = module.Recorder(
        "http://localhost:1", "http://127.0.0.1:2", "http://127.0.0.1:3")
    # No record yet: unknown, not a false claim.
    assert recorder.header_record("GET", "/auth/sso/callback") is None
    recorder.record_response(
        "GET", "/auth/sso/callback", 200,
        {"cache-control": "no-store", "referrer-policy": "no-referrer"})
    # Duplicate/redirect-style events: last matching status wins.
    recorder.record_response(
        "GET", "/auth/sso/callback", 200,
        {"cache-control": "no-store",
         "referrer-policy": "strict-origin-when-cross-origin"})
    landing = recorder.header_record("GET", "/auth/sso/callback")
    assert landing["referrer-policy"] == "strict-origin-when-cross-origin"
    recorder.record_response(
        "POST", "/api/auth/sso/oidc/web/exchange", 200,
        {"cache-control": "no-store", "referrer-policy": "no-referrer"})
    exchange = recorder.header_record(
        "POST", "/api/auth/sso/oidc/web/exchange")
    assert exchange["referrer-policy"] == "no-referrer"
    # A different method on the same path must not collide.
    assert recorder.header_record(
        "GET", "/api/auth/sso/oidc/web/exchange") is None


def check_issuer_gate(module):
    verifier = "selftest-verifier"
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    port = free_port()
    provider = module.PkceProvider(
        port=port,
        client_id="self-test-client",
        client_secret="self-test-secret",
        redirect_uri="http://127.0.0.1:59999/auth/sso/callback",
        email="gate@example.com",
        given_name="Gate",
        family_name="Test",
        mode="valid",
    ).start()
    result = {}
    outcome = {}
    try:
        provider.arm_authorize_gate()

        def call():
            try:
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
                query = urllib.parse.urlencode({
                    "response_type": "code",
                    "client_id": "self-test-client",
                    "redirect_uri": provider._provider.redirect_uri,
                    "scope": "openid email profile",
                    "state": "selftest-state",
                    "nonce": "selftest-nonce",
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                })
                conn.request("GET", "/authorize?" + query)
                response = conn.getresponse()
                result["status"] = response.status
                result["location"] = response.getheader("location")
                response.read()
                conn.close()
            except Exception as exc:  # pragma: no cover - diagnostic only
                outcome["error"] = type(exc).__name__

        worker = threading.Thread(target=call, daemon=True)
        worker.start()
        assert provider.wait_authorize_entered(10), "gate never engaged"
        assert provider.gate_state["entered"] is True
        worker.join(timeout=0.5)
        assert worker.is_alive(), "302 was sent before the gate was released"
        assert provider.gate_state["released"] is False
        assert "status" not in result

        provider.release_authorize_gate()
        worker.join(timeout=15)
        assert not worker.is_alive(), "gated request did not finish"
        assert "error" not in outcome, outcome.get("error")
        assert result["status"] == 302
        assert "code=" in (result["location"] or "")
        assert provider.gate_state["released"] is True
        return {
            "entered_before_response": True,
            "response_withheld_while_held": True,
            "status_after_release": result["status"],
            "location_has_authorization_code": True,
            "released": provider.gate_state["released"],
        }
    finally:
        provider.release_authorize_gate()
        provider.stop()


def main():
    sys.path.insert(0, str(BACKEND))
    module = load_harness()
    stored = check_checkpoint(module)
    check_header_capture(module)
    gate = check_issuer_gate(module)
    print(json.dumps({
        "ok": True,
        "false_checks": stored["false_checks"],
        "unknown_checks": stored["unknown_checks"],
        "header_capture_by_method_path": True,
        "header_missing_is_none": True,
        "issuer_gate": gate,
    }, indent=2))


if __name__ == "__main__":
    main()
