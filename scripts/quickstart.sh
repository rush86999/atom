#!/usr/bin/env bash
set -euo pipefail

# Atom Quick Start Script
# Run: ./scripts/quickstart.sh   (or: make setup)
# Sets up a complete Atom dev environment from scratch.

cd "$(dirname "$0")/.."

# `--check-python` validates only the interpreter guard and exits before any
# prerequisite, venv or dependency work. This is the side-effect-free way to
# verify the supported CPython range on a host or in CI.
CHECK_PYTHON_ONLY=0
if [ "${1:-}" = "--check-python" ]; then
    CHECK_PYTHON_ONLY=1
fi

echo "🚀 Atom Quick Start"
echo "===================="

if [ "$CHECK_PYTHON_ONLY" -eq 0 ]; then
    # Check prerequisites
    for cmd in python3 node npm git make; do
        command -v "$cmd" >/dev/null 2>&1 || { echo "❌ '$cmd' is required but not installed"; exit 1; }
    done

    # Node >= 20.9 is required by Next.js 16 (the frontend framework).
    if [ "$(node -e 'const [ma,mi]=process.versions.node.split(".").map(Number); console.log(ma>20||(ma===20&&mi>=9)?1:0)')" != "1" ]; then
        echo "❌ Node.js 20.9+ required (found $(node --version))"
        exit 1
    fi
    echo "✅ Node $(node --version)"
fi

# Supported interpreter range (F1, Phase D 2026-10-17): the dependency set
# (torch>=2,<3 and the compiled wheels it pulls) publishes distributions for
# CPython 3.11–3.13. CI and both Dockerfiles pin 3.11. The old `>=3.11` guard
# accepted this host's Python 3.14 and dead-ended inside pip with
# "No matching distribution found for torch<3.0.0" — reject an unsupported
# interpreter up front instead of failing deep in the dependency install.
#
# The guard validates the interpreter this run will ACTUALLY use: an existing
# backend/venv (the documented manual path creates it with python3.11) wins,
# then an explicit `PYTHON=python3.12` override, then the system python3.
# Validating only the system python3 made the documented manual path unusable
# (a correct 3.11 venv was refused because the host default was 3.14).
PY_BIN=""
if [ "$CHECK_PYTHON_ONLY" -eq 1 ] && [ -n "${PYTHON:-}" ] && command -v "$PYTHON" >/dev/null 2>&1; then
    # A check-only invocation validates the interpreter the caller named,
    # not an unrelated existing backend/venv.
    PY_BIN="$PYTHON"
elif [ -x "backend/venv/bin/python" ]; then
    PY_BIN="backend/venv/bin/python"
elif [ -n "${PYTHON:-}" ] && command -v "$PYTHON" >/dev/null 2>&1; then
    PY_BIN="$PYTHON"
else
    PY_BIN="python3"
fi
PY_VERSION=$("$PY_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if "$PY_BIN" -c 'import sys; assert (3,11) <= sys.version_info[:2] <= (3,13)' 2>/dev/null; then
    echo "✅ Python $PY_VERSION ($PY_BIN)"
    if [ "$CHECK_PYTHON_ONLY" -eq 1 ]; then
        exit 0
    fi
else
    echo "❌ Python 3.11–3.13 required (found $PY_VERSION via $PY_BIN)."
    echo "   torch<3 publishes no wheels for 3.14. Create the venv with a"
    echo "   supported interpreter and re-run:"
    echo "     python3.11 -m venv backend/venv && bash scripts/quickstart.sh"
    echo "   (or select one explicitly: PYTHON=python3.11 bash scripts/quickstart.sh)"
    exit 1
fi

# --- Backend setup ---
echo ""
echo "📦 Setting up backend..."

if [ ! -d "backend/venv" ]; then
    "$PY_BIN" -m venv backend/venv
fi
# Activate the venv — Python's venv module uses bin/ on POSIX and Scripts/
# on Windows. Both must work so the Makefile's Git-Bash-on-Windows path is
# unblocked without breaking Linux/macOS CI.
if [ -f "backend/venv/Scripts/activate" ]; then
    # shellcheck disable=SC1091
    source backend/venv/Scripts/activate
else
    # shellcheck disable=SC1091
    source backend/venv/bin/activate
fi
# --prefer-binary (F2, Phase D 2026-10-17): some in-range releases publish an
# sdist but no wheel for this platform (cryptography 49.0.0 on Intel macOS);
# plain pip prefers the newest version and then runs a Rust metadata build,
# which dead-ends on hosts without a working Rust toolchain. Prefer-binary
# keeps the range's security floor intact while selecting the newest
# WHEEL-BEARING release where one exists; pure-Python sdists (e.g.
# python-docx) still install normally.
pip install -q --prefer-binary -r backend/requirements.txt
echo "✅ Backend dependencies installed"

# --- Generate .env if missing ---
if [ ! -f "backend/.env" ]; then
    echo ""
    echo "🔧 Generating .env with secure defaults..."

    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    # BYOK vault key must be a VALID FERNET key (44-char base64 = 32 bytes,
    # padded). secrets.token_urlsafe(32) is 43 chars and cryptography REJECTS
    # it — found live 2026-10-11: with a quickstart-generated key, every
    # Settings→AI key store call failed (encrypt_api_key raised), so BYOK
    # was silently unusable on fresh installs (journey J2 evidence).
    BYOK_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

    # Write to an owner-only temp file in backend/ (same directory, hence same
    # filesystem) and publish it with a no-replace hard link at the exact
    # destination. link(2) is atomic, so backend/.env either appears with the
    # complete content or does not appear at all. A failed or partial write
    # therefore only ever exists in the temp file, which the EXIT trap removes.
    # A file that appears concurrently (another quickstart, restored backup,
    # symlink) is preserved instead of being truncated. The umask and traps are
    # scoped to this subshell and never leak to the caller.
    if (
        umask 077
        tmp_env=""
        cleanup_env() {
            [ -z "$tmp_env" ] || rm -f "$tmp_env"
        }
        trap cleanup_env EXIT
        trap 'exit 1' HUP INT TERM

        # mktemp creates in backend/ itself: a temp in TMPDIR could live on a
        # different filesystem, where publication would not be atomic.
        tmp_env=$(mktemp "backend/.env.tmp.XXXXXX") || exit 1
        chmod 600 "$tmp_env" || exit 1

        if ! cat > "$tmp_env" <<EOF
# Auto-generated by quickstart.sh
SECRET_KEY=$SECRET_KEY
JWT_SECRET_KEY=$JWT_SECRET
BYOK_ENCRYPTION_KEY=$BYOK_KEY
DATABASE_URL=sqlite:///./atom_dev.db
ENVIRONMENT=development

# Chat execution contract (verified paths require these). The value must be
# exactly 1 — readers compare == "1", so true/yes DO NOT enable (see
# backend/.env.example §6). Without them a fresh install runs the legacy
# path: no exact-execution failure reporting (M1), no finalized-outcome
# persistence (M2), no durable task lifecycle (task correction).
CHAT_FINALIZATION_M1=1
CHAT_FINALIZATION_M2=1
ATOM_TASK_LIFECYCLE_ENABLED=1

# Core release configuration. The verified release serves the non-streaming
# reply path; streaming remains outside the current release claim. The
# orchestrator enables the stream leg only for the literal "true".
ATOM_CHAT_STREAMING=false

# Add your LLM API key here (at least one required for AI features):
# OPENAI_API_KEY=sk-your-key-here
# ANTHROPIC_API_KEY=sk-ant-your-key-here
# DEEPSEEK_API_KEY=sk-your-key-here

# Or use a local model (no API key needed):
# ATOM_LOCAL_ONLY=true
# OLLAMA_BASE_URL=http://localhost:11434/v1
EOF
        then
            exit 1
        fi
        # A short write can still exit 0 with some writers. The final heredoc
        # line is the completion sentinel, so a truncated config is never
        # published even if the writer did not report an error.
        if ! grep -qx '# OLLAMA_BASE_URL=http://localhost:11434/v1' "$tmp_env"; then
            exit 1
        fi

        # No-replace publication through Python's os.link, which targets this
        # exact path. Shell `ln` (like cp/mv) treats an existing directory as a
        # parent and would create backend/.env/<temp> — a nested write when
        # backend/.env is a stray directory. os.link fails instead, so nothing
        # is ever written inside it. link(2) also fails with EEXIST rather than
        # truncating an existing backend/.env.
        if "$PY_BIN" - "$tmp_env" backend/.env <<'PY'
import os
import sys

try:
    os.link(sys.argv[1], sys.argv[2])
except OSError:
    # The shell inspects the destination below: an existing file/symlink is a
    # lost race, a directory or anything else is a hard failure. The expected
    # no-replace rejection is not a traceback-worthy error.
    sys.exit(1)
PY
        then
            # The published name keeps the inode; the temp name is only a
            # second link to it. Cleanup is best-effort because publication
            # already succeeded.
            if rm -f "$tmp_env"; then
                tmp_env=""
            fi
            exit 0
        fi
        # No nested write happened above. A regular file or symlink is a lost
        # race with a complete concurrent writer and must stay untouched; any
        # other outcome (including a directory at backend/.env) is a failure.
        if [ -f "backend/.env" ] || [ -L "backend/.env" ]; then
            exit 2
        fi
        exit 1
    ); then
        echo "✅ Generated backend/.env"
        echo "⚠️  Edit backend/.env to add your API key, or set ATOM_LOCAL_ONLY=true for Ollama"
    else
        # Exit 2 is a lost race with another writer: its config is complete and
        # must stay untouched. Anything else is a real failure, including a
        # partial write that never reached backend/.env.
        status=$?
        if [ "$status" -eq 2 ]; then
            echo "✅ backend/.env already exists (left untouched)"
        else
            echo "❌ Failed to write backend/.env"
            exit 1
        fi
    fi
else
    echo "✅ backend/.env already exists"
fi

# --- Frontend setup ---
echo ""
echo "📦 Setting up frontend..."

cd frontend-nextjs
npm install --legacy-peer-deps

# Persist a separate web signing secret; never rotate an existing configured key.
python3 ../scripts/setup_web_auth.py --env-file .env.local
echo "✅ Frontend dependencies installed"
cd ..

# --- Check for Ollama ---
echo ""
if command -v ollama >/dev/null 2>&1; then
    echo "🦙 Ollama detected! You can run Atom fully local."
    echo "   To use: set ATOM_LOCAL_ONLY=true in backend/.env"
    echo "   Ollama will serve as the LLM backend (no API key needed)."
else
    echo "💡 Tip: Install Ollama (https://ollama.ai) for free local AI."
    echo "   Then set ATOM_LOCAL_ONLY=true in backend/.env"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "This release is the core company-data + trained-agent workspace:"
echo "  Chat · Data · Workspace · Agents · Activity · Settings"
echo "Deferred surfaces stay in the codebase but are not exposed"
echo "(see docs/acceptance/CORE_RELEASE_SCOPE_2026-10-27.md)."
echo ""
echo "Next steps:"
echo "  1. Edit backend/.env — add an API key or set ATOM_LOCAL_ONLY=true"
echo "  2. Run: ./scripts/dev.sh   (or: make dev)"
echo "  3. Open http://localhost:3001"
echo ""
echo "On first backend startup, the admin password is generated and saved to"
echo "backend/logs/bootstrap_admin_password.txt (sign in as admin@example.com)."
