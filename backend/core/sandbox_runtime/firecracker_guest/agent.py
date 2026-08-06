#!/usr/bin/env python3
"""Firecracker mini-app guest agent (PID 1, runs inside the microVM).

Baked into every mini-app rootfs by ``scripts/build_miniapp_rootfs.sh`` and
launched by the kernel via boot_args ``init=/opt/atom-guest/agent.py``. Runs
as PID 1 (the rootfs has no init system) and must therefore tolerate being
the init process — it never exits until the host kills the VM.

Protocol (vsock command channel, multiplexed):
  1. Connect ``AF_VSOCK, SOCK_STREAM`` to host CID 2 on ``miniapp_port``
     (parsed from ``/proc/cmdline``; default 5050). The host side listens on
     a Unix domain socket configured in Firecracker's ``vsock`` block.
  2. Receive one JSON line: ``{"type":"exec", "code": str, "inputs": dict}``.
  3. Execute ``code`` with ``inputs`` injected as exec globals, capturing
     stdout/stderr. A ``fetch_integration(service, action, params)`` helper is
     injected into globals so user code can make CONDITIONAL mid-run
     integration calls: each call writes a
     ``{"type":"callback","kind":"fetch_integration",...}`` line and blocks on
     the host's ``{"type":"callback_result",...}`` reply (0..N times).
  4. Reply with one terminal JSON line:
     ``{"type":"final", "stdout", "stderr", "exit_code", "state_envelope"}``.
     ``state_envelope`` carries ``{"state", "storage_ops", "record_ops"}``
     extracted from the exec globals after the run, so mini-app state is
     returned over the vsock reply channel (immune to the host's 64 KiB stdout
     cap) rather than parsed out of stdout. ``state_envelope`` is omitted when
     no ``state`` global is present (non-mini-app callers).
  5. Sleep (host tears the VM down).

The guest has NO host filesystem and NO network — all storage and integration
I/O is host-mediated via ``storage_ops`` / ``record_ops`` / the callback channel.
"""
from __future__ import annotations

import io
import json
import os
import socket
import sys


HOST_CID = 2
DEFAULT_PORT = 5050


def parse_miniapp_port() -> int:
    """Read ``miniapp_port=<N>`` from /proc/cmdline (boot_args set it)."""
    try:
        with open("/proc/cmdline", "r", encoding="utf-8") as f:
            cmdline = f.read()
        for token in cmdline.split():
            if token.startswith("miniapp_port="):
                return int(token.split("=", 1)[1])
    except Exception:  # noqa: BLE001
        pass
    return DEFAULT_PORT


def connect_vsock(port: int) -> socket.socket:
    """Open a vsock connection to the host on ``port`` (blocking)."""
    try:
        sock = socket.socket(socket.AF_VSOCK, socket.SOCK_STREAM)
    except AttributeError:  # AF_VSOCK unavailable (non-Linux guest / tests)
        raise RuntimeError("AF_VSOCK is not available on this system")
    sock.settimeout(10)
    sock.connect((HOST_CID, port))
    return sock


def make_fetch_integration(rw_file):
    """Build a ``fetch_integration(service, action, params)`` helper bound to a
    bidirectional socket file object.

    When called by user code mid-``exec``, it writes a callback request line
    and BLOCKS on ``readline()`` for the host's reply. User code is already
    blocking inside ``exec``, so this synchronous round-trip is natural. The
    host services the request via ``ExternalIntegrationService`` (credentials
    resolved host-side; tokens never reach the guest) and writes back the
    result payload. Returns the ``data`` payload on success; raises
    ``RuntimeError`` on host error/timeout so user code can react.
    """

    def fetch_integration(service: str, action: str, params: dict = None):
        req = json.dumps({
            "type": "callback",
            "kind": "fetch_integration",
            "service": str(service),
            "action": str(action),
            "params": params or {},
        }) + "\n"
        rw_file.write(req)
        rw_file.flush()
        reply_line = rw_file.readline()
        if not reply_line:
            raise RuntimeError("integration callback: host closed the channel")
        try:
            reply = json.loads(reply_line)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"integration callback: malformed reply ({e})")
        if not reply.get("ok"):
            raise RuntimeError(
                f"integration call {service}.{action} failed: {reply.get('error', 'unknown')}"
            )
        return reply.get("data")

    return fetch_integration


def run_code(code: str, inputs: dict, fetch_integration=None) -> dict:
    """Execute ``code`` with ``inputs`` as globals; capture stdout/stderr.

    Exposed as a pure-ish function so the harness logic can be unit-tested
    without a microVM (see ``tests/test_mini_app_runtime.py``).

    ``fetch_integration`` (optional callable) is injected into exec globals so
    user code can call ``fetch_integration(service, action, params)`` to make
    conditional mid-run integration requests over the vsock callback channel.

    If the executed code leaves a ``state`` global in scope, it is returned as
    a ``state_envelope`` (with any ``storage_ops`` list) so mini-app state
    round-trips over the vsock reply channel rather than via stdout.
    """
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    g: dict = {"__name__": "__main__"}
    if fetch_integration is not None:
        g["fetch_integration"] = fetch_integration
    g.update(inputs or {})

    try:
        compiled = compile(code, "<miniapp>", "exec")
        real_stdout, real_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = stdout_buf, stderr_buf
        exit_code = 0
        try:
            exec(compiled, g)  # noqa: S102 - this is the intended sandboxed host
        except SystemExit as e:
            exit_code = int(e.code) if e.code is not None else 0
        except BaseException as e:  # noqa: BLE001 - capture traceback into stderr
            import traceback

            traceback.print_exc(file=stderr_buf)
            exit_code = 1
        finally:
            sys.stdout, sys.stderr = real_stdout, real_stderr
    except (SyntaxError, ValueError) as e:
        stderr_buf.write(f"{type(e).__name__}: {e}\n")
        exit_code = 1

    result = {
        "stdout": stdout_buf.getvalue(),
        "stderr": stderr_buf.getvalue(),
        "exit_code": exit_code,
    }

    # Extract the mini-app state envelope from globals (if present). Carrying
    # it in the structured reply avoids the 64 KiB stdout truncation that would
    # corrupt large state objects parsed from a __MINIAPP_STATE__ line.
    if "state" in g:
        try:
            envelope = {"state": g["state"]}
            ops = g.get("storage_ops", [])
            envelope["storage_ops"] = list(ops) if isinstance(ops, list) else []
            # record_ops: structured-data CRUD proposals (host-validated, host-
            # executed against CanvasRecord). Mirrors storage_ops harvesting.
            rec_ops = g.get("record_ops", [])
            envelope["record_ops"] = list(rec_ops) if isinstance(rec_ops, list) else []
            # Serialize to verify the envelope is JSON-encodable (state may
            # contain non-serializable objects, e.g. a pandas DataFrame — in
            # that case we drop the envelope and let stdout carry a marker).
            json.dumps(envelope)
            result["state_envelope"] = envelope
        except (TypeError, ValueError):
            # Fall back: leave it out; the host will look for a stdout marker.
            pass
    return result


def main() -> int:
    port = parse_miniapp_port()
    sock = connect_vsock(port)

    # Bidirectional line protocol over the SAME socket: read the exec request,
    # then (during run_code) the helper writes callback requests + reads
    # replies on the same file object. The socket stays open until the final
    # reply is sent — DO NOT close it early or callbacks will fail.
    rw = sock.makefile("rw", encoding="utf-8", buffering=1)
    line = rw.readline()
    if not line:
        sock.close()
        return 1

    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        rw.write(json.dumps({"type": "final", "stdout": "", "stderr": "malformed request", "exit_code": 1}) + "\n")
        rw.flush()
        sock.close()
        return 1

    # Inject the callback helper so user code can call
    # fetch_integration(service, action, params) mid-run.
    fetch = make_fetch_integration(rw)
    result = run_code(str(msg.get("code", "")), msg.get("inputs") or {}, fetch_integration=fetch)
    result["type"] = "final"  # tag the terminal reply (host breaks its loop on this)
    rw.write(json.dumps(result) + "\n")
    rw.flush()
    sock.close()

    # Never exit — the host kills the VM. Sleeping keeps PID 1 alive so the
    # kernel doesn't panic on init exit.
    import time

    while True:
        time.sleep(3600)
    return 0


if __name__ == "__main__":
    sys.exit(main())
