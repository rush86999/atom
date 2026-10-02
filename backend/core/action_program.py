# -*- coding: utf-8 -*-
"""A typed, executable action program per turn (2026-09-30).

WHY THIS MODULE EXISTS. The turn-decision contract
(``core.turn_decision``, schema ``turn-decision-1``) consolidated
INTERPRETATION into one structured decision per turn, but its actions are
plain dicts keyed by string ``kind``/``authorization``: correct by
convention and by tests, not by type. At the same time the live 2026-09-30
Tennsmith incident showed that the properties which make a scoped
follow-up trustworthy — the sheet resolves to a real identity or is stated
unresolved, filtering happens BEFORE the display window, an empty scoped
result never silently broadens, evidence is never mutated by presentation
— were carried by SCATTERED conventions across the read, ranking and
render seams rather than by one inspectable artifact.

This module is that artifact. It is a SMALL typed action language, not a
general-purpose one:

- The PROPOSAL is data: pydantic ops with explicit references, explicit
  dependencies and explicit modes. Ops have NO ``authorization`` field and
  ``extra="forbid"`` — the language has no word for a self-granted
  permission, so a proposer (today the deterministic gates, tomorrow a
  microLLM emitting the same schema) literally cannot write
  ``authorized=true``. Verdicts are COMPUTED by
  :func:`compute_authorizations` from policy facts supplied by trusted
  code.
- The EXECUTOR is deterministic ordinary code. It performs the pure
  operations completely (filter/rank/window over supplied evidence) and
  records I/O operations (reads) and mutations (patches) as validated,
  authorization-stamped PROPOSALS — the existing read lanes and
  canvas-edit lanes remain their executors until each migrates. One
  interpreter per workflow is the goal; this layer must not become a
  second competing one (the directive behind ``core.turn_decision``).
- EVIDENCE IS IMMUTABLE. The executor deep-copies every candidate list it
  is given; a rendered or filtered view can never rewrite the read. Each
  outcome carries an effect receipt stating what was ordered, what was
  hidden by the display window, and that no binding and no edit
  authorization was created — displaying a match is not proving a row is
  the user's (that stronger channel is
  ``disambiguation.resolved_bindings`` and stays separate).

GENERALIZATION (same day, second step). The workbook ops above are the
WIRED workflow; the language itself is not workbook-shaped.
``SourceReadOp`` expresses a read from ANY source kind — the kind
vocabulary is the repo's existing general mechanisms, not a new taxonomy:
the source nouns ``core.turn_decision`` already recognizes (email, chat,
calendar, ticket, note, …) plus the artifact kinds its edit gates know
(document, canvas, record, task). ``ServiceRef`` references an
INTEGRATION by name and resolves only against a service catalog the
trusted caller supplies (the planner's validated
connected-services ∪ platform-services list) — a service the user has
not connected can never be resolved into a program, only reported
unresolved. ``FilterEvidenceOp`` is the data-type-generic filter: a typed
predicate over any list of structured evidence records (email results,
CRM rows, task lists), executed deterministically with the same
no-broadening/no-mutation receipts as the workbook filter. ``SheetRef``
and ``FilterPreviousOp`` stay as the spreadsheet-specialized, fully wired
path. Per AGENTS.md's general-layer rule there is deliberately NO
per-integration op: every integration is one ``SourceReadOp`` whose
service reference resolves against the same catalog the tool planner
validates against.

SINGLE SOURCE OF TRUTH. Sheet resolution, ranking and the window size are
NOT re-implemented here. The executor calls the ``answer_presentation``
primitives — ``resolve_requested_sheets`` (resolution against the file's
real sheet catalog, never extraction), ``_rank_candidates`` (the stable
answerability-then-scope partition), ``_scoped_sheet_note`` (the honest
miss-note), ``_candidate_sheet``/``_sheet_scope_key`` (candidate shape)
and ``AMBIGUOUS_CANDIDATE_WINDOW`` — so the typed layer and the renderer
cannot drift. Imports are deferred to call time because the presentation
seam calls back into this module
(``answer_presentation.build_targets_from_scan`` executes a program per
target), and neither module may import the other at load time.
"""
from __future__ import annotations

import copy
import time
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA = "action-program-1"

#: Read modes. ``fresh_read`` re-runs retrieval ("search again", rerun,
#: refresh, a direct ask); ``serve_previous`` re-serves already-read
#: evidence (the resolver's ``read`` verdict). The distinction is the
#: program's, made explicit so a follow-up cannot quietly turn "filter
#: what you showed me" into "search everything" or the reverse.
MODE_FRESH_READ = "fresh_read"
MODE_SERVE_PREVIOUS = "serve_previous"

#: Authorization verdicts — the same vocabulary as the turn decision. They
#: appear ONLY in computed outcomes, never in ops.
AUTH_GRANTED = "granted"
AUTH_NEEDS_CONFIRMATION = "needs_confirmation"
AUTH_NEEDS_GRANT = "needs_grant"

#: Outcome statuses. ``empty_in_scope`` and ``unresolved_sheet`` exist so a
#: scope that matched nothing is an EXPLICIT verdict — the two silent
#: failure shapes of the incident class (empty scope becomes an
#: unrestricted search; an unknown sheet name filters nothing and nobody
#: is told) both become recorded facts.
STATUS_OK = "ok"
STATUS_EMPTY_IN_SCOPE = "empty_in_scope"
STATUS_UNRESOLVED_SHEET = "unresolved_sheet"
STATUS_NO_SCOPE = "no_scope"
STATUS_PROPOSED = "proposed"
STATUS_NEEDS_CONFIRMATION = "needs_confirmation"
STATUS_NEEDS_GRANT = "needs_grant"
STATUS_NOT_WIRED = "not_wired"
STATUS_SKIPPED_NO_CANDIDATES = "skipped_no_candidates"
STATUS_EMPTY_RESULT = "empty_result"
STATUS_SKIPPED_NO_EVIDENCE = "skipped_no_evidence"
STATUS_UNRESOLVED_SERVICE = "unresolved_service"
STATUS_UNRESOLVED_SOURCE = "unresolved_source"

#: Source KINDS the language can reference. Drawn from the repo's
#: existing general mechanisms — the source nouns ``core.turn_decision``
#: recognizes (``_SOURCE_NOUN_RE``) and the artifact kinds its edit
#: gates target — NOT a new taxonomy invented here. Adding an
#: integration never adds a kind: it becomes a resolvable ServiceRef.
SOURCE_KINDS = (
    "spreadsheet", "email", "inbox", "thread", "chat", "message", "text",
    "calendar", "ticket", "note", "memo", "letter", "comment", "post",
    "document", "canvas", "record", "task", "web", "agent",
)

#: ``core.turn_decision._requested_sources`` returns the regex's own
#: captures (mostly plurals: "emails", "dms", "texts"); programs carry
#: singular kinds so one vocabulary serves both layers.
_SOURCE_KIND_SINGULARS = {
    "emails": "email", "mails": "email", "mail": "email",
    "dms": "chat", "threads": "thread", "chats": "chat",
    "messages": "message", "texts": "text", "tickets": "ticket",
    "notes": "note", "memos": "memo", "letters": "letter",
    "comments": "comment", "posts": "post", "calendar": "calendar",
    "inbox": "inbox",
}


def normalize_source_kind(source_noun: str) -> str:
    """A decision-layer source noun → its program kind, or "".

    Unknown nouns map to "" and are DROPPED rather than coerced: a kind
    the language does not know is a vocabulary question for a human, not
    something to guess into a program."""
    key = str(source_noun or "").strip().lower()
    kind = _SOURCE_KIND_SINGULARS.get(key, key)
    return kind if kind in SOURCE_KINDS else ""


class SheetRef(BaseModel):
    """A sheet the request named, as a typed reference.

    ``mention`` is the user's own words (or an already-resolved name when
    compiled from the render path, which resolves upstream against the
    file's catalog). Resolution to a REAL sheet identity happens only
    against sheets the file actually indexes — via
    ``answer_presentation.resolve_requested_sheets``, whose two-way
    containment and minimum-length floor never fabricate a sheet — and a
    reference that matches nothing stays ``unresolved``: it is reported,
    never guessed into a scope.
    """
    model_config = ConfigDict(extra="forbid")

    mention: str
    resolved_name: Optional[str] = None
    status: str = Field(default="pending",
                        pattern="^(pending|resolved|unresolved)$")

    def resolve(self, sheet_names: Sequence[str]) -> "SheetRef":
        """Resolve against a real catalog, returning a NEW ref.

        Never raises and never invents: no match means ``unresolved``.
        """
        from core.answer_presentation import (
            _sheet_scope_key,
            resolve_sheet_phrase,
        )

        names = [str(s) for s in sheet_names or []]
        # An exact (collapsed-key) name IS the identity — the render path
        # arrives pre-resolved and must not be re-gated through the phrase
        # regex, which only matches "<qualifier> sheet" wording.
        mention_key = _sheet_scope_key(self.mention)
        if mention_key:
            for name in names:
                if mention_key == _sheet_scope_key(name):
                    return self.model_copy(update={
                        "resolved_name": name, "status": "resolved"})
        matched = resolve_sheet_phrase(self.mention, names)
        if not matched:
            return self.model_copy(update={"status": "unresolved"})
        return self.model_copy(update={
            "resolved_name": matched, "status": "resolved"})


class SourceRef(BaseModel):
    """A reference to a source of evidence of ANY kind — an email
    mailbox, a chat, a calendar, a document, a CRM record set — or to a
    POOL of previously read evidence.

    Same discipline as ``SheetRef``: the mention is the user's words, the
    identity resolves ONLY against a catalog the trusted caller supplies
    (for a pool: the keys of the evidence the caller holds; for an
    artifact: its real name), and no match stays ``unresolved`` —
    reported, never guessed.
    """
    model_config = ConfigDict(extra="forbid")

    mention: str
    kind: str
    resolved_name: Optional[str] = None
    status: str = Field(default="pending",
                        pattern="^(pending|resolved|unresolved)$")

    @field_validator("kind")
    @classmethod
    def _kind_in_vocabulary(cls, value: str) -> str:
        if value not in SOURCE_KINDS:
            raise ValueError(f"unknown source kind: {value!r}")
        return value

    def resolve(self, catalog: Sequence[str]) -> "SourceRef":
        from core.answer_presentation import _sheet_scope_key

        names = [str(s) for s in catalog or []]
        mention_key = _sheet_scope_key(self.mention)
        if mention_key:
            for name in names:
                if mention_key == _sheet_scope_key(name):
                    return self.model_copy(update={
                        "resolved_name": name, "status": "resolved"})
        # Loose containment for spreadsheet-kind phrases only, reusing
        # the shared resolver (never fabricates; same length floor).
        if self.kind == "spreadsheet":
            from core.answer_presentation import resolve_sheet_phrase

            matched = resolve_sheet_phrase(self.mention, names)
            if matched:
                return self.model_copy(update={
                    "resolved_name": matched, "status": "resolved"})
        return self.model_copy(update={"status": "unresolved"})


class ServiceRef(BaseModel):
    """A reference to an INTEGRATION (Outlook, Slack, a CRM, an MCP
    tool surface) by name.

    Resolves ONLY against a service catalog the trusted caller supplies
    — in production the same validated list the tool planner uses
    (connected services ∪ platform services). An integration the user
    has not connected can never resolve into a program: it is reported
    ``unresolved`` and the read op records that fact instead of silently
    pretending the service exists.
    """
    model_config = ConfigDict(extra="forbid")

    mention: str
    resolved_name: Optional[str] = None
    status: str = Field(default="pending",
                        pattern="^(pending|resolved|unresolved)$")

    def resolve(self, service_catalog: Sequence[str]) -> "ServiceRef":
        from core.answer_presentation import _sheet_scope_key

        mention_key = _sheet_scope_key(self.mention)
        for name in [str(s) for s in service_catalog or []]:
            if mention_key and mention_key == _sheet_scope_key(name):
                return self.model_copy(update={
                    "resolved_name": name, "status": "resolved"})
        return self.model_copy(update={"status": "unresolved"})


# ---------------------------------------------------------------------------
# Operations. NOTE ON AUTHORIZATION: no op carries an authorization field,
# and every op forbids extra fields. A proposal that arrives carrying
# ``authorization``/``authorized`` is a validation ERROR, not a grant.
# ---------------------------------------------------------------------------

class _Op(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    depends_on: List[str] = Field(default_factory=list)


class WorkbookReadOp(_Op):
    """Read (or re-serve) workbook evidence for items.

    ``include_sheets`` carries the sheet scope with INCLUDE semantics — a
    ranking axis, never an exclusive filter, matching the established
    discipline in ``answer_presentation``: a reader who says "include the
    Tennsmith sheet" must not lose the RoperWhitney rows they also asked
    for. ``constraints_text`` keeps the user's own scope words verbatim
    beside the typed refs, so the durable record shows both what was said
    and what it compiled to.
    """
    model_config = ConfigDict(extra="forbid")

    op: str = Field(default="workbook_read", frozen=True)
    mode: str = Field(pattern="^(fresh_read|serve_previous)$")
    file_name: str = ""
    targets: List[str] = Field(default_factory=list)
    requested_fields: List[str] = Field(default_factory=list)
    include_sheets: List[SheetRef] = Field(default_factory=list)
    constraints_text: List[str] = Field(default_factory=list)


class SourceReadOp(_Op):
    """Read evidence from ANY source kind — the data-type-generic form
    of ``WorkbookReadOp`` (which stays the fully wired spreadsheet path).

    ``service`` references an INTEGRATION and resolves against the
    caller-supplied service catalog; ``source_kinds`` are the KINDS to
    consult. Every integration is the same op — there is deliberately no
    per-integration branch (the general-layer rule): Outlook, Slack and
    a CRM differ only in whether their ServiceRef resolves. Execution is
    a validated, authorization-stamped PROPOSAL; the integration read
    lanes remain the executors.
    """
    model_config = ConfigDict(extra="forbid")

    op: str = Field(default="source_read", frozen=True)
    mode: str = Field(pattern="^(fresh_read|serve_previous)$")
    source_kinds: List[str] = Field(default_factory=list)
    service: Optional[ServiceRef] = None
    query: str = ""
    targets: List[str] = Field(default_factory=list)
    constraints_text: List[str] = Field(default_factory=list)

    @field_validator("source_kinds")
    @classmethod
    def _kinds_in_vocabulary(cls, value: List[str]) -> List[str]:
        unknown = [k for k in value if k not in SOURCE_KINDS]
        if unknown:
            raise ValueError(f"unknown source kinds: {unknown}")
        return value


class FilterEvidenceOp(_Op):
    """Filter a POOL of previously read evidence by a typed predicate —
    the data-type-generic filter (workbook sheet-scope has its own wired
    ``FilterPreviousOp``; this op serves every other evidence shape:
    email results, CRM rows, task lists, document hits).

    Deterministically EXECUTED over the evidence pool the caller
    supplies. Invariants identical to the workbook filter: the pool is
    never mutated (deep copy in), a predicate that matches nothing is an
    EXPLICIT ``empty_result`` — never silently widened back to the full
    pool — and the receipt states counts, so "filtered to 0" can never be
    presented as "everything matched".
    """
    model_config = ConfigDict(extra="forbid")

    op: str = Field(default="filter_evidence", frozen=True)
    source: SourceRef
    field: str
    operator: str = Field(pattern="^(eq|neq|contains|in|gt|gte|lt|lte)$")
    value: Any = None


class FilterPreviousOp(_Op):
    """Filter/rank PREVIOUSLY read evidence down to a named sheet scope.

    Executed FULLY by the deterministic executor: it never drops a
    candidate (ranking, not elimination), computes the honest miss-note
    for a named sheet that holds none of the matched rows, and reports
    ``empty_in_scope`` rather than broadening when the scope matched
    nothing.
    """
    model_config = ConfigDict(extra="forbid")

    op: str = Field(default="filter_previous", frozen=True)
    item: str = ""
    sheets: List[SheetRef] = Field(default_factory=list)


class RenderOp(_Op):
    """Present evidence. Pure: a style/field preference plus the display
    window. Execution records the presentation PLAN (which rows the window
    will show, what it truncates); the readable text itself is produced by
    the existing pure renderer (``answer_presentation.present``) keyed by
    the same inputs — one renderer, not two.
    """
    model_config = ConfigDict(extra="forbid")

    op: str = Field(default="render", frozen=True)
    style: str = Field(default="default",
                       pattern="^(default|compact|table)$")
    field: Optional[str] = None


class ProposeLessonOp(_Op):
    """Remember something. Always needs confirmation — saving a lesson and
    applying it during retrieval are separately observable facts, and a
    "✓ Learned" badge is not evidence that a search honored the
    instruction.
    """
    model_config = ConfigDict(extra="forbid")

    op: str = Field(default="propose_lesson", frozen=True)
    lesson: str
    destination: Optional[str] = None
    destination_candidates: List[str] = Field(default_factory=list)


class ProposePatchOp(_Op):
    """Change an artifact (quote-draft update, canvas edit, email draft,
    CRM record).

    A PROPOSAL only. ``target_kind`` names the artifact class; the
    canvas lane is the ONE wired executor (propose →
    validate-authorization-and-revision → commit → verify,
    ``chat_canvas_editor.apply_canvas_edit``) and every other kind
    records ``not_wired`` until its lane migrates — expressed uniformly,
    never silently executed. ``user_grounded_instruction`` is grant
    EVIDENCE (the user's own command, detected by trusted code), not a
    grant — the verdict is still computed, never read from the op.
    """
    model_config = ConfigDict(extra="forbid")

    op: str = Field(default="propose_patch", frozen=True)
    target_kind: str = "canvas"
    target_canvas: str = ""
    nomination: bool = False
    user_grounded_instruction: Optional[str] = None


class ConverseOp(_Op):
    """A plain conversational turn with no artifact action."""
    model_config = ConfigDict(extra="forbid")

    op: str = Field(default="converse", frozen=True)


_OPS = (WorkbookReadOp, SourceReadOp, FilterEvidenceOp, FilterPreviousOp,
        RenderOp, ProposeLessonOp, ProposePatchOp, ConverseOp)
_OP_BY_KIND = {cls.model_fields["op"].default: cls for cls in _OPS}


class ActionProgram(BaseModel):
    """One typed, dependency-ordered program per turn."""
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default=SCHEMA, frozen=True)
    session_id: str = ""
    message_excerpt: str = ""
    compiled_from: str = "turn-decision-1"
    #: Discriminated ops; kept as ``Any`` so strict parsing
    #: (:func:`parse_program`) is the only way untyped data becomes a
    #: program. ``model_dump`` serializes op models to dicts natively.
    actions: List[Any] = Field(default_factory=list)

    def to_record(self) -> Dict[str, Any]:
        """Plain-dict form for persistence beside the turn decision (the
        decision row is JSON; op models are not). ``actions`` is ``Any``,
        so pydantic serializes each op model to a dict natively."""
        return self.model_dump()


def parse_program(raw: Dict[str, Any]) -> ActionProgram:
    """Parse a serialized program STRICTLY — the gate a proposer's output
    must pass. Extra keys (e.g. a self-granted ``authorization``) raise a
    validation error here, which is the property the typed language buys.
    """
    data = dict(raw or {})
    if str(data.get("schema_version") or SCHEMA) != SCHEMA:
        raise ValueError(f"unsupported program schema: "
                         f"{data.get('schema_version')!r}")
    data["schema_version"] = SCHEMA
    raw_actions = data.pop("actions", [])
    actions = []
    for a in raw_actions:
        kind = str((a or {}).get("op") or "")
        if kind not in _OP_BY_KIND:
            raise ValueError(f"unknown op kind: {kind!r}")
        actions.append(_OP_BY_KIND[kind].model_validate(a))
    program = ActionProgram.model_validate(data)
    program.actions = actions
    return program


# ---------------------------------------------------------------------------
# Compilation from the turn-decision contract
# ---------------------------------------------------------------------------

#: decision research ``reason`` → read mode. Rerun/refresh/direct/approval
#: are FRESH reads; the resolver's ``read`` verdict re-serves stored
#: evidence. The mapping makes "search again" vs "filter what you showed
#: me" an explicit, testable program fact instead of lane folklore.
_REASON_MODE = {
    "continuation_rerun": MODE_FRESH_READ,
    "continuation_refresh": MODE_FRESH_READ,
    "continuation_read": MODE_SERVE_PREVIOUS,
    "direct_ask": MODE_FRESH_READ,
    "approval_resumes_pending": MODE_FRESH_READ,
    "bare_retry_resumes_pending": MODE_FRESH_READ,
    "source_ask": MODE_FRESH_READ,
}


def _message_sheet_mentions(message: str) -> List[str]:
    """Sheet-reference phrases in the message's own words.

    Uses ``answer_presentation``'s shared extraction (the same regex
    ``resolve_requested_sheets`` matches against real catalogs), so what
    the program records as a pending mention is exactly what could later
    resolve. Compilation does NOT resolve — there is no sheet catalog at
    turn time; guessing a sheet there could only fabricate one.
    """
    from core.answer_presentation import sheet_reference_phrases

    return sheet_reference_phrases(message or "")


def program_from_decision(decision: Dict[str, Any]) -> Optional[ActionProgram]:
    """Compile a ``turn-decision-1`` dict into a typed program, or None.

    Pure and total: every action kind maps to an op, unknown kinds are
    skipped (never guessed), and compilation never fails the turn — the
    decision remains authoritative; the program is its executable shadow.
    Sheet mentions from BOTH the message's sheet references and the
    decision's parsed ``constraints`` become pending ``SheetRef``s,
    resolved later against the file's real catalog.
    """
    decision = decision if isinstance(decision, dict) else {}
    actions: List[Any] = []
    seq = 0

    def _next_id(prefix: str) -> str:
        nonlocal seq
        seq += 1
        return f"{prefix}{seq}"

    for a in decision.get("requested_actions") or []:
        if not isinstance(a, dict):
            continue
        kind = str(a.get("kind") or "")
        if kind == "research":
            target = a.get("target") or {}
            constraints = [str(c) for c in (a.get("constraints") or [])]
            mentions: List[str] = []
            for phrase in (_message_sheet_mentions(
                    str(decision.get("message") or "")) + constraints):
                if phrase and phrase not in mentions:
                    mentions.append(phrase)
            mode = _REASON_MODE.get(str(a.get("reason") or ""),
                                    MODE_FRESH_READ)
            # KIND HONESTY: a source-target research action ("check
            # Chandrakant's email") is a source read, not a workbook read
            # with an empty file name — the pre-generalization compile
            # lost that distinction. A file/workbook target stays the
            # wired WorkbookReadOp; ANY additional non-spreadsheet source
            # the decision carries becomes its OWN SourceReadOp node, so
            # a compound "workbook and email" ask can never lose the
            # email half (the compound-request incident lesson).
            target_kind = str(target.get("kind") or "")
            extra_sources = sorted({
                normalize_source_kind(str(s))
                for s in (a.get("additional_sources") or [])}
                - {"", "spreadsheet"})
            if target_kind == "source":
                kinds = sorted({
                    normalize_source_kind(str(s))
                    for s in (target.get("sources") or [])}
                    - {""})
                actions.append(SourceReadOp(
                    action_id=_next_id("src"),
                    mode=mode,
                    source_kinds=kinds,
                    query=str(decision.get("message") or "")[:200],
                ))
                # The decision repeats the target's sources as
                # additional_sources; they are the SAME ask, already
                # carried by the op above — not compound actions.
                extra_sources = sorted(set(extra_sources) - set(kinds))
            else:
                actions.append(WorkbookReadOp(
                    action_id=_next_id("read"),
                    mode=mode,
                    file_name=str(target.get("name") or ""),
                    targets=[str(t) for t in (target.get("targets") or [])],
                    requested_fields=[str(f) for f in
                                      (a.get("requested_fields") or [])],
                    include_sheets=[SheetRef(mention=m) for m in mentions],
                    constraints_text=constraints,
                ))
            for src_kind in extra_sources:
                actions.append(SourceReadOp(
                    action_id=_next_id("src"),
                    mode=mode,
                    source_kinds=[src_kind],
                    query=str(decision.get("message") or "")[:200],
                ))
        elif kind == "presentation":
            dep = actions[0].action_id if actions else ""
            actions.append(RenderOp(
                action_id=_next_id("render"),
                depends_on=[dep] if dep else [],
                style=str(a.get("style") or "default"),
                field=a.get("field"),
            ))
        elif kind == "learning":
            actions.append(ProposeLessonOp(
                action_id=_next_id("lesson"),
                lesson=str(a.get("lesson") or "")[:400],
                destination=a.get("destination"),
                destination_candidates=[str(d) for d in
                                        (a.get("destination_candidates")
                                         or [])],
            ))
        elif kind == "canvas_edit":
            actions.append(ProposePatchOp(
                action_id=_next_id("patch"),
                target_canvas=str(a.get("target_canvas") or ""),
                nomination=bool(a.get("nomination")),
                user_grounded_instruction=a.get(
                    "user_grounded_instruction") or None,
            ))
        elif kind == "conversation":
            actions.append(ConverseOp(action_id=_next_id("converse")))
    if not actions:
        return None
    return ActionProgram(
        session_id=str(decision.get("session_id") or ""),
        message_excerpt=str(decision.get("message") or "")[:200],
        actions=actions,
    )


# ---------------------------------------------------------------------------
# Validation and authorization — computed, never proposed
# ---------------------------------------------------------------------------

def validate_program(program: ActionProgram,
                     sheet_catalog: Optional[Sequence[str]] = None,
                     service_catalog: Optional[Sequence[str]] = None,
                     ) -> Dict[str, Any]:
    """Reference/permission/structure checks. Returns a report; never
    raises on program content (a malformed program is data, not an
    exception) — parsing already rejected untyped payloads."""
    violations: List[str] = []
    ids = [a.action_id for a in program.actions]
    if len(ids) != len(set(ids)):
        violations.append("duplicate action_id")
    for a in program.actions:
        for dep in a.depends_on:
            if dep not in ids:
                violations.append(f"{a.action_id}: unknown dependency {dep}")
    # Reference check: a resolved ref must name a catalog sheet when the
    # catalog is supplied. Mentions still pending are fine (resolution is
    # execution-time); a resolved name outside the catalog is a
    # fabrication and is flagged. The same check covers integration
    # services: a resolved ServiceRef the service catalog does not know
    # is a fabricated integration.
    if sheet_catalog:
        known = {str(s) for s in sheet_catalog}
        for a in program.actions:
            for ref in list(getattr(a, "include_sheets", [])) + list(
                    getattr(a, "sheets", [])):
                if ref.status == "resolved" and ref.resolved_name not in known:
                    violations.append(
                        f"{a.action_id}: resolved sheet "
                        f"{ref.resolved_name!r} not in catalog")
    if service_catalog:
        known_services = {str(s) for s in service_catalog}
        for a in program.actions:
            service = getattr(a, "service", None)
            if service is not None and service.status == "resolved" and (
                    service.resolved_name not in known_services):
                violations.append(
                    f"{a.action_id}: resolved service "
                    f"{service.resolved_name!r} not in service catalog")
    return {"valid": not violations,
            "violations": violations,
            "action_ids": ids}


def compute_authorizations(program: ActionProgram,
                           policy_facts: Optional[Dict[str, Any]] = None,
                           ) -> Dict[str, str]:
    """Deterministic authorization verdicts, from POLICY FACTS only.

    Reads/filters/renders/conversation are granted (they are read-only).
    A lesson needs confirmation. A patch is granted ONLY when trusted code
    supplies the fact ``user_grounded_edit_instruction`` — a verdict never
    reads an op field for permission, so the proposer cannot influence it.
    """
    facts = policy_facts or {}
    out: Dict[str, str] = {}
    for a in program.actions:
        if isinstance(a, ProposeLessonOp):
            out[a.action_id] = AUTH_NEEDS_CONFIRMATION
        elif isinstance(a, ProposePatchOp):
            out[a.action_id] = (
                AUTH_GRANTED if facts.get("user_grounded_edit_instruction")
                else AUTH_NEEDS_GRANT)
        else:
            out[a.action_id] = AUTH_GRANTED
    return out


# ---------------------------------------------------------------------------
# Deterministic execution
# ---------------------------------------------------------------------------

class ExecutionRecord(BaseModel):
    """Per-action outcomes plus effect receipts. Pure data: the record of
    what the program DID and DID NOT do, suitable for persistence beside
    the structured result."""
    model_config = ConfigDict(extra="allow")

    schema_version: str = SCHEMA
    executed_at: float = Field(default_factory=time.time)
    outcomes: List[Dict[str, Any]] = Field(default_factory=list)
    #: The ranked candidate lists a ``filter_previous`` action produced,
    #: keyed by action_id. Deliberately excluded from serialization — the
    #: receipt states the facts; the lists are working data for the caller.
    ranked_by_action: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict, exclude=True)

    def outcome_for(self, action_id: str) -> Optional[Dict[str, Any]]:
        for o in self.outcomes:
            if o.get("action_id") == action_id:
                return o
        return None


def execute_program(program: ActionProgram,
                    sheet_names: Sequence[str] = (),
                    candidates: Optional[Dict[str, List[Dict[str, Any]]]] = None,
                    requested_fields: Sequence[str] = (),
                    policy_facts: Optional[Dict[str, Any]] = None,
                    service_catalog: Sequence[str] = (),
                    evidence: Optional[Dict[str, List[Dict[str, Any]]]] = None,
                    ) -> ExecutionRecord:
    """Execute the program deterministically over the supplied world.

    ``sheet_names`` is the file's real sheet catalog (used to resolve
    pending refs); ``candidates`` maps item → previous-evidence candidate
    lists; ``requested_fields`` scope answerability ranking exactly as the
    render path does; ``policy_facts`` are authorization facts supplied by
    TRUSTED callers (e.g. the orchestrator's user-grounded-edit detection)
    — never derivable from the program itself; ``service_catalog`` is the
    validated integration list (connected ∪ platform services) ServiceRefs
    resolve against; ``evidence`` maps a source/pool name → structured
    records for ``FilterEvidenceOp``. The executor NEVER mutates the
    inputs (deep copy in, new lists out), never performs I/O, and never
    authorizes anything beyond the computed verdicts.
    """
    from core.answer_presentation import (
        AMBIGUOUS_CANDIDATE_WINDOW,
        _candidate_sheet,
        _rank_candidates,
        _scoped_sheet_note,
        _sheet_scope_key,
    )

    candidates = candidates or {}
    evidence = evidence or {}
    fields = list(requested_fields or [])
    auth = compute_authorizations(program, policy_facts)
    record = ExecutionRecord()
    ranked_by_id: Dict[str, List[Dict[str, Any]]] = {}

    for action in program.actions:
        base: Dict[str, Any] = {"action_id": action.action_id,
                                "op": action.op,
                                "authorization": auth[action.action_id]}
        if isinstance(action, SourceReadOp):
            service = (action.service.resolve(service_catalog)
                       if action.service is not None else None)
            status = STATUS_PROPOSED
            if service is not None and service.status == "unresolved":
                # An integration the catalog does not know is REPORTED,
                # never guessed: the proposal stands (the trusted caller
                # decides) but the receipt says the service did not
                # resolve, so nothing downstream can claim it ran.
                status = STATUS_UNRESOLVED_SERVICE
            base.update({
                "status": status,
                "mode": action.mode,
                "source_kinds": list(action.source_kinds),
                "service": service.model_dump() if service else None,
                # The integration read lanes remain the executors for
                # retrieval; this is the validated, authorization-stamped
                # proposal.
                "executor": ("read-lane" if action.source_kinds == []
                             or "spreadsheet" in action.source_kinds
                             else "integration-lane"),
            })
        elif isinstance(action, FilterEvidenceOp):
            ref = action.source.resolve(list(evidence.keys()))
            pool = copy.deepcopy(list(evidence.get(
                ref.resolved_name or action.source.mention, [])))
            if ref.status != "resolved" or not pool:
                base.update({
                    "status": (STATUS_SKIPPED_NO_EVIDENCE
                               if ref.status == "resolved"
                               else STATUS_UNRESOLVED_SOURCE),
                    "source": ref.model_dump(),
                })
            else:
                filtered = [rec for rec in pool if _apply_predicate(
                    rec, action.field, action.operator, action.value)]
                status = STATUS_OK if filtered else STATUS_EMPTY_RESULT
                base.update({
                    "status": status,
                    "source": ref.model_dump(),
                    "field": action.field,
                    "operator": action.operator,
                    "evidence_total": len(pool),
                    "matched_count": len(filtered),
                    # A predicate that matches nothing is an EXPLICIT
                    # empty result — the receipt says so, and the ranked
                    # list stays empty rather than widening to the pool.
                    "widened_on_empty": False,
                    "preserved": ["record_fields", "record_values"],
                    "creates_binding": False,
                    "authorizes_edit": False,
                })
                ranked_by_id[action.action_id] = filtered
        elif isinstance(action, WorkbookReadOp):
            refs = [r.resolve(sheet_names) if r.status == "pending" else r
                    for r in action.include_sheets]
            base.update({
                "status": STATUS_PROPOSED,
                "mode": action.mode,
                "file_name": action.file_name,
                "targets": list(action.targets),
                # The read lanes remain the executor for retrieval; this is
                # the validated, authorization-stamped proposal.
                "executor": "read-lane",
                "include_sheets": [r.model_dump() for r in refs],
                "unresolved_sheet_mentions": [r.mention for r in refs
                                              if r.status == "unresolved"],
            })
        elif isinstance(action, FilterPreviousOp):
            refs = [r.resolve(sheet_names) if r.status == "pending" else r
                    for r in action.sheets]
            resolved = [r.resolved_name for r in refs
                        if r.status == "resolved" and r.resolved_name]
            source = copy.deepcopy(list(candidates.get(action.item, [])))
            if not source:
                base.update({"status": STATUS_SKIPPED_NO_CANDIDATES,
                             "resolved_sheets": resolved})
            else:
                ranked = _rank_candidates(source, fields, resolved,
                                          item=action.item)
                scope_keys = {_sheet_scope_key(s) for s in resolved}
                in_scope = [c for c in ranked
                            if _sheet_scope_key(_candidate_sheet(c))
                            in scope_keys]
                window = ranked[:AMBIGUOUS_CANDIDATE_WINDOW]
                hidden_in_scope = in_scope[AMBIGUOUS_CANDIDATE_WINDOW:]
                status = STATUS_OK
                if not refs:
                    status = STATUS_NO_SCOPE
                elif not resolved:
                    status = STATUS_UNRESOLVED_SHEET
                elif not in_scope:
                    # The scope is real but holds nothing. NEVER broaden:
                    # every candidate is preserved (reordered only by
                    # answerability) and the miss is stated, not silently
                    # substituted by another sheet's rows.
                    status = STATUS_EMPTY_IN_SCOPE
                base.update({
                    "status": status,
                    "resolved_sheets": resolved,
                    "unresolved_mentions": [r.mention for r in refs
                                            if r.status == "unresolved"],
                    "candidates_total": len(ranked),
                    "in_scope_count": len(in_scope),
                    "per_sheet_counts": _per_sheet_counts(ranked),
                    "window_size": AMBIGUOUS_CANDIDATE_WINDOW,
                    "window_refs": [str(c.get("ref")) for c in window],
                    "window_truncated": max(
                        0, len(ranked) - AMBIGUOUS_CANDIDATE_WINDOW),
                    # The structured fact the incident lacked: rows on the
                    # sheet the reader named that the display window hides.
                    "in_scope_rows_hidden_by_window": len(hidden_in_scope),
                    "hidden_in_scope_refs": [str(c.get("ref"))
                                             for c in hidden_in_scope],
                    "scope_note": _scoped_sheet_note(ranked, resolved),
                    # Effect receipt: evidence passes through untouched.
                    "preserved": ["ref", "identity_cells", "value_basis"],
                    "creates_binding": False,
                    "authorizes_edit": False,
                })
                ranked_by_id[action.action_id] = ranked
        elif isinstance(action, RenderOp):
            dep = (action.depends_on or [None])[0]
            ranked = ranked_by_id.get(dep or "")
            if ranked is None:
                base.update({"status": STATUS_PROPOSED,
                             "executor": "answer_presentation.present"})
            else:
                window = ranked[:AMBIGUOUS_CANDIDATE_WINDOW]
                base.update({
                    "status": STATUS_OK,
                    "style": action.style,
                    "field": action.field,
                    "window_size": AMBIGUOUS_CANDIDATE_WINDOW,
                    "window_refs": [str(c.get("ref")) for c in window],
                    "window_truncated": max(
                        0, len(ranked) - AMBIGUOUS_CANDIDATE_WINDOW),
                    "executor": "answer_presentation.present",
                })
        elif isinstance(action, ProposeLessonOp):
            base.update({"status": STATUS_NEEDS_CONFIRMATION,
                         "destination": action.destination,
                         "destination_candidates": list(
                             action.destination_candidates),
                         "saved": False})
        elif isinstance(action, ProposePatchOp):
            wired = action.target_kind == "canvas"
            base.update({"status": STATUS_NEEDS_GRANT
                         if base["authorization"] == AUTH_NEEDS_GRANT
                         else STATUS_NOT_WIRED,
                         "target_kind": action.target_kind,
                         "target_canvas": action.target_canvas,
                         # The canvas-edit lane (propose → validate →
                         # commit → verify) is the ONE wired mutation
                         # executor; every other artifact kind is
                         # expressed uniformly and records the
                         # integration lane as its future executor.
                         "executor": ("canvas-edit-lane" if wired
                                      else "integration-lane")})
        else:  # ConverseOp
            base.update({"status": STATUS_OK})
        record.outcomes.append(base)
    record.ranked_by_action = ranked_by_id
    return record


def _apply_predicate(record: Dict[str, Any], field: str, operator: str,
                     value: Any) -> bool:
    """One typed predicate over one evidence record. Missing fields and
    type mismatches are NO-MATCH, never errors — a record that does not
    carry the field cannot satisfy the constraint, and a filter that
    crashes is worse than one that reports honestly. Field lookup walks
    dotted paths one level deep ("metadata.sender") for nested records.
    """
    node: Any = record
    for part in str(field or "").split("."):
        if not isinstance(node, dict):
            return False
        node = node.get(part)
        if node is None:
            return False
    try:
        if operator == "eq":
            return node == value
        if operator == "neq":
            return node != value
        if operator == "contains":
            return str(value).lower() in str(node).lower()
        if operator == "in":
            options = value if isinstance(value, (list, tuple, set)) \
                else [value]
            return node in options
        if operator in ("gt", "gte", "lt", "lte"):
            pair = (node, value)
            if all(isinstance(x, (int, float)) for x in pair):
                a, b = float(node), float(value)
            else:
                a, b = str(node), str(value)
            return {"gt": a > b, "gte": a >= b,
                    "lt": a < b, "lte": a <= b}[operator]
    except (TypeError, ValueError):
        return False
    return False


def _per_sheet_counts(ranked: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for c in ranked:
        sheet = str(c.get("ref") or "").partition("!")[0].strip() \
            or "an unnamed sheet"
        counts[sheet] = counts.get(sheet, 0) + 1
    return counts
