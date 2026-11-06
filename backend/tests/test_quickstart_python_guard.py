"""COMPAT-01 — quickstart interpreter guard.

The quickstart dependency set (torch>=2,<3 and compiled wheels) supports
CPython 3.11–3.13. The guard must accept that range and reject 3.14 with the
documented actionable message BEFORE creating a venv or installing anything.

The test drives the real ``scripts/quickstart.sh --check-python`` path with a
fake interpreter, so it covers the script's own guard wiring rather than a
copy of the predicate.
"""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SUPPORTED = ("3.11", "3.12", "3.13")
UNSUPPORTED = ("3.10", "3.14")


def _fake_python(tmp_path: Path, version: str) -> Path:
    """An executable that answers quickstart's two -c probes."""
    script = tmp_path / "fake-python"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'if [ "${1:-}" != "-c" ]; then echo "unexpected argv" >&2; exit 2; fi\n'
        'code="${2:-}"\n'
        'case "$code" in\n'
        "  *version_info.major*)\n"
        f'    echo "{version}"\n'
        "    exit 0\n"
        "    ;;\n"
        "  *assert*)\n"
        f'    case "{version}" in\n'
        "      3.11|3.12|3.13) exit 0 ;;\n"
        "      *) exit 1 ;;\n"
        "    esac\n"
        "    ;;\n"
        "  *)\n"
        '    echo "unexpected -c payload" >&2\n'
        "    exit 2\n"
        "    ;;\n"
        "esac\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def _run_guard(fake_python: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHON"] = str(fake_python)
    return subprocess.run(
        ["bash", "scripts/quickstart.sh", "--check-python"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.parametrize("version", SUPPORTED)
def test_quickstart_accepts_supported_python(version, tmp_path):
    result = _run_guard(_fake_python(tmp_path, version))
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert f"✅ Python {version}" in output
    # --check-python must be side-effect free: no venv/dependency phase.
    assert "📦 Setting up backend" not in output


@pytest.mark.parametrize("version", UNSUPPORTED)
def test_quickstart_rejects_unsupported_python_with_actionable_message(
        version, tmp_path):
    result = _run_guard(_fake_python(tmp_path, version))
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "❌ Python 3.11–3.13 required" in output
    assert f"found {version}" in output
    assert "torch<3 publishes no wheels for 3.14." in output
    assert "python3.11 -m venv backend/venv" in output
    assert "📦 Setting up backend" not in output
