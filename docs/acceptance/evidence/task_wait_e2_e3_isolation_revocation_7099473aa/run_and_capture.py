"""Run one evidence command, preserving stdout/stderr and actual exit code."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

cwd, log_path, exit_path = sys.argv[1:4]
argv = sys.argv[sys.argv.index("--") + 1:]
proc = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE,
                      stderr=subprocess.STDOUT)
Path(log_path).write_bytes(proc.stdout)
Path(exit_path).write_text(json.dumps({
    "argv": argv,
    "cwd": cwd,
    "actual_exit_code": proc.returncode,
}, indent=2, sort_keys=True) + "\n")
sys.stdout.buffer.write(proc.stdout)
raise SystemExit(proc.returncode)
