#!/usr/bin/env bash
# External-storage status for the ATOM split layout (2026-09-05).
#
# LAYOUTS (kept flexible on purpose):
#   local-only  — fresh installs: everything under <repo>/backend/data, no
#                 external drive needed. This script reports that and exits 0.
#   drive-hosted — backend/data/atom_memory is a symlink onto a mounted
#                 volume (default /Volumes/Seagate Portable Drive; override
#                 with ATOM_EXTERNAL_DRIVE). Heavy data lives on the drive:
#                 memory store, backup mirror, optionally Ollama + Docker.
#
# Run this whenever memory/RAG features error, backups stop appearing, or
# Ollama/Docker misbehave. On drive-hosted layouts the overwhelmingly likely
# cause is the drive being unplugged or not yet mounted after reboot/replug.
#
# It also reports ACCEPTANCE-WORLD storage (backend/data/acceptance_worlds),
# which is drive-hosted independently of the memory store: worlds can live on
# the external volume while atom_memory is still local, or vice versa. That
# check is delegated to `core.world_storage_guard` — the same preflight every
# world launcher runs — rather than reimplemented here, so the diagnostic and
# the guard can never disagree about what "correct" means.
#
# LIMIT OF ANY STARTUP CHECK: this script, and the launcher preflight, can
# only describe the state at the moment they run. Neither can protect a
# world that is already running when the drive is unplugged. That is why
# nothing in the guard retries or caches a verdict: an I/O error from a live
# server stays a loud EIO/ENOENT instead of being smoothed over.

set -u

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DRIVE="${ATOM_EXTERNAL_DRIVE:-/Volumes/Seagate Portable Drive}"
MEM_LINK="$REPO/backend/data/atom_memory"
WORLDS="$REPO/backend/data/acceptance_worlds"
GUARD_PY="$REPO/backend/venv314/bin/python"
DRIVE_HOSTED=0
if [ -L "$MEM_LINK" ] || [ -L "$WORLDS" ] || [ -n "${ATOM_EXTERNAL_DRIVE:-}" ]; then
    DRIVE_HOSTED=1
fi
FAIL=0

ok()   { echo "  OK    $1"; }
bad()  { echo "  FAIL  $1"; FAIL=1; }
warn() { echo "  WARN  $1"; }

echo "== External storage status =="
echo

echo "[0] Layout"
if [ "$DRIVE_HOSTED" = "1" ]; then
    ok "drive-hosted (memory store and/or acceptance worlds symlinked onto $DRIVE)"
    echo
else
    ok "local-only — no external drive configured (fresh-install default)"
    echo "        -> Nothing to check for memory/backups; heavy data lives in $REPO/backend/data."
    echo "        -> To host it on an external volume: move the data directory there,"
    echo "           symlink it back, and optionally set ATOM_EXTERNAL_DRIVE."
    echo
    # Worlds storage is checked in BOTH layouts: it can be drive-hosted while
    # the memory store is still local. Do not exit before checking it.
    . "$REPO/scripts/_drive_status_worlds.sh"
    echo
    echo "== Summary =="
    if [ "$FAIL" -eq 0 ]; then
        echo "Local-only layout: all checks passed."
    else
        echo "One or more checks FAILED — see the '->' notes above."
    fi
    exit "$FAIL"
fi
echo

echo "[1] Portable drive"
if [ -d "$DRIVE" ]; then
    ok "drive mounted at $DRIVE"
else
    bad "drive NOT mounted at $DRIVE"
    echo "        -> Replug the drive (or open Finder and select it)."
    echo "        -> macOS mounts it automatically a few seconds after plug-in."
fi
echo

echo "[2] LanceDB memory store (backend/data/atom_memory symlink)"
if [ -L "$MEM_LINK" ] && [ -e "$MEM_LINK" ]; then
    ok "symlink resolves -> $(readlink "$MEM_LINK")"
elif [ -L "$MEM_LINK" ]; then
    bad "symlink is DANGLING (drive missing or renamed)"
    echo "        -> Remount the drive; the app recovers on its next use,"
    echo "           no restart needed. Data is on the drive, not lost."
else
    bad "$MEM_LINK is not a symlink (layout changed?)"
fi
echo

echo "[3] Backup mirror ($DRIVE/atom-backups)"
if [ -d "$DRIVE/atom-backups" ]; then
    N=$(ls "$DRIVE/atom-backups" 2>/dev/null | wc -l | tr -d ' ')
    NEWEST=$(ls -t "$DRIVE/atom-backups" 2>/dev/null | head -1)
    ok "$N snapshots (newest: ${NEWEST:-none})"
else
    bad "backup dir missing (drive missing, or never seeded)"
fi
echo

echo "[4] Ollama models on drive"
if [ -L "$HOME/.ollama/models" ] && [ -e "$HOME/.ollama/models" ]; then
    ok "symlink resolves -> $(readlink "$HOME/.ollama/models")"
elif [ -d "$HOME/.ollama/models" ]; then
    ok "present (local dir, not drive-hosted)"
else
    bad "models path missing — 'ollama list' will fail"
    echo "        -> Remount the drive."
fi
echo

echo "[5] Docker Desktop data folder"
SETTINGS="$HOME/Library/Group Containers/group.com.docker/settings-store.json"
if [ -f "$SETTINGS" ] && grep -q "Volumes" "$SETTINGS" 2>/dev/null; then
    if [ -d "$DRIVE/docker" ]; then
        ok "DataFolder on drive and present"
    else
        bad "DataFolder set to drive but $DRIVE/docker missing"
    fi
else
    ok "not drive-hosted (no action needed)"
fi
echo

# Worlds storage is independent of the memory store, so it is checked last
# in the drive-hosted branch too — the same section the local-only branch
# runs before exiting.
. "$REPO/scripts/_drive_status_worlds.sh"
echo

echo "== Summary =="
if [ "$FAIL" -eq 0 ]; then
    echo "All external-storage checks passed."
else
    echo "One or more checks FAILED — see the '->' recovery notes above."
    echo "In most cases: replug the drive, wait ~10s, then re-run this script."
fi
exit "$FAIL"
