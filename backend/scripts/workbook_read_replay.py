#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run the workbook incident as a revision-stable closure replay.

The replay sends the original two-turn conversation, reads the persisted
pending-file state and trace, and evaluates the final reply against the
workbook evidence contract. It exits nonzero unless every closure condition
passes on one unchanged serving revision.

Turn 2 may acknowledge that the WorkDrive read is still pending; turn 3 then
returns the saved answer. That saved answer is accepted in the delivered
markdown-bullet form, one exact status per requested item:

* ``- **U-22** — 1,777 'List Price' (LINMAC sheet, row 26, cell C26)``
* ``- **622** — 10 possible rows (...)``
* ``- **U-38** — no match in this copy``

The synchronous table contract is still enforced when turn 2 delivers, and
the opt-in strict WorkDrive proof still binds the result to this execution,
the exact resource id, and the downloaded bytes' SHA-256. Real runs can
extend the bounded saved-answer wait with ``--delivery-wait-seconds``.

A DIRECT DELIVERY run (the issue-620 acceptance shape) may instead answer on
turn 1: the first turn's task is ``delivered`` with a ``retrieved`` result,
and the confirmation and retry turns both re-deliver the SAME saved answer
(``delivered``/``delivered``). ``--direct-delivery`` (or a strict run whose
first turn already delivered) additionally requires byte-identical
structured replies on all three turns, the formatter's quantitative
"searched all N sheets of this copy" claim to match the persisted record's
``coverage.indexed_sheets``, the "downloaded copy of <workbook>" source claim
to name that record's file, and the strict proof to match the exact resource
id and SHA-256. A saved-copy-only answer, a re-rendered retry, or an
unverifiable coverage/source claim fails closed.

Two authentication modes are supported:

* ``--token-file PATH`` reads a server-issued bearer token from an explicit
  private file (``chmod 600``). No ambient token paths are consulted, the
  local database/.env is never opened to mint a token, and the value is never
  printed.
* With no ``--token-file`` the existing scratch invocation mints an admin
  token locally, exactly as before.

In both modes the caller identity is resolved with the existing authenticated
``GET /api/auth/me`` endpoint, and the server-returned user id is the identity
the replay sends. An unverified session fails closed.
"""
import argparse
import asyncio
import json
import math
import os
import re
import stat
import sys
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple, cast

import httpx


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

BASE_DEFAULT = "http://127.0.0.1:8001"
TARGETS = (
    "381", "U-22", "622", "SLE24-16", "GSL48-16", "GSL24-16", "SLE16-8", "U-38",
)
FILE_NAME = "Consolidated Price List 2019.xlsx"
ORIGINAL_ASK = (
    "find the prices of these 8 machines in Consolidated Price List "
    "2019.xlsx: 381, U-22, 622, SLE24-16, GSL48-16, GSL24-16, SLE16-8 "
    "and U-38"
)
CONFIRMATION = "That filename is correct"
RETRY_CONFIRMATION = "go"

IDENTITY_ENDPOINT = "/api/auth/me"
TOKEN_FILE_MAX_BYTES = 8192

#: The async saved answer can land a moment after turn 2. Real runs may need a
#: longer bound than the unit-test default, but a replay must never hang on a
#: missing delivery.
DEFAULT_DELIVERY_WAIT_SECONDS = 5.0
MAX_DELIVERY_WAIT_SECONDS = 120.0

#: A saved answer is delivered as markdown bullets, one per requested item:
#: ``- **U-22** — 1,777 'List Price' (LINMAC sheet, row 26, cell C26)``,
#: ``- **622** — 10 possible rows (...)`` or
#: ``- **U-38** — no match in this copy``.
BULLET_OUTCOME_RE = re.compile(
    r"^\s*[-*]\s+\*\*(?P<item>[^*]+?)\*\*\s*[—–-]\s*(?P<text>.+?)\s*$"
)
POSSIBLE_ROWS_RE = re.compile(r"\b(\d+)\s+possible\s+rows?\b", re.IGNORECASE)
SAVED_COPY_PROVENANCE_RE = re.compile(
    r"from the (?:saved|downloaded) copy of\s+", re.IGNORECASE
)
DOWNLOADED_COPY_RE = re.compile(
    r"from the downloaded copy of\s*", re.IGNORECASE
)
COVERAGE_OF_COPY_RE = re.compile(
    r"searched all (?P<count>\d+) sheets? of this copy", re.IGNORECASE
)
COPY_SCOPE_RE = re.compile(r"about this copy", re.IGNORECASE)


class TokenFileError(RuntimeError):
    """The explicit token file is missing, unreadable, or not private."""


def read_token_file(path: str) -> str:
    """Read a server-issued bearer token from an explicit private file.

    The path must be supplied by the operator; there is no ambient default.
    On POSIX the file must not be accessible by group/other, so a token
    cannot be picked up from a shared location. Errors name the path but
    never include the token value.
    """
    if not path:
        raise TokenFileError("no token file path was provided")
    resolved = os.path.realpath(path)
    if not os.path.isfile(resolved):
        raise TokenFileError(f"token file is not a regular file: {path}")
    if os.name == "posix":
        mode = stat.S_IMODE(os.stat(resolved).st_mode)
        if mode & 0o077:
            raise TokenFileError(
                "token file must be private (chmod 600): "
                f"{path} has mode {mode:04o}"
            )
    size = os.path.getsize(resolved)
    if size <= 0:
        raise TokenFileError(f"token file is empty: {path}")
    if size > TOKEN_FILE_MAX_BYTES:
        raise TokenFileError(
            f"token file is larger than {TOKEN_FILE_MAX_BYTES} bytes: {path}"
        )
    try:
        with open(resolved, "r", encoding="utf-8") as handle:
            raw = handle.read()
    except UnicodeDecodeError as exc:
        raise TokenFileError(f"token file is not UTF-8 text: {path}") from exc
    except OSError as exc:
        raise TokenFileError(
            f"could not read token file {path}: {type(exc).__name__}"
        ) from exc
    token = raw.strip()
    if not token:
        raise TokenFileError(f"token file is empty: {path}")
    if any(character.isspace() for character in token):
        raise TokenFileError(
            f"token file must contain exactly one token line: {path}"
        )
    return token


def identity_payload(payload: Any) -> Dict[str, Any]:
    """Unwrap the shapes returned by the existing ``/api/auth/me`` route."""
    if not isinstance(payload, dict):
        return {}
    for key in ("user", "data"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            merged = dict(nested)
            for name in ("user_id", "id", "role", "workspace_id", "tenant_id"):
                if name not in merged and name in payload:
                    merged[name] = payload[name]
            return merged
    return dict(payload)


def identity_user_id(payload: Any) -> str:
    identity = identity_payload(payload)
    for key in ("user_id", "id", "sub"):
        value = identity.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def identity_summary(payload: Any) -> Dict[str, str]:
    """Return only non-secret identity fields (never email or the token)."""
    identity = identity_payload(payload)
    summary: Dict[str, str] = {}
    for key in ("user_id", "role", "workspace_id", "tenant_id"):
        value = identity.get(key)
        if value not in (None, ""):
            summary[key] = str(value)
    if "user_id" not in summary:
        user_id = identity_user_id(payload)
        if user_id:
            summary["user_id"] = user_id
    return summary


async def verify_session(
    client: httpx.AsyncClient,
    base: str,
    token: str,
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """Verify the bearer token through the server's authenticated identity API.

    The token travels only in the Authorization header. Neither returned
    mapping contains it, so callers can safely print or persist the metadata.
    """
    meta: Dict[str, Any] = {
        "verified": False,
        "status_code": None,
        "error": "",
    }
    try:
        response = await client.get(
            f"{base}{IDENTITY_ENDPOINT}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
    except Exception as exc:
        # Never format the request/headers into the error: they hold the token.
        meta["error"] = f"identity request failed: {type(exc).__name__}"
        return {}, meta
    meta["status_code"] = response.status_code
    if response.status_code != 200:
        meta["error"] = (
            "identity endpoint rejected the session "
            f"(HTTP {response.status_code})"
        )
        return {}, meta
    try:
        payload = response.json()
    except Exception:
        meta["error"] = "identity endpoint returned invalid JSON"
        return {}, meta
    identity = identity_summary(payload)
    if not identity.get("user_id"):
        meta["error"] = "identity response did not include a user id"
        return {}, meta
    meta["verified"] = True
    return identity, meta


async def resolve_session(
    client: httpx.AsyncClient,
    base: str,
    token_file: Optional[str],
) -> Tuple[Optional[str], Dict[str, str], Dict[str, Any]]:
    """Resolve a bearer token and the server-confirmed identity behind it.

    With ``token_file`` the token comes from that explicit private file and
    the scratch mint/DB/.env path is not touched. Without it the existing
    scratch invocation mints locally. In both cases the server's identity
    endpoint must confirm the caller before the replay runs.
    """
    mode = "token-file" if token_file else "scratch-mint"
    if token_file:
        try:
            token = read_token_file(token_file)
        except TokenFileError as exc:
            return None, {}, {
                "mode": mode,
                "verified": False,
                "status_code": None,
                "error": str(exc),
            }
    else:
        token, _minted_user_id = mint_token()
        if not token:
            return None, {}, {
                "mode": mode,
                "verified": False,
                "status_code": None,
                "error": "could not mint token (admin@example.com missing)",
            }
    identity, meta = await verify_session(client, base, token)
    meta["mode"] = mode
    if not identity:
        return None, {}, meta
    return token, identity, meta


def auth_report(
    auth_meta: Dict[str, Any],
    identity: Dict[str, str],
) -> Dict[str, Any]:
    """Auth provenance for the closure report (no bearer token, no email)."""
    return {
        "mode": str(auth_meta.get("mode") or ""),
        "identity_verified": bool(auth_meta.get("verified")),
        "identity_status_code": auth_meta.get("status_code"),
        "user_id": str(identity.get("user_id") or ""),
    }


def bounded_delivery_wait(value: Any) -> float:
    """Clamp an operator-supplied saved-answer wait to a finite safe bound."""
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return DEFAULT_DELIVERY_WAIT_SECONDS
    if not math.isfinite(seconds):
        return DEFAULT_DELIVERY_WAIT_SECONDS
    return min(max(0.0, seconds), MAX_DELIVERY_WAIT_SECONDS)


def mint_token() -> Tuple[Optional[str], Optional[str]]:
    try:
        from dotenv import load_dotenv

        for filename in (
            os.path.join(PROJECT_ROOT, ".env"),
            os.path.join(PROJECT_ROOT, ".env.local"),
        ):
            if os.path.exists(filename):
                load_dotenv(filename, override=filename.endswith(".env.local"))
    except Exception:
        pass

    from core.auth import create_access_token
    from core.database import get_db_session
    from core.models import User

    with get_db_session() as db:
        user = db.query(User).filter(User.email == "admin@example.com").first()
        if user is None:
            return None, None
        user_id, email = str(user.id), user.email
        role = getattr(user, "role", None)
        role = getattr(role, "value", role)
    return create_access_token({
        "sub": user_id,
        "user_id": user_id,
        "email": email,
        "role": str(role or "workspace_admin"),
    }), user_id


async def turn(
    client: httpx.AsyncClient,
    base: str,
    token: str,
    user_id: str,
    session_id: str,
    message: str,
) -> Dict[str, Any]:
    response = await client.post(
        f"{base}/api/chat/message",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": message, "session_id": session_id, "user_id": user_id},
        timeout=240,
    )
    response.raise_for_status()
    return cast(Dict[str, Any], response.json())


async def trace(
    client: httpx.AsyncClient,
    base: str,
    token: str,
    session_id: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    response = await client.get(
        f"{base}/api/chat/trace/{session_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if response.status_code != 200:
        return [], {
            "status_code": response.status_code,
            "error": response.text[:500],
        }
    return flatten_trace(response.json()), {"status_code": 200, "error": ""}


def flatten_trace(payload: Any) -> List[Dict[str, Any]]:
    """Flatten the chat trace API's runs[].steps and older flat responses."""
    if isinstance(payload, list):
        list_result: List[Dict[str, Any]] = []
        for item in payload:
            list_result.extend(flatten_trace(item))
        return list_result
    if not isinstance(payload, dict):
        return []

    if isinstance(payload.get("step_type"), str) or "observation" in payload:
        return [payload]

    result: List[Dict[str, Any]] = []
    runs = payload.get("runs")
    if isinstance(runs, list):
        for run in runs:
            result.extend(flatten_trace(run))
    if "steps" in payload:
        result.extend(flatten_trace(payload.get("steps")))
    for key in ("trace", "data", "result"):
        if key in payload and payload[key] is not payload:
            result.extend(flatten_trace(payload[key]))
    if not result and any(key in payload for key in ("step_type", "observation", "action")):
        result.append(payload)
    return result


def summarize_step(step: Dict[str, Any]) -> str:
    kind = step.get("step_type") or step.get("type") or "?"
    action = step.get("action") or {}
    if isinstance(action, dict):
        tool = action.get("tool") or "?"
        params = action.get("params") or {}
    else:
        tool = str(action or "?")
        params = {}
    observation = str(step.get("observation") or "")[:220].replace("\n", " ")
    return f"[{kind}] {tool} {json.dumps(params, default=str)[:140]} :: {observation}"


def pending_state(session_id: str) -> Dict[str, Any]:
    """Read the durable assistant-row task marker without writing the DB."""
    try:
        from core.database import get_db_session
        from core.models import ChatMessage

        with get_db_session() as db:
            rows = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.conversation_id == session_id,
                    ChatMessage.role == "assistant",
                )
                .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
                .limit(24)
                .all()
            )
        for row in rows:
            raw = getattr(row, "metadata_json", None)
            if isinstance(raw, str):
                try:
                    metadata = json.loads(raw or "{}")
                except json.JSONDecodeError:
                    metadata = {}
            elif isinstance(raw, dict):
                metadata = raw
            else:
                metadata = {}
            task = metadata.get("pending_file_task") or metadata.get("_pending_file_task")
            result = metadata.get("pending_file_result") or metadata.get("_pending_file_result")
            if isinstance(task, dict):
                return {
                    "status": task.get("status"),
                    "result_status": result.get("status") if isinstance(result, dict) else None,
                    "task": task,
                    "result": result,
                    "read_error": "",
                }
        return {
            "status": None,
            "result_status": None,
            "task": None,
            "result": None,
            "read_error": "",
        }
    except Exception as exc:
        return {
            "status": None,
            "result_status": None,
            "task": None,
            "result": None,
            "read_error": f"{type(exc).__name__}: {exc}",
        }


def wait_for_delivery(session_id: str, timeout: float = 3.0) -> Dict[str, Any]:
    deadline = time.monotonic() + max(0.0, timeout)
    state = pending_state(session_id)
    while (
        time.monotonic() < deadline
        and state.get("result_status") not in ("delivered", "served")
        and state.get("status") not in ("delivered", "served")
    ):
        time.sleep(0.1)
        state = pending_state(session_id)
    return state


def wait_for_saved_result(session_id: str, timeout: float = 5.0) -> Dict[str, Any]:
    """Wait until the asynchronous read has persisted a saved result.

    Turn 2 may only acknowledge; the durable result it started can land a
    moment later. Waiting here gives the no-reread proof a baseline to
    compare against before turn 3 delivers it.
    """
    deadline = time.monotonic() + max(0.0, timeout)
    state = pending_state(session_id)
    while time.monotonic() < deadline:
        result = state.get("result")
        if isinstance(result, dict) and result.get("identity"):
            break
        time.sleep(0.1)
        state = pending_state(session_id)
    return state


def identity_from_health(payload: Dict[str, Any]) -> Dict[str, Any]:
    identity = payload.get("identity") if isinstance(payload, dict) else {}
    return identity if isinstance(identity, dict) else {}


def same_revision(before: Dict[str, Any], after: Dict[str, Any]) -> bool:
    keys = ("instance_id", "source_id", "revision", "started_at", "pid")
    return all(before.get(key) == after.get(key) for key in keys)


def clean_cell(value: str) -> str:
    return re.sub(r"[`*_]", "", str(value or "")).strip()


def outcome_kind(status: str, evidence: str = "") -> str:
    """Collapse a rendered outcome into found / ambiguous / absent."""
    text = f"{status} {evidence}".upper()
    if "AMBIGUOUS" in text or POSSIBLE_ROWS_RE.search(evidence or ""):
        return "ambiguous"
    if any(token in text for token in (
            "ABSENT", "NOT FOUND", "INCOMPLETE", "NO MATCH")):
        return "absent"
    return "found"


def parse_table_outcomes(reply: str) -> List[Dict[str, Any]]:
    """The synchronous table contract (``| item | outcome | evidence |``)."""
    target_map = {target.lower(): target for target in TARGETS}
    outcomes: List[Dict[str, Any]] = []
    for line in str(reply or "").splitlines():
        if "|" not in line:
            continue
        cells = [clean_cell(cell) for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        target = target_map.get(cells[0].lower())
        if target is None:
            continue
        outcomes.append({
            "target": target,
            "status": cells[1],
            "evidence": cells[2],
            "kind": outcome_kind(cells[1], cells[2]),
            "format": "table",
        })
    return outcomes


def parse_bullet_outcomes(reply: str) -> List[Dict[str, Any]]:
    """The saved-answer contract: one markdown bullet per requested item."""
    target_map = {target.lower(): target for target in TARGETS}
    outcomes: List[Dict[str, Any]] = []
    for line in str(reply or "").splitlines():
        match = BULLET_OUTCOME_RE.match(line)
        if match is None:
            continue
        target = target_map.get(clean_cell(match.group("item")).lower())
        if target is None:
            continue
        evidence = clean_cell(match.group("text"))
        kind = outcome_kind("", evidence)
        status = {
            "absent": "NOT FOUND IN INDEXED CONTENT",
            "ambiguous": "AMBIGUOUS",
            "found": "FOUND",
        }[kind]
        outcomes.append({
            "target": target,
            "status": status,
            "evidence": evidence,
            "kind": kind,
            "format": "bullet",
        })
    return outcomes


def parse_outcomes(reply: str) -> List[Dict[str, Any]]:
    """Parse either delivery shape, preserving exact requested targets.

    Tables remain the synchronous contract; bullets are the saved-answer
    contract. When both appear the table row wins (it is the explicit,
    machine-facing form), but a target is never counted twice.
    """
    outcomes = parse_table_outcomes(reply)
    seen = {row["target"] for row in outcomes}
    for row in parse_bullet_outcomes(reply):
        if row["target"] not in seen:
            outcomes.append(row)
            seen.add(row["target"])
    return outcomes


def _lineage_ok(row: Dict[str, Any]) -> bool:
    """Exact sheet/cell lineage, in either delivery shape."""
    evidence = str(row.get("evidence") or "")
    if re.search(r"(?:!\$?[A-Z]{1,3}\$?\d+|\bR\d{1,6}\b)", evidence,
                 re.IGNORECASE):
        return True
    if row.get("format") != "bullet":
        return False
    return bool(
        re.search(r"\bcell\s+[A-Z]{1,3}\d{1,7}\b", evidence, re.IGNORECASE)
        or re.search(r"\b[A-Za-z0-9_ -]+ sheet,\s*row\s+\d+", evidence,
                     re.IGNORECASE)
        or re.search(r"\bmatched at\s+[A-Z]{1,3}\d{1,7}\b", evidence,
                     re.IGNORECASE)
    )


def quantified_coverage(reply: str) -> Optional[int]:
    """The ``N`` in the formatter's "searched all N sheets of this copy"."""
    match = COVERAGE_OF_COPY_RE.search(str(reply or ""))
    if match is None:
        return None
    try:
        count = int(match.group("count"))
    except (TypeError, ValueError):
        return None
    return count if count > 0 else None


def _coverage_counts(
    structured_result: Any,
) -> Tuple[Optional[int], Optional[int]]:
    """``(indexed_sheets, scanned_sheets)`` from the persisted record."""
    if not isinstance(structured_result, dict):
        return None, None
    coverage = structured_result.get("coverage")
    if not isinstance(coverage, dict):
        return None, None

    def _as_int(value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    return (
        _as_int(coverage.get("indexed_sheets")),
        _as_int(coverage.get("scanned_sheets")),
    )


def coverage_claim_is_truthful(
    reply: str,
    structured_result: Any,
) -> bool:
    """Does the formatter's sheet count match the persisted evidence?

    The saved answer says "searched all N sheets of this copy". That is a
    quantitative claim about the record, so N must equal the record's
    ``coverage.indexed_sheets`` (and ``scanned_sheets`` when present). A
    plausible-looking number is not coverage proof.
    """
    claimed = quantified_coverage(reply)
    indexed, scanned = _coverage_counts(structured_result)
    if claimed is None or indexed is None or claimed != indexed:
        return False
    if scanned is not None and scanned != claimed:
        return False
    return True


def source_claim_is_truthful(
    reply: str,
    structured_result: Any,
) -> bool:
    """Does every "downloaded copy of ..." claim name THIS record's file?

    The formatter emits the claim twice (opening and footer). Each occurrence
    must be followed by the persisted ``source_identity.file_name``. A
    different workbook name, or a claim that only says "saved copy", is not
    evidence that the delivered answer came from the verified download.
    """
    if not isinstance(structured_result, dict):
        return False
    source_identity = structured_result.get("source_identity")
    if not isinstance(source_identity, dict):
        return False
    expected = str(source_identity.get("file_name") or "").strip()
    if not expected:
        return False
    text = str(reply or "")
    matches = list(DOWNLOADED_COPY_RE.finditer(text))
    if not matches:
        return False
    expected_lower = expected.lower()
    for match in matches:
        remainder = text[match.end():].lstrip()
        if not remainder.lower().startswith(expected_lower):
            return False
        tail = remainder[len(expected):]
        # The formatter continues with ":" or " —"; a saved-date parenthetical
        # is allowed. A different file name is not.
        if tail and tail[0] not in " :—–(\n,":
            return False
    return True


def deterministic_delivery(payload: Any) -> bool:
    """The turn was served from structured evidence, not model narration."""
    if not isinstance(payload, dict):
        return False
    data = payload.get("data") or {}
    return bool(
        (isinstance(data, dict) and data.get("deterministic_delivery"))
        or payload.get("model") in ("deterministic", "structured")
    )


def _state_is_delivered(state: Any) -> bool:
    return bool(
        isinstance(state, dict)
        and state.get("status") == "delivered"
        and state.get("result_status") == "delivered"
    )


def resolve_direct_source_proof(result: Any) -> Optional[Dict[str, Any]]:
    """The strict direct-download proof carried by a persisted read result.

    Live reads have carried the proof at the top level, nested inside
    ``identity``, and nested inside ``structured_result``. They are the same
    proof, so resolve them the same way everywhere instead of requiring one
    particular placement.
    """
    if not isinstance(result, dict):
        return None
    proof = result.get("direct_source_proof")
    if isinstance(proof, dict):
        return proof
    identity = result.get("identity")
    if isinstance(identity, dict):
        proof = identity.get("direct_source_proof")
        if isinstance(proof, dict):
            return proof
    structured = result.get("structured_result")
    if isinstance(structured, dict):
        proof = structured.get("direct_source_proof")
        if isinstance(proof, dict):
            return proof
    return None


def _persisted_read_evidence(result: Any) -> Dict[str, Any]:
    """The read fields that must not change across a re-delivery retry.

    The proof is resolved with :func:`resolve_direct_source_proof` so a live
    read that only carries it nested (identity or structured result) compares
    on equal terms with one that also has a top-level copy.
    """
    result = result if isinstance(result, dict) else {}
    return {
        "identity": result.get("identity"),
        "structured_result": result.get("structured_result"),
        "direct_source_proof": resolve_direct_source_proof(result),
        "execution_id": result.get("execution_id"),
        "retrieved_at": result.get("retrieved_at"),
        "attempt_id": result.get("attempt_id"),
        "evidence_revision": result.get("evidence_revision"),
    }


def pending_acknowledgement(
    reply: str,
    state: Dict[str, Any],
) -> bool:
    """Turn 2 acknowledged pending work instead of delivering a result.

    The durable task is still ``pending`` and the reply carries no rendered
    per-item outcome. This is only accepted when a later turn (turn 3) is
    supplied to the evaluator and that turn delivers the saved answer.
    """
    if not str(reply or "").strip():
        return False
    if not isinstance(state, dict) or state.get("status") != "pending":
        return False
    return not parse_outcomes(reply)


def trace_text(steps: Iterable[Dict[str, Any]]) -> str:
    return json.dumps(list(steps), ensure_ascii=False, default=str).lower()


def evaluate(
    identity_before: Dict[str, Any],
    identity_after: Dict[str, Any],
    r1: Dict[str, Any],
    r2: Dict[str, Any],
    steps: List[Dict[str, Any]],
    trace_meta: Dict[str, Any],
    state_after_1: Dict[str, Any],
    state_after_2: Dict[str, Any],
    expected_revision: str = "",
    outage_mode: bool = False,
    strict_workdrive_proof: bool = False,
    expected_resource_id: str = "",
    expected_sha256: str = "",
    r3: Optional[Dict[str, Any]] = None,
    state_after_3: Optional[Dict[str, Any]] = None,
    direct_delivery: bool = False,
) -> Dict[str, Any]:
    state_after_1 = state_after_1 if isinstance(state_after_1, dict) else {}
    state_after_2 = state_after_2 if isinstance(state_after_2, dict) else {}
    state_after_3 = state_after_3 if isinstance(state_after_3, dict) else {}
    # DIRECT DELIVERY (issue 620 acceptance): turn 1 already answered and the
    # confirmation/retry turns re-delivered the SAME saved answer. This is
    # auto-detected from the observed state for strict runs, and can be forced
    # with ``--direct-delivery``. A direct run is always held to the strict
    # proof contract; there is no direct delivery without it.
    direct_delivery_mode = bool(
        direct_delivery
        or (
            strict_workdrive_proof
            and state_after_1.get("status") == "delivered"
        )
    )
    if direct_delivery_mode:
        strict_workdrive_proof = True
    # ASYNC WORKDRIVE DELIVERY (issue 620): turn 2 may only acknowledge that
    # the saved read is still pending; turn 3 then returns the persisted
    # answer. The synchronous path is unchanged: with no turn-3 payload the
    # turn-2 reply must still carry the complete table itself.
    async_ack = (
        isinstance(r3, dict)
        and pending_acknowledgement(str(r2.get("message") or ""),
                                    state_after_2)
    )
    delivered = r3 if async_ack and isinstance(r3, dict) else r2
    reply = str(delivered.get("message") or "")
    lower = reply.lower()
    rows = parse_outcomes(reply)
    by_target = {row["target"]: row for row in rows}
    trace_blob = trace_text(steps)
    workbook_name = FILE_NAME.lower()
    source_refs = bool(
        re.search(r"resource[=_ ]", lower)
        and re.search(r"content[ _-]?hash[=_ ]", lower)
        and re.search(r"ingest(?:ed|ion)?[=_ ]", lower)
    )
    foreign_files = [
        name for name in re.findall(r"[^\n|]*\.xlsx", reply, re.IGNORECASE)
        if workbook_name not in name.lower()
    ]
    found_rows = [row for row in rows if row.get("kind") == "found"]
    missing_rows = [row for row in rows if row.get("kind") == "absent"]
    bullet_rows = parse_bullet_outcomes(reply)
    table_rows = parse_table_outcomes(reply)
    saved_copy_provenance = bool(
        SAVED_COPY_PROVENANCE_RE.search(reply)
        and workbook_name in lower
    )
    downloaded_copy_provenance = bool(
        DOWNLOADED_COPY_RE.search(reply)
        and workbook_name in lower
    )
    coverage_of_copy = bool(COVERAGE_OF_COPY_RE.search(reply))
    quantified_sheets = quantified_coverage(reply)
    copy_scope_stated = bool(COPY_SCOPE_RE.search(reply))
    protocol_tokens = (
        "live tool results", "file_search", "pending file task",
        "workbook read artifact", "sql result", "reproduce verbatim",
        "<tool_call", "</tool_call", "tool_call", "recalculate",
    )
    arithmetic_tokens = (
        "i calculated", "i computed", "interpolat", "recalculate",
        "re-derive", "multiply by", "divided by", "×", "÷",
    )
    deterministic_delivery_turn = deterministic_delivery(delivered)
    delivered_state = state_after_3 if async_ack else state_after_2
    checks = {
        "revision_stable": same_revision(identity_before, identity_after),
        "expected_revision": not expected_revision or identity_after.get("revision") == expected_revision,
        "turn1_success": bool(r1.get("success")) or (
            outage_mode and state_after_1.get("status") == "pending"
        ),
        "turn2_success": bool(r2.get("success")) or (
            outage_mode and deterministic_delivery_turn
        ),
        "pending_after_turn1": state_after_1.get("status") == "pending",
        "pending_served_after_turn2": (
            state_after_2.get("status") in (
                "retrieved", "served", "delivered",
            )
            or async_ack
        ),
        "delivery_state_accounted_for": (
            (
                state_after_3.get("status") == "delivered"
                and state_after_3.get("result_status") == "delivered"
            )
            if async_ack else (
                state_after_2.get("result_status") in ("retrieved", "delivered")
                or state_after_2.get("status") in (
                    "retrieved", "served", "delivered",
                )
            )
        ),
        "pending_state_readable": (
            not state_after_1.get("read_error")
            and not state_after_2.get("read_error")
        ),
        "trace_original_ask": deterministic_delivery_turn or (
            workbook_name in trace_blob and any(
                target.lower() in trace_blob for target in TARGETS
            )
        ),
        "trace_storage_or_datasets": deterministic_delivery_turn or any(
            token in trace_blob for token in ("datasets", "storage", "workdrive")
        ),
        "trace_readable": trace_meta.get("status_code") == 200,
        "direct_structured_delivery": deterministic_delivery_turn,
        "eight_structured_outcomes": len(rows) == len(TARGETS) and set(by_target) == set(TARGETS),
        "found_outcomes": len(found_rows) >= 1,
        "missing_outcomes": len(missing_rows) == 3,
        "delivered_statuses": all(
            row.get("kind") in ("found", "ambiguous", "absent")
            for row in rows
        ),
        "price_and_sheet_cell_lineage": all(
            _lineage_ok(row) and bool(re.search(r"\d", row["evidence"]))
            for row in found_rows
        ),
        "coverage_present": (
            ("coverage" in lower and "indexed content" in lower)
            or (async_ack and coverage_of_copy)
            or (direct_delivery_mode and quantified_sheets is not None)
        ),
        "misses_are_scoped": all(
            "indexed content" in row["evidence"].lower()
            or "indexed content" in lower
            or (async_ack and (
                "no match in this copy" in row["evidence"].lower()
                or "about this copy" in lower
            ))
            or (direct_delivery_mode and (
                "no match in this copy" in row["evidence"].lower()
                and copy_scope_stated
            ))
            for row in missing_rows
        ),
        "provenance_present": (
            (source_refs and (
                "materialized copy" in lower
                or (strict_workdrive_proof and "downloaded" in lower)
            ))
            or (async_ack and saved_copy_provenance)
            or (direct_delivery_mode and downloaded_copy_provenance)
        ),
        "named_file_only": not foreign_files and workbook_name in lower,
        "no_protocol_leakage": not any(token in lower for token in protocol_tokens),
        "no_model_arithmetic": not any(token in lower for token in arithmetic_tokens),
        "no_absolute_absence": not any(
            phrase in lower for phrase in (
                "absent from the workbook", "does not exist in the workbook",
                "the workbook does not contain", "not present in the workbook",
            )
        ),
    }
    if async_ack:
        # The saved answer is the turn-3 delivery, in markdown bullets, one
        # exact status per requested item. A table is the synchronous shape,
        # not this one.
        checks.update({
            "turn2_acknowledgement": True,
            "turn3_success": bool(delivered.get("success")),
            "turn3_delivered": (
                state_after_3.get("status") == "delivered"
                and state_after_3.get("result_status") == "delivered"
            ),
            "markdown_bullets": (
                len(bullet_rows) == len(TARGETS) and not table_rows
            ),
            "delivered_answer_is_saved_result": bool(
                (state_after_3.get("result") or {}).get("delivery_pin")
            ),
        })
        if strict_workdrive_proof:
            checks["strict_answer_not_materialized"] = (
                "materialized copy" not in lower
            )
    if direct_delivery_mode:
        # DIRECT DELIVERY ACCEPTANCE (issue 620): the live Canadian run
        # answered on turn 1 (delivered/retrieved), then turns 2 and 3 both
        # re-delivered the same structured answer (delivered/delivered). The
        # saved answer is the formatter's downloaded-copy output, so the
        # coverage count and source name are quantitative claims that must
        # join to the persisted record, not merely look plausible.
        direct_result = (
            delivered_state.get("result")
            if isinstance(delivered_state, dict) else None
        )
        direct_structured = (
            direct_result.get("structured_result")
            if isinstance(direct_result, dict) else None
        )
        direct_evidence = [
            _persisted_read_evidence(
                state.get("result") if isinstance(state, dict) else None)
            for state in (state_after_1, state_after_2, state_after_3)
        ]
        direct_same_read = bool(
            direct_evidence[0].get("identity")
            and direct_evidence[0].get("structured_result")
            and direct_evidence[0].get("direct_source_proof")
            and direct_evidence[0] == direct_evidence[1] == direct_evidence[2]
        )
        direct_messages = [
            str(turn.get("message") or "")
            for turn in (r1, r2, r3 if isinstance(r3, dict) else {})
        ]
        checks.pop("pending_after_turn1", None)
        checks.update({
            "direct_turn1_delivered": (
                state_after_1.get("status") == "delivered"
            ),
            "direct_turn1_result_retrieved": (
                state_after_1.get("result_status") == "retrieved"
            ),
            "direct_turns_2_3_delivered": (
                _state_is_delivered(state_after_2)
                and _state_is_delivered(state_after_3)
            ),
            "direct_identical_reply": bool(
                direct_messages[0]
                and direct_messages[0] == direct_messages[1]
                == direct_messages[2]
            ),
            "direct_deterministic_each_turn": all(
                deterministic_delivery(turn)
                for turn in (r1, r2, r3)
            ),
            "direct_same_persisted_read": direct_same_read,
            "direct_coverage_quantitative_truthful": (
                coverage_claim_is_truthful(reply, direct_structured)
            ),
            "direct_source_claim_truthful": (
                source_claim_is_truthful(reply, direct_structured)
            ),
            "direct_copy_scope_stated": copy_scope_stated,
            "direct_misses_scoped_to_copy": bool(
                missing_rows
                and copy_scope_stated
                and all(
                    "no match in this copy" in row["evidence"].lower()
                    for row in missing_rows
                )
            ),
            "direct_no_saved_copy_claim": (
                "from the saved copy of" not in lower
            ),
            # The acceptance is only meaningful when the exact resource and
            # digest were supplied; otherwise the strict checks cannot bind
            # the proof to the live download.
            "direct_expected_resource_id": bool(expected_resource_id),
            "direct_expected_sha256": bool(expected_sha256),
        })
    if strict_workdrive_proof:
        # OPT-IN STRICT DIRECT WORKDRIVE PROOF (issue 620): the persisted
        # workbook result must carry a direct download from THIS execution,
        # bound to the exact resource id and the SHA-256 of the bytes the
        # answer was derived from. A materialized copy's hash, a filename, or
        # a successful fetch not joined to the returned result is not proof.
        from core.workdrive_direct_proof import (
            strict_workdrive_proof_checks,
        )

        persisted = (
            delivered_state.get("result")
            if isinstance(delivered_state, dict) else None
        )
        persisted = persisted if isinstance(persisted, dict) else {}
        persisted_identity = persisted.get("identity")
        persisted_identity = (
            persisted_identity if isinstance(persisted_identity, dict) else {}
        )
        persisted_structured = persisted.get("structured_result")
        persisted_structured = (
            persisted_structured
            if isinstance(persisted_structured, dict) else None
        )
        proof = resolve_direct_source_proof(persisted)
        checks.update(strict_workdrive_proof_checks(
            proof=proof,
            identity=persisted_identity,
            structured_result=persisted_structured,
            execution_id=str(persisted.get("execution_id") or ""),
            expected_resource_id=expected_resource_id,
            expected_sha256=expected_sha256,
        ))
    return {
        "checks": checks,
        "all_pass": all(checks.values()),
        "async_delivery": bool(async_ack),
        "direct_delivery": bool(direct_delivery_mode),
        "outcomes": rows,
        "foreign_files": foreign_files,
        "reply_length": len(reply),
        "trace_steps": len(steps),
        "trace_meta": trace_meta,
        "pending_after_turn1": state_after_1,
        "pending_after_turn2": state_after_2,
        "pending_after_turn3": state_after_3,
        "strict_workdrive_proof": bool(strict_workdrive_proof),
    }


def evaluate_retry(
    state_after_2: Dict[str, Any],
    state_after_3: Dict[str, Any],
    r3: Dict[str, Any],
    async_delivery: bool = False,
) -> Dict[str, Any]:
    before = state_after_2.get("result") or {}
    after = state_after_3.get("result") or {}
    before_identity = before.get("identity") or {}
    after_identity = after.get("identity") or {}
    before_workbook = before.get("workbook_read") or before_identity.get(
        "workbook_read"
    )
    after_workbook = after.get("workbook_read") or after_identity.get(
        "workbook_read"
    )
    before_proof = before.get("direct_source_proof") or before_identity.get(
        "direct_source_proof"
    )
    after_proof = after.get("direct_source_proof") or after_identity.get(
        "direct_source_proof"
    )
    before_structured = before.get("structured_result")
    after_structured = after.get("structured_result")
    data = r3.get("data") or {}
    deterministic = bool(
        data.get("deterministic_delivery")
        or r3.get("model") in ("deterministic", "structured")
    )
    message = str(r3.get("message") or "")
    pin = after.get("delivery_pin") or {}
    pinned = str(pin.get("delivered_text") or "")
    reread_fields = (
        "execution_id", "retrieved_at", "attempt_id", "evidence_revision",
    )
    same_identity = bool(before_identity) and before_identity == after_identity
    same_read = all(
        before.get(key) == after.get(key) for key in reread_fields
    )
    if before_workbook:
        same_read = same_read and before_workbook == after_workbook
    if before_proof:
        same_read = same_read and before_proof == after_proof
    if isinstance(before_structured, dict):
        same_read = same_read and before_structured == after_structured
    checks = {
        "successful": bool(r3.get("success")),
        "deterministic_delivery": deterministic,
        "eight_structured_outcomes": (
            len(parse_outcomes(message)) == len(TARGETS)
        ),
        "state_delivered": (
            state_after_3.get("status") == "delivered"
            and state_after_3.get("result_status") == "delivered"
        ),
        "no_reread": bool(same_identity and same_read),
    }
    if async_delivery:
        # The saved answer must be served verbatim from the pinned result:
        # a turn-3 re-read would produce a new retrieved_at/execution or a
        # different pin, and the user would see a freshly read answer.
        checks["async_saved_result_available"] = bool(after.get("identity"))
        checks["delivered_answer_pinned"] = bool(
            pinned and pinned == message[:24000]
        )
    return {"checks": checks, "all_pass": all(checks.values())}


def build_report(
    identity_before: Dict[str, Any],
    identity_after: Dict[str, Any],
    r1: Dict[str, Any],
    r2: Dict[str, Any],
    steps: List[Dict[str, Any]],
    trace_meta: Dict[str, Any],
    state_after_1: Dict[str, Any],
    state_after_2: Dict[str, Any],
    expected_revision: str,
    outage_mode: bool = False,
    strict_workdrive_proof: bool = False,
    expected_resource_id: str = "",
    expected_sha256: str = "",
    r3: Optional[Dict[str, Any]] = None,
    state_after_3: Optional[Dict[str, Any]] = None,
    direct_delivery: bool = False,
) -> Dict[str, Any]:
    report = evaluate(
        identity_before, identity_after, r1, r2, steps, trace_meta,
        state_after_1, state_after_2, expected_revision, outage_mode,
        strict_workdrive_proof, expected_resource_id, expected_sha256,
        r3, state_after_3, direct_delivery,
    )
    report["outage_mode"] = outage_mode
    report["strict_workdrive_proof"] = bool(strict_workdrive_proof)
    report["identity_before"] = identity_before
    report["identity_after"] = identity_after
    report["turn1"] = {
        "success": r1.get("success"),
        "model": r1.get("model"),
        "provider": r1.get("provider"),
        "message": str(r1.get("message") or "")[:2000],
    }
    report["turn2"] = {
        "success": r2.get("success"),
        "model": r2.get("model"),
        "provider": r2.get("provider"),
        "message": str(r2.get("message") or "")[:4000],
    }
    if isinstance(r3, dict):
        report["turn3"] = {
            "success": r3.get("success"),
            "model": r3.get("model"),
            "provider": r3.get("provider"),
            "message": str(r3.get("message") or "")[:4000],
        }
    report["trace_summary"] = [summarize_step(step) for step in steps[-30:]]
    return report


async def main_async(args: argparse.Namespace) -> int:
    base = args.base.rstrip("/")
    session_id = f"wb-replay-{int(time.time())}"
    delivery_wait = bounded_delivery_wait(
        getattr(args, "delivery_wait_seconds", DEFAULT_DELIVERY_WAIT_SECONDS)
    )
    report: Dict[str, Any]
    auth_meta: Dict[str, Any] = {}
    session_identity: Dict[str, str] = {}
    async with httpx.AsyncClient() as client:
        try:
            token, session_identity, auth_meta = await resolve_session(
                client, base, getattr(args, "token_file", None)
            )
            if not token:
                print(
                    f"FATAL: {auth_meta.get('error') or 'session not verified'}",
                    file=sys.stderr,
                )
                return 2
            user_id = session_identity["user_id"]

            health_before = (await client.get(f"{base}/api/health", timeout=10)).json()
            identity_before = identity_from_health(health_before)
            print(f"serving instance: {identity_before.get('instance_id') or identity_before.get('source_id')}")
            print(f"revision: {identity_before.get('revision') or 'unknown'}")
            print(
                f"auth mode: {auth_meta.get('mode')} "
                f"(verified user {user_id})"
            )
            print(f"replay session: {session_id}\n")

            print("=== TURN 1 — the original ask ===")
            started = time.monotonic()
            r1 = await turn(client, base, token, user_id, session_id, ORIGINAL_ASK)
            print(
                f"({time.monotonic() - started:.1f}s) "
                f"success={r1.get('success')} "
                f"model={r1.get('model')}/{r1.get('provider')}"
            )
            sid = r1.get("session_id") or session_id
            state_after_1 = pending_state(sid)

            print("\n=== TURN 2 — the confirmation ===")
            started = time.monotonic()
            r2 = await turn(client, base, token, user_id, sid, CONFIRMATION)
            print(
                f"({time.monotonic() - started:.1f}s) "
                f"success={r2.get('success')} "
                f"model={r2.get('model')}/{r2.get('provider')}"
            )
            state_after_2 = pending_state(sid)
            polled_state_after_2: Optional[Dict[str, Any]] = None
            if pending_acknowledgement(
                    str(r2.get("message") or ""), state_after_2):
                # Keep the turn-2 snapshot (still pending) for async-ack
                # recognition. Poll the saved result separately: it is the
                # retrieval baseline turn 3's no-reread proof compares to.
                polled_state_after_2 = wait_for_saved_result(
                    sid, timeout=delivery_wait
                )

            print("\n=== TURN 3 — saved-answer delivery ===")
            started = time.monotonic()
            r3 = await turn(
                client, base, token, user_id, sid, RETRY_CONFIRMATION
            )
            print(
                f"({time.monotonic() - started:.1f}s) "
                f"success={r3.get('success')} "
                f"model={r3.get('model')}/{r3.get('provider')}"
            )
            state_after_3 = wait_for_delivery(sid, timeout=delivery_wait)

            steps, trace_meta = await trace(client, base, token, sid)
            health_after = (await client.get(f"{base}/api/health", timeout=10)).json()
            identity_after = identity_from_health(health_after)
            report = build_report(
                identity_before,
                identity_after,
                r1,
                r2,
                steps,
                trace_meta,
                state_after_1,
                state_after_2,
                args.expected_revision,
                args.outage_mode,
                args.strict_workdrive_proof,
                args.expected_resource_id,
                args.expected_sha256,
                r3,
                state_after_3,
                getattr(args, "direct_delivery", False),
            )
            report["auth"] = auth_report(auth_meta, session_identity)
            report["polled_state_after_turn2"] = polled_state_after_2
            retry_report = evaluate_retry(
                polled_state_after_2 or state_after_2,
                state_after_3,
                r3,
                async_delivery=bool(report.get("async_delivery")),
            )
            report["retry"] = {
                "success": r3.get("success"),
                "model": r3.get("model"),
                "provider": r3.get("provider"),
                "message": str(r3.get("message") or "")[:2000],
                "state": state_after_3,
                **retry_report,
            }
            report["checks"].update({
                f"retry_{key}": value
                for key, value in retry_report["checks"].items()
            })
            report["all_pass"] = all(report["checks"].values())
        except Exception as exc:
            report = {
                "all_pass": False,
                "error": f"{type(exc).__name__}: {exc}",
                "identity_before": {},
                "identity_after": {},
                "auth": auth_report(auth_meta, session_identity),
            }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False, default=str)
    print("\n=== CLOSURE REPORT ===")
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report.get("all_pass") else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=BASE_DEFAULT)
    parser.add_argument(
        "--token-file",
        default=None,
        metavar="PATH",
        help=(
            "explicit private file (chmod 600) holding a server-issued bearer "
            "token; skips local scratch minting and verifies the caller with "
            "GET /api/auth/me. The token is never printed."
        ),
    )
    parser.add_argument(
        "--delivery-wait-seconds",
        type=float,
        default=DEFAULT_DELIVERY_WAIT_SECONDS,
        metavar="SECONDS",
        help=(
            "bounded wait for the turn-2 saved result and the turn-3 "
            f"delivery (0-{MAX_DELIVERY_WAIT_SECONDS:g}; default "
            f"{DEFAULT_DELIVERY_WAIT_SECONDS:g})"
        ),
    )
    parser.add_argument("--expected-revision", default="")
    parser.add_argument(
        "--outage-mode",
        action="store_true",
        help="accept a deliberately unavailable first-turn narration path",
    )
    parser.add_argument(
        "--strict-workdrive-proof",
        action="store_true",
        help=(
            "require a direct WorkDrive download in the same execution, "
            "bound to the exact resource id and the downloaded bytes' "
            "SHA-256; the server process must also run with "
            "ATOM_620_STRICT_WORKDRIVE_PROOF=1"
        ),
    )
    parser.add_argument(
        "--expected-resource-id", default="",
        help="exact WorkDrive resource id the proof must name",
    )
    parser.add_argument(
        "--expected-sha256", default="",
        help="exact SHA-256 of the downloaded bytes the proof must carry",
    )
    parser.add_argument(
        "--direct-delivery",
        action="store_true",
        help=(
            "accept the issue-620 direct-delivery shape: turn 1 already "
            "delivered the retrieved result, turns 2 and 3 re-deliver the "
            "byte-identical saved answer, and the formatter's coverage/source "
            "claims must match the persisted record. Implies "
            "--strict-workdrive-proof and requires --expected-resource-id "
            "and --expected-sha256"
        ),
    )
    parser.add_argument("--output", default="")
    args = parser.parse_args(argv)
    if args.direct_delivery:
        if not args.expected_resource_id or not args.expected_sha256:
            parser.error(
                "--direct-delivery requires --expected-resource-id and "
                "--expected-sha256"
            )
        args.strict_workdrive_proof = True
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
