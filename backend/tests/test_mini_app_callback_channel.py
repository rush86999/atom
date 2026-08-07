"""Mini-app host-callback channel — guest fetch_integration + host _exchange loop.

WS2 contract: guest logic can call ``fetch_integration(service, action, params)``
mid-run; the host services it over the vsock socket (credentials resolved
host-side, scope-gated, tokens never reach the guest). All FC execution is
mocked — no real VM in CI.
"""
import asyncio
import json

import pytest

from core.sandbox_runtime.firecracker_guest import agent as guest_agent


# ---------------------------------------------------------------------------
# Guest agent: fetch_integration helper
# ---------------------------------------------------------------------------
class TestGuestFetchIntegration:
    def test_fetch_returns_host_result(self):
        """A fake bidirectional file that replies with a callback_result."""
        import io

        class FakeFile:
            def __init__(self, replies):
                self._in = io.StringIO("".join(replies))
                self.written = []

            def write(self, s):
                self.written.append(s)

            def flush(self):
                pass

            def readline(self):
                return self._in.readline()

        reply = json.dumps({"type": "callback_result", "ok": True, "data": {"pages": [1]}}) + "\n"
        f = FakeFile([reply])
        fetch = guest_agent.make_fetch_integration(f)
        result = fetch("notion", "search", {"query": "x"})
        assert result == {"pages": [1]}
        # the request was written as a callback line
        req = json.loads(f.written[0])
        assert req["type"] == "callback" and req["kind"] == "fetch_integration"
        assert req["service"] == "notion" and req["action"] == "search"

    def test_fetch_raises_on_host_error(self):
        import io

        class FakeFile:
            def __init__(self, reply):
                self._in = io.StringIO(reply)
                self.written = []

            def write(self, s):
                self.written.append(s)

            def flush(self):
                pass

            def readline(self):
                return self._in.readline()

        reply = json.dumps({"type": "callback_result", "ok": False, "error": "scope_denied"}) + "\n"
        fetch = guest_agent.make_fetch_integration(FakeFile(reply))
        with pytest.raises(RuntimeError, match="scope_denied"):
            fetch("notion", "search", {})

    def test_fetch_raises_on_closed_channel(self):
        import io

        class FakeFile:
            def write(self, s):
                pass

            def flush(self):
                pass

            def readline(self):
                return ""  # host closed

        fetch = guest_agent.make_fetch_integration(FakeFile())
        with pytest.raises(RuntimeError, match="closed the channel"):
            fetch("notion", "search", {})

    def test_run_code_injects_fetch_into_globals(self):
        """run_code with a fetch_integration callable makes it callable in user code."""
        import io

        class FakeFile:
            def __init__(self, reply):
                self._in = io.StringIO(reply)
                self.written = []

            def write(self, s):
                self.written.append(s)

            def flush(self):
                pass

            def readline(self):
                return self._in.readline()

        reply = json.dumps({"type": "callback_result", "ok": True, "data": {"n": 5}}) + "\n"
        fetch = guest_agent.make_fetch_integration(FakeFile(reply))
        code = "result = fetch_integration('hubspot', 'list_contacts', {})\nstate = {'count': result['n']}"
        res = guest_agent.run_code(code, {"state": {}}, fetch_integration=fetch)
        assert res["state_envelope"]["state"] == {"count": 5}


# ---------------------------------------------------------------------------
# Host runner: _exchange callback loop
# ---------------------------------------------------------------------------
class TestHostExchangeLoop:
    def test_services_callback_then_final(self, monkeypatch, tmp_path):
        """_exchange sends exec, services a callback request, receives final."""
        from core import sandbox_config
        from core.sandbox_runtime import firecracker_runner as fr

        # Build a UDS server that: reads exec line, sends a callback line,
        # reads the callback_result, sends a final line.
        import socket, threading, os, tempfile

        # AF_UNIX paths are capped at ~104 chars on macOS; pytest's tmp_path
        # exceeds that. Use /tmp directly.
        sock_path = tempfile.mkdtemp(dir="/tmp", prefix="cb-") + "/cb.sock"

        def server():
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            srv.bind(sock_path)
            srv.listen(1)
            conn, _ = srv.accept()
            f = conn.makefile("rw")
            f.readline()  # read exec
            f.write(json.dumps({"type": "callback", "kind": "fetch_integration",
                                "service": "notion", "action": "search", "params": {}}) + "\n")
            f.flush()
            f.readline()  # read callback_result
            f.write(json.dumps({"type": "final", "stdout": "", "stderr": "", "exit_code": 0,
                                "state_envelope": {"state": {}, "storage_ops": [], "record_ops": []}}) + "\n")
            f.flush()
            conn.close()
            srv.close()

        t = threading.Thread(target=server, daemon=True)
        t.start()

        # Wait for the socket to exist (simulate the boot-poll)
        import time
        for _ in range(100):
            if os.path.exists(sock_path):
                break
            time.sleep(0.01)

        monkeypatch.setattr(sandbox_config, "get_sandbox_vm_boot_timeout_seconds", lambda: 5)
        runtime = fr.FirecrackerRuntime()

        served = []

        async def cb_handler(req):
            served.append(req)
            return {"ok": True, "data": {"pages": [1, 2]}}

        loop = asyncio.new_event_loop()
        stdout, stderr, exit_code, envelope, callbacks = loop.run_until_complete(
            runtime._exchange("x=1", {}, sock_path, cb_handler)
        )
        loop.close()
        assert exit_code == 0
        assert served[0]["service"] == "notion"
        assert len(callbacks) == 1 and callbacks[0]["ok"] is True
        assert callbacks[0]["service"] == "notion"

    def test_no_handler_returns_callbacks_disabled(self, monkeypatch, tmp_path):
        """When no callback_handler is configured, the guest gets callbacks_disabled."""
        from core import sandbox_config
        from core.sandbox_runtime import firecracker_runner as fr
        import socket, threading, os, time, tempfile

        sock_path = tempfile.mkdtemp(dir="/tmp", prefix="ncb-") + "/nocb.sock"

        def server():
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            srv.bind(sock_path)
            srv.listen(1)
            conn, _ = srv.accept()
            f = conn.makefile("rw")
            f.readline()
            f.write(json.dumps({"type": "callback", "kind": "fetch_integration",
                                "service": "x", "action": "y", "params": {}}) + "\n")
            f.flush()
            f.readline()  # consume the disabled reply
            f.write(json.dumps({"type": "final", "stdout": "", "stderr": "", "exit_code": 0}) + "\n")
            f.flush()
            conn.close()
            srv.close()

        threading.Thread(target=server, daemon=True).start()
        for _ in range(100):
            if os.path.exists(sock_path):
                break
            time.sleep(0.01)

        monkeypatch.setattr(sandbox_config, "get_sandbox_vm_boot_timeout_seconds", lambda: 5)
        runtime = fr.FirecrackerRuntime()
        loop = asyncio.new_event_loop()
        _, _, _, _, callbacks = loop.run_until_complete(
            runtime._exchange("x=1", {}, sock_path, None)  # no handler
        )
        loop.close()
        assert callbacks[0]["ok"] is False
        assert callbacks[0]["error"] == "callbacks_disabled"


# ---------------------------------------------------------------------------
# run_stateful end-to-end: fetch_integration reaches the host handler
# ---------------------------------------------------------------------------
class TestRunStatefulCallback:
    @pytest.mark.asyncio
    async def test_fetch_integration_in_logic(self, db_session, monkeypatch, tmp_path):
        """A logic body that calls fetch_integration gets the host-served result."""
        import contextlib, uuid
        from core.models import Canvas, CanvasLogic, CanvasState, MiniApp
        import core.mini_app_service as svc

        cid = f"c-{uuid.uuid4().hex[:10]}"
        aid = f"app-{uuid.uuid4().hex[:10]}"
        db_session.add(MiniApp(id=aid, tenant_id="t1", created_by="u1", name="t",
                               manifest={"declared_scopes": ["*"]}))
        db_session.add(Canvas(id=cid, tenant_id="t1", created_by="u1", name="i",
                              canvas_type="mini_app", content={}, style={}, status="active", mini_app_id=aid))
        db_session.add(CanvasLogic(canvas_id=cid, language="python",
                                   source="data = fetch_integration('notion','search',{'q':'x'})\nstate = {'r': data}",
                                   created_by="u1"))
        db_session.add(CanvasState(canvas_id=cid, tenant_id="t1", state={}, version=1))
        db_session.commit()

        @contextlib.contextmanager
        def _cm():
            yield db_session
        monkeypatch.setattr("core.database.get_db_session", _cm)

        captured = {}

        class FakeRuntime:
            async def execute_python(self, code, *, policy=None, inputs=None, cwd=None,
                                     image=None, callback_handler=None, **kw):
                # The fake simulates the host side: call fetch_integration via
                # the handler, then return the resulting state.
                handler = callback_handler
                if handler is not None:
                    res = await handler({"kind": "fetch_integration", "service": "notion",
                                         "action": "search", "params": {"q": "x"}})
                    captured["handler_result"] = res
                return type("R", (), {
                    "success": True, "exit_code": 0, "stderr": "",
                    "stdout": "__MINIAPP_STATE__:" + json.dumps({"state": {"r": {"pages": [1]}, "n": 2}, "storage_ops": [], "record_ops": []}),
                    "metadata": {"callbacks": [{"kind": "fetch_integration", "service": "notion", "ok": True}]},
                    "truncated": False,
                })()

        monkeypatch.setattr(svc, "get_miniapp_runtime", FakeRuntime)

        # Mock the unified dispatcher so no real integration is contacted.
        async def fake_dispatch(service, action, params, *, tenant_id, db):
            return {"ok": True, "data": {"pages": [1]}, "backend": "native"}
        monkeypatch.setattr("core.mini_app_integration_dispatch.dispatch", fake_dispatch)

        result = await svc.run_stateful(cid, user_id="u1", scopes=("*",))
        assert result["success"]
        assert result["callbacks"] == [{"kind": "fetch_integration", "service": "notion", "ok": True}]
        assert captured["handler_result"]["ok"] is True

    @pytest.mark.asyncio
    async def test_scope_gate_denies_unauthorized_service(self, db_session, monkeypatch):
        """Without 'integrations.notion' or '*' in scopes, the handler denies."""
        import core.mini_app_service as svc
        handler = svc._make_callback_handler(
            db_session, "t1", ("canvas_render",), None, None  # no integration scope
        )
        result = await handler({"kind": "fetch_integration", "service": "notion",
                                "action": "search", "params": {}})
        assert result["ok"] is False and result["error"] == "scope_denied"
