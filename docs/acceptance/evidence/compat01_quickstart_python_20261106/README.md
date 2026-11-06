# COMPAT-01 — quickstart Python guard evidence

Claim: **Python 3.11+** / supported interpreter range.
Acceptance: 3.11–3.13 accepted; 3.14 rejected with the documented message.

Source checkpoint: `bad2f9596`
Base: merged main `d860072a7`

## What changed

`scripts/quickstart.sh` already rejected CPython outside 3.11–3.13 before
dependency installation. The guard was not independently testable without
running the full setup.

Added a side-effect-free `--check-python` mode:

- validates only the interpreter guard;
- exits before prerequisite checks, venv creation and `pip install`;
- uses an explicitly named `PYTHON` first in check-only mode, so an unrelated
  existing `backend/venv` cannot shadow the interpreter under test;
- default quickstart behavior is unchanged.

`backend/tests/test_quickstart_python_guard.py` drives the real script through
a fake interpreter and covers both sides:

| Version | Expected |
|---|---|
| 3.11, 3.12, 3.13 | accepted, `✅ Python <version>` |
| 3.10, 3.14 | rejected, exit 1, documented `torch<3` message |

Each case also asserts `📦 Setting up backend` is absent, proving the check
mode did not create a venv or install dependencies.

## Commands and results

New controls:

```sh
cd backend
PYTHONPATH=$PWD python3.11 -B -m pytest \
  tests/test_quickstart_python_guard.py -q --tb=short
# 5 passed
```

Real interpreter boundaries:

```sh
PYTHON=$(command -v python3.11) bash scripts/quickstart.sh --check-python
# ✅ Python 3.11 (/usr/local/bin/python3.11), exit 0

PYTHON=/Users/rushiparikh/projects/atom/backend/venv314/bin/python \
  bash scripts/quickstart.sh --check-python
# ❌ Python 3.11–3.13 required (found 3.14 ...), exit 1
```

Updated CI backend selection (33 files, guard test added):

| Interpreter | Result |
|---|---|
| Python 3.11.16 | **611 passed, 1 skipped, 0 failed** |
| Python 3.14.7 | **611 passed, 1 skipped, 0 failed** |

Logs: `guard-tests-311.log`, `real-python-311.log`, `real-python-314.log`,
`ci-selection-311.log`, `ci-selection-314.log`.

## Boundaries

- 3.12/3.13 are exercised through the fake-interpreter controls; only 3.11
  and 3.14 are installed in this environment. The guard is a range predicate,
  so the boundary cases are the decisive real-interpreter checks.
- No dependency installation, venv creation, live model/provider, credential,
  spend, send, download or deployment operation was used.
- Default quickstart behavior and the documented supported range are
  unchanged.

## Source hashes

| File | Git blob | SHA-256 |
|---|---|---|
| `scripts/quickstart.sh` | `7a2530bbc17e62d6ec16f0c27134cb0747bf2d06` | `740381e79b0bf9fa2387c74082ac081c72197e0a678e1e95045125567a9e7781` |
| `backend/tests/test_quickstart_python_guard.py` | `5db181c765504d2d0781437b764685d2ec1c5fb8` | `e54a38b72fbb2996579c085ee41c7daf728c5bb34f616d9820a1dd59f480a791` |
| `.github/workflows/ci.yml` | `44d072c082505e025e80d298d944f800b068bdf1` | `816843c05a72f4a7b2f0fc1071b12ee0016b6b03b4593b9b98463076e45ee9af` |

Artifact hashes are in `verification.json`.
