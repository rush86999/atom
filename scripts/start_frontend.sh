#!/usr/bin/env bash
# Canonical ATOM frontend launcher.
#
# Why this exists (2026-09-05 incident): `next dev` AUTO-INCREMENTS the port
# when the default is busy (3000 -> 3001) with only a console warning. OAuth
# redirect URIs are registered against FIXED ports in provider consoles, so a
# drifted frontend silently breaks every browser-facing OAuth flow and serves
# provider callbacks to whatever app squatted the port (we landed Zoho OAuth
# on the atom-saas frontend that way).
#
# Rule: the frontend must bind its registered port exactly, or fail loudly.
# Use this script instead of bare `npm run dev`.

set -u

PORT="${1:-${FRONTEND_PORT:-3000}}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$REPO_ROOT/frontend-nextjs"
LOG_FILE="$FRONTEND_DIR/logs/next_dev_$PORT.log"

if [ ! -d "$FRONTEND_DIR" ]; then
    echo "FATAL: $FRONTEND_DIR not found (run from the atom repo)"
    exit 1
fi

# --- Preflight: fail loudly if the registered port is taken ---------------
if lsof -ti ":$PORT" >/dev/null 2>&1; then
    PID=$(lsof -ti ":$PORT" | head -1)
    CWD=$(lsof -p "$PID" 2>/dev/null | grep cwd | awk '{print $NF}')
    echo "FATAL: port $PORT is already in use by pid $PID (cwd: ${CWD:-unknown})"
    echo ""
    echo "Browser-facing OAuth redirects are registered against FIXED ports."
    echo "Starting on a different port would silently break them."
    echo ""
    echo "Options:"
    echo "  1. Stop the conflicting app:            kill $PID"
    echo "     (if it's another project, restart it on its own port, e.g. 3100)"
    echo "  2. Or use a different port AND update every redirect registration"
    echo "     that points at the old one + FRONTEND_URL in backend/.env"
    exit 1
fi

# --- Launch ----------------------------------------------------------------
mkdir -p "$(dirname "$LOG_FILE")"
cd "$FRONTEND_DIR" || exit 1
echo "==> Starting ATOM frontend on port $PORT (log: $LOG_FILE)"
nohup npm run dev -- -p "$PORT" >> "$LOG_FILE" 2>&1 &
NEW_PID=$!

# --- Post-start identity check --------------------------------------------
echo -n "==> Waiting for readiness"
for _ in $(seq 1 30); do
    CODE=$(curl -s -m 5 -o /dev/null -w "%{http_code}" "http://localhost:$PORT/" 2>/dev/null)
    [ "$CODE" != "000" ] && break
    echo -n "."
    sleep 2
done
echo
if [ "$CODE" = "000" ]; then
    echo "FAILED: frontend did not become reachable — last log lines:"
    tail -10 "$LOG_FILE"
    exit 1
fi

# Distinguish ATOM from sibling projects that might answer on the same port:
# ATOM's router 307s unknown paths to /login; a foreign app 404s or serves
# its own content.
MARKER=$(curl -s -m 10 -o /dev/null -w "%{http_code}" "http://localhost:$PORT/__atom_identity_probe__" 2>/dev/null)
if [ "$MARKER" = "307" ] || [ "$MARKER" = "200" ]; then
    echo "==> ATOM frontend verified on http://localhost:$PORT (pid $NEW_PID)"
    echo "==> OAuth landing: $PORT/oauth/success (requires session; "
    echo "    real flows carry the cookie and land directly)"
else
    echo "WARNING: something answered on $PORT but did NOT behave like ATOM"
    echo "(identity probe returned $MARKER, expected 307). Check what is"
    echo "actually serving before trusting OAuth redirects."
fi
