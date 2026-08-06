#!/usr/bin/env python3
"""Firecracker mini-app guest agent (PID 1, runs inside the microVM).

Baked into every mini-app rootfs by ``scripts/build_miniapp_rootfs.sh`` and
launched by the kernel via boot_args ``init=/opt/atom-guest/agent.py``. Runs
as PID 1 (the rootfs has no init system) and must therefore tolerate being
the init process — it never exits until the host kills the VM.

Protocol (vsock command channel):
  1. Connect ``AF_VSOCK, SOCK_STREAM`` to host CID 2 on ``miniapp_port``
     (parsed from ``/proc/cmdline``; default 5050). The host side listens on
     a Unix domain socket configured in Firecracker's ``vsock`` block.
  2. Receive one JSON line: ``{"code": str, "inputs": dict}``.
  3. Execute ``code`` with ``inputs`` injected as exec globals, capturing
     stdout/stderr.
  4. Reply with one JSON line:
     ``{"stdout", "stderr", "exit_code", "state_envelope"}``. The
     ``state_envelope`` carries ``{"state", "storage_ops"}`` extracted from the
     exec globals after the run, so mini-app state is returned over the vsock
     reply channel (immune to the host's 64 KiB stdout cap) rather than parsed
     out of stdout. ``state_envelope`` is omitted when no ``state`` global is
     present (non-mini-app callers).
  5. Sleep (host tears the VM down).

The guest has NO host filesystem and NO network — all storage is host-mediated
via ``storage_ops`` parsed by the host from the envelope.
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


def run_code(code: str, inputs: dict) -> dict:
    """Execute ``code`` with ``inputs`` as globals; capture stdout/stderr.

    Exposed as a pure-ish function so the harness logic can be unit-tested
    without a microVM (see ``tests/test_mini_app_runtime.py``).

    If the executed code leaves a ``state`` global in scope, it is returned as
    a ``state_envelope`` (with any ``storage_ops`` list) so mini-app state
    round-trips over the vsock reply channel rather than via stdout.
    """
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    g: dict = {"__name__": "__main__"}
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

    # Receive one line of JSON (the host sends exactly one command per VM).
    line = sock.makefile("r", encoding="utf-8").readline()
    if not line:
        sock.close()
        return 1

    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        sock.sendall((json.dumps({"stdout": "", "stderr": "malformed request", "exit_code": 1}) + "\n").encode("utf-8"))
        sock.close()
        return 1

    result = run_code(str(msg.get("code", "")), msg.get("inputs") or {})
    payload = json.dumps(result) + "\n"
    sock.sendall(payload.encode("utf-8"))
    sock.close()

    # Never exit — the host kills the VM. Sleeping keeps PID 1 alive so the
    # kernel doesn't panic on init exit.
    import time

    while True:
        time.sleep(3600)
    return 0


if __name__ == "__main__":
    sys.exit(main())
