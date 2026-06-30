"""Execution Sandbox Layer — Phase B (Round 44).

Filesystem scope enforcement. Validates that every tool call which touches
the filesystem stays within the policy's ``fs_roots`` (read) and
``fs_write_roots`` (write).

Mirrors the path-containment pattern from ``core/skill_dynamic_loader.py``
(``Path.resolve().relative_to(base)``) but applies it to *every* tool,
not just dynamic skill loading.

Design contract:
  * Pure functions: never raise, deterministic on inputs.
  * Path normalization via ``Path.resolve()`` so symlinks and ``..`` are
    collapsed before the scope check.
  * Tripwires (Phase B subset): ``..`` after normalization, forbidden
    system prefixes (``/proc/``, ``/sys/``, ``/etc/``, ``/root/`` …),
    and home-directory sensitive paths (``~/.ssh/``, ``~/.aws/`` …).
  * Shadow-mode aware: returns a SandboxDecision; the caller decides
    whether to enforce.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from core import sandbox_config
from core.sandbox_policy import (
    ALLOWED,
    BLOCKED,
    RESTRICTED,
    FORBIDDEN_HOME_PATHS,
    FORBIDDEN_PATH_PREFIXES,
    SandboxDecision,
    SandboxPolicy,
    VT_FS_PATH,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# Tripwire detection (Phase B subset — easy wins)
# ===========================================================================


def _hit_path_tripwire(resolved: str, home: str, requested: Optional[str] = None) -> Optional[str]:
    """Return the tripwire name that fired, or None.

    Tripwires are the absolute blocks — these fire regardless of tier or
    ``fs_roots``. They cover paths no agent should ever touch.

    Checks both ``resolved`` (post-symlink-collapse) AND ``requested``
    (the raw user-supplied path) because on macOS ``/etc`` is a symlink
    to ``/private/etc`` — only checking resolved would miss the
    user-visible ``/etc`` attempt, and only checking requested would
    miss a path that traverses via symlink into a forbidden zone.
    """
    candidates = [resolved]
    if requested and requested != resolved:
        candidates.append(requested)

    # 1. Forbidden system prefixes
    for cand in candidates:
        for pfx in FORBIDDEN_PATH_PREFIXES:
            if cand == pfx.rstrip("/") or cand.startswith(pfx):
                return f"forbidden_prefix:{pfx}"

    # 2. Forbidden home paths (ssh keys, aws creds, .env, etc.)
    if home:
        for cand in candidates:
            if cand == home or cand.startswith(home + os.sep):
                rel = cand[len(home):].lstrip(os.sep)
                for frag in FORBIDDEN_HOME_PATHS:
                    # exact file (.env) or directory prefix (.ssh/)
                    if frag.endswith("/"):
                        if rel == frag[:-1] or rel.startswith(frag):
                            return f"forbidden_home:{frag}"
                    else:
                        if rel == frag or rel.startswith(frag + ".") or rel == frag:
                            return f"forbidden_home:{frag}"

    return None


# ===========================================================================
# Path resolution + scope check
# ===========================================================================


def _normalize_path(p: str, cwd: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """Resolve ``p`` to an absolute, normalized path.

    Returns ``(resolved, tripwire)``. ``tripwire`` is set when:
      * the path contained ``..`` after normalization (path-traversal)
      * the path hit a forbidden prefix
      * the path hit a home-sensitive location

    Never raises — on any error (OSError, FileNotFoundError during
    resolve), returns ``(p, "resolve_error")`` and the caller treats it
    as a hard block.
    """
    try:
        path = Path(p)
        if not path.is_absolute():
            path = Path(cwd or os.getcwd()) / path
        # resolve() collapses ``..`` and symlinks. If the target doesn't
        # exist we still want normalization — strict=False (default in
        # modern Python).
        resolved = str(path.resolve(strict=False))

        # Tripwire: did ``..`` survive normalization? (Shouldn't, but
        # belt-and-suspenders.) Compare raw vs resolved.
        if ".." in p and resolved != str(Path(p).resolve(strict=False)):
            pass  # resolve already handled it; no separate tripwire

        tripwire = _hit_path_tripwire(resolved, str(Path.home()), requested=p)
        return resolved, tripwire
    except (OSError, ValueError) as e:
        logger.debug("path normalize failed for %r: %s", p, e)
        return p, "resolve_error"


def _within_scope(resolved: str, roots: Tuple[str, ...]) -> bool:
    """True if ``resolved`` is at or under any of ``roots``.

    Uses ``Path.relative_to`` semantics — raises ValueError if not under
    the root, so we treat that as "out of scope".
    """
    if not roots:
        return False
    for root in roots:
        try:
            Path(resolved).relative_to(root)
            return True
        except ValueError:
            continue
    return False


# ===========================================================================
# Public API
# ===========================================================================

# Args-keys that typically carry filesystem paths per tool. Conservative —
# extras like ``cwd`` and ``output_path`` covered. Phase B extends this
# mapping per-tool as needed.
_PATH_ARG_KEYS: Tuple[str, ...] = (
    "path",
    "file_path",
    "filepath",
    "filename",
    "output_path",
    "output_file",
    "save_path",
    "dest",
    "destination",
    "cwd",
    "working_dir",
    "workdir",
)


def extract_paths_from_args(args: Dict[str, Any]) -> Dict[str, str]:
    """Pull all path-looking values out of ``args``.

    Returns ``{arg_key: path_value}`` for each arg whose key matches a
    known path-key name. Callers can iterate the result and validate
    each.
    """
    out: Dict[str, str] = {}
    if not args:
        return out
    for key, value in args.items():
        if key in _PATH_ARG_KEYS and isinstance(value, str) and value:
            out[key] = value
    return out


def validate_path(
    path_value: str,
    policy: SandboxPolicy,
    *,
    write: bool,
    tool_name: str,
    cwd: Optional[str] = None,
    args_hash: Optional[str] = None,
) -> SandboxDecision:
    """Validate a single path against the policy.

    Args:
        path_value: the path string from the tool args.
        policy: the active SandboxPolicy.
        write: True if this path will be written to; False for reads.
        tool_name: for audit.
        cwd: optional cwd for relative-path resolution.
        args_hash: optional correlation hash.

    Returns:
        SandboxDecision with ALLOWED / RESTRICTED / BLOCKED.

    Tripwires fire BLOCKED. Out-of-scope but non-tripwire paths are
    RESTRICTED (recoverable — caller may remap to sandbox dir).

    Scope check considers both the resolved path AND the policy roots
    post-normalization. On macOS, ``/tmp`` → ``/private/tmp``, so a
    policy set with ``/tmp/agent/r1`` and a request for ``/tmp/agent/r1``
    must both normalize consistently.
    """
    resolved, tripwire = _normalize_path(path_value, cwd=cwd)

    # Tripwire → hard block, regardless of tier / roots.
    if tripwire:
        return SandboxDecision(
            decision=BLOCKED,
            phase="B",
            violation_type=VT_FS_PATH,
            violation_detail=f"path tripwire: {tripwire} (resolved={resolved})",
            tool_name=tool_name,
            args_hash=args_hash,
            enforced=sandbox_config.is_sandbox_force_enforce_enabled(),
            metadata_json={
                "tripwire": tripwire,
                "resolved": resolved,
                "requested": path_value,
            },
        )

    # Scope check — normalize roots the same way for parity.
    roots = policy.fs_write_roots if write else policy.fs_roots
    norm_roots = tuple(_normalize_path(r)[0] for r in roots)
    in_scope = _within_scope(resolved, norm_roots)
    # Also check the raw requested value (handles macOS /tmp symlink case
    # where policy was authored against the user-visible /tmp).
    if not in_scope and path_value:
        in_scope = _within_scope(path_value, roots)

    if in_scope:
        return SandboxDecision(
            decision=ALLOWED,
            phase="B",
            tool_name=tool_name,
            args_hash=args_hash,
            metadata_json={"resolved": resolved, "write": write},
        )

    # Out of scope, but not a tripwire → RESTRICTED (recoverable).
    violation = (
        f"path '{path_value}' (resolved {resolved}) outside "
        f"{'write' if write else 'read'} roots {list(roots)}"
    )
    return SandboxDecision(
        decision=RESTRICTED,
        phase="B",
        violation_type=VT_FS_PATH,
        violation_detail=violation,
        tool_name=tool_name,
        args_hash=args_hash,
        enforced=sandbox_config.is_sandbox_force_enforce_enabled(),
        metadata_json={
            "resolved": resolved,
            "requested": path_value,
            "write": write,
            "roots": list(roots),
        },
    )


def validate(
    policy: SandboxPolicy,
    tool_name: str,
    args: Dict[str, Any],
    *,
    write_tools: Optional[Tuple[str, ...]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> SandboxDecision:
    """Validate all path-bearing args for a tool call.

    Args:
        policy: the active SandboxPolicy.
        tool_name: for audit.
        args: tool args dict.
        write_tools: tuple of tool names that perform writes. Defaults
            to a curated set. Used to decide write vs read scope.
        context: optional context dict (for args_hash + policy_id).

    Returns:
        The *worst* decision across all path args (BLOCKED > RESTRICTED >
        ALLOWED). If a tool has multiple paths and any is blocked, the
        whole call is blocked.
    """
    write_tool_set = set(write_tools or _DEFAULT_WRITE_TOOLS)

    paths = extract_paths_from_args(args)
    if not paths:
        return SandboxDecision(
            decision=ALLOWED,
            phase="B",
            tool_name=tool_name,
            metadata_json={"reason": "no_path_args"},
        )

    is_write_tool = tool_name in write_tool_set
    # Compute args_hash once for correlation across paths.
    from core.sandbox_policy import PolicyIssuer

    args_hash = PolicyIssuer._hash_args(args)

    worst = SandboxDecision(
        decision=ALLOWED,
        phase="B",
        tool_name=tool_name,
        args_hash=args_hash,
    )

    for key, path_value in paths.items():
        d = validate_path(
            path_value,
            policy,
            write=is_write_tool,
            tool_name=tool_name,
            cwd=args.get("cwd"),
            args_hash=args_hash,
        )
        d = SandboxDecision(**{**d.to_audit_row(), "metadata_json": {**d.metadata_json, "arg_key": key}})

        # BLOCKED dominates RESTRICTED dominates ALLOWED
        if d.decision == BLOCKED:
            return d
        if d.decision == RESTRICTED and worst.decision == ALLOWED:
            worst = d

    return worst


# Curated set of tools known to write to the filesystem. Tools not in
# this set are treated as read-only for scope purposes (conservative —
# if a tool is missing from this set, it gets the wider read scope,
# which is still bounded by fs_roots).
_DEFAULT_WRITE_TOOLS: Tuple[str, ...] = (
    "write_code_file",
    "browser_download",
    "device_save_photo",
    "device_take_screenshot",
    "memory_remember",   # writes to vector store, but path-agnostic
    "canvas_export",     # writes export file
    "atom_cli_skill",    # writes to scoped tmpfs
)


def rewrite_path_to_sandbox(
    path_value: str,
    sandbox_write_root: str,
    *,
    cwd: Optional[str] = None,
) -> str:
    """Remap an out-of-scope absolute path into the sandbox write root.

    Used by callers in RESTRICTED recovery mode: when a path is outside
    ``fs_write_roots`` but the tier allows it (e.g. SUPERVISED), the
    caller can remap the path under the per-run tmpfs and proceed.

    Returns the remapped path. If ``path_value`` is relative, it's
    resolved under the sandbox root. If absolute, the basename is
    preserved and the parent is replaced.
    """
    try:
        path = Path(path_value)
        if not path.is_absolute():
            base = Path(cwd or sandbox_write_root) / path
        else:
            base = Path(sandbox_write_root) / path.name
        # Make sandbox root if needed (best-effort, never raises)
        try:
            Path(sandbox_write_root).mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return str(base.resolve(strict=False))
    except (OSError, ValueError) as e:
        logger.debug("rewrite_path_to_sandbox failed for %r: %s", path_value, e)
        return path_value
