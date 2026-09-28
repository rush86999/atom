"""Isolated-acceptance server launcher.

Run as a plain script (cmdline contains neither 'uvicorn' nor
'main_api_app:app'), so scripts/restart_backend.sh's
`pkill -f "uvicorn main_api_app:app"` — which matches by full command line
regardless of port — cannot sweep the isolated acceptance server when
another stream restarts the live backend.
"""
import os
import sys

sys.path.insert(0, os.getcwd())  # farm root must be importable when run as a script

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main_api_app:app",
        host="127.0.0.1",
        port=int(os.environ["ACC_PORT"]),
        timeout_keep_alive=75,
    )
