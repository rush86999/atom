"""Tests for the opt-in live-replay lane (synthetic loops only).

Nothing here contacts a provider, reads a credential from the environment or an
auth file, creates a world or launches a browser. The relay is exercised
in-process against a loopback synthetic upstream that returns authored
OpenAI-compatible responses (plus one stub upstream for the trusted-live state
path), and the driver's live configuration is validated against its refusal
matrix. A trusted-URL test only inspects argv/headers; it never dispatches.

The default scripted episode is covered by
``test_browser_invoice_partial_evidence_preflight.py`` and
``..._observer.py``; this file only adds the opt-in lane plus a regression that
the default preflight report did not change shape.
"""
from __future__ import annotations

import importlib.util
import json
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
DRIVER_PATH = REPO / "scripts" / "acceptance" / (
    "browser_invoice_partial_evidence.py")
RELAY_PATH = REPO / "backend" / "scripts" / "orchestration_acceptance" / (
    "live_model_relay.py")
RUN_ISOLATED_PATH = REPO / "backend" / "scripts" / (
    "orchestration_acceptance") / "run_isolated.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # Register before exec: dataclasses resolve string annotations through
    # sys.modules[cls.__module__], which is None for an unregistered module.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def driver():
    return _load(DRIVER_PATH, "browser_invoice_partial_evidence_live")


@pytest.fixture(scope="module")
def relay():
    return _load(RELAY_PATH, "live_model_relay_for_tests")


# ---------------------------------------------------------------------------
# Synthetic loopback upstream (authored responses; records every request)
# ---------------------------------------------------------------------------

class SyntheticUpstream:
    def __init__(self, **options) -> None:
        self.model = options.get("model", "deepseek-v4.1-flash")
        self.content = options.get("content", '{"decision": "clarify"}')
        self.prompt_tokens = options.get("prompt_tokens", 10)
        self.completion_tokens = options.get("completion_tokens", 5)
        self.status = options.get("status", 200)
        self.location = options.get("location")
        self.delay = options.get("delay", 0.0)
        self.omit_usage = options.get("omit_usage", False)
        self.requests = []
        self._server = None
        self._thread = None
        self._lock = threading.Lock()

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def record(self, entry) -> None:
        with self._lock:
            self.requests.append(entry)

    def start(self) -> "SyntheticUpstream":
        upstream = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length)
                try:
                    body = json.loads(raw or b"{}")
                except ValueError:
                    body = {"raw": raw.decode("utf-8", "replace")}
                upstream.record({
                    "path": self.path,
                    "body": body,
                    "headers": dict(self.headers),
                    "at": time.time(),
                })
                if upstream.delay:
                    time.sleep(upstream.delay)
                payload = {
                    "id": "synthetic-1",
                    "object": "chat.completion",
                    "model": upstream.model,
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant",
                                    "content": upstream.content},
                        "finish_reason": "stop",
                    }],
                }
                if not upstream.omit_usage:
                    payload["usage"] = {
                        "prompt_tokens": upstream.prompt_tokens,
                        "completion_tokens": upstream.completion_tokens,
                        "total_tokens": (upstream.prompt_tokens
                                         + upstream.completion_tokens),
                    }
                encoded = json.dumps(payload).encode()
                self.send_response(upstream.status)
                self.send_header("Content-Type", "application/json")
                if upstream.location:
                    self.send_header("Location", upstream.location)
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, *args):
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self._server.cfg = self
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)


@pytest.fixture
def upstream():
    server = SyntheticUpstream().start()
    yield server
    server.stop()


class RunningRelay(SimpleNamespace):
    port: int
    state: object
    upstream: object

    def post(self, body, *, token="run-token", timeout=10.0):
        import httpx

        return httpx.post(
            f"http://127.0.0.1:{self.port}/v1/{token}/chat/completions",
            json=body, timeout=timeout)

    def get(self, path: str, *, timeout=5.0):
        import httpx

        return httpx.get(f"http://127.0.0.1:{self.port}{path}",
                         timeout=timeout)


@pytest.fixture
def relay_factory(relay, tmp_path):
    created = []

    def _make(upstream_server, **limit_overrides):
        limits = relay.RelayLimits(**{
            "max_calls": 12,
            "max_spend_usd": 0.50,
            "max_output_tokens": 1200,
            "input_usd_per_1m": 0.30,
            "output_usd_per_1m": 1.20,
            "call_timeout_s": 5.0,
            "max_wall_clock_s": 60.0,
            **limit_overrides,
        })
        state = relay.RelayState(
            provider="opencode-go",
            model="deepseek-v4.1-flash",
            run_token="run-token",
            upstream_base_url=upstream_server.base_url,
            limits=limits,
            ledger_path=tmp_path / "relay_ledger.jsonl",
        )
        client = relay.HttpUpstream(
            upstream_server.base_url, call_timeout_s=limits.call_timeout_s)
        server = relay.build_server(port=0, relay=state, upstream=client)
        thread = threading.Thread(
            target=server.serve_forever, daemon=True)
        thread.start()
        created.append((server, thread, client))
        return RunningRelay(port=server.server_address[1], state=state,
                            upstream=client)

    yield _make
    for server, thread, client in created:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        client.close()


def _chat(model="deepseek-v4.1-flash", **extra):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "Which source has the invoice?"}],
    }
    body.update(extra)
    return body


# ---------------------------------------------------------------------------
# Relay behaviour
# ---------------------------------------------------------------------------

def test_relay_forwards_one_chat_completion_and_settles_usage(
        upstream, relay_factory):
    running = relay_factory(upstream)
    response = running.post(_chat())
    assert response.status_code == 200
    assert response.json()["model"] == "deepseek-v4.1-flash"
    assert response.headers.get("X-Atom-Relay-Seq") == "1"

    assert len(upstream.requests) == 1
    forwarded = upstream.requests[0]
    assert forwarded["path"] == "/v1/chat/completions"
    assert forwarded["body"]["model"] == "deepseek-v4.1-flash"
    # The relay never forwards an inbound authorization and holds no credential.
    assert "authorization" not in {key.lower() for key in forwarded["headers"]}

    ledger = running.get("/ledger").json()
    assert ledger["budget"]["calls_started"] == 1
    assert ledger["budget"]["calls_completed"] == 1
    assert ledger["budget"]["reserved_usd"] == 0
    entry = ledger["entries"][0]
    assert entry["operation"] == "chat.completions"
    assert entry["requested_model"] == "deepseek-v4.1-flash"
    assert entry["served_model"] == "deepseek-v4.1-flash"
    assert entry["usage"]["prompt_tokens"] == 10
    assert entry["usage"]["completion_tokens"] == 5
    assert entry["usage_unknown"] is False
    assert entry["settled_by"] == "usage"
    assert entry["cost_usd"] == pytest.approx(
        (10 * 0.30 + 5 * 1.20) / 1_000_000, rel=1e-6)
    assert entry["response_sha256"]


def test_call_cap_is_reserved_before_dispatch(upstream, relay_factory):
    running = relay_factory(upstream, max_calls=2)
    assert running.post(_chat()).status_code == 200
    assert running.post(_chat()).status_code == 200
    refused = running.post(_chat())
    assert refused.status_code == 429
    body = refused.json()
    assert body["error"]["type"] == "budget_exhausted"
    assert body["error"]["reason"] == "call_cap"
    # Physical proof: the upstream saw exactly the capped number of requests.
    assert len(upstream.requests) == 2
    budget = running.get("/livez").json()["budget"]
    assert budget["calls_started"] == 2
    assert budget["refusals"]["call_cap"] == 1


def test_spend_cap_refuses_before_any_dispatch(upstream, relay_factory):
    running = relay_factory(upstream, max_spend_usd=0.0000001)
    refused = running.post(_chat())
    assert refused.status_code == 402
    assert refused.json()["error"]["reason"] == "spend_cap"
    assert upstream.requests == []
    budget = running.get("/livez").json()["budget"]
    assert budget["calls_started"] == 0
    assert budget["charged_usd"] == 0
    assert budget["reserved_usd"] == 0
    assert budget["refusals"]["spend_cap"] == 1


def test_max_tokens_is_clamped_before_dispatch(upstream, relay_factory):
    running = relay_factory(upstream, max_output_tokens=64)
    assert running.post(_chat(max_tokens=99_999)).status_code == 200
    assert upstream.requests[0]["body"]["max_tokens"] == 64
    entry = running.get("/ledger").json()["entries"][0]
    assert entry["clamped"] is True
    assert entry["requested_max_tokens"] == 99_999
    assert entry["sent_max_tokens"] == 64


def test_non_integer_max_tokens_is_replaced(upstream, relay_factory):
    running = relay_factory(upstream, max_output_tokens=64)
    assert running.post(_chat(max_tokens="lots")).status_code == 200
    assert upstream.requests[0]["body"]["max_tokens"] == 64
    assert running.get("/ledger").json()["entries"][0]["clamped"] is True


def test_streaming_is_rejected_without_dispatch(upstream, relay_factory):
    running = relay_factory(upstream)
    response = running.post(_chat(stream=True))
    assert response.status_code == 400
    assert response.json()["error"]["type"] == "stream_unsupported"
    assert upstream.requests == []


def test_model_not_pinned_is_rejected_without_dispatch(
        upstream, relay_factory):
    running = relay_factory(upstream)
    response = running.post(_chat(model="gemini-3-flash"))
    assert response.status_code == 400
    assert response.json()["error"]["type"] == "model_not_pinned"
    assert upstream.requests == []
    budget = running.get("/livez").json()["budget"]
    assert budget["refusals"]["model_not_pinned"] == 1


def test_unknown_path_and_token_are_404(upstream, relay_factory):
    running = relay_factory(upstream)
    assert running.post(_chat(), token="wrong-token").status_code == 404
    assert running.get("/v1/wrong-token/models").status_code == 404
    assert running.get("/nope").status_code == 404
    assert upstream.requests == []


def test_models_probe_is_answered_locally_with_the_pin(
        upstream, relay_factory):
    running = relay_factory(upstream)
    response = running.get("/v1/run-token/models")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == [
        "deepseek-v4.1-flash"]
    assert upstream.requests == []
    assert running.get("/livez").json()["budget"]["models_probes"] == 1


def test_missing_usage_charges_the_reservation_not_a_guess(
        relay_factory):
    server = SyntheticUpstream(omit_usage=True).start()
    try:
        running = relay_factory(server)
        assert running.post(_chat()).status_code == 200
        entry = running.get("/ledger").json()["entries"][0]
        assert entry["usage"] is None
        assert entry["usage_unknown"] is True
        assert entry["settled_by"] == "reservation"
        assert entry["cost_usd"] == pytest.approx(
            entry["reserved_usd"], rel=1e-9)
        budget = running.get("/livez").json()["budget"]
        assert budget["usage_unknown_calls"] == 1
        assert budget["input_tokens"] == 0
        assert budget["output_tokens"] == 0
    finally:
        server.stop()


def test_response_content_is_never_written_to_the_ledger(relay_factory):
    secret = "sk-live-secret-abcdef123456"
    content = '{"unique_completion_marker": "MODEL-CONTENT-42", "token": ' + \
              json.dumps(secret) + '}'
    server = SyntheticUpstream(content=content).start()
    try:
        running = relay_factory(server)
        assert running.post(_chat()).status_code == 200
        raw_ledger = running.get("/ledger").text
        assert "MODEL-CONTENT-42" not in raw_ledger
        assert secret not in raw_ledger
        assert '"content"' not in raw_ledger
        entry = running.get("/ledger").json()["entries"][0]
        assert "response_head" not in entry
        assert "response_head_redacted" not in entry
        # Metadata is still present: the ledger can prove what was served.
        assert entry["response_bytes"] > 0
        assert entry["response_sha256"]
        assert entry["served_model"] == "deepseek-v4.1-flash"
    finally:
        server.stop()


def test_call_timeout_is_bounded_and_charged_once(relay_factory):
    server = SyntheticUpstream(delay=1.0).start()
    try:
        running = relay_factory(server, call_timeout_s=0.2)
        response = running.post(_chat())
        assert response.status_code == 504
        assert response.json()["error"]["reason"] == "timeout"
        # The relay made exactly one attempt (no retries).
        assert len(server.requests) == 1
        entry = running.get("/ledger").json()["entries"][0]
        assert entry["status"] == 504
        assert entry["settled_by"] == "reservation"
        assert entry["cost_usd"] == pytest.approx(
            entry["reserved_usd"], rel=1e-9)
    finally:
        server.stop()


def test_redirect_is_not_followed_and_is_one_physical_call(relay_factory):
    server = SyntheticUpstream(
        status=302, location="https://opencode.ai/zen/v1/elsewhere").start()
    try:
        running = relay_factory(server)
        response = running.post(_chat())
        assert response.status_code == 302
        # Exactly one request: the relay never follows the Location.
        assert len(server.requests) == 1
        entry = running.get("/ledger").json()["entries"][0]
        assert entry["status"] == 302
    finally:
        server.stop()


def test_upstream_error_is_one_attempt_and_not_retried(relay_factory):
    server = SyntheticUpstream(status=500).start()
    try:
        running = relay_factory(server)
        assert running.post(_chat()).status_code == 500
        assert len(server.requests) == 1
        budget = running.get("/livez").json()["budget"]
        assert budget["calls_started"] == 1
        assert budget["calls_completed"] == 1
    finally:
        server.stop()


def test_ledger_file_is_truncated_per_relay_process(relay, upstream, tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    ledger_path.write_text('{"stale": true}\n', encoding="utf-8")
    relay.RelayState(
        provider="opencode-go", model="deepseek-v4.1-flash",
        run_token="run-token", upstream_base_url=upstream.base_url,
        limits=relay.RelayLimits(), ledger_path=ledger_path)
    assert ledger_path.read_text(encoding="utf-8") == ""


# ---------------------------------------------------------------------------
# Upstream gate: loopback synthetic OR exactly one trusted live destination
# ---------------------------------------------------------------------------

TRUSTED = "https://opencode.ai/zen/v1"
CREDENTIAL = "sk-opencode-caller-supplied-123456"


@pytest.mark.parametrize("url,needle", [
    ("https://opencode.ai/zen/v1", "credential seam"),
    ("http://api.openai.com/v1", "not loopback"),
    ("http://192.168.1.50:1234/v1", "not loopback"),
    ("ftp://127.0.0.1:1234/v1", "got scheme"),
    ("", "required"),
    ("http://127.0.0.1:1234", "API prefix"),
    ("http://user:pass@127.0.0.1:1234/v1", "userinfo"),
    ("https://api.openai.com/v1", "got scheme"),
    ("https://opencode.ai/zen/v1/chat/completions", "fixed to"),
    ("https://opencode.ai/zen/v1?x=1", "query or fragment"),
    ("https://opencode.ai:8443/zen/v1", "must not name a port"),
    ("https://opencode.ai/v1", "fixed to"),
])
def test_upstream_gate_refuses_anything_but_the_two_known_destinations(
        relay, url, needle):
    with pytest.raises(ValueError, match=needle):
        relay.validate_upstream_base_url(url)


def test_trusted_live_destination_is_accepted_only_with_the_explicit_seam(
        relay):
    assert relay.validate_upstream_base_url(TRUSTED, allow_live=True) == TRUSTED
    assert relay.upstream_kind(TRUSTED) == "trusted_live"
    assert relay.is_trusted_live_upstream(TRUSTED) is True
    # Normalisation: a trailing slash is the same fixed destination.
    assert relay.validate_upstream_base_url(
        TRUSTED + "/", allow_live=True) == TRUSTED
    assert relay.is_trusted_live_upstream("https://opencode.ai/zen/v1/") is True


def test_loopback_upstream_is_accepted(relay):
    assert relay.validate_upstream_base_url(
        "http://127.0.0.1:1234/v1/") == "http://127.0.0.1:1234/v1"
    assert relay.upstream_kind("http://127.0.0.1:1234/v1") == (
        "synthetic_loopback")
    assert relay.is_trusted_live_upstream("http://127.0.0.1:1234/v1") is False


def test_relay_never_reads_the_process_environment_or_an_auth_file(relay):
    source = RELAY_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in source
    assert "getenv" not in source
    for credential_name in (
            "OPENCODE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
            "GOOGLE_API_KEY", "GEMINI_API_KEY"):
        assert credential_name not in source
    for forbidden in ("auth.json", "load_dotenv", "dotenv", "Path.home"):
        assert forbidden not in source


def test_live_http_client_needs_the_caller_key_and_refuses_it_on_loopback(
        relay):
    with pytest.raises(ValueError, match="caller-supplied"):
        relay.HttpUpstream(TRUSTED)
    with pytest.raises(ValueError, match="loopback synthetic"):
        relay.HttpUpstream("http://127.0.0.1:1234/v1", api_key=CREDENTIAL)
    live = relay.HttpUpstream(TRUSTED, api_key=CREDENTIAL)
    headers = live._headers()
    assert headers["Authorization"] == f"Bearer {CREDENTIAL}"
    assert live.upstream_kind == "trusted_live"
    loopback = relay.HttpUpstream("http://127.0.0.1:1234/v1")
    assert "Authorization" not in loopback._headers()


def test_live_transport_ledger_has_metadata_only(relay, tmp_path):
    """The live state path is exercised with a stub upstream, never a network."""
    secret = "sk-opencode-caller-supplied-123456"
    content = '{"unique_completion_marker": "LIVE-MODEL-CONTENT-7"}'
    body = json.dumps({
        "model": "deepseek-v4.1-flash",
        "choices": [{"message": {"role": "assistant", "content": content},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 7,
                  "total_tokens": 18},
    }).encode()

    class StubUpstream:
        calls = 0

        def post_chat(self, payload):
            self.calls += 1
            return relay.UpstreamResult(200, body)

    stub = StubUpstream()
    state = relay.RelayState(
        provider="opencode-go", model="deepseek-v4.1-flash",
        run_token="run-token", upstream_base_url=TRUSTED,
        limits=relay.RelayLimits(), ledger_path=tmp_path / "ledger.jsonl")
    server = relay.build_server(port=0, relay=state, upstream=stub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        response = __import__("httpx").post(
            f"http://127.0.0.1:{port}/v1/run-token/chat/completions",
            json=_chat(), timeout=10)
        assert response.status_code == 200
        assert stub.calls == 1
        raw = __import__("httpx").get(
            f"http://127.0.0.1:{port}/ledger", timeout=10).text
        assert secret not in raw
        assert "LIVE-MODEL-CONTENT-7" not in raw
        assert '"content"' not in raw
        entry = json.loads(raw)["entries"][0]
        assert entry["upstream_error"] is None
        assert entry["response_sha256"]
        assert "response_head" not in entry
        budget = json.loads(raw)["budget"]
        assert budget["upstream_kind"] == "trusted_live"
        assert budget["live_upstream_enabled"] is True
        assert state.charged_usd > 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_credential_shape_is_validated_without_recording_it(relay):
    assert relay.validate_credential(CREDENTIAL) == CREDENTIAL
    for bad in ("", "   ", "sk-two\nlines", "sk with space", "x" * 5000):
        with pytest.raises(ValueError):
            relay.validate_credential(bad)
    with pytest.raises(ValueError, match="whitespace"):
        relay.HttpUpstream(TRUSTED, api_key="sk-two\nlines")


def test_relay_main_refuses_live_without_a_stdin_credential(relay, capsys):
    code = relay.main([
        "--port", "0", "--run-token", "token",
        "--upstream-base-url", TRUSTED,
        "--input-usd-per-1m", "0.3", "--output-usd-per-1m", "1.2",
    ])
    assert code == 2
    assert "without a caller-supplied credential" in capsys.readouterr().err


def test_relay_main_refuses_a_credential_for_a_loopback_upstream(
        relay, capsys, monkeypatch):
    import io

    monkeypatch.setattr(relay.sys, "stdin", io.StringIO(CREDENTIAL + "\n"))
    code = relay.main([
        "--port", "0", "--run-token", "token",
        "--upstream-base-url", "http://127.0.0.1:9/v1",
        "--upstream-api-key-stdin",
        "--input-usd-per-1m", "0.3", "--output-usd-per-1m", "1.2",
    ])
    assert code == 2
    assert "loopback synthetic upstream" in capsys.readouterr().err


def test_relay_placeholder_key_shape_is_enforced(relay):
    assert relay.validate_dummy_key(relay.RELAY_DUMMY_KEY)
    with pytest.raises(ValueError, match="relay placeholder"):
        relay.validate_dummy_key("sk-operator-real-credential-123456")
    with pytest.raises(ValueError, match="too short"):
        relay.validate_dummy_key("relay-local-")


# ---------------------------------------------------------------------------
# Launcher wiring (signature + refusals, no process launched)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def launcher():
    return _load(RUN_ISOLATED_PATH, "run_isolated_for_live_tests")


def test_launch_server_live_arguments_are_opt_in(launcher):
    import inspect

    signature = inspect.signature(launcher.launch_server)
    for name in ("provider_endpoint", "provider_base_url_env",
                 "provider_api_key_env", "provider_api_key",
                 "provider_catalog"):
        assert signature.parameters[name].default is None


def test_sandbox_profile_allows_exactly_the_server_and_provider_port(
        launcher):
    profile = launcher._sandbox_profile(8037, extra_ports=(8117,))
    outbound = [line for line in profile.splitlines()
                if line.startswith("(allow network-outbound")]
    assert len(outbound) == 2
    assert 'localhost:8037' in outbound[0]
    assert 'localhost:8117' in outbound[1]
    assert "(deny network*)" in profile


def test_launch_server_refuses_a_credential_looking_key(
        launcher, tmp_path):
    with pytest.raises(ValueError, match="relay placeholder"):
        launcher.launch_server(
            8037, tmp_path / "world",
            provider_endpoint="http://127.0.0.1:8117/v1/token",
            provider_base_url_env="OPENCODE_BASE_URL",
            provider_api_key_env="OPENCODE_API_KEY",
            provider_api_key="sk-real-operator-credential",
            provider_catalog={"opencode-go": ["deepseek-v4.1-flash"]})


def test_launch_server_refuses_mixed_transports(launcher, tmp_path):
    with pytest.raises(RuntimeError, match="mutually exclusive"):
        launcher.launch_server(
            8037, tmp_path / "world", provider_shim=True,
            provider_endpoint="http://127.0.0.1:8117/v1/token",
            provider_base_url_env="OPENCODE_BASE_URL",
            provider_api_key_env="OPENCODE_API_KEY",
            provider_api_key="relay-local-not-a-secret",
            provider_catalog={"opencode-go": ["deepseek-v4.1-flash"]})


def test_launch_server_refuses_a_non_loopback_endpoint(launcher, tmp_path):
    with pytest.raises(RuntimeError, match="loopback"):
        launcher.launch_server(
            8037, tmp_path / "world",
            provider_endpoint="https://opencode.ai/zen/v1",
            provider_base_url_env="OPENCODE_BASE_URL",
            provider_api_key_env="OPENCODE_API_KEY",
            provider_api_key="relay-local-not-a-secret",
            provider_catalog={"opencode-go": ["deepseek-v4.1-flash"]})


def test_launch_live_relay_is_pinned(launcher, monkeypatch):
    monkeypatch.setattr(launcher, "_refuse_if_port_held",
                        lambda port, label: None)
    with pytest.raises(RuntimeError, match="pinned"):
        launcher.launch_live_relay(
            8117, upstream_base_url="http://127.0.0.1:9/v1",
            run_token="token", ledger_path=Path("/tmp/unused-ledger.jsonl"),
            model="gemini-3-flash",
            limits={"max_model_calls": 1, "max_spend_usd": 1.0,
                    "max_output_tokens": 10, "input_usd_per_1m": 0.3,
                    "output_usd_per_1m": 1.2})


def test_launch_live_relay_requires_prices(launcher, monkeypatch):
    monkeypatch.setattr(launcher, "_refuse_if_port_held",
                        lambda port, label: None)
    with pytest.raises(RuntimeError, match="input_usd_per_1m"):
        launcher.launch_live_relay(
            8117, upstream_base_url="http://127.0.0.1:9/v1",
            run_token="token", ledger_path=Path("/tmp/unused-ledger.jsonl"),
            limits={"max_model_calls": 1, "max_spend_usd": 1.0,
                    "max_output_tokens": 10})


def test_launch_live_relay_requires_a_caller_credential_for_the_live_route(
        launcher, monkeypatch):
    monkeypatch.setattr(launcher, "_refuse_if_port_held",
                        lambda port, label: None)
    with pytest.raises(RuntimeError, match="caller-supplied"):
        launcher.launch_live_relay(
            8117, upstream_base_url=TRUSTED,
            run_token="token", ledger_path=Path("/tmp/unused-ledger.jsonl"),
            limits={"max_model_calls": 1, "max_spend_usd": 1.0,
                    "max_output_tokens": 10, "input_usd_per_1m": 0.3,
                    "output_usd_per_1m": 1.2})


def test_launch_live_relay_refuses_a_credential_for_a_synthetic_upstream(
        launcher, monkeypatch):
    monkeypatch.setattr(launcher, "_refuse_if_port_held",
                        lambda port, label: None)
    with pytest.raises(RuntimeError, match="loopback synthetic"):
        launcher.launch_live_relay(
            8117, upstream_base_url="http://127.0.0.1:9/v1",
            run_token="token", ledger_path=Path("/tmp/unused-ledger.jsonl"),
            limits={"max_model_calls": 1, "max_spend_usd": 1.0,
                    "max_output_tokens": 10, "input_usd_per_1m": 0.3,
                    "output_usd_per_1m": 1.2},
            upstream_api_key=CREDENTIAL)


def test_launch_live_relay_refuses_a_malformed_credential(
        launcher, monkeypatch):
    monkeypatch.setattr(launcher, "_refuse_if_port_held",
                        lambda port, label: None)
    with pytest.raises(RuntimeError, match="invalid live credential"):
        launcher.launch_live_relay(
            8117, upstream_base_url=TRUSTED,
            run_token="token", ledger_path=Path("/tmp/unused-ledger.jsonl"),
            limits={"max_model_calls": 1, "max_spend_usd": 1.0,
                    "max_output_tokens": 10, "input_usd_per_1m": 0.3,
                    "output_usd_per_1m": 1.2},
            upstream_api_key="sk-two\nlines")


def test_relay_command_keeps_the_credential_out_of_argv(launcher, tmp_path):
    cmd = launcher._relay_command(
        8117, upstream_base_url=TRUSTED, run_token="token",
        ledger_path=tmp_path / "ledger.jsonl", model="deepseek-v4.1-flash",
        provider="opencode-go",
        limits={"max_model_calls": 1, "max_spend_usd": 1.0,
                "max_output_tokens": 10, "input_usd_per_1m": 0.3,
                "output_usd_per_1m": 1.2},
        api_key_stdin=True)
    assert "--upstream-api-key-stdin" in cmd
    assert CREDENTIAL not in " ".join(cmd)
    assert all("sk-" not in part for part in cmd)


def test_relay_env_is_scrubbed_of_provider_credentials(launcher, monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", CREDENTIAL)
    monkeypatch.setenv("OPENAI_API_KEY", CREDENTIAL)
    env = launcher._relay_subprocess_env()
    assert "OPENCODE_API_KEY" not in env
    assert "OPENAI_API_KEY" not in env
    assert CREDENTIAL not in json.dumps(env)


def _free_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]
    finally:
        probe.close()


def test_launch_live_relay_starts_serves_and_records(
        launcher, upstream, tmp_path, monkeypatch):
    """The launch path (argv, readiness, pin check, ledger file) runs for real."""
    import httpx

    monkeypatch.setattr(launcher, "VENV_PY", Path(sys.executable))
    port = _free_port()
    proc = launcher.launch_live_relay(
        port,
        upstream_base_url=upstream.base_url,
        run_token="scripted-token",
        ledger_path=tmp_path / "ledger.jsonl",
        limits={"max_model_calls": 2, "max_spend_usd": 0.5,
                "max_output_tokens": 32, "input_usd_per_1m": 0.30,
                "output_usd_per_1m": 1.20},
        log_path=tmp_path / "relay.log",
    )
    try:
        state = launcher.launch_live_relay.last_state
        assert state["model"] == "deepseek-v4.1-flash"
        assert state["provider"] == "opencode-go"
        response = httpx.post(
            f"http://127.0.0.1:{port}/v1/scripted-token/chat/completions",
            json=_chat(max_tokens=10_000), timeout=15)
        assert response.status_code == 200
        ledger = launcher.fetch_relay_ledger(port)
        assert ledger["available"] is True
        assert ledger["budget"]["calls_started"] == 1
        entry = ledger["entries"][0]
        assert entry["sent_max_tokens"] == 32
        assert entry["served_model"] == "deepseek-v4.1-flash"
        assert (tmp_path / "ledger.jsonl").is_file()
        assert (tmp_path / "relay.log").is_file()
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_launch_live_relay_refuses_a_held_port(launcher, upstream, tmp_path):
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    try:
        with pytest.raises(RuntimeError, match="already in use"):
            launcher.launch_live_relay(
                holder.getsockname()[1],
                upstream_base_url=upstream.base_url,
                run_token="scripted-token",
                ledger_path=tmp_path / "ledger.jsonl",
                limits={"max_model_calls": 1, "max_spend_usd": 0.5,
                        "max_output_tokens": 32, "input_usd_per_1m": 0.30,
                        "output_usd_per_1m": 1.20},
            )
    finally:
        holder.close()



# ---------------------------------------------------------------------------
# Driver live configuration
# ---------------------------------------------------------------------------

def _live_args(**overrides):
    values = {
        "preflight": False,
        "execute": True,
        "world": "live-config-test-world-does-not-exist",
        "backend_port": 8037,
        "frontend_port": 3137,
        "shim_port": 8107,
        "out": "/tmp/live-config-out",
        "expect_source_sha": "",
        "admin_password_file": "",
        "provision_admin_password": False,
        "headed": False,
        "live_flash": False,
        "live_upstream_url": "",
        "live_credential_stdin": False,
        "relay_port": None,
        "max_model_calls": None,
        "max_output_tokens": None,
        "max_spend_usd": None,
        "live_call_timeout_s": None,
        "max_wall_clock_s": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def live_env(driver, monkeypatch):
    monkeypatch.setattr(driver.D3, "_port_free", lambda port: True)
    monkeypatch.setenv(driver.LIVE_ACK_ENV, driver.LIVE_ACK_VALUE)
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    return driver


def test_default_configuration_is_scripted(live_env):
    assert live_env._live_config(_live_args()) is None


def test_live_flags_without_the_mode_selector_are_refused(live_env):
    with pytest.raises(live_env.PreflightError, match="require --live-flash"):
        live_env._live_config(_live_args(live_upstream_url="http://x"))


def test_live_mode_requires_execute(live_env):
    with pytest.raises(live_env.PreflightError, match="requires --execute"):
        live_env._live_config(_live_args(
            live_flash=True, execute=False, preflight=True,
            live_upstream_url="http://127.0.0.1:9/v1"))


def test_live_mode_requires_out(live_env):
    with pytest.raises(live_env.PreflightError, match="requires --out"):
        live_env._live_config(_live_args(
            live_flash=True, out="", live_upstream_url="http://127.0.0.1:9/v1"))


def test_live_mode_requires_the_spend_acknowledgement(
        live_env, monkeypatch):
    monkeypatch.delenv(live_env.LIVE_ACK_ENV, raising=False)
    with pytest.raises(live_env.PreflightError, match="second opt-in"):
        live_env._live_config(_live_args(
            live_flash=True, live_upstream_url="http://127.0.0.1:9/v1"))


def test_live_mode_requires_an_upstream(live_env):
    with pytest.raises(live_env.PreflightError, match="upstream-url"):
        live_env._live_config(_live_args(live_flash=True))


def test_live_mode_refuses_an_external_upstream(live_env):
    with pytest.raises(live_env.PreflightError, match="got scheme"):
        live_env._live_config(_live_args(
            live_flash=True, live_upstream_url="https://api.openai.com/v1"))


def test_live_mode_requires_the_credential_seam_for_the_trusted_destination(
        live_env, tmp_path, monkeypatch):
    monkeypatch.setattr(live_env, "_world_path",
                        lambda name: tmp_path / "world")
    with pytest.raises(live_env.PreflightError, match="live-credential-stdin"):
        live_env._live_config(_live_args(
            live_flash=True, live_upstream_url=TRUSTED))


def test_live_mode_refuses_a_credential_on_a_synthetic_upstream(
        live_env, tmp_path, monkeypatch):
    monkeypatch.setattr(live_env, "_world_path",
                        lambda name: tmp_path / "world")
    with pytest.raises(live_env.PreflightError, match="synthetic"):
        live_env._live_config(_live_args(
            live_flash=True, live_upstream_url="http://127.0.0.1:9/v1",
            live_credential_stdin=True))


def test_live_config_trusted_destination_records_only_the_seam(
        live_env, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", "sk-should-never-be-read-9876")
    monkeypatch.setattr(live_env, "_world_path",
                        lambda name: tmp_path / "world")
    config = live_env._live_config(_live_args(
        live_flash=True, live_upstream_url=TRUSTED,
        live_credential_stdin=True))
    assert config["upstream_kind"] == "trusted_live"
    assert config["live_upstream_enabled"] is True
    assert config["credential_seam"] == "operator_stdin"
    assert config["credential_source"].startswith("operator-supplied on stdin")
    assert "sk-should-never-be-read-9876" not in json.dumps(config)
    assert config["provider_catalog"] == {
        "opencode-go": ["deepseek-v4.1-flash"]}


def test_live_mode_refuses_a_busy_relay_port(live_env, monkeypatch):
    monkeypatch.setattr(live_env.D3, "_port_free", lambda port: False)
    with pytest.raises(live_env.PreflightError, match="already in use"):
        live_env._live_config(_live_args(
            live_flash=True, live_upstream_url="http://127.0.0.1:9/v1"))


def test_live_mode_refuses_an_existing_world(live_env, tmp_path,
                                             monkeypatch):
    existing = tmp_path / "world"
    existing.mkdir()
    monkeypatch.setattr(live_env, "_world_path", lambda name: existing)
    with pytest.raises(live_env.PreflightError, match="already exists"):
        live_env._live_config(_live_args(
            live_flash=True, live_upstream_url="http://127.0.0.1:9/v1"))


def test_live_mode_refuses_a_model_without_catalog_price(
        live_env, monkeypatch):
    import core.llm.opencode_catalog as catalog

    monkeypatch.setitem(catalog.OPCODE_KNOWN_PRICES,
                        live_env.LIVE_MODEL, None)
    with pytest.raises(live_env.PreflightError, match="no catalog price"):
        live_env._live_config(_live_args(
            live_flash=True, live_upstream_url="http://127.0.0.1:9/v1"))


def test_live_config_is_complete_and_pinned(live_env, tmp_path,
                                            monkeypatch):
    monkeypatch.setattr(live_env, "_world_path",
                        lambda name: tmp_path / "world")
    config = live_env._live_config(_live_args(
        live_flash=True,
        live_upstream_url="http://127.0.0.1:9/v1",
        relay_port=8117))
    assert config["provider"] == "opencode-go"
    assert config["model"] == "deepseek-v4.1-flash"
    assert config["pin"] == "opencode-go:deepseek-v4.1-flash"
    assert config["provider_catalog"] == {
        "opencode-go": ["deepseek-v4.1-flash"]}
    assert config["relay_url"].startswith("http://127.0.0.1:8117/v1/")
    assert config["limits"]["max_model_calls"] == 12
    assert config["limits"]["max_spend_usd"] == 0.50
    assert config["limits"]["max_output_tokens"] == 1200
    assert config["pricing"]["source"].endswith("OPCODE_KNOWN_PRICES")
    assert config["pricing"]["input_usd_per_1m"] == 0.30
    assert config["pricing"]["output_usd_per_1m"] == 1.20
    assert config["dummy_key"].startswith("relay-local-")
    assert config["live_upstream_enabled"] is False
    assert "no credential" in config["credential_source"]


def test_live_config_honours_the_timing_flags(live_env, tmp_path, monkeypatch):
    monkeypatch.setattr(live_env, "_world_path",
                        lambda name: tmp_path / "world")
    config = live_env._live_config(_live_args(
        live_flash=True, live_upstream_url="http://127.0.0.1:9/v1",
        live_call_timeout_s=7.5, max_wall_clock_s=120.0))
    assert config["limits"]["call_timeout_s"] == 7.5
    assert config["limits"]["max_wall_clock_s"] == 120.0


def test_live_config_never_carries_a_provider_credential(
        live_env, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", "sk-operator-secret-value-9876")
    monkeypatch.setattr(live_env, "_world_path",
                        lambda name: tmp_path / "world")
    config = live_env._live_config(_live_args(
        live_flash=True, live_upstream_url="http://127.0.0.1:9/v1"))
    assert "sk-operator-secret-value-9876" not in json.dumps(config)
    assert config["dummy_key"] == "relay-local-not-a-secret"


def test_read_live_credential_uses_stdin_only(driver, monkeypatch):
    import io

    monkeypatch.setattr(driver.sys, "stdin", io.StringIO("sk-from-stdin-123\n"))
    assert driver._read_live_credential() == "sk-from-stdin-123"


def test_read_live_credential_rejects_empty_or_whitespace(driver, monkeypatch):
    import io

    monkeypatch.setattr(driver.sys, "stdin", io.StringIO(""))
    with pytest.raises(driver.PreflightError, match="no key arrived"):
        driver._read_live_credential()
    monkeypatch.setattr(driver.sys, "stdin", io.StringIO("sk with space\n"))
    with pytest.raises(driver.PreflightError, match="whitespace"):
        driver._read_live_credential()


# ---------------------------------------------------------------------------
# Live question scoping (model prose is evidence, never a pass on its own)
# ---------------------------------------------------------------------------

def test_live_question_accepts_an_invoice_scoped_question(driver):
    assert driver._live_question_ok({
        "question": "Which file is the supplier invoice?",
        "concept": "invoice_reconciliation",
    })
    assert driver._live_question_ok({
        "question": "Please attach the missing paperwork.",
        "missing_roles": ["invoice"],
    })
    assert driver._live_question_ok({
        "question": "Which document carries INV-TRIGGER-91?"})


def test_live_question_rejects_empty_or_foreign_questions(driver):
    assert not driver._live_question_ok({})
    assert not driver._live_question_ok({"question": "   "})
    assert not driver._live_question_ok({
        "question": "Which warehouse should receive the shipment?",
        "concept": "goods_receipt",
    })


# ---------------------------------------------------------------------------
# Live episode assertions (ledger + isolation), without launching anything
# ---------------------------------------------------------------------------

def _live_scenario(driver, tmp_path, *, upstream_kind="synthetic_loopback"):
    scenario = {
        "kind": "browser_invoice_partial_evidence_scenario",
        "labels": driver._live_labels({"upstream_kind": upstream_kind}),
        "mode": "live_flash",
        "fixtures": {
            "expected_total": driver.EXPECTED_TOTAL,
            "po": {"po_id": driver.PO},
            "complete": {"invoice_id": driver.INVOICE},
        },
        "live": {"requested_pin": driver.LIVE_PIN},
    }
    live = {
        "provider": driver.LIVE_PROVIDER,
        "model": driver.LIVE_MODEL,
        "pin": driver.LIVE_PIN,
        "upstream_kind": upstream_kind,
        "live_upstream_enabled": upstream_kind == "trusted_live",
        "relay_port": 8117,
        "relay_ledger_path": str(tmp_path / "relay_ledger.jsonl"),
        "limits": dict(driver.LIVE_DEFAULTS),
    }
    db_path = tmp_path / "scratch_run.db"
    sqlite3 = __import__("sqlite3")
    con = sqlite3.connect(db_path)
    con.execute("create table goal_runs (id text primary key)")
    con.commit()
    con.close()
    return scenario, live, db_path


def _clean_ledger(driver, *, upstream_kind="synthetic_loopback"):
    return {
        "available": True,
        "budget": {
            "calls_started": 3,
            "calls_completed": 3,
            "input_tokens": 900,
            "output_tokens": 120,
            "charged_usd": 0.0005,
            "reserved_usd": 0.0,
            "usage_unknown_calls": 0,
            "models_probes": 1,
            "refusals": {"call_cap": 0, "spend_cap": 0, "wall_clock": 0,
                         "model_not_pinned": 0},
            "upstream_kind": upstream_kind,
            "live_upstream_enabled": upstream_kind == "trusted_live",
        },
        "entries": [
            {
                "seq": index,
                "operation": "chat.completions",
                "status": 200,
                "requested_model": driver.LIVE_MODEL,
                "served_model": driver.LIVE_MODEL,
                "usage": {"prompt_tokens": 300, "completion_tokens": 40},
                "usage_unknown": False,
                "cost_usd": 0.0001,
            }
            for index in (1, 2, 3)
        ],
    }


def _recording_step():
    failures = []

    def step(name, checks, details=None):
        failures.append((name, {k: v for k, v in checks.items() if not v}))

    return step, failures


def test_live_episode_assertions_pass_on_a_clean_ledger(driver, tmp_path,
                                                        monkeypatch):
    scenario, live, db_path = _live_scenario(driver, tmp_path)
    Path(live["relay_ledger_path"]).write_text("{}\n", encoding="utf-8")
    ledger = _clean_ledger(driver)
    monkeypatch.setattr(driver.D3.R, "fetch_relay_ledger",
                        lambda port: ledger)
    step, failures = _recording_step()
    assignment = {"steps": [
        {"adapter": "document.text", "status": "applied"},
        {"adapter": "invoice.reconcile", "status": "applied"},
    ]}
    driver._assert_live_episode(scenario, live, step, assignment,
                                db_path=db_path)
    assert failures and failures[0][1] == {}
    assert scenario["live"]["served_pin"] == driver.LIVE_PIN
    assert scenario["live"]["totals"]["calls"] == 3
    assert scenario["live"]["secrets_recorded"] is False
    assert len(scenario["relay_ledger"]) == 3


def test_live_episode_assertions_pass_on_a_clean_trusted_ledger(
        driver, tmp_path, monkeypatch):
    scenario, live, db_path = _live_scenario(
        driver, tmp_path, upstream_kind="trusted_live")
    Path(live["relay_ledger_path"]).write_text("{}\n", encoding="utf-8")
    ledger = _clean_ledger(driver, upstream_kind="trusted_live")
    monkeypatch.setattr(driver.D3.R, "fetch_relay_ledger",
                        lambda port: ledger)
    step, failures = _recording_step()
    driver._assert_live_episode(
        scenario, live, step,
        {"steps": [{"adapter": "invoice.reconcile", "status": "applied"}]},
        db_path=db_path)
    assert failures and failures[0][1] == {}
    assert scenario["live"]["secrets_recorded"] is False
    assert scenario["live"]["model_content_recorded"] is False
    assert scenario["live"]["credential_fields_recorded"] is False


@pytest.mark.parametrize("mutate, failing_check", [
    (lambda driver, ledger: ledger["entries"][0].update(
        served_model="gemini-3-flash"), "served_pin_only"),
    (lambda driver, ledger: ledger["entries"][0].update(
        requested_model="gpt-5"), "requested_pin_only"),
    (lambda driver, ledger: ledger["budget"].update(
        charged_usd=99.0), "spend_within_cap"),
    (lambda driver, ledger: ledger["budget"].update(
        calls_started=50), "calls_within_cap"),
    (lambda driver, ledger: ledger["budget"].update(
        live_upstream_enabled=True), "transport_state_matches"),
    (lambda driver, ledger: ledger["budget"].update(
        upstream_kind="trusted_live"), "transport_state_matches"),
    (lambda driver, ledger: ledger["budget"]["refusals"].update(
        call_cap=1), "no_budget_refusal"),
    (lambda driver, ledger: ledger["entries"][0].update(
        usage_unknown=True), "usage_measured"),
    (lambda driver, ledger: ledger["entries"][0].update(
        status=502), "every_call_succeeded"),
    (lambda driver, ledger: ledger["entries"][0].update(
        response_head="sk-live-secret-abcdef123456"),
     "no_secret_in_ledger"),
    (lambda driver, ledger: ledger["entries"][0].update(
        operation="models.list"), "every_call_is_chat_completions"),
    (lambda driver, ledger: ledger["budget"]["refusals"].update(
        model_not_pinned=1), "no_foreign_model_attempt"),
    (lambda driver, ledger: ledger["entries"][0].update(
        content="unique model text"), "no_model_content_in_ledger"),
    (lambda driver, ledger: ledger["entries"][0].update(
        api_key="sk-live-secret-abcdef123456"),
     "no_credential_fields_in_ledger"),
])
def test_live_episode_assertions_fail_closed(driver, tmp_path, monkeypatch,
                                             mutate, failing_check):
    scenario, live, db_path = _live_scenario(driver, tmp_path)
    Path(live["relay_ledger_path"]).write_text("{}\n", encoding="utf-8")
    ledger = _clean_ledger(driver)
    mutate(driver, ledger)
    monkeypatch.setattr(driver.D3.R, "fetch_relay_ledger",
                        lambda port: ledger)
    step, failures = _recording_step()
    driver._assert_live_episode(
        scenario, live, step,
        {"steps": [{"adapter": "document.text"}]}, db_path=db_path)
    assert failures[0][1].get(failing_check) is False


def test_live_episode_assertions_fail_on_an_outbound_adapter(
        driver, tmp_path, monkeypatch):
    scenario, live, db_path = _live_scenario(driver, tmp_path)
    Path(live["relay_ledger_path"]).write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(driver.D3.R, "fetch_relay_ledger",
                        lambda port: _clean_ledger(driver))
    step, failures = _recording_step()
    driver._assert_live_episode(scenario, live, step, {"steps": [
        {"adapter": "document.text"},
        {"adapter": "email.send", "status": "applied"},
    ]}, db_path=db_path)
    assert failures[0][1].get("no_outbound_or_send_adapter") is False


def test_foreign_model_refusal_is_not_budget_exhaustion(driver):
    assert driver._live_budget_exhausted(
        {"budget": {"refusals": {"model_not_pinned": 3}}}) is False
    assert driver._live_budget_exhausted(
        {"budget": {"refusals": {"call_cap": 1}}}) is True
    assert driver._live_budget_exhausted({"budget": {}}) is False


def test_live_branch_skips_the_provider_shim(driver):
    """Static tripwire: the live lane must never fall back to the shim."""
    source = DRIVER_PATH.read_text(encoding="utf-8")
    live_block = source.split("            # OPT-IN live replay", 1)[1]
    live_block = live_block.split("        cleanups.append(backend)", 1)[0]
    assert "launch_shim" not in live_block
    assert "launch_live_relay" in live_block
    assert 'provider_base_url_env="OPENCODE_BASE_URL"' in live_block
    assert 'provider_api_key_env="OPENCODE_API_KEY"' in live_block
    assert "_read_live_credential()" in live_block
    assert "upstream_api_key=relay_api_key" in live_block


def test_driver_never_discovers_a_credential_from_an_auth_file(driver):
    """The only credential read is the explicit stdin seam."""
    source = DRIVER_PATH.read_text(encoding="utf-8")
    for forbidden in ("auth.json", "load_dotenv", "dotenv"):
        assert forbidden not in source
    # No environment lookup of a provider key: the live key is stdin-only.
    assert 'os.environ.get("OPENCODE_API_KEY"' not in source
    assert 'os.getenv("OPENCODE_API_KEY"' not in source



# ---------------------------------------------------------------------------
# Regression: the default preflight report keeps its scripted shape
# ---------------------------------------------------------------------------

def test_default_preflight_report_is_unchanged(driver, tmp_path, monkeypatch):
    monkeypatch.delenv(driver.LIVE_ACK_ENV, raising=False)
    assert driver.main(["--preflight", "--out", str(tmp_path)]) == 0
    report = json.loads((tmp_path / "preflight.json").read_text())
    assert report["kind"] == "browser_invoice_partial_evidence_preflight"
    assert report["ok"] is True
    assert report["world_created"] is False
    assert report["browser_launched"] is False
    assert report["provider_contacted"] is False
    assert report["labels"] == driver.LABELS
    assert "SIMULATED MODEL DECISIONS" in report["labels"]["model_decisions"]
    assert len(report["shim"]["responses"]) == 5
    assert report["expected_total"] == "140.25"


def test_live_flags_are_rejected_on_the_preflight_path(
        driver, tmp_path, monkeypatch):
    monkeypatch.setenv(driver.LIVE_ACK_ENV, driver.LIVE_ACK_VALUE)
    monkeypatch.setattr(driver.D3, "_port_free", lambda port: True)
    code = driver.main([
        "--preflight", "--out", str(tmp_path / "out"),
        "--live-flash",
        "--live-upstream-url", "http://127.0.0.1:9/v1",
    ])
    assert code == 2
