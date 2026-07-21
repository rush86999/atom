"""Execution Sandbox Layer — Phase C (Round 45).

Tripwire pattern registry + matcher. Tripwires are deterministic
regex-based detectors for actions no legitimate agent should ever take:
credential reads, destructive DB writes, privilege escalation, cron
jobs, admin grants, reverse shells.

Extends the ``_IRREVERSIBLE_PATTERNS`` heuristic from
``core/llm/self_consistency_voter.py`` with a broader, categorized
registry.

Design contract:
  * Pure functions: never raise, deterministic on inputs.
  * Tripwire hit → SandboxDecision BLOCKED (NOT RESTRICTED — tripwires
    are unrecoverable). KillRun fires (caller responsibility).
  * Pattern matches are case-insensitive (commands are case-insensitive
    on most shells; argument case preserved for evidence).
  * False-positive avoidance: patterns are anchored on word boundaries
    where appropriate.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import sandbox_config
from core.sandbox_policy import (
    ALLOWED,
    BLOCKED,
    SandboxDecision,
    VT_TRIPWIRE,
)

logger = logging.getLogger(__name__)


# ===========================================================================
# Tripwire categories + patterns
# ===========================================================================
@dataclass(frozen=True)
class TripwirePattern:
    """A single tripwire pattern.

    Attributes:
        id: stable identifier for audit + Prometheus labels
        category: one of CREDENTIAL/DESTRUCTIVE/PRIVILEGE/CRON/ADMIN/REVERSE_SHELL
        regex: compiled regex to match against the command/args text
        description: human-readable explanation for the audit row.
    """

    id: str
    category: str
    regex: "re.Pattern[str]"
    description: str


# Compile patterns at module-load (one-time cost). Word boundaries used
# where a substring match would be a false positive (e.g. "DROP" inside
# "DROPDOWN").
def _compile(pattern: str) -> "re.Pattern[str]":
    return re.compile(pattern, re.IGNORECASE | re.MULTILINE)


_TRIPWIRES: Tuple[TripwirePattern, ...] = (
    # --- Credential reads (Phase C red-team primary surface) ----------
    TripwirePattern(
        id="cred_ssh_key",
        category="CREDENTIAL",
        regex=_compile(r"\bcat\s+[^\s]*\.ssh[/\\]|"
                       r"\bcat\s+[^\s]*id_(rsa|ed25519|ecdsa)\b|"
                       r"\bcat\s+[^\s]*authorized_keys\b"),
        description="reading SSH private keys or authorized_keys",
    ),
    TripwirePattern(
        id="cred_aws",
        category="CREDENTIAL",
        regex=_compile(r"\bcat\s+[^\s]*\.aws[/\\](credentials|config)\b|"
                       r"\bprintenv\s+AWS_SECRET_ACCESS_KEY\b"),
        description="reading AWS credentials",
    ),
    TripwirePattern(
        id="cred_env_file",
        category="CREDENTIAL",
        regex=_compile(r"\bcat\s+[^\s]*\.env(\.|$|\s)|"
                       r"\bcat\s+/etc/(env|environment)\b"),
        description="reading .env or /etc/environment files",
    ),
    TripwirePattern(
        id="cred_env_var_dump",
        category="CREDENTIAL",
        regex=_compile(r"\b(printenv|env|export)\b.*\b(SECRET|TOKEN|API_KEY|PASSWORD|PASSPHRASE)\b"),
        description="dumping secret-bearing environment variables",
    ),

    # --- Destructive DB writes ---------------------------------------
    TripwirePattern(
        id="destructive_drop_table",
        category="DESTRUCTIVE",
        regex=_compile(r"\bDROP\s+(TABLE|DATABASE|SCHEMA|INDEX)\b"),
        description="DROP TABLE / DATABASE / SCHEMA / INDEX",
    ),
    TripwirePattern(
        id="destructive_delete_users",
        category="DESTRUCTIVE",
        regex=_compile(r"\bDELETE\s+FROM\s+\w*[Uu]ser\w*\b|"
                       r"\bTRUNCATE\s+TABLE\b"),
        description="DELETE FROM users* or TRUNCATE TABLE",
    ),
    TripwirePattern(
        id="destructive_drop_column",
        category="DESTRUCTIVE",
        regex=_compile(r"\bALTER\s+TABLE\s+\w+\s+DROP\s+(COLUMN|CONSTRAINT)\b"),
        description="DROP COLUMN / CONSTRAINT — irreversible schema change",
    ),

    # --- Privilege escalation ----------------------------------------
    TripwirePattern(
        id="priv_usermod",
        category="PRIVILEGE",
        regex=_compile(r"\busermod\b|"
                       r"\bvisudo\b|"
                       r"\bsudoers\b"),
        description="modifying users or sudoers",
    ),
    TripwirePattern(
        id="priv_setuid",
        category="PRIVILEGE",
        regex=_compile(r"\bchmod\s+[0-7]*4[0-7][0-7][0-7]\b|"
                       r"\bchmod\s+u?S\b|"
                       r"\bsetuid\b"),
        description="setting setuid bit or calling setuid()",
    ),
    TripwirePattern(
        id="priv_sudo_unsafe",
        category="PRIVILEGE",
        regex=_compile(r"\bsudo\s+(rm|dd|mkfs|fdisk|shutdown|reboot|chmod\s+\+x)\b"),
        description="sudo rm/dd/mkfs/shutdown/reboot — destructive via sudo",
    ),

    # --- Cron jobs (persistence primitive) ---------------------------
    TripwirePattern(
        id="cron_edit",
        category="CRON",
        regex=_compile(r"\bcrontab\s+(-e|-l|--edit)\b|"
                       r"/etc/cron\.d/?\b|"
                       r"/etc/cron\.(hourly|daily|weekly|monthly)\b"),
        description="editing crontab or writing cron.d (persistence)",
    ),
    TripwirePattern(
        id="cron_systemd_timer",
        category="CRON",
        regex=_compile(r"\bsystemctl\s+(enable|start|edit)\s+\S+\.timer\b|"
                       r"/etc/systemd/system/\S+\.timer\b"),
        description="enabling systemd timer (persistence)",
    ),

    # --- Admin grants -------------------------------------------------
    TripwirePattern(
        id="admin_grant_sql",
        category="ADMIN",
        regex=_compile(r"\bGRANT\s+(ALL|SUPERUSER|ADMIN)\b|"
                       r"\bALTER\s+ROLE\b"),
        description="SQL GRANT ALL or ALTER ROLE (privilege grant)",
    ),
    TripwirePattern(
        id="admin_iam_attach",
        category="ADMIN",
        regex=_compile(r"AttachRolePolicy|PutRolePolicy|CreateAccessKey\b"),
        description="AWS IAM privilege grant / key creation",
    ),

    # --- Reverse shells ----------------------------------------------
    TripwirePattern(
        id="rshell_bash_i",
        category="REVERSE_SHELL",
        regex=_compile(r"\bbash\s+-i\b|"
                       r"\bsh\s+-i\b|"
                       r"\bzsh\s+-i\b"),
        description="interactive shell invocation (reverse shell primitive)",
    ),
    TripwirePattern(
        id="rshell_nc_exec",
        category="REVERSE_SHELL",
        regex=_compile(r"\bnc\b\s+\S*\s*-e\s|"
                       r"\bncat\b\s+\S*\s*-e\s|"
                       r"\bsocat\b\s+.*\bEXEC\b"),
        description="netcat/socat EXEC redirect (reverse shell)",
    ),
    TripwirePattern(
        id="rshell_dev_tcp",
        category="REVERSE_SHELL",
        regex=_compile(r"/dev/tcp/|/dev/udp/"),
        description="bash /dev/tcp reverse shell primitive",
    ),
    TripwirePattern(
        id="rshell_python_socket",
        category="REVERSE_SHELL",
        regex=_compile(r"socket\.socket\(\s*socket\.AF_INET\s*,\s*socket\.SOCK_STREAM"),
        description="raw socket creation in Python (reverse shell)",
    ),

    # --- Data exfiltration via HTTP ----------------------------------
    TripwirePattern(
        id="exfil_curl_to_external",
        category="EXFIL",
        regex=_compile(r"\b(curl|wget)\s+https?://(?!("
                       r"api\.anthropic\.com|"
                       r"api\.openai\.com|"
                       r"generativelanguage\.googleapis\.com|"
                       r"pypi\.org|"
                       r"files\.pythonhosted\.org|"
                       r"github\.com|"
                       r"raw\.githubusercontent\.com"
                       r")\b)"),
        description="HTTP request to non-allowlisted host (exfil)",
    ),
)


# ===========================================================================
# Matching
# ===========================================================================


def _extract_text_for_matching(args: Dict[str, Any]) -> str:
    """Pull a flat text representation of args for regex matching.

    Walks the args dict, concatenating string values. This is intentionally
    lossy — we don't need structured matching, just substring detection.
    """
    parts: List[str] = []

    def _walk(obj: Any) -> None:
        if isinstance(obj, str):
            parts.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                _walk(v)
        else:
            parts.append(str(obj))

    _walk(args or {})
    return " ".join(parts)


def match(args: Dict[str, Any]) -> Optional[TripwirePattern]:
    """Return the first tripwire that matches, or None.

    Iterates the registry in declaration order. Returns the first hit —
    a single command may match multiple patterns; we surface the
    highest-priority one (declaration order is priority).
    """
    text = _extract_text_for_matching(args)
    if not text:
        return None
    for tw in _TRIPWIRES:
        try:
            if tw.regex.search(text):
                return tw
        except re.error as e:
            logger.warning("tripwire regex %s failed: %s", tw.id, e)
    return None


def all_patterns() -> Tuple[TripwirePattern, ...]:
    """Expose the registry (for docs / introspection / tests)."""
    return _TRIPWIRES


# ===========================================================================
# Public API
# ===========================================================================


def check_python_ast(code: str) -> Optional[str]:
    """Analyze python code using AST. Returns validation error message or None if safe."""
    import ast
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return check_js_ast(code)
        
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                if name.name in {"os", "sys", "subprocess", "shutil", "socket", "pty", "importlib"}:
                    return f"AST violation: Forbidden import of module '{name.name}'"
        elif isinstance(node, ast.ImportFrom):
            if node.module in {"os", "sys", "subprocess", "shutil", "socket", "pty", "importlib"}:
                return f"AST violation: Forbidden import from module '{node.module}'"
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in {"eval", "exec", "open", "compile", "__import__"}:
                    return f"AST violation: Forbidden built-in call '{node.func.id}()'"
                if node.func.id == "getattr":
                    if node.args and isinstance(node.args[0], ast.Name) and node.args[0].id in {"os", "sys", "subprocess", "shutil", "socket"}:
                        return f"AST violation: Forbidden reflection getattr() on module '{node.args[0].id}'"
            elif isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id in {"os", "sys", "subprocess", "shutil", "importlib"}:
                        return f"AST violation: Forbidden system attribute call '{node.func.value.id}.{node.func.attr}()'"
        elif isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Attribute):
                if isinstance(node.value.value, ast.Name) and node.value.value.id == "os" and node.value.attr == "environ":
                    if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                        key = node.slice.value.upper()
                        if any(k in key for k in ["SECRET", "TOKEN", "API_KEY", "PASSWORD", "AWS"]):
                            return f"AST violation: Access to secret-bearing environment variable '{node.slice.value}'"
    return check_js_ast(code)


def check_js_ast(code: str) -> Optional[str]:
    """Scan string arguments for dangerous JavaScript/TypeScript patterns."""
    js_patterns = [
        (r"eval\s*\(", "eval() execution"),
        (r"Function\s*\(", "Function constructor execution"),
        (r"child_process", "child_process execution"),
        (r"process\.env\.(SECRET|TOKEN|API_KEY|PASSWORD|AWS)", "process.env secret access"),
    ]
    for pattern, desc in js_patterns:
        if re.search(pattern, code, re.IGNORECASE):
            return f"JS/TS AST violation: Forbidden {desc}"
    return None


def _check_ast_violations(args: Dict[str, Any]) -> Optional[str]:
    """Scan string arguments for valid Python code and analyze via AST."""
    def _walk(obj: Any) -> Optional[str]:
        if isinstance(obj, str):
            if len(obj.strip()) > 5:
                violation = check_python_ast(obj)
                if violation:
                    return violation
        elif isinstance(obj, dict):
            for v in obj.values():
                violation = _walk(v)
                if violation:
                    return violation
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                violation = _walk(v)
                if violation:
                    return violation
        return None
        
    return _walk(args or {})


def check(
    *,
    tool_name: str,
    args: Dict[str, Any],
    args_hash: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> SandboxDecision:
    """Evaluate args against the tripwire registry.

    Returns:
      * ALLOWED when no pattern matches.
      * BLOCKED with violation_type=VT_TRIPWIRE on first match. The
        ``enforced`` flag reflects shadow-mode state.
    """
    try:
        # Check AST violations first
        ast_violation = _check_ast_violations(args)
        if ast_violation:
            return SandboxDecision(
                decision=BLOCKED,
                phase="C",
                violation_type=VT_TRIPWIRE,
                violation_detail=ast_violation,
                tool_name=tool_name,
                args_hash=args_hash,
                enforced=sandbox_config.is_sandbox_force_enforce_enabled(),
                killrun_triggered=True,
                metadata_json={
                    "tripwire_id": "ast_violation",
                    "category": "AST_INVARIANT",
                    "description": ast_violation,
                },
            )

        hit = match(args)
        if hit is None:
            return SandboxDecision(
                decision=ALLOWED,
                phase="C",
                tool_name=tool_name,
                args_hash=args_hash,
            )
        return SandboxDecision(
            decision=BLOCKED,
            phase="C",
            violation_type=VT_TRIPWIRE,
            violation_detail=f"tripwire {hit.id} ({hit.category}): {hit.description}",
            tool_name=tool_name,
            args_hash=args_hash,
            enforced=sandbox_config.is_sandbox_force_enforce_enabled(),
            killrun_triggered=True,  # tripwires always fire KillRun
            metadata_json={
                "tripwire_id": hit.id,
                "category": hit.category,
                "description": hit.description,
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.debug("tripwire check failed open for %s: %s", tool_name, e)
        return SandboxDecision(
            decision=ALLOWED,
            phase="C",
            tool_name=tool_name,
            args_hash=args_hash,
            metadata_json={"error": str(e)},
        )


# ===========================================================================
# Megafile & Bloat Tripwire (Swarm Coordination — Cursor Pattern)
# ===========================================================================

@dataclass
class MegafileWarning:
    """Payload emitted when a file crosses the bloat threshold."""

    file_path: str
    line_count: int
    edit_count: int
    threshold_loc: int
    threshold_edits: int
    severity: str  # "WARNING" | "CRITICAL"
    recommendation: str

    def to_harness_patch_proposal(self) -> Dict[str, Any]:
        """Format as a HarnessEvolutionService-compatible patch proposal."""
        return {
            "patch_id": f"megafile_{Path(self.file_path).stem}",
            "target_component": "file_modularization",
            "mutation_payload": {
                "file_path": self.file_path,
                "action": "decompose_into_modules",
                "reason": self.recommendation,
                "current_line_count": self.line_count,
                "current_edit_count": self.edit_count,
            },
            "model_scope": "workspace",
            "severity": self.severity,
        }


class MegafileDetector:
    """Tracks file edit operations and flags files that become hotspot 'megafiles'.

    Implements the Cursor swarm pattern: when a shared file is too large or
    edited too frequently within a single execution loop, it blocks forward
    progress by causing constant merge conflicts and context overflows.  This
    detector emits a :class:`MegafileWarning` that callers should forward to
    :class:`~core.harness_evolution_service.HarnessEvolutionService` as a
    modularisation patch proposal.

    Usage::

        detector = MegafileDetector(loc_threshold=800, edit_threshold=5)
        warning = detector.record_edit("/path/to/big_file.py", line_count=920)
        if warning:
            harness_service.queue_patch(warning.to_harness_patch_proposal())

    The detector is stateful per execution loop.  Call :meth:`reset` between
    loops to clear the per-session edit counters.
    """

    DEFAULT_LOC_THRESHOLD: int = 800
    DEFAULT_EDIT_THRESHOLD: int = 5

    def __init__(
        self,
        loc_threshold: int = DEFAULT_LOC_THRESHOLD,
        edit_threshold: int = DEFAULT_EDIT_THRESHOLD,
    ) -> None:
        self._loc_threshold = loc_threshold
        self._edit_threshold = edit_threshold
        # Maps absolute file path → number of edits in this loop
        self._edit_counts: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_edit(
        self,
        file_path: str,
        *,
        line_count: Optional[int] = None,
    ) -> Optional[MegafileWarning]:
        """Record an edit to *file_path* and return a warning if bloat thresholds are crossed.

        Args:
            file_path: Absolute (or workspace-relative) path of the edited file.
            line_count: Current line count of the file after the edit.  When
                        omitted the LOC threshold is skipped.

        Returns:
            A :class:`MegafileWarning` if either threshold is exceeded, else
            ``None``.
        """
        abs_path = str(Path(file_path).resolve()) if Path(file_path).exists() else file_path
        self._edit_counts[abs_path] = self._edit_counts.get(abs_path, 0) + 1
        edit_count = self._edit_counts[abs_path]

        lc = line_count or 0
        lc_exceeded = lc > self._loc_threshold
        edit_exceeded = edit_count >= self._edit_threshold

        if not (lc_exceeded or edit_exceeded):
            return None

        severity = "CRITICAL" if (lc_exceeded and edit_exceeded) else "WARNING"
        reasons: List[str] = []
        if lc_exceeded:
            reasons.append(f"{lc} LOC (threshold {self._loc_threshold})")
        if edit_exceeded:
            reasons.append(f"{edit_count} edits this loop (threshold {self._edit_threshold})")

        recommendation = (
            f"File '{Path(file_path).name}' is a hotspot megafile ({', '.join(reasons)}). "
            "Block further commits and decompose into smaller focused modules."
        )
        warning = MegafileWarning(
            file_path=abs_path,
            line_count=lc,
            edit_count=edit_count,
            threshold_loc=self._loc_threshold,
            threshold_edits=self._edit_threshold,
            severity=severity,
            recommendation=recommendation,
        )
        logger.warning(
            "MegafileDetector [%s]: %s",
            severity, recommendation,
        )
        return warning

    def is_blocked(self, file_path: str) -> bool:
        """Return True if the file has already been flagged as a megafile this loop."""
        abs_path = str(Path(file_path).resolve()) if Path(file_path).exists() else file_path
        return self._edit_counts.get(abs_path, 0) >= self._edit_threshold

    def reset(self) -> None:
        """Clear per-loop edit counters.  Call between execution loops."""
        self._edit_counts.clear()

    def summary(self) -> List[Dict[str, Any]]:
        """Return all tracked files with their edit counts for the current loop."""
        return [
            {"file": f, "edits": c}
            for f, c in sorted(self._edit_counts.items(), key=lambda x: -x[1])
        ]
