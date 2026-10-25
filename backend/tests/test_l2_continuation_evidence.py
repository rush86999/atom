"""L2 — the continuation ask's evidence requirement (S7 finding).

Preserved finding (composed job run 4,
``browser_composed_job_20261017_221606_5fdbf5.json``): the S7 continuation
ask

    "What is the current Valid until date on the draft, and does it still
     match the approved record?"

was answered correctly but settled ``unconfirmed`` (``s7-reply-received``
exclusion): the accepted decision carried only a conversation action
(``references.sources: []``, ``provenance.signals: []``,
``task_state_view.active_objective: null``), so no evidence requirement was
captured and the turn's own VERIFIED retrieval of the named source
(``context_assembly`` carried ``approved_records_q2026_114.txt``) could not
certify. The S3 comparison turn — the same subject with a message-named
source — captured ``references.sources: ["document"]`` and validated.

Repair (L2, 2026-10-18): the async interpretation's resolved source
reference is composed into the accepted decision
(``apply_interpretation_references``) — fail-closed against the
conversation's OBSERVED evidence. Corrected after owner review: the
reference authority must not be permissive.

Reference-resolution contract (owner review, 2026-10-18):

* **Requested sources nominate; observed sources are evidence.**
  ``session_requested_sources`` (requirement carriers) never resolve a
  reference; only ``session_observed_sources`` (supplied retrieval
  observations) do.
* **No substring donation.** Token-boundary matching with plural
  tolerance only: "approved" never matches "unapproved"; "record" matches
  "records".
* **All eligible matches are collected before deciding.** Zero -> the
  unresolved reference is preserved (name proposals inside an observed
  evidence context); one -> the identity is adopted; several -> the
  AMBIGUITY is preserved (never insertion-order selection).
* **Generic kinds cannot prove an antecedent.** A kind proposal resolves
  to the observed sources of its family (one -> adopt, several ->
  ambiguity, none -> no obligation).
* **Several proposed files never collapse into the first filename** — the
  candidate set is unioned; several distinct candidates mean ambiguity.

Layer map:

* decision layer — the composer, the split collectors, and the
  interpretation-prompt enrichment (successor-only capability tests);
* real turn chain — ``_drive_continuation_turn`` drives the product entry
  point (``process_chat_message``) with controlled external seams (the
  interpretation record, the retrieval assembler, the planner/reply
  endpoints); decision, composition, requirement stash, settlement and
  the durable row run REAL. Parent-compatible: on the parent (no
  composition) the capture test fails for the intended reason.
"""

import asyncio
import json
import re
import uuid
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Shared product-boundary harness (fixtures + helpers).
from tests.test_source_ask_tool_execution import (
    _ScriptedReplyEndpoint,
    _authorized_workspace,
    _register_local_route,
    scoped_world,  # noqa: F401 — pytest fixture
    world_app,  # noqa: F401 — pytest fixture
)

S7_ASK = ("What is the current Valid until date on the draft, and does it "
          "still match the approved record?")
PRIOR_FILE = "approved_records_q2026_114.txt"
PRIOR_FILE_2 = "approved_records_q2026_115.txt"
ATTEMPT1_ANNOTATED_SOURCES = [
    "approved_records_q2026_114.txt (the user's uploaded Approved Records "
    "document)",
    "draft quotation (source not yet named by the user)",
]
PRIOR_REQ_KEY = "_evidence_requirement_l2prior0001"
PRIOR_OBS_KEY = "_retrieval_source_observations_l2prior0001"
S7_REPLY = ("The draft’s Valid until date is 2026-12-31, which still "
            "matches the approved record’s Approved valid until: "
            "2026-12-31.")
S7_CANVAS = {
    "canvas_id": "canvas-s7",
    "canvas_type": "document",
    "title": "Quotation Q-2026-114 (DRAFT)",
    "content": {"body": (
        "# Quotation Q-2026-114 (DRAFT)\n\n"
        "Client: Dunmore Fabrication LLC\n"
        "Unit price: $48,000.00\n"
        "Terms: Net 45\n"
        "Valid until: 2026-12-31\n")},
}


def _source_refs_from_prompt(prompt: str) -> dict:
    """Parse the structured SOURCE REFERENCES JSON block from the prompt."""
    match = re.search(
        r"SOURCE REFERENCES \(structured JSON\): (\{.*\})", prompt or "")
    assert match, f"structured source references missing from prompt: {prompt!r}"
    return json.loads(match.group(1))


class _RecordingStructuredGeneration:
    """The ONLY controlled seam in the producer-boundary tests."""

    def __init__(self, payload: dict, *, validate: bool = True):
        self.payload = payload
        self.validate = validate
        self.prompts: list[str] = []
        self.response_models: list = []
        self.call_kwargs: list[dict] = []
        self.calls = 0

    async def generate_structured_response(
        self, *, prompt, response_model, system_instruction, model=None,
        task_type=None, temperature=None, disable_reasoning=None,
        max_tokens=None, route_trace_id=None, allow_moa=None, **kwargs,
    ):
        self.prompts.append(prompt)
        self.response_models.append(response_model)
        self.call_kwargs.append({
            "model": model,
            "task_type": task_type,
            "temperature": temperature,
            "disable_reasoning": disable_reasoning,
            "max_tokens": max_tokens,
            "route_trace_id": route_trace_id,
            "allow_moa": allow_moa,
            **kwargs,
        })
        self.calls += 1
        if self.validate:
            return response_model(**self.payload)
        return dict(self.payload)


class _SlowGeneration(_RecordingStructuredGeneration):
    """A generation that outlives the patched wait_for deadline."""

    def __init__(self, delay: float):
        super().__init__({}, validate=False)
        self.delay = delay

    async def generate_structured_response(self, **kwargs):
        self.calls += 1
        await asyncio.sleep(self.delay)
        return {}


def _run_producer_boundary(
    world_app, scoped_world, *, sources, message=S7_ASK,
    observed_files=None, requested=None, canvas=True,
    scope_change=None, validate=True, generation=None,
):
    """Real interpretation normalization -> real composer -> real stash.

    Only ``generate_structured_response`` is replaced (the model call).
    Everything after it — normalization, floor construction, reference
    composition, catalog identity resolution and the execution-keyed
    requirement stash — runs the product code unchanged.
    """
    from core.turn_decision import (
        apply_interpretation_references, build_turn_decision,
        interpret_turn_request, reset_interpretation_for_tests,
        turn_evidence_required,
    )
    from integrations.chat_orchestrator import _stash_evidence_requirement

    ws = _authorized_workspace(world_app, scoped_world)
    for name in (observed_files or []):
        _seed_catalog_document(scoped_world, ws, file_name=name)
    session = _session_with(observed_files=observed_files,
                            requested=requested)
    context = ({"canvas_id": "canvas-l2",
                "canvas_title": "Quotation Q-2026-114 (DRAFT)",
                "canvas_summary": "Draft quotation with Terms and "
                                  "Valid until."}
               if canvas else {})
    generated = {
        "actions": [{"kind": "research",
                     "subjects": ["draft quotation"], "note": ""}],
        "subjects": ["draft quotation"],
        "sources": list(sources),
        "requested_fields": ["valid until date"],
        "output_format": "",
        "constraints": [],
        "scope_change": scope_change or (
            "continue" if observed_files else "replace"),
        "confidence": 0.9,
    }
    generation = generation or _RecordingStructuredGeneration(
        generated, validate=validate)
    reset_interpretation_for_tests()
    interpretation = asyncio.run(interpret_turn_request(
        message, session, [], context=context, session_id="sess-l2",
        request_id="req-l2", llm_service=generation))
    decision = build_turn_decision(
        message, session, [], context, session_id="sess-l2")
    composed = apply_interpretation_references(
        decision, interpretation, session)
    execution_id = f"exec-{uuid.uuid4().hex[:8]}"
    requirement = _stash_evidence_requirement(
        session, execution_id, composed, message,
        turn_evidence_required(composed),
        workspace_id=ws["workspace_id"], canvas_attached=bool(canvas),
        accepted_request=interpretation)
    return {
        "ws": ws,
        "session": session,
        "interpretation": interpretation,
        "decision": decision,
        "composed": composed,
        "requirement": requirement,
        "generation": generation,
        "execution_id": execution_id,
    }


def _resolved_interpretation(sources=None, scope_change="continue"):
    """The semantic layer's record for the S7 ask (the controlled seam)."""
    return {
        "schema": "turn-interpretation-1",
        "request_id": "",
        "origin": "llm:test-model",
        "unresolved_reason": "",
        "message": S7_ASK,
        "actions": [{"kind": "research", "subjects": [],
                     "note": "", "authorization": "granted"}],
        "subjects": [],
        "sources": list(sources if sources is not None
                        else ["the approved record"]),
        "requested_fields": ["valid until date"],
        "output_format": "",
        "constraints": [],
        "scope_change": scope_change,
        "confidence": 0.9,
        "deterministic_decision": None,
    }


def _observed(*names):
    return [{
        "observation_id": f"l2-prior-{i}",
        "source": "ingested",
        "file_name": name,
        "title": name,
        "workspace_id": "ws-1",
        "content_hash": "",
    } for i, name in enumerate(names)]


def _session_with(observed_files=None, requested=None):
    """A conversation state: observed retrieval observations (+ optional
    requirement nominations)."""
    session = {}
    if observed_files:
        session[PRIOR_OBS_KEY] = _observed(*observed_files)
    if requested:
        session[PRIOR_REQ_KEY] = requested
    return session


def _seed_conversation_evidence(session, workspace_id, observed_files=None):
    """The conversation's prior verified evidence (the S3 turn's carriers,
    reconstructed from the preserved run-4 records)."""
    files = list(observed_files or [PRIOR_FILE])
    session[PRIOR_REQ_KEY] = {
        "required": True,
        "sources": ["document"],
        "file": None,
        "fields": ["expiration_date"],
        "subjects": [],
        "identity": {"state": "kind_only", "candidates": []},
        "artifact_attached": True,
        # The prior S3 turn was broad ("flag anything that differs"); the
        # S7 date-only follow-up must not inherit it.
        "broader_comparison": True,
    }
    session[PRIOR_OBS_KEY] = [
        {"observation_id": f"l2-prior-{i}",
         "source": "ingested",
         "file_name": name,
         "title": name,
         "workspace_id": workspace_id,
         "content_hash": ""}
        for i, name in enumerate(files)]


def _seed_catalog_document(scoped_world, ws, file_name=PRIOR_FILE):
    """The uploaded document as catalog identity (world state — the same
    IngestedDocument row the product upload route writes; no receipt)."""
    from datetime import datetime, timezone

    from core.models import IngestedDocument

    db = scoped_world["Session"]()
    try:
        db.add(IngestedDocument(
            id=f"doc_l2_{uuid.uuid4().hex[:8]}",
            workspace_id=ws["workspace_id"],
            tenant_id=ws["tenant_id"],
            external_id=f"upload_l2_{uuid.uuid4().hex[:8]}",
            integration_id="manual_upload",
            file_name=file_name,
            file_path=f"upload:{file_name}",
            file_type="txt",
            file_size_bytes=111,
            content_preview=("ATOM PHASE D FIXTURE — internal notes.\n"
                             "Approved valid until: 2026-12-31\n"),
            ingested_at=datetime.now(timezone.utc),
            freshness_status="fresh",
        ))
        db.commit()
    finally:
        db.close()


def _turn_outcome(scoped_world) -> dict:
    """The latest execution row's full task_outcome (fresh ORM read)."""
    db = scoped_world["Session"]()
    try:
        from core.models import AgentExecution

        row = (db.query(AgentExecution)
               .order_by(AgentExecution.started_at.desc(),
                         AgentExecution.id.desc())
               .first())
        if row is None:
            return {}
        meta = row.metadata_json if isinstance(row.metadata_json, dict) else {}
        return meta.get("task_outcome") or {}
    finally:
        db.close()


def _settlement_from_turn(session, execution_id, workspace_id):
    """The settlement decision over the turn's OWN session state.

    ``_context_backed_fulfillment`` is the resolver's single certification
    predicate (consumed by ``_fallback_turn_outcome`` and the durable
    builder); calling it with the real session carriers asserts the
    certification the served turn would resolve. The scratch harness has
    no task run, so the response envelope's work-turn gate would discard
    the outcome before it is attached — this reads the same decision one
    layer earlier, on the state the turn actually produced."""
    from integrations.chat_orchestrator import (
        _context_backed_fulfillment, _fallback_turn_outcome,
    )

    verdict = _context_backed_fulfillment(session, execution_id,
                                          workspace_id)
    settled = _fallback_turn_outcome(
        session, execution_id, {}, {}, workspace_id=workspace_id)
    return verdict, settled


def _turn_requirement(session, out):
    eid = str(out.get("execution_id") or "")
    return eid, (session.get(f"_evidence_requirement_{eid}") or {})


def _drive_continuation_turn(
        scoped_world, world_app, *, interpretation,
        session_id="sess-l2", reply_text=S7_REPLY,
        message=S7_ASK, session_out=None, seed_evidence=True,
        observed_files=None, canvas=None, persist_history=False):
    """One real product turn for the continuation ask.

    Controlled external seams: the interpretation record, the
    memory-context assembler (retrieval), the planner structured call and
    the reply endpoint. Decision, composition, requirement stash,
    settlement and the durable row run for real."""
    import integrations.chat_orchestrator as co
    from core.llm_service import LLMService

    files = list(observed_files or [PRIOR_FILE])
    ep = _ScriptedReplyEndpoint(reply_text)
    ep.__enter__()
    try:
        ws = _authorized_workspace(world_app, scoped_world)
        for name in files:
            _seed_catalog_document(scoped_world, ws, file_name=name)
        _register_local_route(world_app, ws, ep.base_url)
        orch = co.ChatOrchestrator.__new__(co.ChatOrchestrator)
        orch.tenant_id = "default"
        orch._cancelled_sessions = set()
        orch._budget_exceeded_runs = set()
        orch.llm_service = LLMService(tenant_id="default")
        session = {"id": session_id, "history": []}
        if seed_evidence:
            _seed_conversation_evidence(session, ws["workspace_id"],
                                        observed_files=files)
        if session_out is not None:
            session_out["session"] = session
            session_out["workspace_id"] = ws["workspace_id"]
            session_out["interpret_calls"] = 0

        async def _fake_interpret(message_, session_=None, history=None,
                                  context=None, **kw):
            if session_out is not None:
                session_out["interpret_calls"] = (
                    session_out.get("interpret_calls") or 0) + 1
            return dict(interpretation)

        async def _fake_assemble(**kwargs):
            out = kwargs.get("source_observations_out")
            if isinstance(out, list):
                out.append({
                    "observation_id": "l2-turn-obs",
                    "source": "ingested",
                    "file_name": files[0],
                    "title": files[0],
                    "workspace_id": ws["workspace_id"],
                    "content_hash": "",
                    "excerpt": "Approved valid until: 2026-12-31",
                    "field_associations": {
                        "expiration_date": {
                            "value": "2026-12-31",
                            "subject": "",
                            "span": "Approved valid until: 2026-12-31",
                        },
                    },
                })
            return ("MEMORY CONTEXT: the record "
                    f"({files[0]}) — Approved valid until: 2026-12-31")

        async def _plan_ce(*a, **k):
            class _P:
                wants_edit = False
            return _P()

        async def _structured(llm_service, *, prompt, response_model,
                              system_instruction, **_kw):
            from core.chat_tool_planner import ToolPlan

            return ToolPlan(use_tool=False, service=None, intent="search",
                            query="", reason="conversation turn")

        with ExitStack() as st:
            for cm in [
                patch.object(orch, "_get_or_create_session",
                             return_value=session),
                patch.object(orch, "_resolve_canvas_ctx",
                             new=AsyncMock(return_value=canvas)),
                patch.object(orch, "_record_chat_step", new=AsyncMock()),
                patch.object(orch, "_emit_agent_status", new=AsyncMock()),
                *([] if persist_history else [
                    patch.object(orch, "_update_session", new=MagicMock())]),
                patch.object(orch, "_load_conversation_mail_handles",
                             return_value=([], [])),
                patch.object(orch, "_route_to_features",
                             new=AsyncMock(return_value={})),
                patch("core.memory_context_assembler.assembly_enabled",
                      return_value=True),
                patch("core.memory_context_assembler."
                      "assemble_memory_context", new=_fake_assemble),
                patch("core.turn_decision.interpret_turn_request",
                      new=_fake_interpret),
                patch("core.chat_mini_app_authoring.try_handle",
                      new=AsyncMock(return_value=None)),
                patch("core.chat_tool_planner._provenance_menu",
                      new=AsyncMock(return_value="")),
                patch("integrations.chat_orchestrator."
                      "_verbatim_mail_evidence",
                      new=AsyncMock(return_value=[])),
                patch("integrations.chat_orchestrator._begin_task_edit",
                      return_value={"status": "legacy"}),
                patch("core.chat_canvas_editor.plan_canvas_edit",
                      new=AsyncMock(side_effect=_plan_ce)),
                patch("core.student_learning_service.get_agent_lessons",
                      return_value=[]),
                patch("core.chat_tool_planner._structured_with_fallback",
                      new=AsyncMock(side_effect=_structured)),
            ]:
                st.enter_context(cm)
            _context = {"workspace_id": ws["workspace_id"]}
            if canvas:
                _context["canvas_id"] = canvas["canvas_id"]
            out = asyncio.run(orch.process_chat_message(
                ws["user_id"], message, session_id, context=_context))
        return out, session, ep
    finally:
        ep.__exit__()


class TestL2ReferenceResolution:
    """The composer's reference contract (owner-review corrections).

    Successor-only capability tests (the composer does not exist on the
    parent)."""

    def test_unique_name_reference_resolves_to_the_conversation_source(self):
        from core.turn_decision import (
            apply_interpretation_references, build_turn_decision,
            turn_evidence_required,
        )

        session = _session_with(observed_files=[PRIOR_FILE])
        decision = build_turn_decision(S7_ASK, session, [])
        assert decision["references"]["sources"] == []
        assert turn_evidence_required(decision) is False
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(), session)
        assert composed["references"]["sources"] == ["document"]
        assert composed["references"]["file"] == {"file_name": PRIOR_FILE}
        marker = composed["references"]["continuation_evidence"]
        assert marker["state"] == "resolved"
        assert marker["resolved_file"] == PRIOR_FILE
        assert turn_evidence_required(composed) is True

    def test_two_candidates_preserve_ambiguity(self):
        """Owner regression: Alpha and Beta approved-record files must
        never be silently reduced to one."""
        from core.turn_decision import (
            apply_interpretation_references, build_turn_decision,
        )

        session = _session_with(observed_files=[
            "alpha_approved_records.txt", "beta_approved_records.txt"])
        decision = build_turn_decision(S7_ASK, session, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(), session)
        refs = composed["references"]
        marker = refs["continuation_evidence"]
        assert marker["state"] == "ambiguous"
        assert refs.get("file") is None, (
            "no candidate may be silently selected; got "
            f"{refs.get('file')!r}")
        names = sorted(c["file_name"] for c in marker["candidates"])
        assert names == ["alpha_approved_records.txt",
                         "beta_approved_records.txt"]
        assert refs["sources"] == ["document"]

    def test_wrong_name_does_not_resolve_by_substring(self):
        """Owner regression: 'the approved record' must never resolve to
        `unapproved_records.txt` (no substring donation)."""
        from core.turn_decision import (
            apply_interpretation_references, build_turn_decision,
        )

        session = _session_with(observed_files=["unapproved_records.txt"])
        decision = build_turn_decision(S7_ASK, session, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(), session)
        refs = composed["references"]
        marker = refs["continuation_evidence"]
        assert marker["state"] == "unresolved"
        assert refs.get("file") is None
        assert marker["names"] == ["the approved record"]
        assert "unapproved_records.txt" not in json.dumps(refs)

    def test_short_identifier_constraint_is_preserved(self):
        """Owner regression: a short numeric identifier ("381") is an
        identity constraint — never discarded; it must not match a
        different order number (6603)."""
        from core.turn_decision import (
            apply_interpretation_references, build_turn_decision,
        )

        negative = _session_with(
            observed_files=["approved_records_6603.txt"])
        decision = build_turn_decision(S7_ASK, negative, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(["approved record 381"]),
            negative)
        marker = composed["references"]["continuation_evidence"]
        assert marker["state"] == "unresolved", (
            f"381 must not match 6603; got {marker!r}")
        assert composed["references"].get("file") is None

        positive = _session_with(
            observed_files=["approved_records_381.txt"])
        decision = build_turn_decision(S7_ASK, positive, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(["approved record 381"]),
            positive)
        assert composed["references"]["file"] == {
            "file_name": "approved_records_381.txt"}
        assert (composed["references"]["continuation_evidence"]["state"]
                == "resolved")

    def test_identifier_suffix_is_not_stemmed(self):
        """Owner regression: "AB12" is an identifier — its characters are
        part of the identity; never stemmed to match "AB12S"."""
        from core.turn_decision import (
            apply_interpretation_references, build_turn_decision,
        )

        negative = _session_with(
            observed_files=["approved_records_AB12S.txt"])
        decision = build_turn_decision(S7_ASK, negative, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(["approved record AB12"]),
            negative)
        marker = composed["references"]["continuation_evidence"]
        assert marker["state"] == "unresolved", (
            f"AB12 must not match AB12S; got {marker!r}")
        assert composed["references"].get("file") is None

        positive = _session_with(
            observed_files=["approved_records_AB12.txt"])
        decision = build_turn_decision(S7_ASK, positive, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(["approved record AB12"]),
            positive)
        assert composed["references"]["file"] == {
            "file_name": "approved_records_AB12.txt"}

    def test_unmatched_proposal_is_never_dropped(self):
        """Owner regression: "Alpha and Gamma records" with only Alpha
        observed — the unmatched Gamma proposal must be preserved
        (unresolved), never silently dropped because Alpha resolved."""
        from core.turn_decision import (
            apply_interpretation_references, build_turn_decision,
        )

        negative = _session_with(observed_files=["alpha_records.txt"])
        decision = build_turn_decision(S7_ASK, negative, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(
                ["Alpha records", "Gamma records"]), negative)
        marker = composed["references"]["continuation_evidence"]
        assert marker["state"] == "unresolved", (
            f"the unmatched Gamma proposal must win; got {marker!r}")
        assert marker["names"] == ["Gamma records"]
        assert composed["references"].get("file") is None, (
            "Alpha must not be adopted while Gamma is unmatched")

        # Positive twin 1: BOTH observed -> two distinct files clarify.
        both = _session_with(
            observed_files=["alpha_records.txt", "gamma_records.txt"])
        decision = build_turn_decision(S7_ASK, both, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(
                ["Alpha records", "Gamma records"]), both)
        marker = composed["references"]["continuation_evidence"]
        assert marker["state"] == "ambiguous"
        assert sorted(c["file_name"] for c in marker["candidates"]) == [
            "alpha_records.txt", "gamma_records.txt"]

        # Positive twin 2: the same source proposed twice -> resolved.
        same = _session_with(observed_files=["alpha_records.txt"])
        decision = build_turn_decision(S7_ASK, same, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(
                ["Alpha records", "Alpha records"]), same)
        assert composed["references"]["file"] == {
            "file_name": "alpha_records.txt"}
        assert (composed["references"]["continuation_evidence"]["state"]
                == "resolved")

    def test_missing_kind_proposal_is_never_dropped(self):
        """Owner regression: `document` AND `email` proposed with only a
        document observed — the email request must not disappear because
        the document resolved."""
        from core.turn_decision import (
            apply_interpretation_references, build_turn_decision,
        )

        negative = _session_with(
            observed_files=[PRIOR_FILE])
        decision = build_turn_decision(S7_ASK, negative, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(["document", "email"]),
            negative)
        marker = composed["references"]["continuation_evidence"]
        assert marker["state"] == "unresolved", (
            f"the missing email antecedent must block adoption; got "
            f"{marker!r}")
        assert marker["names"] == ["email"]
        assert marker["no_antecedent"] == ["email"]
        assert composed["references"].get("file") is None, (
            "the document must not be adopted while email is missing")

        # Positive twin: both observed -> two distinct files clarify.
        both = {
            PRIOR_OBS_KEY: _observed(PRIOR_FILE) + [{
                "observation_id": "l2-prior-mail",
                "source": "communication",
                "file_name": "inbox_thread.txt",
                "title": "inbox_thread.txt",
                "workspace_id": "ws-1",
                "content_hash": "",
            }],
        }
        decision = build_turn_decision(S7_ASK, both, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(["document", "email"]), both)
        marker = composed["references"]["continuation_evidence"]
        assert marker["state"] == "ambiguous"
        assert sorted(c["file_name"] for c in marker["candidates"]) == [
            "approved_records_q2026_114.txt", "inbox_thread.txt"]

    def test_punctuation_distinct_filenames_are_not_merged(self):
        """Owner regression: `approved_records_AB-12.txt` and
        `approved_records_AB12.txt` are DISTINCT identities — dedupe must
        preserve separators, so the reference clarifies instead of
        silently choosing one."""
        from core.turn_decision import (
            apply_interpretation_references, build_turn_decision,
        )

        negative = _session_with(observed_files=[
            "approved_records_AB-12.txt", "approved_records_AB12.txt"])
        decision = build_turn_decision(S7_ASK, negative, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(["the approved record"]),
            negative)
        marker = composed["references"]["continuation_evidence"]
        assert marker["state"] == "ambiguous", (
            f"distinct identities must clarify; got {marker!r}")
        assert sorted(c["file_name"] for c in marker["candidates"]) == [
            "approved_records_AB-12.txt", "approved_records_AB12.txt"]
        assert composed["references"].get("file") is None

        # Positive twin 1: only AB-12 observed -> resolved to it.
        single = _session_with(observed_files=["approved_records_AB-12.txt"])
        decision = build_turn_decision(S7_ASK, single, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(["the approved record"]),
            single)
        assert composed["references"]["file"] == {
            "file_name": "approved_records_AB-12.txt"}

        # Positive twin 2: the exact full identity resolves directly.
        exact = _session_with(observed_files=[
            "approved_records_AB-12.txt", "approved_records_AB12.txt"])
        decision = build_turn_decision(S7_ASK, exact, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(
                ["approved_records_AB-12.txt"]), exact)
        assert composed["references"]["file"] == {
            "file_name": "approved_records_AB-12.txt"}

    def test_single_letter_identifier_is_not_a_stopword(self):
        """Owner regression: "A" acts as a source identifier — it is never
        dropped as a stopword, so `approved record A` cannot resolve to
        `approved_records_B.txt`."""
        from core.turn_decision import (
            apply_interpretation_references, build_turn_decision,
        )

        negative = _session_with(observed_files=["approved_records_B.txt"])
        decision = build_turn_decision(S7_ASK, negative, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(["approved record A"]),
            negative)
        marker = composed["references"]["continuation_evidence"]
        assert marker["state"] == "unresolved", (
            f"A must constrain the reference; got {marker!r}")
        assert composed["references"].get("file") is None

        # Positive twin: the A file observed -> resolved to it.
        positive = _session_with(observed_files=["approved_records_A.txt"])
        decision = build_turn_decision(S7_ASK, positive, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(["approved record A"]),
            positive)
        assert composed["references"]["file"] == {
            "file_name": "approved_records_A.txt"}

    def test_generic_kind_without_observed_evidence_is_not_adopted(self):
        """Owner regression: `document` describes a proposed lookup; with
        no observed evidence it cannot nominate an antecedent."""
        from core.turn_decision import (
            apply_interpretation_references, build_turn_decision,
        )

        session = _session_with()
        decision = build_turn_decision(S7_ASK, session, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(["document"]), session)
        assert composed["references"] == decision["references"], (
            "no observed evidence context -> the decision is unchanged")

    def test_kind_with_one_observed_source_adopts_that_identity(self):
        from core.turn_decision import (
            apply_interpretation_references, build_turn_decision,
        )

        session = _session_with(observed_files=[PRIOR_FILE])
        decision = build_turn_decision(S7_ASK, session, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(["document"]), session)
        assert composed["references"]["file"] == {"file_name": PRIOR_FILE}
        assert (composed["references"]["continuation_evidence"]["state"]
                == "resolved")

    def test_requirement_named_file_without_observation_is_not_evidence(self):
        """Owner regression: a requirement carrier nominates; it is never
        prior evidence."""
        from core.turn_decision import (
            apply_interpretation_references, build_turn_decision,
            session_observed_sources,
        )

        session = _session_with(requested={
            "required": True, "sources": ["document"],
            "identity": {"state": "unresolved",
                         "names": [PRIOR_FILE],
                         "file_name": PRIOR_FILE},
        })
        assert session_observed_sources(session) == [], (
            "requirement carriers must not appear in the observed pool")
        decision = build_turn_decision(S7_ASK, session, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(), session)
        assert composed["references"] == decision["references"]

    def test_unresolved_interpretation_changes_nothing(self):
        from core.turn_decision import (
            apply_interpretation_references, build_turn_decision,
        )

        session = _session_with(observed_files=[PRIOR_FILE])
        decision = build_turn_decision(S7_ASK, session, [])
        degraded = dict(_resolved_interpretation())
        degraded["origin"] = "unresolved"
        degraded["scope_change"] = "unresolved"
        composed = apply_interpretation_references(
            decision, degraded, session)
        assert composed["references"] == decision["references"]

    def test_no_observed_context_leaves_the_decision_unchanged(self):
        from core.turn_decision import (
            apply_interpretation_references, build_turn_decision,
        )

        session = _session_with()
        decision = build_turn_decision(S7_ASK, session, [])
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(), session)
        assert composed["references"] == decision["references"]

    def test_floor_captured_references_always_win(self):
        from core.turn_decision import (
            apply_interpretation_references, build_turn_decision,
        )

        named = ("Search my documents for the valid until date and does it "
                 "still match the approved record?")
        session = _session_with(observed_files=[PRIOR_FILE])
        decision = build_turn_decision(named, session, [])
        assert decision["references"]["sources"] == ["documents"]
        composed = apply_interpretation_references(
            decision, _resolved_interpretation(["email"]), session)
        assert composed["references"] == decision["references"]

    def test_collectors_split_requested_from_observed(self):
        from core.turn_decision import (
            session_evidence_sources, session_observed_sources,
            session_requested_sources,
        )

        session = _session_with(
            observed_files=[PRIOR_FILE],
            requested={"required": True, "sources": ["document"],
                       "identity": {"state": "resolved",
                                    "file_name": "nominated_other.txt"}})
        observed = session_observed_sources(session)
        requested = session_requested_sources(session)
        assert [e["file_name"] for e in observed] == [PRIOR_FILE]
        assert all(e["observed"] is True for e in
                   session_evidence_sources(session)
                   if e["file_name"] == PRIOR_FILE)
        assert any(e["file_name"] == "nominated_other.txt"
                   for e in requested)
        assert any(e["observed"] is False for e in
                   session_evidence_sources(session)
                   if e["file_name"] == "nominated_other.txt")

    def test_interpretation_prompt_carries_prior_evidence_sources(self):
        from core.turn_decision import _interpretation_prompt

        session = _session_with(
            observed_files=[PRIOR_FILE],
            requested={"required": True, "sources": ["document"],
                       "identity": {"state": "resolved",
                                    "file_name": "nominated_other.txt"}})
        prompt = _interpretation_prompt(S7_ASK, [], session, {
            "canvas_id": "canvas-l2",
            "canvas_title": "Quotation Q-2026-114 (DRAFT)",
            "canvas_summary": "Draft quotation with Terms and Valid until.",
        })
        assert "SOURCE REFERENCES (structured JSON):" in prompt
        assert "PRIOR EVIDENCE SOURCES (this conversation)" not in prompt
        refs = _source_refs_from_prompt(prompt)
        assert refs["observed_evidence"] == [
            {"kind": "document", "file_name": PRIOR_FILE}]
        assert refs["requested_sources"] == [
            {"kind": "document", "file_name": "nominated_other.txt"}]
        assert refs["attached_artifact"]["canvas_id"] == "canvas-l2"
        assert "not an external evidence source" in (
            refs["attached_artifact"]["role"])

    def test_stash_carries_ambiguous_and_unresolved_identities(self):
        """The requirement builder carries the composer's ambiguity /
        unresolved states into the requirement identity verbatim."""
        from integrations.chat_orchestrator import (
            _stash_evidence_requirement,
        )

        for state, expected in (
            ("ambiguous", "ambiguous"), ("unresolved", "unresolved")):
            marker = {"origin": "interpretation", "state": state,
                      "proposed": ["the approved record"],
                      "resolved_kinds": ["document"],
                      "resolved_file": "",
                      "candidates": [{"file_name": "a.txt"},
                                     {"file_name": "b.txt"}],
                      "names": ["the approved record"]}
            decision = {"references": {"sources": ["document"], "file": None,
                                       "continuation_evidence": marker}}
            session = {}
            req = _stash_evidence_requirement(
                session, f"exec-{state}", decision, S7_ASK, True)
            assert req["identity"]["state"] == expected, req["identity"]
            if state == "ambiguous":
                assert len(req["identity"]["candidates"]) == 2
            else:
                assert req["identity"]["names"] == ["the approved record"]


class TestL2ProducerBoundary:
    """The producer contract through the REAL normalization/composer/stash.

    Only the model generation call is replaced. The prompt/schema contract
    is asserted on the generation request; the exact annotated payload and
    the strict consumer controls (unresolved/ambiguous/floor-wins) run the
    real normalization, composer and requirement stash. The served S3->S7
    run remains the proof that the real model follows the contract.
    """

    def test_clean_prior_filename_resolves_through_real_normalization(
            self, scoped_world, world_app):
        out = _run_producer_boundary(
            world_app, scoped_world, sources=[PRIOR_FILE],
            observed_files=[PRIOR_FILE])
        interp = out["interpretation"]
        assert interp["sources"] == [PRIOR_FILE], interp
        marker = out["composed"]["references"]["continuation_evidence"]
        assert marker["state"] == "resolved", marker
        assert marker["resolved_file"] == PRIOR_FILE, marker
        assert out["composed"]["references"]["file"] == {
            "file_name": PRIOR_FILE}
        req = out["requirement"]
        assert req["required"] is True
        assert "document" in [s.lower() for s in req["sources"]]
        assert req["artifact_attached"] is True
        assert req["file"]["file_name"] == PRIOR_FILE
        assert req["identity"]["state"] == "resolved", req["identity"]
        assert req["identity"]["file_name"] == PRIOR_FILE
        assert req["identity"]["file_id"]

        generation = out["generation"]
        assert generation.calls == 1
        prompt = generation.prompts[0]
        assert "SOURCE REFERENCES (structured JSON):" in prompt
        assert "PRIOR EVIDENCE SOURCES (this conversation)" not in prompt
        assert "source references by the names the user used" not in prompt
        assert "SUPPORTED SOURCE KINDS:" in prompt
        from core.action_program import SOURCE_KINDS

        emitted_kinds = prompt.split(
            "SUPPORTED SOURCE KINDS:", 1)[1].split("\n", 1)[0].strip()
        assert emitted_kinds == ", ".join(SOURCE_KINDS)
        refs = _source_refs_from_prompt(prompt)
        assert refs["observed_evidence"] == [
            {"kind": "document", "file_name": PRIOR_FILE}]
        assert refs["attached_artifact"]["canvas_id"] == "canvas-l2"
        assert refs["attached_artifact"]["role"].startswith("attached")
        description = generation.response_models[0].model_fields[
            "sources"].description
        assert "copy the observed filename exactly" in description
        assert "complete filename/name exactly" in description
        assert "Do not append explanations, parentheses" in description
        assert "attached draft/canvas" in description
        assert "several observed sources could match" in description.casefold()
        assert "do not choose one" in description.casefold()
        assert "source kind without naming a specific source" in (
            description.casefold())
        assert "prefer the kind shown" in description.casefold()
        from typing import get_args, get_origin

        annotation = generation.response_models[0].model_fields[
            "sources"].annotation
        assert get_origin(annotation) is list
        assert get_args(annotation) == (str,)
        from core.turn_decision import turn_evidence_required

        assert turn_evidence_required(out["composed"]) is True

    def test_long_observed_filename_can_be_copied_exactly(
            self, scoped_world, world_app):
        long_name = "approved_records_" + ("a" * 140) + ".txt"
        assert len(long_name) > 160
        out = _run_producer_boundary(
            world_app, scoped_world, sources=[long_name],
            observed_files=[long_name])
        assert out["interpretation"]["sources"] == [long_name]
        marker = out["composed"]["references"]["continuation_evidence"]
        assert marker["state"] == "resolved", marker
        assert marker["resolved_file"] == long_name
        req = out["requirement"]
        assert req["identity"]["state"] == "resolved", req["identity"]
        assert req["identity"]["file_name"] == long_name

    def test_attempt1_annotated_payload_stays_unresolved(
            self, scoped_world, world_app):
        from core.turn_decision import turn_evidence_required
        from integrations.chat_orchestrator import (
            _context_backed_fulfillment,
        )

        out = _run_producer_boundary(
            world_app, scoped_world,
            sources=ATTEMPT1_ANNOTATED_SOURCES,
            observed_files=[PRIOR_FILE])
        assert out["interpretation"]["sources"] == \
            ATTEMPT1_ANNOTATED_SOURCES
        marker = out["composed"]["references"]["continuation_evidence"]
        assert marker["state"] == "unresolved", marker
        assert marker["names"] == ATTEMPT1_ANNOTATED_SOURCES, marker
        assert marker["resolved_file"] == ""
        assert out["composed"]["references"]["file"] is None
        # The requirement IS captured; only its source identity stays
        # unresolved (the reporting distinction the owner required).
        assert turn_evidence_required(out["composed"]) is True
        req = out["requirement"]
        assert req["required"] is True
        assert req["sources"] == ["document"]
        assert req["identity"]["state"] == "unresolved", req["identity"]
        assert req["identity"]["names"] == ATTEMPT1_ANNOTATED_SOURCES
        assert req["file"] is None
        # No substring salvage: the unresolved identity carries no adopted
        # filename at all.
        assert "file_name" not in req["identity"]

        session = out["session"]
        eid = out["execution_id"]
        session[f"_retrieval_source_observations_{eid}"] = [{
            "source": "ingested", "file_name": PRIOR_FILE,
            "title": PRIOR_FILE,
            "workspace_id": out["ws"]["workspace_id"],
            "content_hash": "",
        }]
        verdict = _context_backed_fulfillment(
            session, eid, out["ws"]["workspace_id"])
        assert verdict["state"] == "unresolved", verdict
        assert verdict["names"] == ATTEMPT1_ANNOTATED_SOURCES, verdict

    def test_attached_draft_is_not_invented_as_external_lookup(
            self, scoped_world, world_app):
        from core.turn_decision import turn_evidence_required

        out = _run_producer_boundary(
            world_app, scoped_world, sources=["draft quotation"],
            observed_files=[PRIOR_FILE], canvas=True)
        marker = out["composed"]["references"]["continuation_evidence"]
        assert marker["state"] == "unresolved", marker
        assert marker["names"] == ["draft quotation"]
        assert out["composed"]["references"]["file"] is None
        assert turn_evidence_required(out["composed"]) is True
        req = out["requirement"]
        assert req["required"] is True
        assert req["sources"] == ["document"]
        assert req["artifact_attached"] is True
        assert req["file"] is None
        assert req["identity"]["state"] == "unresolved", req["identity"]
        assert req["identity"]["names"] == ["draft quotation"]
        assert "file_name" not in req["identity"]

        refs = _source_refs_from_prompt(out["generation"].prompts[0])
        assert refs["attached_artifact"]["canvas_id"] == "canvas-l2"
        assert refs["observed_evidence"] == [
            {"kind": "document", "file_name": PRIOR_FILE}]
        assert refs["requested_sources"] == []

    def test_unknown_external_source_remains_an_open_obligation(
            self, scoped_world, world_app):
        from core.turn_decision import turn_evidence_required
        from integrations.chat_orchestrator import (
            _context_backed_fulfillment,
        )

        unknown = "unknown_supplier_register.txt"
        out = _run_producer_boundary(
            world_app, scoped_world, sources=[unknown],
            observed_files=[PRIOR_FILE])
        marker = out["composed"]["references"]["continuation_evidence"]
        assert marker["state"] == "unresolved", marker
        assert marker["names"] == [unknown]
        assert turn_evidence_required(out["composed"]) is True
        req = out["requirement"]
        assert req["required"] is True
        assert req["identity"]["state"] == "unresolved", req["identity"]
        assert req["identity"]["names"] == [unknown]

        # Even when THIS turn retrieved the prior document, the unknown
        # source is not donated that identity: the obligation stays open.
        session = out["session"]
        eid = out["execution_id"]
        session[f"_retrieval_source_observations_{eid}"] = [{
            "source": "ingested", "file_name": PRIOR_FILE,
            "title": PRIOR_FILE,
            "workspace_id": out["ws"]["workspace_id"],
            "content_hash": "",
        }]
        verdict = _context_backed_fulfillment(
            session, eid, out["ws"]["workspace_id"])
        assert verdict["state"] == "unresolved", verdict
        assert verdict["names"] == [unknown], verdict

    def test_multiple_plausible_sources_still_clarify(
            self, scoped_world, world_app):
        out = _run_producer_boundary(
            world_app, scoped_world, sources=["approved record"],
            observed_files=[PRIOR_FILE, PRIOR_FILE_2])
        marker = out["composed"]["references"]["continuation_evidence"]
        assert marker["state"] == "ambiguous", marker
        assert marker["resolved_file"] == ""
        assert out["composed"]["references"]["file"] is None
        req = out["requirement"]
        assert req["required"] is True
        assert req["identity"]["state"] == "ambiguous", req["identity"]
        names = {c.get("file_name")
                 for c in (req["identity"].get("candidates") or [])}
        assert names == {PRIOR_FILE, PRIOR_FILE_2}, req["identity"]

    def test_generic_kind_ask_uses_observed_family(
            self, scoped_world, world_app):
        from core.turn_decision import turn_evidence_required

        out = _run_producer_boundary(
            world_app, scoped_world, sources=["document"],
            observed_files=[PRIOR_FILE])
        assert out["interpretation"]["sources"] == ["document"]
        marker = out["composed"]["references"]["continuation_evidence"]
        assert marker["state"] == "resolved", marker
        assert marker["resolved_file"] == PRIOR_FILE
        assert turn_evidence_required(out["composed"]) is True
        req = out["requirement"]
        assert req["required"] is True
        assert req["sources"] == ["document"]
        assert req["identity"]["state"] == "resolved"
        assert req["identity"]["file_name"] == PRIOR_FILE

    def test_first_turn_source_request_is_supported(
            self, scoped_world, world_app):
        out = _run_producer_boundary(
            world_app, scoped_world,
            sources=["my uploaded Approved Records document"],
            message=(
                "Compare the draft quotation with my uploaded Approved "
                "Records document. Does the Valid Until date in the draft "
                "match the approved record? Flag anything that differs. "
                "Do not change anything yet."),
            observed_files=None, canvas=True, scope_change="replace")
        # The deterministic floor captures the message-named source; the
        # producer's descriptive wording does not replace it.
        assert "document" in (out["decision"]["references"]["sources"]
                              or [])
        assert "continuation_evidence" not in (
            out["composed"]["references"] or {})
        req = out["requirement"]
        assert req["required"] is True
        assert "document" in [s.lower() for s in req["sources"]]
        assert req["artifact_attached"] is True

    def test_deterministic_floor_precedence_beats_producer(
            self, scoped_world, world_app):
        out = _run_producer_boundary(
            world_app, scoped_world, sources=["unknown_other.txt"],
            message=(
                "Compare the draft quotation with my uploaded Approved "
                "Records document. Does the Valid Until date in the draft "
                "match the approved record? Flag anything that differs. "
                "Do not change anything yet."),
            observed_files=[PRIOR_FILE], canvas=True, scope_change="replace")
        assert (out["decision"]["references"]["sources"] or []) == [
            "document"]
        # Floor-wins: the producer's unknown source is not composed over a
        # deterministic capture.
        assert "continuation_evidence" not in (
            out["composed"]["references"] or {})
        assert (out["composed"]["references"]["sources"] or []) == [
            "document"]
        req = out["requirement"]
        assert req["required"] is True
        assert "document" in [s.lower() for s in req["sources"]]


    def test_producer_contract_forbids_choosing_among_ambiguous_sources(
            self, scoped_world, world_app):
        """The producer must not pick one observed filename when the
        request's wording could match several; the composer's ambiguity
        path is only safe if the producer preserves the wording."""
        out = _run_producer_boundary(
            world_app, scoped_world, sources=["approved record"],
            observed_files=[PRIOR_FILE, PRIOR_FILE_2])
        prompt = out["generation"].prompts[0].casefold()
        description = out["generation"].response_models[0].model_fields[
            "sources"].description.casefold()
        for text in (prompt, description):
            assert "several observed sources could match" in text
            assert "do not choose one" in text
            assert "preserve the wording" in text
            assert "source kind without naming a specific source" in text
            assert "prefer the kind shown" in text
            assert "copy that source's complete filename/name exactly" in text

    def test_named_unobserved_source_is_not_collapsed_to_a_kind(
            self, scoped_world, world_app):
        """The producer contract distinguishes a named source from an
        unnamed kind ask; a prompt-compliant unknown source stays named
        and therefore remains an open obligation."""
        unknown = "unknown_supplier_register.txt"
        out = _run_producer_boundary(
            world_app, scoped_world, sources=[unknown],
            observed_files=[PRIOR_FILE])
        prompt = out["generation"].prompts[0].casefold()
        assert "if the request names a specific source" in prompt
        assert "copy that source's complete filename/name exactly" in prompt
        assert "only when the request asks for a source kind without " \
               "naming a specific source" in prompt
        assert out["interpretation"]["sources"] == [unknown]
        from core.turn_decision import turn_evidence_required

        assert turn_evidence_required(out["composed"]) is True
        req = out["requirement"]
        assert req["required"] is True
        assert req["identity"]["state"] == "unresolved"
        assert req["identity"]["names"] == [unknown]

    def test_malformed_sources_fail_closed(
            self, scoped_world, world_app):
        out = _run_producer_boundary(
            world_app, scoped_world,
            sources=[{"not": "a source string"}],
            observed_files=[PRIOR_FILE], validate=True)
        interp = out["interpretation"]
        assert interp["origin"] == "unresolved"
        assert interp["scope_change"] == "unresolved"
        assert interp["sources"] == []
        assert "continuation_evidence" not in (
            out["composed"]["references"] or {})
        req = out["requirement"]
        assert req["identity"]["state"] in ("kind_only", "unresolved")
        assert "file_name" not in req["identity"]

    def test_canvas_only_turn_does_not_invent_an_external_source(
            self, scoped_world, world_app):
        out = _run_producer_boundary(
            world_app, scoped_world, sources=[],
            message="What is on this draft?",
            observed_files=None, canvas=True, scope_change="replace")
        refs = _source_refs_from_prompt(out["generation"].prompts[0])
        assert refs["observed_evidence"] == []
        assert refs["requested_sources"] == []
        assert refs["attached_artifact"]["canvas_id"] == "canvas-l2"
        assert out["interpretation"]["sources"] == []
        assert "continuation_evidence" not in (
            out["composed"]["references"] or {})
        req = out["requirement"]
        assert req["artifact_attached"] is True
        assert req["required"] is False
        assert req["sources"] == []
        assert req["identity"]["state"] == "kind_only"


class TestL2InterpretationPolicy:
    """Execution-policy controls for the interpretation call.

    The served attempt-2 diagnosis was completion-within-deadline, not
    dispatch: the request needs a bounded, non-reasoning shape. These
    controls pin the forwarded settings, the derivation of the output
    budget, fail-closed timeout behavior, late-worker isolation, and the
    MoA opt-out boundary.
    """

    def test_forwarded_settings_are_bounded_and_traced(
            self, scoped_world, world_app):
        from core.turn_decision import _INTERPRET_OUTPUT_BUDGET_TOKENS

        out = _run_producer_boundary(
            world_app, scoped_world, sources=[PRIOR_FILE],
            observed_files=[PRIOR_FILE])
        forwarded = out["generation"].call_kwargs[0]
        assert forwarded["task_type"] == "planning"
        assert forwarded["temperature"] == 0.0
        assert forwarded["disable_reasoning"] is True
        assert forwarded["max_tokens"] == _INTERPRET_OUTPUT_BUDGET_TOKENS
        assert forwarded["route_trace_id"] == "turn_interpretation:req-l2"
        assert forwarded["allow_moa"] is False
        assert forwarded["model"] is None

    def test_output_budget_covers_representative_records(self):
        from core.turn_decision import _INTERPRET_OUTPUT_BUDGET_TOKENS

        def _estimate(text: str) -> int:
            try:
                import tiktoken

                return len(tiktoken.get_encoding("cl100k_base").encode(text))
            except Exception:  # noqa: BLE001 — conservative fallback
                return (len(text) + 2) // 3

        def _actions(n_subjects: int):
            return [{
                "kind": "research",
                "subjects": ["s" * 200] * n_subjects,
                "note": "n" * 200,
                "authorization": "granted",
            } for _ in range(3)]

        attempt1 = {
            "schema": "turn-interpretation-1",
            "request_id": "req-0123456789abcdef",
            "origin": "llm:glm-5.3-flash", "unresolved_reason": "",
            "message": "x" * 500,
            "actions": _actions(2), "subjects": [],
            "sources": ATTEMPT1_ANNOTATED_SOURCES,
            "requested_fields": ["expiration_date"],
            "output_format": "", "constraints": [],
            "scope_change": "continue", "confidence": 0.9,
        }
        multiple_long = {
            "schema": "turn-interpretation-1",
            "request_id": "req-0123456789abcdef",
            "origin": "llm:glm-5.3-flash", "unresolved_reason": "",
            "message": "x" * 500,
            "actions": _actions(4),
            "subjects": ["s" * 200] * 8,
            "sources": ["approved_records_" + ("a" * 480) + ".txt"] + [
                "source_" + str(i) + "_" + ("b" * 120) for i in range(7)],
            "requested_fields": ["f" * 80] * 8,
            "output_format": "markdown",
            "constraints": ["c" * 200] * 8,
            "scope_change": "continue", "confidence": 0.9,
        }
        largest = max(
            _estimate(json.dumps(record, ensure_ascii=False))
            for record in (attempt1, multiple_long))
        assert largest * 1.5 <= _INTERPRET_OUTPUT_BUDGET_TOKENS, (
            f"representative record estimate {largest} leaves less than "
            f"1.5x headroom under the {_INTERPRET_OUTPUT_BUDGET_TOKENS}-"
            "token budget")

    def test_moa_gate_can_fire_but_interpretation_opts_out(
            self, scoped_world, world_app):
        from core.llm.byok_handler import BYOKHandler, QueryComplexity

        # The gate is capable of firing on this call's shape ...
        assert BYOKHandler._moa_eligible(
            None, QueryComplexity.COMPLEX, "planning") is True
        # ... and the interpretation call opts out explicitly.
        out = _run_producer_boundary(
            world_app, scoped_world, sources=[PRIOR_FILE],
            observed_files=[PRIOR_FILE])
        assert out["generation"].call_kwargs[0]["allow_moa"] is False

    def test_timeout_returns_unresolved_and_adopts_no_source(
            self, scoped_world, world_app, monkeypatch):
        from core.turn_decision import reset_interpretation_for_tests

        monkeypatch.setattr("core.turn_decision._INTERPRET_TIMEOUT_S", 0.01)
        slow = _SlowGeneration(delay=0.2)
        out = _run_producer_boundary(
            world_app, scoped_world, sources=[PRIOR_FILE],
            observed_files=[PRIOR_FILE], generation=slow)
        interp = out["interpretation"]
        assert interp["origin"] == "unresolved"
        assert interp["unresolved_reason"] == "timeout"
        assert interp["sources"] == []
        assert "continuation_evidence" not in (
            out["composed"]["references"] or {})
        req = out["requirement"]
        assert req["required"] is False
        assert req["identity"]["state"] == "kind_only"
        assert req["file"] is None
        reset_interpretation_for_tests()


class TestL2ContinuationChain:
    """The real turn chain (parent-compatible; parent fails the capture)."""

    def test_continuation_ask_captures_the_evidence_requirement(
            self, scoped_world, world_app):
        session_out = {}
        out, session, ep = _drive_continuation_turn(
            scoped_world, world_app,
            interpretation=_resolved_interpretation(),
            session_out=session_out)

        eid, req = _turn_requirement(session, out)
        assert eid, "the turn must bind an execution id"
        assert req.get("required") is True, (
            "the continuation ask must carry the evidence obligation "
            f"(parent: no composition -> required False); got {req!r}")
        assert "document" in (req.get("sources") or [])
        identity = req.get("identity") or {}
        assert identity.get("file_name") == PRIOR_FILE, (
            f"the resolved antecedent identity must ride the requirement; "
            f"got {identity!r}")

        verdict, settled = _settlement_from_turn(
            session, eid, session_out["workspace_id"])
        assert verdict and verdict.get("state") in (
            "completed", "partial", "unsupplied"), (
            "the turn's own verified retrieval must certify the "
            f"continuation ask; got {verdict!r}")
        assert settled.get("state") == "completed"
        assert settled.get("delivered") is True

        outcome = _turn_outcome(scoped_world)
        assert outcome.get("execution_id") == eid

    def test_identifier_constraint_negative_and_positive(
            self, scoped_world, world_app):
        """Owner regression through the real turn: a short identifier
        constraint is preserved — 381 never resolves to 6603; with the
        381 file observed it resolves and certifies. The bounded
        refinement keeps the model's more specific proposal authoritative
        when it resolves inside the short window."""
        session_out = {}
        out, session, ep = _drive_continuation_turn(
            scoped_world, world_app,
            interpretation=_resolved_interpretation(["approved record 381"]),
            observed_files=["approved_records_6603.txt"],
            session_out=session_out)
        eid, req = _turn_requirement(session, out)
        identity = req.get("identity") or {}
        assert req.get("required") is True
        assert identity.get("state") == "unresolved", (
            f"381 must not resolve to 6603; got {identity!r}")
        assert "6603" not in json.dumps(identity)
        verdict, settled = _settlement_from_turn(
            session, eid, session_out["workspace_id"])
        assert verdict and verdict.get("state") == "unresolved"
        assert settled.get("delivered") is True

        session_out2 = {}
        out2, session2, ep2 = _drive_continuation_turn(
            scoped_world, world_app,
            interpretation=_resolved_interpretation(["approved record 381"]),
            observed_files=["approved_records_381.txt"],
            session_out=session_out2)
        eid2, req2 = _turn_requirement(session2, out2)
        identity2 = req2.get("identity") or {}
        assert identity2.get("state") == "resolved", identity2
        assert identity2.get("file_name") == "approved_records_381.txt"
        verdict2, settled2 = _settlement_from_turn(
            session2, eid2, session_out2["workspace_id"])
        assert verdict2 and verdict2.get("state") in (
            "completed", "partial", "unsupplied")
        assert settled2.get("delivered") is True

    def test_unmatched_proposal_never_resolves_to_the_matched_one(
            self, scoped_world, world_app):
        """Owner regression through the real turn: Alpha resolved and
        Gamma unmatched — the requirement stays unresolved (Gamma named);
        Alpha is never adopted as the single answer."""
        session_out = {}
        out, session, ep = _drive_continuation_turn(
            scoped_world, world_app,
            interpretation=_resolved_interpretation(
                ["Alpha records", "Gamma records"]),
            observed_files=["alpha_records.txt"],
            session_out=session_out)
        eid, req = _turn_requirement(session, out)
        identity = req.get("identity") or {}
        assert req.get("required") is True
        assert identity.get("state") == "unresolved", (
            f"the unmatched Gamma proposal must win; got {identity!r}")
        assert identity.get("names") == ["Gamma records"]
        verdict, settled = _settlement_from_turn(
            session, eid, session_out["workspace_id"])
        assert verdict and verdict.get("state") == "unresolved"
        assert settled.get("delivered") is True

    def test_missing_kind_proposal_through_the_real_turn(
            self, scoped_world, world_app):
        """Owner regression through the real turn: document+email proposed
        with only a document observed -> the requirement stays unresolved
        with the missing email named; the document is never adopted."""
        session_out = {}
        out, session, ep = _drive_continuation_turn(
            scoped_world, world_app,
            interpretation=_resolved_interpretation(["document", "email"]),
            observed_files=[PRIOR_FILE],
            session_out=session_out)
        eid, req = _turn_requirement(session, out)
        identity = req.get("identity") or {}
        assert req.get("required") is True
        assert identity.get("state") == "unresolved", (
            f"the missing email antecedent must block adoption; got "
            f"{identity!r}")
        assert identity.get("names") == ["email"]
        verdict, settled = _settlement_from_turn(
            session, eid, session_out["workspace_id"])
        assert verdict and verdict.get("state") == "unresolved"
        assert settled.get("delivered") is True

    def test_punctuation_distinct_filenames_through_the_real_turn(
            self, scoped_world, world_app):
        """Owner regression through the real turn: AB-12 and AB12 are
        distinct identities -> the requirement is ambiguous with both;
        nothing is silently chosen."""
        session_out = {}
        out, session, ep = _drive_continuation_turn(
            scoped_world, world_app,
            interpretation=_resolved_interpretation(["the approved record"]),
            observed_files=["approved_records_AB-12.txt",
                            "approved_records_AB12.txt"],
            session_out=session_out)
        eid, req = _turn_requirement(session, out)
        identity = req.get("identity") or {}
        assert identity.get("state") == "ambiguous", identity
        names = sorted(str(c.get("file_name") or "")
                       for c in (identity.get("candidates") or []))
        assert names == ["approved_records_AB-12.txt",
                         "approved_records_AB12.txt"]
        verdict, settled = _settlement_from_turn(
            session, eid, session_out["workspace_id"])
        assert verdict and verdict.get("state") == "ambiguous"
        assert settled.get("delivered") is True

    def test_single_letter_identifier_through_the_real_turn(
            self, scoped_world, world_app):
        """Owner regression through the real turn: `approved record A`
        with only the B file observed -> unresolved; B is never
        adopted."""
        session_out = {}
        out, session, ep = _drive_continuation_turn(
            scoped_world, world_app,
            interpretation=_resolved_interpretation(["approved record A"]),
            observed_files=["approved_records_B.txt"],
            session_out=session_out)
        eid, req = _turn_requirement(session, out)
        identity = req.get("identity") or {}
        assert identity.get("state") == "unresolved", identity
        assert "approved_records_B.txt" not in json.dumps(identity)
        verdict, settled = _settlement_from_turn(
            session, eid, session_out["workspace_id"])
        assert verdict and verdict.get("state") == "unresolved"
        assert settled.get("delivered") is True

    def test_ambiguous_reference_never_selects_a_source(
            self, scoped_world, world_app, monkeypatch):
        """Owner regression through the real turn: two matching sources ->
        the requirement carries the ambiguity and the settlement asks
        which one — no file is silently adopted."""
        session_out = {}
        out, session, ep = _drive_continuation_turn(
            scoped_world, world_app,
            interpretation=_resolved_interpretation(),
            observed_files=["alpha_approved_records.txt",
                            "beta_approved_records.txt"],
            session_out=session_out)
        eid, req = _turn_requirement(session, out)
        identity = req.get("identity") or {}
        assert req.get("required") is True
        assert identity.get("state") == "ambiguous", (
            f"ambiguity must be preserved; got {identity!r}")
        names = sorted(str(c.get("file_name") or "")
                       for c in (identity.get("candidates") or []))
        assert names == ["alpha_approved_records.txt",
                         "beta_approved_records.txt"]
        verdict, settled = _settlement_from_turn(
            session, eid, session_out["workspace_id"])
        assert verdict and verdict.get("state") == "ambiguous"
        assert settled.get("state") == "partial", (
            "a validated delivery whose open work is the source "
            f"clarification; got {settled!r}")
        assert settled.get("delivered") is True
        assert any("which source" in str(w)
                   for w in (settled.get("open_work") or []))

    def test_wrong_name_never_resolves_to_the_unapproved_file(
            self, scoped_world, world_app, monkeypatch):
        """Owner regression through the real turn: only an unapproved file
        is observed -> the reference stays unresolved; the wrong file is
        never adopted and the settlement reports the honest non-match."""
        session_out = {}
        out, session, ep = _drive_continuation_turn(
            scoped_world, world_app,
            interpretation=_resolved_interpretation(),
            observed_files=["unapproved_records.txt"],
            session_out=session_out)
        eid, req = _turn_requirement(session, out)
        identity = req.get("identity") or {}
        assert req.get("required") is True
        assert identity.get("state") == "unresolved", (
            f"the wrong name must stay unresolved; got {identity!r}")
        assert "unapproved_records.txt" not in json.dumps(identity)
        verdict, settled = _settlement_from_turn(
            session, eid, session_out["workspace_id"])
        assert verdict and verdict.get("state") == "unresolved"
        assert settled.get("state") == "partial", (
            "a validated delivery whose open work is the honest "
            f"non-match; got {settled!r}")
        assert settled.get("delivered") is True
        assert any("no ingested document matches" in str(w)
                   for w in (settled.get("open_work") or []))

    def test_unresolved_interpretation_recovers_the_named_antecedent(
            self, scoped_world, world_app, monkeypatch):
        """A degraded interpretation does not erase an EXPLICIT, named
        source the conversation already observed. The requirement is
        recovered from the request + observed evidence, not invented by
        the interpreter: the date-only scope stays narrow and the source
        identity is the one the user named."""
        degraded = dict(_resolved_interpretation())
        degraded["origin"] = "unresolved"
        degraded["scope_change"] = "unresolved"
        degraded["sources"] = []
        degraded["requested_fields"] = []
        degraded["actions"] = []
        session_out = {}
        out, session, ep = _drive_continuation_turn(
            scoped_world, world_app, interpretation=degraded,
            session_out=session_out)
        eid, req = _turn_requirement(session, out)
        assert req.get("required") is True, req
        assert req.get("sources") == ["document"], req
        assert req.get("fields") == ["expiration_date"], req
        assert req.get("broader_comparison") is False, req
        identity = req.get("identity") or {}
        assert identity.get("state") == "resolved", identity
        assert identity.get("file_name") == PRIOR_FILE, identity
        assert identity.get("file_id"), identity
        verdict, settled = _settlement_from_turn(
            session, eid, session_out["workspace_id"])
        assert verdict and verdict.get("state") == "completed", verdict
        assert settled.get("state") == "completed", settled
        assert settled.get("delivered") is True, settled

    def test_degraded_turn_certifies_narrow_comparison_zero_writes(
            self, scoped_world, world_app, monkeypatch):
        """The captured date-only ask, through the real turn with an
        attached canvas: the source is bound to THIS execution and
        workspace, the comparison covers exactly the date, the canvas is
        untouched, and the response, settlement and fresh history agree."""
        import copy

        from core.models import CanvasAudit, ChatMessage

        degraded = dict(_resolved_interpretation())
        degraded["origin"] = "unresolved"
        degraded["scope_change"] = "unresolved"
        degraded["sources"] = []
        degraded["requested_fields"] = []
        degraded["actions"] = []
        canvas_before = copy.deepcopy(S7_CANVAS)
        accepted = {}

        import core.turn_decision as td

        _orig_apply = td.apply_interpretation_references

        def _capture_apply(decision, interpretation, session_arg):
            accepted["origin"] = (interpretation or {}).get("origin")
            accepted["refinement"] = (interpretation or {}).get(
                "refinement")
            return _orig_apply(decision, interpretation, session_arg)

        monkeypatch.setattr(
            td, "apply_interpretation_references", _capture_apply)
        session_out = {}
        out, session, ep = _drive_continuation_turn(
            scoped_world, world_app, interpretation=degraded,
            canvas=S7_CANVAS, session_out=session_out,
            persist_history=True)

        eid, req = _turn_requirement(session, out)
        assert req.get("required") is True, req
        assert req.get("sources") == ["document"], req
        assert req.get("fields") == ["expiration_date"], req
        assert req.get("broader_comparison") is False, req
        assert req.get("artifact_attached") is True, req
        identity = req.get("identity") or {}
        assert identity.get("state") == "resolved", identity
        assert identity.get("file_name") == PRIOR_FILE, identity
        assert identity.get("file_id"), identity
        # execution/workspace binding: the requirement key is this turn's
        # execution and the observation carries the authenticated workspace.
        assert eid and str(out.get("execution_id") or "") == eid
        observations = session.get(
            f"_retrieval_source_observations_{eid}") or []
        assert observations and all(
            str(o.get("workspace_id") or "") == session_out["workspace_id"]
            for o in observations), observations

        assert session_out.get("interpret_calls") == 1, (
            "the bounded refinement is attempted once inside its short "
            "window")
        assert accepted.get("origin") == "deterministic:continuation", (
            "an unresolved refinement must fall back to the explicit "
            f"deterministic record; got {accepted!r}")
        assert (accepted.get("refinement") or {}).get(
            "status") == "completed", accepted
        assert (accepted.get("refinement") or {}).get(
            "outcome") == "unresolved", accepted
        verdict, settled = _settlement_from_turn(
            session, eid, session_out["workspace_id"])
        assert verdict and verdict.get("state") == "completed", verdict
        assert verdict.get("supplied_fields") == ["expiration_date"], verdict
        assert verdict.get("missing_comparison") is not True, verdict
        assert settled.get("state") == "completed", settled
        assert settled.get("delivered") is True, settled

        message = str(out.get("message") or "")
        assert message.startswith("Verified comparison"), message
        assert "expiration date" in message.casefold(), message
        assert "2026-12-31" in message, message
        assert "payment terms" not in message.casefold(), message
        assert "terms" not in message.casefold(), (
            "the narrow date-only reply must not import the prior broad "
            f"comparison: {message}")
        assert out.get("success") is True, out
        assert out.get("outcome") == settled.get("state"), (
            out.get("outcome"), settled)

        # ZERO WRITES: the canvas snapshot and the audit trail are
        # unchanged; the turn is a read-only continuation.
        assert S7_CANVAS["content"] == canvas_before["content"]
        db = scoped_world["Session"]()
        try:
            audits = (db.query(CanvasAudit)
                      .filter(CanvasAudit.canvas_id
                              == S7_CANVAS["canvas_id"]).count())
            assert audits == 0, audits
            rows = (db.query(ChatMessage)
                    .filter(ChatMessage.conversation_id == session["id"])
                    .order_by(ChatMessage.created_at).all())
            assistants = [r for r in rows if r.role == "assistant"]
            if not assistants:
                _all = db.query(ChatMessage).all()
                assistants = [r for r in _all if r.role == "assistant"]
            assert assistants, (
                "the turn must persist its assistant reply; rows="
                + repr([(r.conversation_id, r.role, str(r.content)[:50])
                        for r in db.query(ChatMessage).all()]))
            assert assistants[-1].content == message, (
                "fresh history must agree with the delivered response")
        finally:
            db.close()
        # The prior conversation carrier is preserved, not overwritten by
        # this turn's requirement. The prior S3 carrier is BROAD; the
        # current date-only requirement is narrow, proving the prior
        # contract was not imported.
        assert f"_evidence_requirement_{eid}" in session
        assert PRIOR_REQ_KEY in session
        assert session[PRIOR_REQ_KEY]["broader_comparison"] is True
        assert req["broader_comparison"] is False

    def test_resolved_empty_source_model_still_binds_the_named_reference(
            self, scoped_world, world_app, monkeypatch):
        """A schema-valid model record with sources=[] made no source
        decision. The real turn must fill the named reference instead of
        falling back to kind_only and certifying a memory answer."""
        empty = dict(_resolved_interpretation())
        empty["sources"] = []
        empty["requested_fields"] = []
        empty["actions"] = []
        empty["origin"] = "llm:test-model"
        accepted = {}

        import core.turn_decision as td

        _orig_apply = td.apply_interpretation_references

        def _capture_apply(decision, interpretation, session_arg):
            if isinstance(interpretation, dict):
                accepted.setdefault("actions", [
                    str(action.get("kind") or "")
                    for action in (interpretation.get("actions") or [])
                    if isinstance(action, dict)])
                accepted.setdefault(
                    "refinement", interpretation.get("refinement"))
            return _orig_apply(decision, interpretation, session_arg)

        monkeypatch.setattr(
            td, "apply_interpretation_references", _capture_apply)
        session_out = {}
        out, session, ep = _drive_continuation_turn(
            scoped_world, world_app, interpretation=empty,
            canvas=S7_CANVAS, session_out=session_out,
            persist_history=True)
        eid, req = _turn_requirement(session, out)
        assert req.get("required") is True, req
        assert req.get("sources") == ["document"], req
        assert req.get("fields") == ["expiration_date"], req
        assert req.get("broader_comparison") is False, req
        identity = req.get("identity") or {}
        assert identity.get("state") == "resolved", identity
        assert identity.get("file_name") == PRIOR_FILE, identity
        verdict, settled = _settlement_from_turn(
            session, eid, session_out["workspace_id"])
        assert verdict and verdict.get("state") == "completed", verdict
        assert settled.get("state") == "completed", settled
        assert str(out.get("message") or "").startswith(
            "Verified comparison"), out.get("message")
        assert "research" in (accepted.get("actions") or []), accepted
        assert (accepted.get("refinement") or {}).get(
            "status") == "completed", accepted
        assert (accepted.get("refinement") or {}).get(
            "outcome") == "resolved", accepted

    def test_mixed_floor_file_unresolved_source_survives_settlement_and_history(
            self, scoped_world, world_app, monkeypatch):
        """A valid workbook result cannot erase the unresolved named
        record. The request-bound verdict must survive the builder,
        finalizer, persistence and fresh history."""
        import copy

        from core.models import CanvasAudit, ChatMessage
        from core.turn_decision import (
            build_turn_decision as td_build_turn_decision,
            deterministic_continuation_ready,
        )

        empty = dict(_resolved_interpretation())
        empty["sources"] = []
        empty["requested_fields"] = []
        empty["actions"] = []
        empty["origin"] = "llm:test-model"
        mixed_message = (
            "Compare the draft with catalog_2019.xlsx and the approved "
            "record on the valid until date.")
        canvas_before = copy.deepcopy(S7_CANVAS)
        # Positive twin: the same source/field without the workbook is the
        # bounded date-only continuation.
        positive_session = {"id": "sess-positive", "history": []}
        _seed_conversation_evidence(
            positive_session, "ws-positive", observed_files=[PRIOR_FILE])
        positive_decision = td_build_turn_decision(
            S7_ASK, positive_session, [])
        assert deterministic_continuation_ready(
            S7_ASK, positive_session, positive_decision) is not None

        session_out = {}
        out, session, ep = _drive_continuation_turn(
            scoped_world, world_app, interpretation=empty,
            message=mixed_message, canvas=S7_CANVAS,
            session_out=session_out, persist_history=True)
        eid, req = _turn_requirement(session, out)
        assert req.get("required") is True, req
        assert req.get("fields") == ["expiration_date"], req
        identity = req.get("identity") or {}
        assert identity.get("state") == "unresolved", identity
        assert identity.get("names") == ["approved record"], identity
        floor_file = req.get("file") or {}
        assert "catalog_2019.xlsx" in str(
            floor_file.get("name") or floor_file.get("file_name") or ""), req
        assert str(out.get("execution_id") or "") == eid

        verdict, settled = _settlement_from_turn(
            session, eid, session_out["workspace_id"])
        assert verdict and verdict.get("state") == "unresolved", verdict
        assert settled.get("state") == "partial", settled
        assert settled.get("delivered") is True, settled
        assert any("approved record" in str(w)
                   for w in (settled.get("open_work") or [])), settled
        assert out.get("outcome") == "partial", out
        durable = _turn_outcome(scoped_world)
        assert durable.get("execution_id") == eid, durable
        assert durable.get("objective_met") is not True, durable
        for gap in durable.get("gaps") or []:
            if gap.get("criterion_id") == "context_fulfillment":
                assert gap.get("status") == "unresolved", durable
                assert gap.get("next_evidence_needed") == (
                    "resolve the named source"), durable
        assert S7_CANVAS["content"] == canvas_before["content"]
        db = scoped_world["Session"]()
        try:
            assert (db.query(CanvasAudit)
                    .filter(CanvasAudit.canvas_id
                            == S7_CANVAS["canvas_id"]).count()) == 0
            rows = (db.query(ChatMessage)
                    .filter(ChatMessage.conversation_id == session["id"])
                    .order_by(ChatMessage.created_at).all())
            assistants = [r for r in rows if r.role == "assistant"]
            assert assistants and assistants[-1].content == out.get(
                "message"), (
                "fresh history must agree with the partial response")
        finally:
            db.close()

    def test_additional_action_prevents_read_only_completion(
            self, scoped_world, world_app, monkeypatch):
        """A date read plus an insertion is not a read-only continuation.
        The obligation table refuses the fast path and the request-bound
        marker blocks completion, without an extra phrase blacklist."""
        import copy

        from core.models import CanvasAudit, ChatMessage
        from core.turn_decision import (
            build_turn_decision as td_build_turn_decision,
            deterministic_continuation_ready,
        )

        empty = dict(_resolved_interpretation())
        empty["sources"] = []
        empty["requested_fields"] = []
        empty["actions"] = []
        empty["origin"] = "llm:test-model"
        message = (
            "Check the valid until date on the draft matches the approved "
            "record and insert client name.")
        canvas_before = copy.deepcopy(S7_CANVAS)
        # Positive twin: removing the insertion clause is the bounded
        # date-only continuation.
        positive_session = {"id": "sess-positive", "history": []}
        _seed_conversation_evidence(
            positive_session, "ws-positive", observed_files=[PRIOR_FILE])
        positive_decision = td_build_turn_decision(
            S7_ASK, positive_session, [])
        assert deterministic_continuation_ready(
            S7_ASK, positive_session, positive_decision) is not None
        negative_session = {"id": "sess-negative", "history": []}
        _seed_conversation_evidence(
            negative_session, "ws-negative", observed_files=[PRIOR_FILE])
        negative_decision = td_build_turn_decision(
            message, negative_session, [])
        assert deterministic_continuation_ready(
            message, negative_session, negative_decision) is None, (
            "an additional insertion must not take the read-only fast path")

        session_out = {}
        out, session, ep = _drive_continuation_turn(
            scoped_world, world_app, interpretation=empty,
            message=message, canvas=S7_CANVAS,
            session_out=session_out, persist_history=True)
        assert session_out.get("interpret_calls") == 1, (
            "the fast path must not be taken")
        eid, req = _turn_requirement(session, out)
        assert req.get("required") is True, req
        identity = req.get("identity") or {}
        assert identity.get("state") == "unresolved", identity
        assert any("insert client" in str(n).casefold()
                   for n in (identity.get("names") or [])), identity
        verdict, settled = _settlement_from_turn(
            session, eid, session_out["workspace_id"])
        assert verdict and verdict.get("state") == "unresolved", verdict
        assert settled.get("state") == "partial", settled
        assert any("insert client" in str(w).casefold()
                   for w in (settled.get("open_work") or [])), settled
        assert out.get("outcome") != "completed", out
        durable = _turn_outcome(scoped_world)
        assert durable.get("execution_id") == eid, durable
        assert durable.get("objective_met") is not True, durable
        for gap in durable.get("gaps") or []:
            if gap.get("criterion_id") == "context_fulfillment":
                assert gap.get("status") == "unresolved", durable
                assert gap.get("next_evidence_needed") == (
                    "complete the additional action"), durable
        assert S7_CANVAS["content"] == canvas_before["content"]
        db = scoped_world["Session"]()
        try:
            assert (db.query(CanvasAudit)
                    .filter(CanvasAudit.canvas_id
                            == S7_CANVAS["canvas_id"]).count()) == 0
            rows = (db.query(ChatMessage)
                    .filter(ChatMessage.conversation_id == session["id"])
                    .order_by(ChatMessage.created_at).all())
            assistants = [r for r in rows if r.role == "assistant"]
            assert assistants and assistants[-1].content == out.get(
                "message")
        finally:
            db.close()

    def test_degraded_ambiguous_source_clarifies_without_selecting(
            self, scoped_world, world_app, monkeypatch):
        """Two observed candidates for the named reference: the turn
        preserves both, selects neither, and settles partial with the
        clarification as open work."""
        degraded = dict(_resolved_interpretation())
        degraded["origin"] = "unresolved"
        degraded["scope_change"] = "unresolved"
        degraded["sources"] = []
        degraded["requested_fields"] = []
        degraded["actions"] = []
        session_out = {}
        out, session, ep = _drive_continuation_turn(
            scoped_world, world_app, interpretation=degraded,
            observed_files=["alpha_approved_records.txt",
                            "beta_approved_records.txt"],
            canvas=S7_CANVAS, session_out=session_out)
        eid, req = _turn_requirement(session, out)
        identity = req.get("identity") or {}
        assert req.get("required") is True, req
        assert identity.get("state") == "ambiguous", identity
        assert "file_name" not in identity, identity
        names = sorted(str(c.get("file_name"))
                       for c in (identity.get("candidates") or []))
        assert names == ["alpha_approved_records.txt",
                         "beta_approved_records.txt"], identity
        assert not str(out.get("message") or "").startswith(
            "Verified comparison"), (
            "an ambiguous source must not produce a deterministic "
            "comparison against whichever candidate retrieval returned")
        verdict, settled = _settlement_from_turn(
            session, eid, session_out["workspace_id"])
        assert verdict and verdict.get("state") == "ambiguous", verdict
        assert settled.get("state") == "partial", settled
        assert settled.get("delivered") is True, settled
        assert any("which source" in str(w)
                   for w in (settled.get("open_work") or [])), settled

    def test_degraded_broad_followup_keeps_the_obligation_open(
            self, scoped_world, world_app, monkeypatch):
        """A genuinely broad follow-up is not narrowed to the date just
        because interpretation failed: the whole-document obligation stays
        open and the settlement is partial, not completed."""
        degraded = dict(_resolved_interpretation())
        degraded["origin"] = "unresolved"
        degraded["scope_change"] = "unresolved"
        degraded["sources"] = []
        degraded["requested_fields"] = []
        degraded["actions"] = []
        broad_ask = (
            "Compare the draft quotation with my uploaded Approved Records "
            "document. Does the Valid Until date match? Flag anything that "
            "differs. Do not change anything yet.")
        session_out = {}
        out, session, ep = _drive_continuation_turn(
            scoped_world, world_app, interpretation=degraded,
            message=broad_ask, canvas=S7_CANVAS, session_out=session_out)
        eid, req = _turn_requirement(session, out)
        assert req.get("required") is True, req
        assert req.get("fields") == ["expiration_date"], req
        assert req.get("broader_comparison") is True, req
        assert session_out.get("interpret_calls") == 1, (
            "a genuinely broad follow-up stays on the interpretation path")
        verdict, settled = _settlement_from_turn(
            session, eid, session_out["workspace_id"])
        assert settled.get("state") == "partial", settled
        assert settled.get("delivered") is True, settled
        assert settled.get("state") != "completed"
        assert any("comparison" in str(w).casefold()
                   for w in (settled.get("open_work") or [])), settled

    def test_degraded_interpretation_without_a_named_source_stays_unobligated(
            self, scoped_world, world_app, monkeypatch):
        """The degraded fallback resolves only a source the REQUEST names.
        A bare question ("what is the status?") over prior observations
        does not become an evidence obligation by implication."""
        degraded = dict(_resolved_interpretation())
        degraded["origin"] = "unresolved"
        degraded["scope_change"] = "unresolved"
        degraded["sources"] = []
        degraded["requested_fields"] = []
        degraded["actions"] = []
        session_out = {}
        out, session, ep = _drive_continuation_turn(
            scoped_world, world_app, interpretation=degraded,
            message="What is the status?",
            session_out=session_out)
        eid, req = _turn_requirement(session, out)
        assert req.get("required") is not True, (
            "an unnamed source is never inferred from prior observations")
        assert (req.get("identity") or {}).get("state") == "kind_only", req
        verdict, settled = _settlement_from_turn(
            session, eid, session_out["workspace_id"])
        assert verdict is None
        assert settled.get("state") == "unconfirmed"

    def test_message_named_source_ask_keeps_its_capture(
            self, scoped_world, world_app, monkeypatch):
        named = ("Search my documents for the valid until date and does it "
                 "still match the approved record?")
        session_out = {}
        out, session, ep = _drive_continuation_turn(
            scoped_world, world_app,
            interpretation=_resolved_interpretation(["email"]),
            message=named, session_out=session_out)
        eid, req = _turn_requirement(session, out)
        assert req.get("required") is True
        assert req.get("sources") == ["documents"], (
            "the floor's own capture (the decision's raw nouns) is not "
            f"overridden by the interpretation; got {req.get('sources')!r}")
        verdict, settled = _settlement_from_turn(
            session, eid, session_out["workspace_id"])
        assert verdict is not None
        assert settled.get("state") == "completed"
