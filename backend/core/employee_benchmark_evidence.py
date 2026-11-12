"""Server-controlled employee benchmark evidence producer (offline).

The employee G5 held-out two-domain campaign produced real served-model work
and call journals, but nothing wrote a *scored* record — the frozen workload
identity, the authoritative completion time and the exact accepted
``(provider, model)`` pair — into durable execution evidence. Generic execution metadata (a run's
``provider``/``model``/``result_summary``) is not benchmark authority, and a
caller's claim about its own score, timestamp or route is not evidence.

This module is the missing intake writer. It is deliberately offline and
narrow: it scores one campaign observation against a **frozen** benchmark set,
binds the result to a **scoring version**, the **authoritative execution
completion time** and the **provider-echoed served identity from the campaign's
own sealed transport journal**, and appends the record under the reserved
``benchmark_evidence`` key of the run's ``AgentExecution.metadata_json``. It
never routes, authorizes an effect, calls a provider, or reads a global
leaderboard.

Authority rules (acceptance contract)
-------------------------------------
* **Caller claims are never authority.** ``score``, ``accuracy``, ``passed``,
  ``observed_at``, ``provider``/``model``, tenant/workspace, dataset and
  scoring claims inside the observation are stripped and reported in
  ``rejected_claims``; the verdict is computed from the frozen checks and the
  durable execution row.
* **Frozen binding.** The dataset is read from the server-controlled registry
  and its canonical digest and scoring version must match the registry pin. A
  changed set or a different scoring generation is a different benchmark.
* **Authoritative completion time.** The evidence timestamp is the durable
  execution's ``completed_at`` (``observed_at_source ==
  "execution_completion"``), never a payload value and never the server intake
  clock. Intake time is recorded separately (``intake_at``) for audit only.
  Re-ingesting the same run, or replaying an old journal later, cannot refresh
  the result.
* **Campaign-owned journal.** Only a journal opened by the campaign through
  :func:`open_campaign_transport_journal`, sealed at the execution's completion
  time and bound to that execution, is accepted. A plain list/dict — even with
  a ``recorded_by`` string — is not authority; it cannot authenticate an
  arbitrary or imported journal.
* **Exact accepted identity.** Only an *accepted* transport call's
  ``response_identity`` (provider echo) counts. Requested/attempted routes are
  audit-only. A missing or conflicting echo, an unattributed call, or a
  disagreement with the execution row's durable ``model_provenance`` makes the
  result ineligible. The accepted call keeps two distinct identities: the
  callable route that was selected and accepted (``served_route``) and the
  concrete build the provider echoed (``response_identity``). A versioned echo
  of the same route is the build of that route, not a different route: the two
  must share the provider and the normalized model family, and only then does
  the evidence record the route with the build kept separately. A different
  family, a different provider, several distinct echoes, or a durable
  execution build that disagrees with the echo stays a conflict.
* **Scope from the durable row.** Tenant/workspace/agent come from the
  ``AgentExecution`` row; supplied claims must match or the intake is refused.
* **Generic metadata is not authority.** Readers only consume the validated
  reserved block; a caller-injected ``benchmark_evidence`` value fails the
  record digest/authority checks and is discarded, never scored.

Artifacts follow the existing assessment qualification convention: a
``judgment-*.json`` file carrying ``served_provider``/``served_model``,
``dataset_id``/``dataset_sha256`` and ``scoring`` can be written to a
server-configured directory for audit. The durable join in
``AgentExecution.metadata_json`` is the authoritative record;
:func:`load_employee_benchmark_evidence` turns it into records directly
comparable by :func:`core.llm.model_evidence_comparison.compare_model_evidence`.

Integration contract
--------------------
1. The campaign opens its own journal with
   :func:`open_campaign_transport_journal`, records the accepted provider echo
   for each call while it runs, and seals it with the durable execution
   completion time. It hands the producer that journal and the observed
   outputs (``observation``); it does not hand over a score or a timestamp.
2. :func:`produce_employee_benchmark_evidence` returns ``recorded`` /
   ``already_recorded`` / ``rejected`` with explicit reason codes and writes
   nothing on rejection.
3. The routing/graduation consumer calls
   :func:`load_employee_benchmark_evidence` (or feeds the evidence into
   ``compare_model_evidence``); an ineligible run simply has no comparison
   record.

Configuration
-------------
The registry lives at ``backend/config/employee_benchmark_registry.json``
(override with ``ATOM_EMPLOYEE_BENCHMARK_FILE``); it names the frozen set,
its canonical digest, the scoring version and the canonical task scope. The
registry grants no routing or effect authority by itself. An optional
server-configured ``artifact_dir`` writes the audit ``judgment-*.json``
described above; the durable metadata record remains the authority.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import re
from decimal import Decimal, InvalidOperation
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from weakref import WeakSet

from core.llm.model_evidence_comparison import (
    normalize_task_scope,
    task_scope_digest,
)
from core.llm.model_provenance import (
    normalize_model_family,
    provenance_from_metadata,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "atom-employee-benchmark-evidence-1"
JUDGMENT_SCHEMA = "atom-employee-benchmark-judgment-1"
REGISTRY_SCHEMA = "atom-employee-benchmark-registry-1"
SET_SCHEMA = "atom-employee-benchmark-set-1"

#: Reserved execution-metadata key. Owned by this producer; every other
#: metadata field is generic observability, not benchmark authority.
EVIDENCE_KEY = "benchmark_evidence"
PRODUCER_ID = "atom.employee_benchmark_evidence"
TRANSPORT_RECORDER = "atom-llm-transport"

# Rejection reason codes (stable, asserted by callers/tests).
REASON_EXECUTION_NOT_FOUND = "execution_not_found"
REASON_EXECUTION_UNREADABLE = "execution_unreadable"
REASON_AGENT_MISMATCH = "agent_mismatch"
REASON_SCOPE_MISMATCH = "tenant_workspace_mismatch"
REASON_EXECUTION_SCOPE_MISSING = "execution_scope_missing"
REASON_BENCHMARK_UNKNOWN = "benchmark_not_registered"
REASON_BENCHMARK_AMBIGUOUS = "benchmark_ambiguous"
REASON_BENCHMARK_CONFIG_INVALID = "benchmark_config_invalid"
REASON_DATASET_MISSING = "dataset_missing"
REASON_DATASET_UNREADABLE = "dataset_unreadable"
REASON_DATASET_IDENTITY_MISMATCH = "dataset_identity_mismatch"
REASON_SCORING_VERSION_MISMATCH = "scoring_version_mismatch"
REASON_OBSERVATION_MISSING = "observation_missing"
REASON_IDENTITY_MISSING = "served_identity_missing"
REASON_IDENTITY_CONFLICT = "served_identity_conflict"
REASON_IDENTITY_UNATTRIBUTED = "served_identity_unattributed"
REASON_JOURNAL_UNTRUSTED = "transport_journal_untrusted"
REASON_JOURNAL_UNSEALED = "transport_journal_unsealed"
REASON_JOURNAL_MISMATCH = "transport_journal_mismatch"
REASON_EXECUTION_INCOMPLETE = "execution_incomplete"
REASON_EXECUTION_TIME_MISSING = "execution_completion_missing"
REASON_PRIOR_CONFLICT = "conflicting_prior_evidence"
REASON_ARTIFACT_FAILED = "artifact_write_failed"

REASON_METADATA_TAMPERED = "metadata_record_tampered"
REASON_METADATA_AUTHORITY = "metadata_authority_invalid"
REASON_METADATA_SCHEMA = "metadata_schema_invalid"
REASON_METADATA_SCOPE = "metadata_scope_invalid"
REASON_METADATA_BENCHMARK_CHANGED = "benchmark_changed_since_record"

_UNKNOWN_IDENTITIES = frozenset({
    "", "auto", "default", "unknown", "none", "null", "n/a",
})

#: Keys a caller may not assert in the observation. Everything here is
#: either producer-owned (score/time/identity) or durable-row-owned (scope).
_CLAIM_KEYS = frozenset({
    "score", "accuracy", "passed", "ok", "judgment", "verdict",
    "status_claim", "observed_at", "evaluated_at", "verified_at",
    "recorded_at", "completed_at", "finished_at", "started_at",
    "provider", "model", "served_provider", "served_model",
    "requested_provider", "requested_model", "served_route",
    "model_provenance", "tenant_id", "workspace_id", "agent_id",
    "dataset_id", "dataset_sha256", "scoring", "scoring_version",
    "benchmark_id", "benchmark", "authority", "integrity", "evidence_id",
})

_CHECK_OPERATORS = ("equals", "one_of", "contains", "min", "max", "absent")
_MISSING = object()


class _ConfigError(ValueError):
    """A server-controlled benchmark/registry definition is unusable."""


# ---------------------------------------------------------------------------
# Canonical serialization / digests
# ---------------------------------------------------------------------------


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _identity(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return None if not text or text.casefold() in _UNKNOWN_IDENTITIES else text


def _pair(value: Any) -> Tuple[Optional[str], Optional[str]]:
    if not isinstance(value, Mapping):
        return None, None
    return _identity(value.get("provider")), _identity(value.get("model"))


def _model_family(value: Any) -> str:
    """Normalized model family used to relate a callable route and a build."""
    return normalize_model_family(_identity(value))


#: Alias tags that name the same route rather than a concrete build.
_ALIAS_TAGS = frozenset({"free", "preview", "latest"})


def _is_concrete_build(value: Any) -> bool:
    """True when ``value`` names a dated/snapshot build, not a route alias.

    ``gpt-5.4-2026-03`` is a build; ``gpt-5.4`` and ``gpt-5.4-latest`` are
    callable route labels for that family. Variant tiers stay distinct because
    the normalized family keeps them (``deepseek-v4-flash`` != ``v4-pro``).
    """
    text = _identity(value)
    if not text:
        return False
    name = text.casefold().split("/", 1)[-1]
    tokens = [token for token in re.split(r"[-_:\s]+", name) if token]
    without_alias_tags = "-".join(
        token for token in tokens if token not in _ALIAS_TAGS)
    return normalize_model_family(text) != without_alias_tags


def _build_claim(value: Any, route: Any) -> Optional[str]:
    """A concrete build identity claimed for ``route`` (not the route alias).

    A label that is only the selected route, or an alias tag of it, is not a
    build claim: it says nothing about which build served the call.
    """
    text = _identity(value)
    route_text = _identity(route)
    if not text or not route_text:
        return None
    if text.casefold() == route_text.casefold():
        return None
    if _model_family(text) != _model_family(route_text):
        return None
    return text if _is_concrete_build(text) else None


def _dedupe(values: Sequence[str]) -> List[str]:
    return list(dict.fromkeys(str(item) for item in values if item))


def _utc(value: Optional[Any]) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _strict_utc(value: Any) -> Optional[datetime]:
    """Parse a durable timestamp; never invent one for authority."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Campaign-owned transport journal
# ---------------------------------------------------------------------------

_JOURNAL_TOKEN = object()
_OWNED_JOURNALS: "WeakSet[CampaignTransportJournal]" = WeakSet()

#: The only surface a campaign uses to hand over accepted response evidence.
#: Ownership is process-local: a journal created by any other path (or a plain
#: list/dict, however its ``recorded_by`` field is spelled) is not evidence.
def open_campaign_transport_journal(
    *,
    campaign_id: str,
    execution_id: str,
) -> "CampaignTransportJournal":
    campaign_key = str(campaign_id or "").strip()
    execution_key = str(execution_id or "").strip()
    if not campaign_key or not execution_key:
        raise ValueError(
            "a campaign journal requires a campaign id and execution id")
    journal = CampaignTransportJournal(
        _token=_JOURNAL_TOKEN,
        campaign_id=campaign_key,
        execution_id=execution_key,
    )
    _OWNED_JOURNALS.add(journal)
    return journal


class CampaignTransportJournal:
    """Campaign-owned record of accepted provider calls.

    The campaign records the provider-echoed identity for each accepted call
    while it runs and seals the journal with the durable execution completion
    time. The producer accepts only journals created by
    :func:`open_campaign_transport_journal` and sealed before hand-over, so a
    caller cannot manufacture a fresh journal for an old run.
    """

    def __init__(
        self,
        *,
        _token: Any,
        campaign_id: str,
        execution_id: str,
    ) -> None:
        if _token is not _JOURNAL_TOKEN:
            raise TypeError(
                "use open_campaign_transport_journal() to create a journal")
        self.campaign_id = campaign_id
        self.execution_id = execution_id
        self._entries: List[Dict[str, Any]] = []
        self._sealed = False
        self._completed_at: Optional[datetime] = None

    @property
    def sealed(self) -> bool:
        return self._sealed

    @property
    def completed_at(self) -> Optional[datetime]:
        return self._completed_at

    @property
    def entries(self) -> List[Dict[str, Any]]:
        """A detached copy: post-seal mutation cannot alter the evidence."""
        return copy.deepcopy(self._entries)

    def record_call(
        self,
        *,
        accepted: bool,
        response_identity: Optional[Mapping[str, Any]] = None,
        served_route: Optional[Mapping[str, Any]] = None,
        requested_route: Optional[Mapping[str, Any]] = None,
        call_id: Optional[str] = None,
        unattributed: bool = False,
    ) -> Dict[str, Any]:
        """Record one transport call; only the provider echo is identity.

        ``accepted`` must be the transport's own acceptance verdict. The
        recorder marker is set here, not supplied by the caller.
        """
        if self._sealed:
            raise RuntimeError("a sealed campaign journal cannot be appended")
        if not isinstance(accepted, bool):
            raise TypeError("accepted must be a bool")
        self._entries.append({
            "call_id": str(call_id or f"call-{len(self._entries) + 1}"),
            "recorded_by": TRANSPORT_RECORDER,
            "accepted": accepted,
            "requested_route": (
                dict(requested_route)
                if isinstance(requested_route, Mapping) else None),
            "served_route": (
                dict(served_route)
                if isinstance(served_route, Mapping) else None),
            "response_identity": (
                dict(response_identity)
                if isinstance(response_identity, Mapping) else None),
            "unattributed": bool(unattributed),
        })
        return self.entries[-1]

    def seal(self, *, completed_at: Any) -> None:
        """Bind the journal to the durable execution completion time."""
        if self._sealed:
            raise RuntimeError("campaign journal is already sealed")
        parsed = _strict_utc(completed_at)
        if parsed is None:
            raise ValueError(
                "a campaign journal must be sealed with the execution "
                "completion time")
        self._completed_at = parsed
        self._sealed = True


def activate_campaign_journal(
    journal: CampaignTransportJournal,
) -> None:
    """Record accepted provider echoes into ``journal`` in this process.

    The transport calls the installed sink only after it accepted a response;
    the producer still validates the sealed journal against the durable row.
    """
    if not isinstance(journal, CampaignTransportJournal):
        raise TypeError("activate_campaign_journal requires a campaign journal")

    def _sink(
        provider: str,
        model: str,
        requested: Any,
        response_identity: Any = None,
    ) -> None:
        provider = str(provider or "").strip()
        model = str(model or "").strip()
        if not provider or not model:
            return
        requested_route = None
        if isinstance(requested, (tuple, list)) and len(requested) >= 2:
            requested_route = {
                "provider": str(requested[0] or "").strip(),
                "model": str(requested[1] or "").strip(),
            }
            if not (requested_route["provider"]
                    and requested_route["model"]):
                requested_route = None
        # Only the transport's provider echo is identity. When it is absent the
        # call is recorded as accepted with no identity, which makes the
        # producer reject the campaign instead of scoring a served-route alias.
        journal.record_call(
            accepted=True,
            requested_route=requested_route,
            served_route={"provider": provider, "model": model},
            response_identity=(
                dict(response_identity)
                if isinstance(response_identity, Mapping) else None),
        )

    from core.llm.model_provenance import set_campaign_transport_sink

    set_campaign_transport_sink(_sink)


def deactivate_campaign_journal() -> None:
    """Stop recording accepted provider echoes into the in-process journal."""
    from core.llm.model_provenance import clear_campaign_transport_sink

    clear_campaign_transport_sink()


def _journal_reasons(
    journal: Any, *, execution_id: str,
) -> List[str]:
    """Why a hand-over journal is not authoritative evidence."""
    if (not isinstance(journal, CampaignTransportJournal)
            or journal not in _OWNED_JOURNALS):
        return [REASON_JOURNAL_UNTRUSTED]
    reasons: List[str] = []
    if not journal.sealed or journal.completed_at is None:
        reasons.append(REASON_JOURNAL_UNSEALED)
    if str(journal.execution_id or "").strip() != execution_id:
        reasons.append(REASON_JOURNAL_MISMATCH)
    return _dedupe(reasons)


def _completion_reasons(
    *,
    execution_status: Any,
    execution_completed_at: Any,
    journal: CampaignTransportJournal,
) -> Tuple[Optional[datetime], List[str]]:
    """Bind the observation to authoritative execution completion."""
    reasons: List[str] = []
    status = str(execution_status or "").strip().casefold()
    if status and status != "completed":
        reasons.append(REASON_EXECUTION_INCOMPLETE)
    completed_at = _strict_utc(execution_completed_at)
    if completed_at is None:
        reasons.append(REASON_EXECUTION_TIME_MISSING)
        return None, _dedupe(reasons)
    sealed_at = journal.completed_at
    if sealed_at is None:
        reasons.append(REASON_JOURNAL_UNSEALED)
    elif abs((sealed_at - completed_at).total_seconds()) > 1:
        # The journal was sealed for a different observation than the durable
        # execution completion: an imported or replayed journal cannot lend
        # its freshness to this run.
        reasons.append(REASON_JOURNAL_MISMATCH)
    return completed_at, _dedupe(reasons)


# ---------------------------------------------------------------------------
# Server-controlled registry + frozen set
# ---------------------------------------------------------------------------


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def benchmark_registry_path() -> Path:
    configured = os.getenv("ATOM_EMPLOYEE_BENCHMARK_FILE")
    if configured:
        return Path(configured)
    return _backend_root() / "config" / "employee_benchmark_registry.json"


_REGISTRY_CACHE: Dict[str, Any] = {"signature": None, "registry": None}


def load_benchmark_registry() -> Dict[str, Any]:
    """Read the server-controlled benchmark registry (mtime-cached)."""
    path = benchmark_registry_path()
    try:
        stat = path.stat()
    except OSError:
        return {"schema": None, "benchmarks": [], "path": str(path)}
    signature = (str(path), stat.st_mtime_ns, stat.st_size)
    if _REGISTRY_CACHE.get("signature") == signature:
        return _REGISTRY_CACHE["registry"]
    try:
        registry = json.loads(path.read_text())
    except Exception as exc:  # noqa: BLE001 — fail closed on unreadable config
        logger.warning("employee benchmark registry unreadable: %s", exc)
        registry = {"schema": None, "benchmarks": [], "error": str(exc)}
    if not isinstance(registry, Mapping):
        registry = {"schema": None, "benchmarks": [],
                    "error": "registry is not an object"}
    registry = dict(registry)
    registry.setdefault("benchmarks", [])
    registry["path"] = str(path)
    _REGISTRY_CACHE["signature"] = signature
    _REGISTRY_CACHE["registry"] = registry
    return registry


def _locate_dataset(raw: Any, *, registry_path: Optional[str]) -> Optional[Path]:
    """Resolve a registry dataset path, refusing escapes from an allowed root."""
    text = str(raw or "").strip()
    if not text:
        return None
    roots: List[Path] = []
    if registry_path:
        roots.append(Path(registry_path).resolve().parent)
    roots.append(_repo_root())
    path = Path(text)
    candidates = [path] if path.is_absolute() else [
        base / path for base in roots]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        for root in roots:
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                continue
            if resolved.is_file():
                return resolved
    return None


def _dataset_digest(dataset: Mapping[str, Any]) -> str:
    return _digest({
        key: value for key, value in dataset.items() if key != "set_sha256"})


def _scoring_digest(dataset: Mapping[str, Any]) -> str:
    scoring = dataset.get("scoring")
    scoring = scoring if isinstance(scoring, Mapping) else {}
    return _digest({
        "version": scoring.get("version"),
        "rule": scoring.get("rule"),
        "cases": dataset.get("cases"),
    })


def _select_entry(
    registry: Mapping[str, Any], benchmark_id: Optional[str],
) -> Tuple[Optional[Mapping[str, Any]], List[str]]:
    entries = [
        entry for entry in (registry.get("benchmarks") or [])
        if isinstance(entry, Mapping)]
    if benchmark_id:
        matches = [
            entry for entry in entries
            if str(entry.get("id") or "") == str(benchmark_id)]
        if not matches:
            return None, [REASON_BENCHMARK_UNKNOWN]
        return matches[0], []
    if len(entries) == 1:
        return entries[0], []
    if not entries:
        return None, [REASON_BENCHMARK_UNKNOWN]
    return None, [REASON_BENCHMARK_AMBIGUOUS]


def _prepare_benchmark(
    benchmark_id: Optional[str],
    *,
    registry: Optional[Mapping[str, Any]] = None,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any], List[str]]:
    """Load and validate the frozen set against its server-controlled pin."""
    registry = registry if registry is not None else load_benchmark_registry()
    registry_path = (
        str(registry.get("path")) if isinstance(registry, Mapping)
        and registry.get("path") else None)
    entry, reasons = _select_entry(registry, benchmark_id)
    if reasons:
        return None, registry, reasons
    assert entry is not None

    entry_id = str(entry.get("id") or "").strip()
    capability = str(entry.get("capability") or "").strip()
    if not entry_id or not capability:
        return None, registry, [REASON_BENCHMARK_CONFIG_INVALID]

    dataset_path = _locate_dataset(
        entry.get("dataset"), registry_path=registry_path)
    if dataset_path is None:
        return None, registry, [
            REASON_DATASET_MISSING
            if entry.get("dataset") else REASON_BENCHMARK_CONFIG_INVALID]
    try:
        dataset = json.loads(dataset_path.read_text())
    except Exception as exc:  # noqa: BLE001 — unreadable set is not evidence
        logger.warning("employee benchmark set unreadable: %s", exc)
        return None, registry, [REASON_DATASET_UNREADABLE]
    if not isinstance(dataset, Mapping) or dataset.get("schema") != SET_SCHEMA:
        return None, registry, [REASON_DATASET_UNREADABLE]

    if str(dataset.get("id") or "").strip() != entry_id:
        return None, registry, [REASON_DATASET_IDENTITY_MISMATCH]
    digest = _dataset_digest(dataset)
    if dataset.get("set_sha256") and str(dataset["set_sha256"]) != digest:
        return None, registry, [REASON_DATASET_IDENTITY_MISMATCH]
    pinned_digest = str(entry.get("dataset_sha256") or "").strip()
    if not pinned_digest or pinned_digest != digest:
        return None, registry, [REASON_DATASET_IDENTITY_MISMATCH]

    dataset_scoring = dataset.get("scoring")
    dataset_scoring = (
        dataset_scoring if isinstance(dataset_scoring, Mapping) else {})
    dataset_scoring_version = str(
        dataset_scoring.get("version") or "").strip()
    pinned_scoring = str(entry.get("scoring_version") or "").strip()
    if (not pinned_scoring or not dataset_scoring_version
            or pinned_scoring != dataset_scoring_version):
        return None, registry, [REASON_SCORING_VERSION_MISMATCH]

    cases = dataset.get("cases")
    if not isinstance(cases, Mapping) or not cases:
        return None, registry, [REASON_BENCHMARK_CONFIG_INVALID]

    scope = normalize_task_scope(entry.get("task_scope"))
    if not (scope["task_policy"] or scope["decision_options"]
            or scope["subject_field"]):
        return None, registry, [REASON_BENCHMARK_CONFIG_INVALID]

    benchmark = {
        "benchmark_id": entry_id,
        "capability": capability,
        "dataset": dataset,
        "dataset_ref": str(entry.get("dataset") or ""),
        "dataset_sha256": digest,
        "dataset_version": str(dataset.get("version") or ""),
        "scoring": dict(dataset_scoring),
        "scoring_version": dataset_scoring_version,
        "scoring_sha256": _scoring_digest(dataset),
        "rubric_version": str(entry.get("rubric_version") or "").strip(),
        "contract_version": str(entry.get("contract_version") or "").strip(),
        "task_scope": scope,
    }
    return benchmark, registry, []


# ---------------------------------------------------------------------------
# Deterministic scoring over the frozen checks
# ---------------------------------------------------------------------------


def _resolve_path(view: Any, path: str) -> Any:
    current = view
    for part in str(path).split("."):
        if isinstance(current, Mapping):
            if part not in current:
                return _MISSING
            current = current[part]
        elif isinstance(current, (list, tuple)):
            try:
                index = int(part)
            except (TypeError, ValueError):
                return _MISSING
            if index < 0 or index >= len(current):
                return _MISSING
            current = current[index]
        else:
            return _MISSING
    return current


def _decimal(value: Any) -> Optional[Decimal]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    if isinstance(value, str):
        text = value.strip()
        if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
            return None
        try:
            return Decimal(text)
        except InvalidOperation:
            return None
    return None


def _values_equal(actual: Any, expected: Any) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        return (isinstance(actual, bool) and isinstance(expected, bool)
                and actual == expected)
    if actual is None or expected is None:
        return actual is expected
    left, right = _decimal(actual), _decimal(expected)
    if left is not None and right is not None:
        return left == right
    return str(actual).strip() == str(expected).strip()


def _bounded(value: Any) -> Any:
    """Bound an observed value for the audit trail without losing identity."""
    if isinstance(value, str):
        return value if len(value) <= 500 else {
            "kind": "text", "length": len(value),
            "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest()}
    if isinstance(value, (Mapping, list, tuple)):
        return {"kind": type(value).__name__, "length": len(value),
                "sha256": _digest(value)}
    if value is _MISSING:
        return None
    return value


def _evaluate_check(check: Mapping[str, Any], actual: Any) -> Dict[str, Any]:
    operator = next(
        (name for name in _CHECK_OPERATORS if name in check), None)
    if operator is None:
        raise _ConfigError(f"check has no known operator: {check!r}")
    expected = check[operator]
    if operator == "absent":
        passed = (
            actual is _MISSING or actual is None
            or (isinstance(actual, str) and not actual.strip()))
    elif operator == "equals":
        passed = actual is not _MISSING and _values_equal(actual, expected)
    elif operator == "one_of":
        passed = (
            actual is not _MISSING and isinstance(expected, (list, tuple))
            and any(_values_equal(actual, item) for item in expected))
    elif operator == "contains":
        if actual is _MISSING or actual is None:
            passed = False
        elif isinstance(actual, (list, tuple)):
            passed = any(_values_equal(item, expected) for item in actual)
        elif isinstance(actual, Mapping):
            passed = any(
                _values_equal(item, expected) for item in actual.values())
        else:
            passed = str(expected) in str(actual)
    elif operator == "min":
        left, right = _decimal(actual), _decimal(expected)
        passed = left is not None and right is not None and left >= right
    else:  # max
        left, right = _decimal(actual), _decimal(expected)
        passed = left is not None and right is not None and left <= right
    return {
        "path": str(check.get("path") or ""),
        "operator": operator,
        "expected": expected,
        "actual": _bounded(actual),
        "passed": bool(passed),
    }


def _strip_claims(
    value: Any, path: str, rejected: List[str],
) -> Any:
    """Remove caller-authored authority claims from an observation subtree."""
    if isinstance(value, Mapping):
        cleaned: Dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            child = f"{path}.{name}" if path else name
            if name.casefold() in _CLAIM_KEYS:
                rejected.append(child)
                continue
            cleaned[name] = _strip_claims(item, child, rejected)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [
            _strip_claims(item, f"{path}[{index}]", rejected)
            for index, item in enumerate(value)]
    return value


def _case_score(
    case_id: str, definition: Mapping[str, Any], observed: Any,
    run_context: Mapping[str, Any],
) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    seen = isinstance(observed, Mapping)
    view: Dict[str, Any] = {"run": dict(run_context)}
    if seen:
        view.update(observed)
    declared = definition.get("checks")
    if not isinstance(declared, (list, tuple)) or not declared:
        raise _ConfigError(f"case {case_id} declares no checks")
    for check in declared:
        if not isinstance(check, Mapping):
            raise _ConfigError(f"case {case_id} has a non-object check")
        checks.append(_evaluate_check(check, _resolve_path(
            view, str(check.get("path") or ""))))
    passed = seen and all(check["passed"] for check in checks)
    return {
        "case_id": case_id,
        "domain": str(definition.get("domain") or ""),
        "observed": seen,
        "passed": passed,
        "checks": checks,
    }


def score_employee_benchmark(
    benchmark: Mapping[str, Any],
    observation: Any,
) -> Tuple[Optional[Dict[str, Any]], List[str], List[str]]:
    """Score one observation against the frozen checks.

    Returns ``(score, reasons, rejected_claims)``. The caller supplies only
    observed outputs; any authority claim it tries to assert is stripped and
    listed. No timestamp, score or identity is read from the observation.
    """
    rejected: List[str] = []
    if not isinstance(observation, Mapping):
        return None, [REASON_OBSERVATION_MISSING], rejected
    cleaned = _strip_claims(observation, "observation", rejected)
    cases = cleaned.get("cases") if isinstance(cleaned, Mapping) else None
    if not isinstance(cases, Mapping) or not cases:
        return None, [REASON_OBSERVATION_MISSING], rejected
    run_context = cleaned.get("run")
    run_context = run_context if isinstance(run_context, Mapping) else {}

    dataset = benchmark.get("dataset") or {}
    declared_cases = dataset.get("cases") or {}
    try:
        results = [
            _case_score(
                case_id, definition,
                cases.get(case_id), run_context)
            for case_id, definition in sorted(declared_cases.items())
            if isinstance(definition, Mapping)
        ]
    except _ConfigError as exc:
        logger.warning("employee benchmark definition invalid: %s", exc)
        return None, [REASON_BENCHMARK_CONFIG_INVALID], rejected

    if not results:
        return None, [REASON_BENCHMARK_CONFIG_INVALID], rejected
    passed_cases = sum(1 for result in results if result["passed"])
    accuracy = round(passed_cases / len(results), 4)
    score = {
        "scoring_version": benchmark.get("scoring_version"),
        "scoring_sha256": benchmark.get("scoring_sha256"),
        "case_count": len(results),
        "passed_cases": passed_cases,
        "accuracy": accuracy,
        "passed": passed_cases == len(results),
        "cases": results,
    }
    return score, [], rejected


# ---------------------------------------------------------------------------
# Accepted served identity from the recorded transport
# ---------------------------------------------------------------------------


def _served_identity_from_journal(
    journal: Any,
) -> Tuple[Optional[Dict[str, str]], List[str], Dict[str, Any]]:
    """The one accepted callable route and its provider build.

    Requested/attempted routes are never evidence. The recorder marker and the
    boolean acceptance flag are required. The provider echo
    (``response_identity``) is the concrete build that answered the call; the
    accepted ``served_route`` is the callable route the transport selected.
    Both identities are kept distinct: the route is the evidence identity, the
    echo is its build.

    A versioned echo of the accepted route (same provider, same normalized
    family) is that route's build, not a different route. A missing echo, a
    different provider/family, several distinct accepted routes or several
    distinct echo builds make the whole run ineligible.
    """
    reasons: List[str] = []
    if (not isinstance(journal, Sequence) or isinstance(journal, (str, bytes))
            or not journal):
        return None, [REASON_IDENTITY_MISSING], {
            "calls": 0, "accepted_calls": 0,
            "requested_routes": [], "digest": _digest([])}

    routes: List[Dict[str, str]] = []
    builds: List[str] = []
    requested: List[Dict[str, str]] = []
    accepted_calls = 0
    normalized: List[Dict[str, Any]] = []
    for entry in journal:
        if not isinstance(entry, Mapping):
            reasons.append(REASON_JOURNAL_UNTRUSTED)
            continue
        if str(entry.get("recorded_by") or "") != TRANSPORT_RECORDER:
            reasons.append(REASON_JOURNAL_UNTRUSTED)
        accepted = entry.get("accepted")
        if not isinstance(accepted, bool):
            reasons.append(REASON_JOURNAL_UNTRUSTED)
            continue
        if accepted is not True:
            continue
        if entry.get("unattributed") is True:
            reasons.append(REASON_IDENTITY_MISSING)
            continue
        response_provider, response_model = _pair(
            entry.get("response_identity"))
        served_provider, served_model = _pair(entry.get("served_route"))
        if not (response_provider and response_model):
            # The provider echo is the evidence; an accepted call without one
            # cannot establish the served identity.
            reasons.append(REASON_IDENTITY_MISSING)
            continue
        if served_provider or served_model:
            if served_provider and (
                    served_provider.casefold()
                    != response_provider.casefold()):
                # A different provider never served this echo.
                reasons.append(REASON_IDENTITY_CONFLICT)
                continue
            if served_model and (
                    served_model.casefold() != response_model.casefold()):
                if _model_family(
                        served_model) != _model_family(response_model):
                    # A genuinely different model is a conflicting echo.
                    reasons.append(REASON_IDENTITY_CONFLICT)
                    continue
                if _is_concrete_build(served_model):
                    # The accepted route was already a concrete build: a
                    # different echo is a changed build, not its version.
                    reasons.append(REASON_IDENTITY_CONFLICT)
                    continue
                # The accepted route is an alias label; the echo may be the
                # concrete build that answered it.
        # The callable route is the accepted served route when known; the
        # echo stays the build. Without a served route both fall back to the
        # echo (no route alias was recorded, so nothing is invented).
        route = {
            "provider": served_provider or response_provider,
            "model": served_model or response_model,
        }
        if route not in routes:
            routes.append(route)
        if response_model not in builds:
            builds.append(response_model)
        accepted_calls += 1
        normalized.append({
            "call_id": str(entry.get("call_id") or ""),
            **route,
            "resolved_model": response_model,
        })
        requested_provider, requested_model = _pair(
            entry.get("requested_route"))
        if requested_provider and requested_model:
            requested_pair = {
                "provider": requested_provider,
                "model": requested_model,
            }
            if requested_pair not in requested:
                requested.append(requested_pair)

    if len(routes) > 1:
        # Several distinct accepted callable routes are not one observation.
        reasons.append(REASON_IDENTITY_CONFLICT)
    if len(builds) > 1:
        # Genuine conflicting echoes within one run: the same route resolving
        # through different provider builds cannot be a single observation.
        reasons.append(REASON_IDENTITY_CONFLICT)
    if not routes:
        reasons.append(REASON_IDENTITY_MISSING)
    identity = None
    if len(routes) == 1 and len(builds) == 1:
        identity = {**routes[0], "resolved_model": builds[0]}
    route_pair = (
        {"provider": identity["provider"], "model": identity["model"]}
        if identity else None)
    audit = {
        "recorder": TRANSPORT_RECORDER,
        "calls": len(journal),
        "accepted_calls": accepted_calls,
        "requested_routes": requested,
        "fallback": bool(
            route_pair and requested and any(
                pair != route_pair for pair in requested)),
        "digest": _digest(normalized),
    }
    return identity, _dedupe(reasons), audit


def _execution_identity_reasons(
    metadata: Any, identity: Mapping[str, str],
) -> List[str]:
    """Disagreement between the journal and durable execution provenance.

    The durable row may record the callable route alias, the provider build,
    or both. Either way it must name the same provider and the same model
    family as the journal's accepted route. Any build witness the row records
    (a concrete ``resolved_model`` or a concrete ``model`` that is a build of
    the route) must match the journal's provider echo exactly: an alias alone
    is never evidence that a changed build still served this run.
    """
    provenance = provenance_from_metadata(metadata)
    nested = (
        metadata.get("model_provenance")
        if isinstance(metadata, Mapping) else None)
    nested = nested if isinstance(nested, Mapping) else {}
    route_provider = identity["provider"]
    route_model = identity["model"]
    build = _identity(identity.get("resolved_model"))
    reasons: List[str] = []
    provider = _identity(provenance.get("provider"))
    model = _identity(provenance.get("model"))
    if provider and provider.casefold() != route_provider.casefold():
        reasons.append(REASON_IDENTITY_CONFLICT)
    if model:
        if _model_family(model) != _model_family(route_model):
            reasons.append(REASON_IDENTITY_CONFLICT)
        else:
            claim = _build_claim(model, route_model)
            if claim and build and claim.casefold() != build.casefold():
                reasons.append(REASON_IDENTITY_CONFLICT)
    durable_build = _identity(provenance.get("resolved_model"))
    if not durable_build:
        durable_build = _identity(nested.get("resolved_model"))
    if durable_build and build and (
            durable_build.casefold() != build.casefold()):
        reasons.append(REASON_IDENTITY_CONFLICT)
    serving = [
        entry for entry in (
            provenance.get("serving_models")
            or nested.get("serving_models") or [])
        if isinstance(entry, Mapping)]
    for entry in serving:
        serving_provider = _identity(entry.get("provider"))
        serving_model = _identity(entry.get("model"))
        if serving_provider and (
                serving_provider.casefold() != route_provider.casefold()):
            reasons.append(REASON_IDENTITY_CONFLICT)
        if not serving_model:
            continue
        if _model_family(serving_model) != _model_family(route_model):
            reasons.append(REASON_IDENTITY_CONFLICT)
            continue
        claim = _build_claim(serving_model, route_model)
        if claim and build and claim.casefold() != build.casefold():
            reasons.append(REASON_IDENTITY_CONFLICT)
    unattributed = provenance.get("unattributed_calls")
    if not unattributed:
        unattributed = nested.get("unattributed_calls")
    if isinstance(unattributed, int) and not isinstance(unattributed, bool) \
            and unattributed > 0:
        reasons.append(REASON_IDENTITY_UNATTRIBUTED)
    return _dedupe(reasons)


# ---------------------------------------------------------------------------
# Durable record: digests, validation and the guarded writer
# ---------------------------------------------------------------------------


def _record_body(record: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in record.items() if key != "integrity"}


def record_digest(record: Mapping[str, Any]) -> str:
    return _digest(_record_body(record))


def _core_digest(record: Mapping[str, Any]) -> str:
    """Idempotency key: the authoritative verdict, not intake bookkeeping."""
    cases = [
        {
            "case_id": case.get("case_id"),
            "passed": case.get("passed"),
            "checks": [
                {"path": check.get("path"), "passed": check.get("passed")}
                for check in case.get("checks") or []
            ],
        }
        for case in record.get("cases") or []
    ]
    return _digest({
        "evidence_id": record.get("evidence_id"),
        "dataset": record.get("dataset"),
        "scoring": record.get("scoring"),
        "task_scope": (record.get("task_scope") or {}).get("digest"),
        "identity": [record.get("provider"), record.get("model")],
        "passed": record.get("passed"),
        "accuracy": record.get("accuracy"),
        "cases": cases,
    })


def _authority_valid(record: Mapping[str, Any]) -> bool:
    authority = record.get("authority")
    return (
        isinstance(authority, Mapping)
        and authority.get("producer") == PRODUCER_ID
        and authority.get("intake") == "server"
        and authority.get("caller_claims") == "rejected")


def validate_benchmark_record(
    raw: Any,
    *,
    registry: Optional[Mapping[str, Any]] = None,
    benchmark: Optional[Mapping[str, Any]] = None,
    verify_registry: bool = True,
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Recompute and verify a durable record; return ``(record, reasons)``."""
    if not isinstance(raw, Mapping):
        return None, [REASON_METADATA_SCHEMA]
    record = dict(raw)
    reasons: List[str] = []
    if record.get("schema") != SCHEMA_VERSION:
        reasons.append(REASON_METADATA_SCHEMA)
    if not _authority_valid(record):
        reasons.append(REASON_METADATA_AUTHORITY)
    if str(record.get("observed_at_source") or "") != (
            "execution_completion"):
        reasons.append(REASON_METADATA_AUTHORITY)
    observed_at = _strict_utc(record.get("observed_at"))
    execution = record.get("execution")
    execution_completed_at = _strict_utc(
        execution.get("completed_at") if isinstance(execution, Mapping)
        else None)
    if (observed_at is None or execution_completed_at is None
            or observed_at != execution_completed_at):
        reasons.append(REASON_METADATA_AUTHORITY)
    if _strict_utc(record.get("intake_at")) is None:
        reasons.append(REASON_METADATA_AUTHORITY)
    provider = _identity(record.get("provider"))
    model = _identity(record.get("model"))
    build = _identity(record.get("resolved_model"))
    served = record.get("served_identity")
    served_provider, served_model = _pair(served)
    served_build = (
        _identity(served.get("resolved_model"))
        if isinstance(served, Mapping) else None)
    if (not provider or not model or served_provider != provider
            or served_model != model):
        reasons.append(REASON_METADATA_AUTHORITY)
    if build:
        # The recorded build must belong to the recorded callable route, and
        # the served-identity block (when it names one) must agree with it.
        if _model_family(build) != _model_family(model):
            reasons.append(REASON_METADATA_AUTHORITY)
        if served_build and served_build.casefold() != build.casefold():
            reasons.append(REASON_METADATA_AUTHORITY)
    elif served_build:
        reasons.append(REASON_METADATA_AUTHORITY)
    dataset = record.get("dataset")
    scoring = record.get("scoring")
    scope = record.get("task_scope")
    if not (isinstance(dataset, Mapping) and dataset.get("id")
            and dataset.get("sha256")):
        reasons.append(REASON_METADATA_SCHEMA)
    if not (isinstance(scoring, Mapping) and scoring.get("version")):
        reasons.append(REASON_METADATA_SCHEMA)
    if not isinstance(scope, Mapping):
        reasons.append(REASON_METADATA_SCOPE)
    else:
        scope_without_digest = {
            key: value for key, value in scope.items() if key != "digest"}
        if scope.get("digest") != task_scope_digest(scope_without_digest):
            reasons.append(REASON_METADATA_SCOPE)
    integrity = record.get("integrity")
    if not isinstance(integrity, Mapping) or (
            integrity.get("record_sha256") != record_digest(record)):
        reasons.append(REASON_METADATA_TAMPERED)
    elif integrity.get("core_sha256") != _core_digest(record):
        reasons.append(REASON_METADATA_TAMPERED)

    if verify_registry and not reasons:
        if benchmark is None:
            resolved, _registry, load_reasons = _prepare_benchmark(
                str((record.get("benchmark") or {}).get("id") or "") or None,
                registry=registry)
            if load_reasons:
                reasons.append(REASON_METADATA_BENCHMARK_CHANGED)
                benchmark = None
            else:
                benchmark = resolved
        if benchmark is not None:
            if (str(dataset.get("id")) != benchmark["benchmark_id"]
                    or str(dataset.get("sha256"))
                    != benchmark["dataset_sha256"]
                    or str(scoring.get("version"))
                    != benchmark["scoring_version"]):
                reasons.append(REASON_METADATA_BENCHMARK_CHANGED)
            elif scope.get("digest") != task_scope_digest(
                    benchmark["task_scope"]):
                reasons.append(REASON_METADATA_BENCHMARK_CHANGED)
    return (None if reasons else record), _dedupe(reasons)


def _coerce_records(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, Mapping):
        return [dict(raw)]
    if isinstance(raw, (list, tuple)):
        return [dict(item) for item in raw if isinstance(item, Mapping)]
    return []


def _metadata_mapping(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except ValueError:
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def inspect_employee_benchmark_evidence(
    metadata: Any,
    *,
    registry: Optional[Mapping[str, Any]] = None,
    verify_registry: bool = True,
) -> Dict[str, Any]:
    """Validate the reserved block only; generic metadata is never authority."""
    metadata = _metadata_mapping(metadata)
    raw_records = _coerce_records(metadata.get(EVIDENCE_KEY))
    records: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    for raw in raw_records:
        record, reasons = validate_benchmark_record(
            raw, registry=registry, verify_registry=verify_registry)
        if record is not None:
            records.append(record)
        else:
            rejected.append({
                "evidence_id": raw.get("evidence_id"),
                "reasons": reasons,
            })
    return {
        "authority_key": EVIDENCE_KEY,
        "schema": SCHEMA_VERSION,
        "records": records,
        "rejected": rejected,
    }


def evidence_comparison_record(record: Mapping[str, Any]) -> Dict[str, Any]:
    """A validated durable record as a ``compare_model_evidence`` input.

    The comparison identity is the callable route; the provider build is
    carried separately as ``resolved_model`` so the comparator can surface a
    conflicting build under the same route instead of accepting the alias as
    proof of an unchanged build.
    """
    scope = record.get("task_scope") or {}
    build = _identity(record.get("resolved_model"))
    row = {
        "source": "employee_benchmark",
        "evidence_id": str(record.get("evidence_id") or ""),
        "provider": record.get("provider"),
        "model": record.get("model"),
        "task_scope": {
            key: value for key, value in scope.items() if key != "digest"},
        "rubric_version": str(record.get("rubric_version") or ""),
        "contract_version": str(record.get("contract_version") or ""),
        "observed_at": record.get("observed_at"),
        "passed": bool(record.get("passed")),
        "accuracy": record.get("accuracy"),
        "dataset_id": (record.get("dataset") or {}).get("id"),
        "dataset_sha256": (record.get("dataset") or {}).get("sha256"),
        "scoring_version": (record.get("scoring") or {}).get("version"),
        "phase": (record.get("benchmark") or {}).get("id"),
        "registry_status": (
            "qualified" if record.get("passed") else "failed"),
        "model_provenance": {
            "provider": record.get("provider"),
            "model": record.get("model"),
        },
    }
    if build:
        row["resolved_model"] = build
    return row


def load_employee_benchmark_evidence(
    metadata: Any,
    *,
    registry: Optional[Mapping[str, Any]] = None,
    verify_registry: bool = True,
) -> List[Dict[str, Any]]:
    """Comparison-ready evidence from the validated reserved block."""
    inspection = inspect_employee_benchmark_evidence(
        metadata, registry=registry, verify_registry=verify_registry)
    return [
        evidence_comparison_record(record)
        for record in inspection["records"]]


# ---------------------------------------------------------------------------
# Intake
# ---------------------------------------------------------------------------


def _judgment_artifact(record: Mapping[str, Any]) -> Dict[str, Any]:
    """The assessment-convention artifact (served pair + frozen binding)."""
    return {
        "schema": JUDGMENT_SCHEMA,
        "evidence_id": record.get("evidence_id"),
        "benchmark_id": (record.get("benchmark") or {}).get("id"),
        "dataset_id": (record.get("dataset") or {}).get("id"),
        "dataset_sha256": (record.get("dataset") or {}).get("sha256"),
        "scoring": record.get("scoring"),
        "observed_at": record.get("observed_at"),
        "observed_at_source": "execution_completion",
        "intake_at": record.get("intake_at"),
        "served_provider": record.get("provider"),
        "served_model": record.get("model"),
        "resolved_model": record.get("resolved_model"),
        "passed": record.get("passed"),
        "ok": record.get("passed"),
        "accuracy": record.get("accuracy"),
        "cases": record.get("cases"),
        "rubric_version": record.get("rubric_version"),
        "contract_version": record.get("contract_version"),
        "task_scope": record.get("task_scope"),
        "execution_id": (record.get("execution") or {}).get("id"),
        "campaign_id": (record.get("transport") or {}).get("campaign_id"),
    }


def _safe_slug(value: Any) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip("-")
    return text[:120] or "evidence"


def _write_artifact(
    artifact_dir: Path, record: Mapping[str, Any],
) -> Dict[str, Any]:
    artifact = _judgment_artifact(record)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    name = f"judgment-{_safe_slug(record.get('evidence_id'))}.json"
    path = artifact_dir / name
    payload = json.dumps(artifact, indent=2, sort_keys=True,
                         default=str) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload)
    os.replace(temporary, path)
    return {
        "schema": JUDGMENT_SCHEMA,
        "path": str(path),
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    }


def _rejected(
    reasons: Sequence[str],
    *,
    benchmark_id: Optional[str] = None,
    detail: Optional[str] = None,
    rejected_claims: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    return {
        "status": "rejected",
        "schema": SCHEMA_VERSION,
        "benchmark_id": benchmark_id,
        "reasons": _dedupe(list(reasons)),
        "detail": detail,
        "rejected_claims": list(rejected_claims or []),
        "evidence": None,
    }


def produce_employee_benchmark_evidence(
    *,
    execution_id: str,
    observation: Any,
    transport_journal: Any,
    benchmark_id: Optional[str] = None,
    registry: Optional[Mapping[str, Any]] = None,
    session_factory: Any = None,
    agent_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    artifact_dir: Optional[Any] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Score one campaign observation and append durable benchmark evidence.

    ``execution_id`` must name an existing ``AgentExecution``; its tenant,
    workspace and agent are the authority (supplied values are claims that must
    match). ``observation`` carries observed campaign outputs only.
    ``transport_journal`` must be the campaign's own sealed
    :class:`CampaignTransportJournal`, bound to this execution. ``now`` is the
    server intake clock for audit only; the evidence timestamp is always the
    execution's durable ``completed_at``.

    On success the validated record is appended under
    ``metadata_json[EVIDENCE_KEY]``. On rejection nothing is written.
    """
    execution_key = str(execution_id or "").strip()
    if not execution_key:
        return _rejected([REASON_EXECUTION_NOT_FOUND])

    journal_reasons = _journal_reasons(
        transport_journal, execution_id=execution_key)
    if journal_reasons:
        return _rejected(journal_reasons, benchmark_id=benchmark_id)

    benchmark, _registry, reasons = _prepare_benchmark(
        benchmark_id, registry=registry)
    if reasons or benchmark is None:
        return _rejected(reasons or [REASON_BENCHMARK_UNKNOWN],
                         benchmark_id=benchmark_id)

    score, score_reasons, rejected_claims = score_employee_benchmark(
        benchmark, observation)
    if score_reasons or score is None:
        return _rejected(
            score_reasons or [REASON_OBSERVATION_MISSING],
            benchmark_id=benchmark["benchmark_id"],
            rejected_claims=rejected_claims)

    identity, identity_reasons, transport_audit = (
        _served_identity_from_journal(transport_journal.entries))
    if identity_reasons or identity is None:
        return _rejected(
            identity_reasons or [REASON_IDENTITY_MISSING],
            benchmark_id=benchmark["benchmark_id"],
            rejected_claims=rejected_claims)
    transport_audit["campaign_id"] = transport_journal.campaign_id

    from core.models import AgentExecution

    try:
        if session_factory is None:
            from core.database import get_db_session

            scope = get_db_session()
        else:
            scope = session_factory()
        with scope as db:
            execution = db.get(AgentExecution, execution_key)
            if execution is None:
                execution = (
                    db.query(AgentExecution)
                    .filter(AgentExecution.id == execution_key)
                    .first())
            if execution is None:
                return _rejected(
                    [REASON_EXECUTION_NOT_FOUND],
                    benchmark_id=benchmark["benchmark_id"],
                    rejected_claims=rejected_claims)

            row_agent = str(execution.agent_id or "").strip()
            row_tenant = str(execution.tenant_id or "").strip()
            row_workspace = str(execution.workspace_id or "").strip()
            if agent_id is not None and str(agent_id).strip() != row_agent:
                return _rejected(
                    [REASON_AGENT_MISMATCH],
                    benchmark_id=benchmark["benchmark_id"],
                    rejected_claims=rejected_claims)
            if (tenant_id is not None
                    and str(tenant_id).strip() != row_tenant) or (
                    workspace_id is not None
                    and str(workspace_id).strip() != row_workspace):
                return _rejected(
                    [REASON_SCOPE_MISMATCH],
                    benchmark_id=benchmark["benchmark_id"],
                    rejected_claims=rejected_claims)
            if not row_agent or not row_tenant or not row_workspace:
                return _rejected(
                    [REASON_EXECUTION_SCOPE_MISSING],
                    benchmark_id=benchmark["benchmark_id"],
                    rejected_claims=rejected_claims)

            metadata = _metadata_mapping(execution.metadata_json)
            identity_reasons = _execution_identity_reasons(metadata, identity)
            if identity_reasons:
                return _rejected(
                    identity_reasons,
                    benchmark_id=benchmark["benchmark_id"],
                    rejected_claims=rejected_claims)

            completed_at, completion_reasons = _completion_reasons(
                execution_status=getattr(execution, "status", None),
                execution_completed_at=getattr(
                    execution, "completed_at", None),
                journal=transport_journal,
            )
            if completion_reasons or completed_at is None:
                return _rejected(
                    completion_reasons or [REASON_EXECUTION_INCOMPLETE],
                    benchmark_id=benchmark["benchmark_id"],
                    rejected_claims=rejected_claims)

            intake_at = _utc(now)
            run_scope = benchmark["task_scope"]
            record: Dict[str, Any] = {
                "schema": SCHEMA_VERSION,
                "authority": {
                    "producer": PRODUCER_ID,
                    "intake": "server",
                    "caller_claims": "rejected",
                },
                "evidence_id": (
                    f"employee-benchmark:{benchmark['benchmark_id']}:"
                    f"{execution_key}"),
                "capability": benchmark["capability"],
                "benchmark": {
                    "id": benchmark["benchmark_id"],
                    "dataset_version": benchmark["dataset_version"],
                    "frozen": str(
                        benchmark["dataset"].get("frozen") or ""),
                },
                "dataset": {
                    "id": benchmark["benchmark_id"],
                    "sha256": benchmark["dataset_sha256"],
                    "reference": benchmark["dataset_ref"],
                },
                "scoring": {
                    "version": benchmark["scoring_version"],
                    "sha256": benchmark["scoring_sha256"],
                },
                "task_scope": {
                    **run_scope,
                    "digest": task_scope_digest(run_scope),
                },
                "rubric_version": benchmark["rubric_version"],
                "contract_version": benchmark["contract_version"],
                "provider": identity["provider"],
                "model": identity["model"],
                "resolved_model": identity.get("resolved_model"),
                "served_identity": {
                    "provider": identity["provider"],
                    "model": identity["model"],
                    "resolved_model": identity.get("resolved_model"),
                    "source": "provider_response",
                    "identity_source": (
                        "transport_journal+execution"
                        if provenance_from_metadata(metadata)
                        else "transport_journal"),
                },
                "requested_routes": transport_audit["requested_routes"],
                "fallback": transport_audit["fallback"],
                "observed_at": completed_at.isoformat(),
                "observed_at_source": "execution_completion",
                "intake_at": intake_at.isoformat(),
                "passed": score["passed"],
                "accuracy": score["accuracy"],
                "case_count": score["case_count"],
                "cases": score["cases"],
                "execution": {
                    "id": execution_key,
                    "agent_id": row_agent,
                    "tenant_id": row_tenant,
                    "workspace_id": row_workspace,
                    "completed_at": completed_at.isoformat(),
                },
                "transport": transport_audit,
                "rejected_claims": _dedupe(rejected_claims),
            }

            existing_raw = _coerce_records(metadata.get(EVIDENCE_KEY))
            kept: List[Dict[str, Any]] = []
            discarded: List[Dict[str, Any]] = []
            for raw in existing_raw:
                validated, keep_reasons = validate_benchmark_record(
                    raw, benchmark=benchmark)
                if validated is not None:
                    kept.append(validated)
                else:
                    discarded.append({
                        "evidence_id": raw.get("evidence_id"),
                        "reasons": keep_reasons,
                    })

            core = _core_digest(record)
            # A stored record for this run that no longer validates means the
            # frozen set or scoring generation changed after it was written.
            # Re-scoring the same run under a new rubric would relabel history,
            # so the earlier observed result stays authoritative.
            if any(item.get("evidence_id") == record["evidence_id"]
                   for item in discarded):
                return _rejected(
                    [REASON_PRIOR_CONFLICT],
                    benchmark_id=benchmark["benchmark_id"],
                    detail=(
                        "the stored evidence for this run no longer matches "
                        "the current frozen benchmark or scoring version; "
                        "start a new campaign run instead of rescoring it"),
                    rejected_claims=rejected_claims)
            for prior in kept:
                if prior.get("evidence_id") != record["evidence_id"]:
                    continue
                prior_build = _identity(prior.get("resolved_model"))
                new_build = _identity(record.get("resolved_model"))
                if prior_build and new_build and (
                        prior_build.casefold() != new_build.casefold()):
                    # The same run cannot be served by two provider builds;
                    # the first observed build stays authoritative.
                    return _rejected(
                        [REASON_PRIOR_CONFLICT],
                        benchmark_id=benchmark["benchmark_id"],
                        detail=(
                            "existing evidence for this run was served by a "
                            "different provider build; refusing to overwrite "
                            "the earlier observation"),
                        rejected_claims=rejected_claims)
                prior_core = (prior.get("integrity") or {}).get(
                    "core_sha256")
                if prior_core == core:
                    return {
                        "status": "already_recorded",
                        "schema": SCHEMA_VERSION,
                        "benchmark_id": benchmark["benchmark_id"],
                        "evidence_id": record["evidence_id"],
                        "served_identity": identity,
                        "observed_at": prior.get("observed_at"),
                        "passed": prior.get("passed"),
                        "accuracy": prior.get("accuracy"),
                        "rejected_claims": _dedupe(rejected_claims),
                        "discarded_metadata": discarded,
                        "evidence": prior,
                    }
                # A different verdict/identity for the same run is a conflict:
                # the first observed result stays authoritative.
                return _rejected(
                    [REASON_PRIOR_CONFLICT],
                    benchmark_id=benchmark["benchmark_id"],
                    detail=(
                        "existing evidence for this run differs from the "
                        "current score or served identity; refusing to "
                        "overwrite the earlier observation"),
                    rejected_claims=rejected_claims)

            record["integrity"] = {
                "record_sha256": "",
                "core_sha256": core,
                "dataset_sha256": benchmark["dataset_sha256"],
                "scoring_sha256": benchmark["scoring_sha256"],
                "journal_sha256": transport_audit["digest"],
            }
            record["integrity"]["record_sha256"] = record_digest(record)

            if artifact_dir is not None:
                try:
                    artifact = _write_artifact(
                        Path(artifact_dir), record)
                except OSError as exc:
                    logger.warning(
                        "employee benchmark artifact write failed: %s", exc)
                    return _rejected(
                        [REASON_ARTIFACT_FAILED],
                        benchmark_id=benchmark["benchmark_id"],
                        detail=str(exc),
                        rejected_claims=rejected_claims)
                record["artifact"] = artifact
                # The artifact reference is part of the durable record.
                record["integrity"]["record_sha256"] = record_digest(record)

            checked, check_reasons = validate_benchmark_record(
                record, benchmark=benchmark)
            if checked is None:
                return _rejected(
                    check_reasons or [REASON_METADATA_AUTHORITY],
                    benchmark_id=benchmark["benchmark_id"],
                    rejected_claims=rejected_claims)

            metadata[EVIDENCE_KEY] = kept + [record]
            execution.metadata_json = metadata
            db.commit()
            return {
                "status": "recorded",
                "schema": SCHEMA_VERSION,
                "benchmark_id": benchmark["benchmark_id"],
                "evidence_id": record["evidence_id"],
                "served_identity": identity,
                "observed_at": record["observed_at"],
                "passed": record["passed"],
                "accuracy": record["accuracy"],
                "artifact": record.get("artifact"),
                "rejected_claims": _dedupe(rejected_claims),
                "discarded_metadata": discarded,
                "evidence": record,
            }
    except Exception as exc:  # noqa: BLE001 — intake must not corrupt rows
        logger.exception("employee benchmark intake failed: %s", exc)
        return _rejected(
            [REASON_EXECUTION_UNREADABLE],
            benchmark_id=benchmark["benchmark_id"],
            detail=f"{type(exc).__name__}: {exc}",
            rejected_claims=rejected_claims)


__all__ = [
    "CampaignTransportJournal",
    "EVIDENCE_KEY",
    "JUDGMENT_SCHEMA",
    "SCHEMA_VERSION",
    "activate_campaign_journal",
    "benchmark_registry_path",
    "deactivate_campaign_journal",
    "evidence_comparison_record",
    "inspect_employee_benchmark_evidence",
    "load_benchmark_registry",
    "load_employee_benchmark_evidence",
    "open_campaign_transport_journal",
    "produce_employee_benchmark_evidence",
    "record_digest",
    "score_employee_benchmark",
    "validate_benchmark_record",
]
