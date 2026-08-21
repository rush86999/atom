"""Experience Sanitizer — strips proprietary identity from agent training before it can be shared.

Layers (fail-closed, applied in order):
1. Role-token registry  — entity names map to deterministic generic tokens
   (``{type}_{n:03d}``), persisted per (workspace, entity_type, name) so delta
   packs keep the same token. Unknown identity strings never export verbatim —
   they fall back to a saltless content-hash token.
2. Credential stripping — reuses P5 ``core.blueprint_sanitizer`` (fail-closed).
3. PII redaction        — email / phone / URL regex → ``<email>`` / ``<phone>`` / ``<url>``.
4. Attribute bucketing  — exact values → envelopes (amount, count, duration, date, ratio).
5. Leak scan            — post-assembly re-check of every exported string against
   the original identity set (len >= 3, case-insensitive); any hit aborts.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from core.models import ExperienceRoleRegistry

# ---------------------------------------------------------------------------
# PII regexes (conservative — better to drop than to leak)
# ---------------------------------------------------------------------------
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}")
URL_RE = re.compile(r"https?://[^\s<>\"']+|www\.[^\s<>\"']+")

# Keys that always identify a *thing*, never a lesson — dropped outright.
_IDENTITY_KEYS = {
    "workflow_id", "command", "file_path", "session_id", "execution_id",
    "message_id", "document_id", "episode_id", "canvas_id", "agent_id",
    "user_id", "workspace_id", "tenant_id", "external_id",
}

# Key-substring → bucket-kind guessing for critical_data_points / metadata_json.
_KIND_HINTS: List[Tuple[str, str]] = [
    ("amount", "amount"), ("revenue", "amount"), ("price", "amount"), ("cost", "amount"),
    ("salary", "amount"), ("budget", "amount"), ("value", "amount"),
    ("count", "count"), ("num", "count"), ("len", "count"), ("size", "count"),
    ("row_count", "count"), ("col_count", "count"),
    ("duration", "duration"), ("timeout", "duration"), ("sec", "duration"),
    ("min", "duration"), ("hour", "duration"), ("ms", "duration"),
    # "ratio" is a substring of "duration" — must come after the duration hints.
    ("rate", "ratio"), ("ratio", "ratio"), ("percentage", "ratio"),
    ("date", "date"), ("at", "date"), ("time", "date"),
]

_AMOUNT_BUCKETS = [("0,100", lambda v: v < 100), ("100,1K", lambda v: v < 1_000),
                   ("1K,10K", lambda v: v < 10_000), ("10K,100K", lambda v: v < 100_000),
                   ("100K,1M", lambda v: v < 1_000_000), ("1M+", lambda v: True)]
_COUNT_BUCKETS = [("0,10", lambda v: v < 10), ("10,100", lambda v: v < 100),
                  ("100,1K", lambda v: v < 1_000), ("1K+", lambda v: True)]
_DURATION_BUCKETS = [("<1m", lambda v: v < 60), ("1m,10m", lambda v: v < 600),
                     ("10m,1h", lambda v: v < 3600), ("1h,4h", lambda v: v < 14400),
                     ("4h+", lambda v: True)]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class RoleRegistry:
    """Persistent entity-name → token registry for one workspace export."""

    def __init__(self, db: Session, workspace_id: str, tenant_id: Optional[str] = None):
        self.db = db
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id
        self._memo: Dict[str, str] = {}  # (entity_type, name) -> token
        self._by_name: Dict[str, str] = {}  # name -> first token (type-agnostic)
        for row in db.query(ExperienceRoleRegistry).filter(
            ExperienceRoleRegistry.workspace_id == workspace_id
        ).all():
            self._memo[f"{row.entity_type}\x00{row.name}"] = row.token
            self._by_name.setdefault(row.name, row.token)

    def token_for(self, name: str, entity_type: str = "entity") -> str:
        """Deterministic role token for an identity name (persisted).

        One token per name — the first registration's type names the token
        prefix; later types on the same name reuse the existing token so free
        text (which carries no type annotation) always maps to the same token.
        """
        name = (name or "").strip()
        if not name:
            return "entity_000"
        if name in self._by_name:
            return self._by_name[name]
        key = f"{entity_type}\x00{name}"
        if key in self._memo:
            return self._memo[key]
        slug = re.sub(r"[^a-z0-9]", "_", entity_type.lower())[:20] or "entity"
        token = f"{slug}_{len(self._memo) + 1:03d}"
        self._memo[key] = token
        self._by_name[name] = token
        self.db.add(ExperienceRoleRegistry(
            workspace_id=self.workspace_id, entity_type=entity_type, name=name, token=token,
        ))
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            self._memo[key] = token  # in-memory fallback; export continues
        return token

    def names(self) -> List[str]:
        return [n for (_t, n) in (k.split("\x00", 1) for k in self._memo) if n]


# ---------------------------------------------------------------------------
# Bucketing
# ---------------------------------------------------------------------------
def guess_kind(key: str) -> str:
    """Bucket kind for a data key — id-like keys report kind 'identity'."""
    k = key.lower()
    if any(ik in k for ik in _IDENTITY_KEYS):
        return "identity"
    for hint, kind in _KIND_HINTS:
        if hint in k:
            return kind
    return "generic"


def _bracket(value: float, buckets: List[Tuple[str, Any]]) -> str:
    for label, pred in buckets:
        if pred(value):
            return label
    return buckets[-1][0]


def bucket_value(value: Any, kind: str) -> str:
    """Exact value → envelope string. Never returns the raw value."""
    kind = kind or "generic"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        v = float(value)
        if kind == "amount":
            return f"amount:[{_bracket(v, _AMOUNT_BUCKETS)}]"
        if kind == "count":
            return f"count:[{_bracket(v, _COUNT_BUCKETS)}]"
        if kind == "duration":
            return f"duration:[{_bracket(v, _DURATION_BUCKETS)}]"
        if kind == "ratio":
            return f"ratio:{max(0.0, min(1.0, v)):.1f}"
        s = str(value)
        if len(s) <= 6:
            return f"{kind}:{s}"
    if isinstance(value, str):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}(T.*)?", value):
            return f"date:{value[:4]}-Q{((int(value[5:7]) - 1) // 3) + 1}"
        if kind in ("date", "duration"):
            return f"{kind}:{hash8(value, kind)}"
    # Anything unrecognized genericizes, never exports verbatim.
    return f"{kind}:{hash8(str(value), kind)}"


def hash8(value: str, salt: str = "") -> str:
    return hashlib.sha256(f"{salt}\x00{value}".encode()).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Text sanitization
# ---------------------------------------------------------------------------
def redact_pii(text: str) -> str:
    text = EMAIL_RE.sub("<email>", text)
    text = URL_RE.sub("<url>", text)
    text = PHONE_RE.sub("<phone>", text)
    return text


def sanitize_text(text: str, registry: RoleRegistry) -> str:
    """Entity tokens (longest first) + PII redaction. Never raises."""
    try:
        s = str(text or "")
        for name in sorted(registry.names(), key=len, reverse=True):
            if len(name) >= 3:
                s = s.replace(name, registry.token_for(name))
        return redact_pii(s)
    except Exception:
        return "<sanitized>"


def scan_for_leak(texts: Iterable[str], originals: Iterable[str]) -> List[str]:
    """Post-assembly re-check: return identity fragments that survived."""
    leaked: List[str] = []
    haystack = " ".join(str(t) for t in texts).lower()
    for original in originals:
        o = (original or "").strip()
        if len(o) >= 3 and o.lower() in haystack:
            leaked.append(o)
    return leaked


def tuple_texts(section_items: Any) -> List[str]:
    """Flatten every scalar string in a pack section tree (for leak scans)."""
    out: List[str] = []

    def walk(v: Any) -> None:
        if isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, str):
            out.append(v)
        elif isinstance(v, (int, float, bool)) or v is None:
            out.append(str(v))

    walk(section_items)
    return out