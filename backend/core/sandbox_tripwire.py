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
from dataclasses import dataclass
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
