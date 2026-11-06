import os, socket, subprocess, sys, time
from websockets.sync.client import connect

backend = sys.argv[1]
port = int(sys.argv[2])
log_path = sys.argv[3]
import hashlib, os, secrets
synthetic = os.environ.get("WS_SYNTHETIC_TOKEN") or ".".join(
    secrets.token_urlsafe(16) for _ in range(3))
print("synthetic_digest", hashlib.sha256(synthetic.encode()).hexdigest())
env = dict(os.environ)
env["PYTHONPATH"] = backend + os.pathsep + env.get("PYTHONPATH", "")
log = open(log_path, "wb")
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "ws_log_probe_app:app",
     "--host", "127.0.0.1", "--port", str(port), "--log-level", "info"],
    cwd="/private/tmp", env=env, stdout=log, stderr=subprocess.STDOUT)
try:
    for _ in range(80):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.25)
    for path in (f"/ws?token={synthetic}&api_key={synthetic}&x=1",
                 f"/ws/reject?token={synthetic}&x=1"):
        try:
            with connect(f"ws://127.0.0.1:{port}{path}", open_timeout=5) as ws:
                try:
                    ws.recv(timeout=1)
                except Exception:
                    pass
        except Exception:
            pass
    time.sleep(1)
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    log.close()
text = open(log_path, "r", encoding="utf-8", errors="replace").read()
print("log_bytes", len(text))
print("raw_synthetic_present", synthetic in text)
print("redacted_marker_count", text.count("<redacted>"))
print("ws_path_lines", sum(1 for line in text.splitlines() if "/ws" in line))
for line in text.splitlines():
    if "/ws" in line:
        print("WS_LINE", line[:260])
