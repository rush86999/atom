"""Pure successor gates for the composed S7 date-only continuation.

These predicates are intentionally small and I/O-free: the acceptance
runner supplies captured/durable records, and the permanent tests replay
the reproduced false positives without another campaign.

The 2026-10-23 review found two holes in the first correction:

* ``cf_completed_scope`` accepted any supplied field containing the
  substring ``date`` (for example ``unrelated_date``), and did not check
  the accepted requirement's field set.
* ``s7_settlement_ok`` accepted a partial when *one* recognized prior
  obligation was present, even if another open obligation was the
  current turn's own missing field/comparison.

Both are closed here: the date-only scope requires the canonical
``expiration_date`` field on BOTH sides, and a partial is accepted only
when EVERY open obligation is the identified prior S3 verification.

Obligation accounting
---------------------
The runner captures the durable prior obligation from THIS run before
S7 (the task record's open questions at that point) and passes it as
``expected_prior``. The gate matches actual S7 open questions against
that captured identity (``question_id`` + ``source_operation`` +
``next_action`` + ``kind``); a fresh run's UUIDs are therefore first-class,
while an S7-created obligation cannot bootstrap itself into the expected
set. When no structured capture exists, the fallback requires every
``open_work`` string to equal the exact fixture-bounded prior obligation
(``S7_PRIOR_OBLIGATION``). That fallback is deliberately conservative but
it is a LIMITATION: it proves "every recorded text gap is the known prior
obligation", not that the text channel enumerated every obligation. The
runner records which channel it used and ``ATTEMPT3_RESULT.md`` discloses
the limitation. When the structured record IS available the text snapshot
is still cross-checked, so a structured record cannot hide an extra
recorded gap.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Iterable, List, Optional

FIXTURE_NAME = "approved_records_q2026_114.txt"
EXPECTED_DATE_FIELD = "expiration_date"
S7_PRIOR_OBLIGATION = "re-run the workbook verification for the quote's items"
PRIOR_OBLIGATION_KIND = "verification"


def _canonical(value: Any) -> str:
    return str(value or "").strip().casefold()


def _field_list(value: Any) -> List[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [_canonical(item) for item in value if _canonical(item)]


def _fixture_matched(cf: Dict[str, Any]) -> bool:
    return any(
        _canonical(item.get("file_name")) == _canonical(FIXTURE_NAME)
        for item in (cf.get("matched") or [])
        if isinstance(item, dict))


def cf_completed_scope(
        cf: Dict[str, Any],
        requirement: Dict[str, Any]) -> bool:
    """The date-only typed scope was fully supplied by the named source.

    Exact canonical coverage, not substring matching: the accepted
    requirement must be a non-broader, required, attached-artifact
    request for exactly ``expiration_date``, and the fulfillment carrier
    must supply exactly that field. ``unrelated_date``, an extra field,
    a missing field, or a broader S3 requirement is not this scope.
    """
    cf = cf if isinstance(cf, dict) else {}
    requirement = requirement if isinstance(requirement, dict) else {}
    requested = _field_list(requirement.get("fields"))
    supplied = _field_list(cf.get("supplied_fields"))
    return bool(
        cf.get("state") == "completed"
        and requirement.get("required") is True
        and requirement.get("artifact_attached") is True
        and requirement.get("broader_comparison") is False
        and requested == [EXPECTED_DATE_FIELD]
        and supplied == [EXPECTED_DATE_FIELD]
        and _fixture_matched(cf)
        and not cf.get("missing_comparison")
        and not (cf.get("missing_fields") or []))


def s7_completed_scope(
        cf: Dict[str, Any],
        task: Dict[str, Any],
        requirement: Dict[str, Any]) -> bool:
    """The clean-completion case: exact date scope plus a met objective."""
    task = task if isinstance(task, dict) else {}
    return bool(
        cf_completed_scope(cf, requirement)
        and task.get("objective_met") is True
        and (task.get("delivery") or {}).get("delivered") is True)


def _fallback_texts(fallback: Dict[str, Any]) -> List[str]:
    return [
        str(item).strip()
        for item in ((fallback or {}).get("open_work") or [])
        if str(item).strip()]


def _structured_open(
        obligations: Optional[Iterable[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    return [
        item for item in (obligations or [])
        if isinstance(item, dict)
        and _canonical(item.get("status") or "open") == "open"]


def obligation_identity(item: Dict[str, Any]) -> Dict[str, str]:
    """The durable fields that identify one task obligation."""
    return {
        "question_id": _canonical(item.get("question_id")),
        "source_operation": _canonical(item.get("source_operation")),
        "next_action": str(item.get("next_action") or "").strip(),
        "kind": _canonical(item.get("kind")),
    }


def capture_prior_obligation(
        obligations: Optional[Iterable[Dict[str, Any]]]
        ) -> Dict[str, Any]:
    """Capture the open obligations that exist BEFORE the S7 turn.

    The caller invokes this only between the durable record's update after
    S3 and the start of S7. The returned identities are the expected prior
    work: they cannot be derived from whatever S7 later reports, so a
    fresh run's generated UUIDs are legitimate and an S7-created
    obligation is not.
    """
    items = _structured_open(obligations)
    return {
        "source": "durable_task_record_before_s7",
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "items": [dict(item) for item in items],
    }


def _expected_items(expected_prior: Any) -> List[Dict[str, Any]]:
    if isinstance(expected_prior, dict):
        expected_prior = expected_prior.get("items")
    return _structured_open(expected_prior)


def _is_prior_s3_obligation(
        item: Any,
        expected_prior: Optional[Iterable[Dict[str, Any]]] = None) -> bool:
    """The identified prior obligation, never a generic negative phrase.

    Text items must equal the fixture-bounded prior obligation exactly.
    Structured items must match an identity captured from the durable
    record BEFORE S7: question_id + source_operation + next_action + kind.
    A question that appears only in S7's own open list is not owned.
    """
    if isinstance(item, dict):
        if _canonical(item.get("status") or "open") != "open":
            return False
        identity = obligation_identity(item)
        if identity["kind"] != PRIOR_OBLIGATION_KIND:
            return False
        return any(
            identity == obligation_identity(expected)
            for expected in _expected_items(expected_prior))
    text = str(item).strip()
    if text == S7_PRIOR_OBLIGATION:
        return True
    # Live-world shape: the prior open obligation is not guaranteed to be
    # the scratch fixture's workbook wording. The text must still match an
    # obligation captured from THIS run's durable record before S7; an
    # arbitrary partial text is rejected.
    return any(
        text == str(expected.get("next_action") or "").strip()
        for expected in _expected_items(expected_prior)
        if str(expected.get("next_action") or "").strip())


def all_open_work_is_prior_s3(
        fallback: Dict[str, Any],
        obligations: Optional[Iterable[Dict[str, Any]]] = None,
        expected_prior: Optional[Iterable[Dict[str, Any]]] = None) -> bool:
    """Every remaining obligation belongs to the captured prior work.

    A single recognized prior obligation is not enough: an additional
    unknown, turn-own, or second prior-looking gap rejects the
    honest-partial branch. At least one open obligation must exist.

    Structured obligations are authoritative for IDENTITY, but the
    expected identity must have been captured BEFORE S7. The resolver's
    text snapshot is still checked when present. Otherwise a structured
    record that omitted a text gap (the reproduced "current requested
    field could not be checked" case) would license the partial.
    """
    texts = _fallback_texts(fallback)
    if obligations is not None:
        structured = _structured_open(obligations)
        expected = _expected_items(expected_prior)
        return bool(
            structured
            and expected
            and all(
                _is_prior_s3_obligation(item, expected)
                for item in structured)
            and all(
                _is_prior_s3_obligation(item, expected)
                for item in texts))
    return bool(texts) and all(
        _is_prior_s3_obligation(item) for item in texts)


def no_open_obligations(
        fallback: Dict[str, Any],
        obligations: Optional[Iterable[Dict[str, Any]]] = None) -> bool:
    """No open structured question and no fallback open-work text."""
    if _fallback_texts(fallback):
        return False
    if obligations is None:
        return True
    return not _structured_open(obligations)


def s7_settlement_ok(
        final: Dict[str, Any],
        cf: Dict[str, Any],
        task: Dict[str, Any],
        fallback: Dict[str, Any],
        requirement: Dict[str, Any],
        obligations: Optional[Iterable[Dict[str, Any]]] = None,
        expected_prior: Optional[Iterable[Dict[str, Any]]] = None) -> bool:
    """S7's date-only continuation settled truthfully.

    ``completed`` requires the exact date scope, a met objective, a
    delivered result, and no open obligations. ``partial`` is honest only
    when THIS turn's date scope is fully supplied, the result was
    delivered, and EVERY open obligation (structured and text) is the
    prior broader S3 verification (S3 timed out before it could run).
    """
    if not isinstance(final, dict) or final.get("final_success") is not True:
        return False
    outcome = final.get("final_outcome")
    delivered = ((task or {}).get("delivery") or {}).get("delivered") is True
    if outcome == "completed":
        return bool(
            s7_completed_scope(cf, task, requirement)
            and no_open_obligations(fallback, obligations))
    if outcome == "partial":
        return bool(
            cf_completed_scope(cf, requirement)
            and delivered
            and all_open_work_is_prior_s3(
                fallback, obligations, expected_prior))
    return False


def restart_agreement_ok(pre: Dict[str, Any],
                         post: Dict[str, Any]) -> bool:
    """Exact agreement with the accepted PRE-restart S7 outcome.

    Both ``completed`` and the reviewed honest ``partial`` are legitimate.
    An arbitrary partial is rejected because ``s7_gate_ok`` must be true
    (the reviewed date/source/settlement gate accepted the pre-restart
    settlement). The reload must reproduce the same outcome, success,
    content, execution identity, status, and delivery record exactly.
    """
    if not isinstance(pre, dict) or not isinstance(post, dict):
        return False
    if pre.get("outcome") not in ("completed", "partial"):
        return False
    if pre.get("s7_gate_ok") is not True:
        return False
    keys = ("outcome", "success", "message", "execution_id", "status",
            "delivery")
    return all(pre.get(key) == post.get(key) for key in keys)


def _ref_supplies_fixture(ref: Any) -> bool:
    if not isinstance(ref, dict):
        return False
    if _canonical(ref.get("file_name")) == _canonical(FIXTURE_NAME):
        return True
    source = ref.get("source")
    return bool(
        isinstance(source, dict)
        and _canonical(source.get("source_id")) == _canonical(FIXTURE_NAME))


def _record_supplied_fixture(record: Dict[str, Any]) -> bool:
    """Did this execution's durable outcome actually carry the fixture?

    Top-level durable evidence counts. A tool-outcome reference counts
    only when that tool is marked ``verified`` — a planned or unverified
    reference is not proof the fixture was supplied.
    """
    outcome = (record or {}).get("task_outcome") or {}
    for ref in outcome.get("evidence_refs") or []:
        if _ref_supplies_fixture(ref):
            return True
    for tool in outcome.get("tool_outcomes") or []:
        if not isinstance(tool, dict) or tool.get("verified") is not True:
            continue
        for ref in tool.get("evidence_refs") or []:
            if _ref_supplies_fixture(ref):
                return True
    return False


def continuation_source_ok(
        refs: Dict[str, Any],
        observed: Iterable[Dict[str, Any]],
        origin: Any,
        scope_change: Any,
        *,
        expected_conversation_id: Any,
        expected_workspace_id: Any,
        antecedent_records: Dict[str, Dict[str, Any]]) -> bool:
    """The continuation resolved a fixture antecedent in the same scope.

    Two carried ids agreeing with each other is not attribution. Each
    antecedent must resolve to a durable execution in the SAME
    conversation and workspace, and the antecedent that the observation
    binds to the fixture must have actually supplied the fixture in its
    recorded outcome.
    """
    refs = refs if isinstance(refs, dict) else {}
    conversation = str(expected_conversation_id or "").strip()
    workspace = str(expected_workspace_id or "").strip()
    if not conversation or not workspace:
        return False
    if refs.get("state") != "resolved":
        return False
    if _canonical(refs.get("resolved_file")) != _canonical(FIXTURE_NAME):
        return False
    _origin = str(origin or "").strip().casefold()
    if not (_origin.startswith("llm:")
            or _origin.startswith("deterministic:")):
        return False
    if _canonical(scope_change) == "unresolved":
        return False

    antecedent_ids = {
        str(item.get("execution_id") or "").strip()
        for item in (refs.get("antecedents") or [])
        if isinstance(item, dict) and item.get("execution_id")}
    antecedent_ids.discard("")
    if not antecedent_ids:
        return False

    fixture_antecedent_ids = {
        str(item.get("execution_id") or "").strip()
        for item in (observed or [])
        if isinstance(item, dict)
        and _canonical(item.get("file_name")) == _canonical(FIXTURE_NAME)
        and str(item.get("execution_id") or "").strip() in antecedent_ids}
    if not fixture_antecedent_ids:
        return False

    supplied_ids = set()
    records = antecedent_records or {}
    for antecedent_id in antecedent_ids:
        record = records.get(antecedent_id)
        if not isinstance(record, dict):
            return False
        if str(record.get("session_id") or "").strip() != conversation:
            return False
        if str(record.get("workspace_id") or "").strip() != workspace:
            return False
        if _record_supplied_fixture(record):
            supplied_ids.add(antecedent_id)
    # The specific antecedent the observation binds to the fixture must
    # be the one whose durable outcome supplied it.
    return bool(fixture_antecedent_ids & supplied_ids)
