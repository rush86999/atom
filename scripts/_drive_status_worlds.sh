#!/usr/bin/env bash
# Acceptance-worlds storage checks for scripts/drive_status.sh.
#
# Sourced, not executed: drive_status.sh runs this in BOTH the drive-hosted
# and local-only branches, because worlds storage can be drive-hosted while
# the memory store is still local (they are configured independently).
#
# The real logic lives in `core/world_storage_guard.py` — the same preflight
# every world launcher runs before it creates anything. This wrapper only
# presents it, so the diagnostic and the guard can never disagree about what
# "correct" means. Expects: REPO, DRIVE, WORLDS, GUARD_PY, ok(), bad(), warn(),
# and FAIL (mutated by bad()).

# shellcheck shell=bash

echo "[W] Acceptance worlds storage ($WORLDS)"

if [ ! -x "$GUARD_PY" ]; then
    warn "guard interpreter not found at $GUARD_PY"
    echo "        -> Cannot verify worlds storage. World launchers will refuse"
    echo "           to run if they cannot verify storage either."
elif [ ! -f "$REPO/backend/config/world_storage.json" ]; then
    ok "no worlds config — guard is default-off, storage not enforced"
    echo "        -> Worlds launchers are NOT checking where worlds live."
else
    # Run from backend/ so `-m core.world_storage_guard` resolves; this
    # script is invoked from anywhere, and the guard is anchored to
    # backend/ regardless (AGENTS.md: never CWD-relative).
    guard() { (cd "$REPO/backend" && "$GUARD_PY" -m core.world_storage_guard "$@"); }

    # 1. Preflight: interlock, volume identity, root shape. This is the same
    #    call a launcher makes, so passing here means a launcher would start.
    if CFG_OUT="$(guard check 2>&1)"; then
        echo "$CFG_OUT" | sed -n '1,6p' | sed 's/^/        /'
        ok "worlds storage preflight passed"
    else
        echo "$CFG_OUT" | sed 's/^/        /'
        bad "worlds storage preflight FAILED — world launchers will refuse to start"
        echo "        -> Fix the condition above before running a preview or"
        echo "           acceptance harness. Do NOT work around it by creating"
        echo "           the directory by hand: that is how an empty world gets"
        echo "           created and then 'passes' against nothing."
    fi

    # 2. Representative internal symlink resolution. rsync -a copies broken
    #    and mis-anchored links verbatim, so these accumulate silently and
    #    only surface as a confusing runtime error much later.
    if AUDIT_OUT="$(guard audit-symlinks 2>&1)"; then
        BROKEN_N="$(echo "$AUDIT_OUT" | sed -n 's/^broken *: *//p' | head -1)"
        ok "internal world symlinks resolve (${BROKEN_N:-0} broken in sample)"
    else
        BROKEN_N="$(echo "$AUDIT_OUT" | sed -n 's/^broken *: *//p' | head -1)"
        MIS_N="$(echo "$AUDIT_OUT" | sed -n 's/^misanchored *: *//p' | head -1)"
        bad "broken internal world symlinks: ${BROKEN_N:-?}"
        echo "        -> Preserved verbatim by 'rsync -a'. A world whose"
        echo "           backend_root link dangles will fail at import time, not"
        echo "           here. List them with:"
        echo "             (cd $REPO/backend && $GUARD_PY -m core.world_storage_guard audit-symlinks --all)"
        if [ "${MIS_N:-0}" != "0" ]; then
            warn "mis-anchored internal symlinks: $MIS_N"
            echo "        -> These point back at the canonical worlds root. They are"
            echo "           correct ONLY while that root is itself a symlink; if it"
            echo "           is a plain directory they silently read the wrong tree."
        fi
    fi
fi
echo
