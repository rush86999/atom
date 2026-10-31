# Conversation-derived, reference-bound learning

Status: **bounded successor implementation complete; independent verifier
review pending.** Approval-binding source `e05bc55a6` (tree `37ec5a02`),
building on parser/continuation source `dfa940ee5` / `237a187df`,
method-boundary source `525a768d1` / `a660065cd`, closure source
`54543b493` / `550e8c165`, consumer source `37904dcd0` / `a888f5d6c` and
applicability source `50b53bef6` (tree `cf7d8d3`). This is deliberately
separate from the accepted local-core closure at `da9cc8b12` / tag
`local-core-2026-10-30-final`. It does not relabel historical browser/live
evidence or claim a full application journey on this source.

Applicability evidence:
`docs/acceptance/evidence/durable_assignment_20261030/conversation-learning-50b53be/`.

Earlier consumer wiring:
`docs/acceptance/evidence/durable_assignment_20261030/conversation-learning-a888f5d6c/`.

Closure evidence:
`docs/acceptance/evidence/durable_assignment_20261030/conversation-learning-54543b493/`.

Method-boundary evidence:
`docs/acceptance/evidence/durable_assignment_20261030/conversation-learning-525a768d1/`.

Parser/continuation evidence:
`docs/acceptance/evidence/durable_assignment_20261030/conversation-learning-dfa940ee5/`.

Approval-binding evidence:
`docs/acceptance/evidence/durable_assignment_20261030/conversation-learning-e05bc55a6/`.

## 1. Why this phase exists

The accepted core could learn a rule from a chat message or a canvas teaching
form, but it did not preserve the conversation's resource relationships. A
statement such as “use the revised adjustment from the workbook, except for
the northern accounts” can depend on:

- which workbook and which version;
- which adjustment and which field identifies the account group;
- what “northern” means in the dataset;
- the effective period;
- whether the speaker was authoring a rule or quoting a source.

This phase makes those dependencies explicit and blocks promotion until they
are resolved. Reference resolution, evidence sufficiency and teaching
authority are validated separately.

## 2. Reused mechanisms (no second store)

| Concern | Reused mechanism |
|---|---|
| Candidate/review ledger | append-only `ConversationEvent` rows (`learning_candidate_*`) |
| Resource identity | `DatasetEntry` catalog + `assignment_resources.resource_binding` contract |
| Source version/access | `source_version`, `access_scope`, workspace/tenant scope |
| Accepted teaching | `student_learning_service.journal_standing_lesson_entry` |
| Work-time application | the same agent lesson log; structured method lives in `details.conversation_learning` |
| UI | new review panel on `/learning`, backed by the public routes |

No graph database, vector index, or parallel knowledge table was added.

## 3. Contract

### 3.1 Evidence package

`ConversationEvidence` carries:

- workspace/account/thread identity;
- `MessageEvidence` with provider id, revision/hash, mailbox owner,
  sender/recipients, sent/received time, authored vs quoted segments,
  attachments, reply references and source access status;
- `ResourceBinding` with catalog id, provider/file identity, source version,
  sheet/locator, coverage and authenticated access scope;
- `ReferenceEdge` with origin message/span, reference text, general relation,
  resolution status, target binding, candidates, basis and confirmer;
- coverage including message/resource limits and traversal depth.

### 3.2 Resolution order

1. explicit user-confirmed target;
2. provider attachment/message identity;
3. exact catalog/resource reference;
4. exact name inside the authenticated workspace/tenant;
5. contextual candidates (attached/previous) only when unique.

Ambiguity is never resolved by recency or similarity. Punctuation is part of
an identifier (`rates-2026.xlsx` is not `rates 2026.xlsx`). A same-name
attachment with two catalog rows is ambiguous, not a first-match pick.

### 3.3 Dependency states

`resolved`, `ambiguous`, `missing`, `access_denied`, `stale`, `incomplete`,
`conflicting`, `not_applicable`. A candidate is review-ready only when every
required dependency is resolved and the method is explicit.

### 3.4 Method status

`explicit`, `example_only`, `partially_inferred`, `unresolved`. An example or
inference cannot promote until the user confirms the governing method.
Supported arithmetic is a bounded allowlist (`sum`, `count`, `multiply_sum`,
`percentage`, `ratio`) with Decimal arithmetic and explicit units/rounding —
never `eval`, macros or model-generated code.

### 3.5 Promotion

Promotion requires:

- review-ready dependencies;
- `confirmed_revision == revision` and `confirmed_digest == digest`;
- an authored, accessible authority message;
- a lesson that does not expand permissions unless the authored authority
  excerpt itself states that expansion.

The write goes through `journal_standing_lesson_entry`; an incoming email
cannot write a lesson directly.

### 3.6 Applicability enforcement

- Promotion writes the candidate context through the existing
  `normalize_lesson_context` into the journal entry's top-level `context`.
  Provenance remains separately under `details.conversation_learning`.
- Method application evaluates that top-level context before arithmetic:
  wrong context refuses, missing context returns the missing keys, equally
  specific conflicting methods surface a conflict, and a more specific lesson
  supersedes a general one.
- Normal work-time `get_agent_lessons` excludes context-bound lessons unless
  the caller supplies matching task context. Format/mapping lessons continue
  through `resolve_artifact_teaching`'s existing context resolver.
- Refusal returns before calculation and does not mutate the candidate,
  journal or governing state.

### 3.7 Scope, authority and reuse enforcement

- Email evidence is scoped to authorized canvases **before** any limit. An
  empty workspace returns no threads, messages or catalog rows. Default-scope
  (`NULL`) canvases are visible only to the default workspace.
- Every candidate mutation re-authorizes the target employee in the caller's
  workspace/tenant. Reviewer identity comes from the authenticated database
  user; client `reviewer` text is ignored. Viewer roles are refused.
- Promotion validates current reference versions. Normal work-time lesson
  retrieval also checks the governing dataset version, so a changed source
  blocks reuse even when the candidate endpoint is never called. The raw
  journal keeps the old lesson with `stale`/`revalidation_required` provenance.
- The `learning` capability is enabled in the core profile and appears in
  navigation. The page uses an authorized employee selector and exposes an
  apply-to-unfamiliar-work action after promotion.

### 3.8 Ordinary consumer closure

- `resolve_teaching_contract` returns a typed decision independent of prompt
  rendering: `applicable_lessons`, `required_context`, `conflicts`,
  `excluded_lessons`, `consumed_lesson_refs`, `source_bindings`,
  `method_status`, `method_lessons`, `all_context_values`.
- Applicable guidance and unresolved requirements are resolved
  independently. A general lesson cannot hide a relevant scoped requirement;
  an unrelated scoped lesson is excluded by the bounded relevance vocabulary
  and does not block the task. Matching one instruction never asserts that
  all required teaching dependencies are satisfied.
- Chat resolves teaching BEFORE intent analysis / reply generation. Missing
  context is a typed clarification created before the reply budget is spent;
  the model cannot generate a speculative answer that is later replaced.
- The pending clarification is durable in session metadata (and in the
  existing task ledger when the conversation already has an active task). It
  stores the original objective, session/user/employee/workspace, lesson
  IDs/revisions, requested fields, allowed values, source bindings, request
  identity and state. No second task engine or new GoalRun is created.
- The original request establishes only unambiguous allowed context (e.g.
  “Customer-A” → `customer`). The answer turn binds to the pending request;
  “Probably licensed” preserves uncertainty, multiple values are ambiguous,
  and an explicit value for an established key is a scope update. A
  self-reported qualification is `user_confirmation`, never independently
  verified certification.
- Approved methods run through `conversation_learning.apply_lesson_method`.
  The reply is rendered from the typed result; the model does not redo the
  arithmetic. Wrong context is an explicit exclusion (no calculation),
  missing context is a clarification, and competing equally specific methods
  are a conflict (no calculation).
- Duplicate confirmation replays the stored result idempotently. A
  clarification from a foreign session/user/workspace/employee cannot mutate
  the obligation.
- Assignment start resolves applicable conversation methods and compiles the
  promoted method into the existing `formula.calculate` step. Wrong context
  returns HTTP 409 `teaching_context_mismatch`; missing context returns HTTP
  409 `teaching_context_unresolved` with the missing keys. The assignment
  read model exposes `effective_lesson_ids` (id + revision) on start and on
  `GET /api/assignments/{run_id}`.
- Context-only conversation lessons no longer manufacture an artifact
  `format_spec` error.
- Parallel canvas/review/derivation consumers still call
  `get_agent_lessons` without task context, so context-bound conversation
  methods stay out of those prompts; artifact format/mapping lessons keep
  using `resolve_artifact_teaching`'s existing context resolver.

### 3.9 Deterministic method boundary

The deterministic Chat shortcut is four explicit stages:

1. **Extract** every candidate for each declared input, retaining concept,
   column, raw value, Decimal value, raw unit, span and source. Aliases that
   map to one concept are checked together.
2. **Validate** against the accepted method: missing, malformed, multiple
   conflicting values, incompatible units and unknown units are typed
   questions. No first/last/nearest selection.
3. **Execute** only validated inputs through the existing
   `apply_lesson_method` allowlist and Decimal arithmetic.
4. **Settle** the typed `calculation_receipt` (`covered_obligations =
   ["calculation"]`) through the existing obligation/finalization path. The
   calculator never returns a whole-task completed verdict.

Unit evidence is explicit: user-stated unit, required method unit, normalized
unit (when recognized), authority (`user_message` or `method_declared`) and
compatibility status. Explicit CAD with a USD method is incompatible; unknown
units are unresolved; no currency conversion is authorized. Absent units use
the method-declared unit and record that basis.

Operand questions reuse the durable teaching-clarification carrier with
`kind="operands"`; the pending record stores the objective, method
id/revision, accepted context, competing/missing operands and units, request
identity and completed work. Confirmed answers become operand overrides and
resume the original objective; duplicate confirmation replays; changed method
revisions reassess; refresh/restart preserves the pending question.

For a compound request, the existing request-assignment extractor identifies
the additional work. The calculation receipt is retained, the remaining
obligation is kept open in the approval ledger (pending `HITLAction` and the
active task ledger where present), and the turn outcome is `partial`. No
outbound action runs during this repair.

### 3.10 Prefix units, answer validation and compound continuation

- Prefix (`$`, `€`, `£`) and suffix units are captured in the same candidate
  record and validated against the method. `€7.50` with a USD method is
  incompatible; it is never an absent unit. No currency conversion is
  implicit.
- Clarification answers use the same extraction/validation contract as the
  original input: labeled answers collect every candidate, bare answers
  collect every numeric token, malformed tokens remain malformed, and
  multiple values remain ambiguous. A failed answer refreshes the pending
  question to the latest candidates instead of reverting to the original.
- Compound email work continues to a real draft. If the recipient is missing,
  a durable `email_draft` clarification asks for it while retaining the draft
  and receipt. The recipient answer updates the draft, creates a concrete
  `AgentProposal` (`action_type=send_email`) and files a
  `chat_request_obligation` HITL row.
- `hitl_resume` handles `chat_request_obligation` by approving/rejecting the
  prepared proposal through `ProposalService`. Approval executes the existing
  email path, not a second send path. Tests use a controlled
  `EmailCanvasService.send_email` mock; no real send runs.

### 3.11 Approval payload binding

A chat `chat_request_obligation` approval is bound to the exact reviewed
proposal payload, not just the proposal id:

- `payload_sha256` covers `action_type`, `canvas_id`, `to`, `cc`, `subject`,
  `body`, `attachment_ids`, `attachment_hashes`, `thread_id`, `reply_all`;
- `artifact_revision` is the draft canvas content hash at review time.

`ProposalService.approve_proposal` compares both values before the
`pending_approval → approved` claim, performs the conditional UPDATE, re-reads
and compares again while holding the row lock, then commits and executes the
action captured from the reviewed read. A changed payload raises
`ProposalApprovalInvalidated`; the claim is rolled back, the proposal remains
`pending_approval`, and `hitl_resume` returns `payload_changed` with
`fresh_review_required=true`. No transport runs.

Rejection, duplicate approval (already executed → replayed), missing binding
(fail closed) and terminal proposal states remain preserved.

## 4. Acceptance matrix

All cases run through the shared implementation in
`backend/tests/test_conversation_learning.py` and
`backend/tests/test_conversation_learning_routes.py`.

| # | Case | Test | Result |
|---|---|---|---|
| 1 | Explicit attachment reference resolves | `test_explicit_attachment_reference_resolves` | pass |
| 2 | Same-name attachments require clarification | `test_same_name_attachments_require_clarification` | pass |
| 3 | “Previous workbook” only when unambiguous | `test_previous_workbook_resolves_only_when_unambiguous` | pass |
| 4 | “Usual method” remains unresolved | `test_usual_method_remains_unresolved_until_established` | pass |
| 5 | Conflicting examples do not fabricate a rule | `test_conflicting_examples_do_not_produce_a_fabricated_rule` | pass |
| 6 | Complete method transfers to unfamiliar data | `test_complete_referenced_method_transfers_to_unfamiliar_data` | pass |
| 7 | Missing units block a numerical conclusion | `test_missing_units_block_a_numerical_conclusion` | pass |
| 8 | Version change invalidates relevant reuse | `test_version_change_invalidates_relevant_reuse` | pass |
| 9 | Revoked access prevents retrieval | `test_revoked_access_prevents_source_retrieval` | pass |
| 10 | Quoted instructions are not authority | `test_quoted_instructions_do_not_become_new_authority` | pass |
| 11 | Source permission requests are not authority | `test_source_content_permission_request_is_not_authority` | pass |
| 12 | Restart preserves dependencies/confirmations | `test_restart_preserves_dependencies_and_confirmations` | pass |
| 13 | Changed content invalidates old approval | `test_changed_candidate_content_invalidates_old_approval` | pass |
| 14 | Rejection has no governing effect | `test_rejecting_a_proposal_has_no_governing_effect` | pass |
| 15 | Correction preserves unrelated teaching | `test_correction_preserves_unrelated_teaching` | pass |

Additional coverage:

- punctuation-sensitive identifiers do not collide;
- promoted lessons carry and re-apply their validated method
  (`test_promoted_lesson_applies_its_method_to_new_rows`);
- empty-workspace disclosure, foreign-employee targeting, viewer refusal,
  forged reviewer text, source-change work-time blocking and promotion
  blocking are permanent negatives;
- local thread listing and evidence resolution through the public routes.

The applicability-phase service/route suite was **37 passed**; assignment
regressions **126 passed**; teaching/renderer regressions **137 passed**;
frontend targeted **35 passed**; TypeScript clean. The production frontend
build succeeded. Those numbers remain in the `conversation-learning-50b53be`
evidence.

The earlier consumer source added the chat/assignment wiring and recorded
**303 passed**. The closure source adds the typed resolver, durable
clarification, deterministic chat execution, wrong/conflict outcomes and the
browser/restart journeys. The method-boundary source adds candidate/unit
validation, calculation receipts, compound-request settlement and operand
clarification. The parser/continuation source adds prefix units, shared
answer validation and resumable compound email work. The approval-binding
source binds the reviewed proposal payload and artifact revision. Its targeted
backend set is **425 passed**; its frontend learning suites are **4 passed**;
TypeScript `--noEmit` is clean. Fourteen
`test_chat_canvas_editor.py` tests fail in a wider run; the same failure mode
is present at the parent commit `55dddd6d4` with `lane refused pre-planning:
the turn's own words do not authorize a canvas mutation`; they are
pre-existing and unrelated, and are not counted in the 420-pass set.

Two domains are exercised by the method-transfer case: sales pricing
(`quantity × unit price`) and payroll-style units/rates, with independently
expected totals `20.00` and `16.50`.

## 5. Public routes

- `GET /api/conversation-learning/employees`
- `GET /api/conversation-learning/threads`
- `POST /api/conversation-learning/evidence`
- `GET /api/conversation-learning/threads/{thread_id}/evidence`
- `GET /api/conversation-learning/threads/{thread_id}/candidates`
- `POST /api/conversation-learning/candidates`
- `GET /api/conversation-learning/candidates/{candidate_id}`
- `POST /api/conversation-learning/candidates/{candidate_id}/revise`
- `POST /api/conversation-learning/candidates/{candidate_id}/resolve`
- `POST /api/conversation-learning/candidates/{candidate_id}/confirm`
- `POST /api/conversation-learning/candidates/{candidate_id}/promote`
- `POST /api/conversation-learning/candidates/{candidate_id}/apply`
- `POST /api/conversation-learning/candidates/{candidate_id}/reject`

All routes scope candidates by the authenticated workspace/tenant.

## 6. UI

`/learning` lists persisted local email threads, loads the evidence package,
and shows the compact review:

- proposed lesson;
- where it applies;
- referenced data and versions (including ambiguity candidates);
- method and assumptions;
- exceptions;
- unresolved questions with resource/answer controls;
- supporting messages and the authority excerpt;
- confirm/promote/reject actions.

## 6.1 Full-app browser journey

The production frontend build and full app were exercised on
`127.0.0.1:3130` / `127.0.0.1:8071` against an isolated world:

1. open the persisted local thread;
2. select the authorized employee from the selector;
3. propose/review the lesson with the resolved `rates.xlsx` binding;
4. confirm and promote;
5. apply with the wrong Customer-B/unlicensed context → visible refusal;
6. apply with matching Customer-A/licensed context → **15 USD**;
7. change the governing dataset version `v1` → `v2`;
8. reload: candidate `invalidated`, apply HTTP 409;
9. restart the backend against the same world;
10. reopen: candidate still `invalidated`, top-level context preserved, raw
    lesson `stale`, apply HTTP 409;
11. no page errors.

## 6.2 Ordinary Chat closure live evidence

Isolated world `/Users/rushiparikh/projects/atom-conversation-context-world`,
backend `127.0.0.1:8071`, frontend `127.0.0.1:3130`. The browser journey
promoted a fresh scoped method through `/learning`:
lesson `77fcb41c777f45b1bf50e4a6f5644267` rev `1`, context
`customer=Customer-A, qualification=licensed`, method `multiply_sum` over
`Qty`/`Price`. A general lesson was added through normal `/teach`.

| Case | Result |
|---|---|
| Ask without qualification | visible ask for `qualification (one of: licensed)`; general lesson retained in `memory_context`; both lesson refs named |
| Answer “licensed” | original objective resumed; deterministic `multiply_sum(quantity=2 units, unit_price=7.50 USD) = 15 USD`; lesson id/rev exact; outcome `completed`; no “1.75”, no extra confirmation |
| Refresh | result visible; history last assistant outcome `completed` with the same lesson revision |
| Restart while waiting | pending clarification survived a backend restart; same session answered “licensed”; same exact result and lesson revision |
| Wrong context | outcome `partial`, `teaching_exclusion` (`teaching_context_mismatch`), no `teaching_execution` |
| Duplicate “licensed” | replayed the stored `completed` result idempotently |
| “Probably licensed” | did not confirm; asked for a plain value; a later “licensed” completed |

Configuration: `ATOM_TURN_DECISION_ROUTING=0`, local Ollama,
`ATOM_TASK_LIFECYCLE_ENABLED=1`, `ATOM_LOCAL_ONLY=true`. The task ledger is
used only when the conversation already has an active task; otherwise the
existing session/assistant-metadata carrier is the durable obligation. The
isolated world used `agent-browser-final` (workspace `default`) and moved
`agent-learn` to `agent-learn-ws` so its older scoped lesson would not appear
as a sibling method. This is world isolation, not a product change.

Artifacts and hashes are in the closure evidence directory. Assignment
evidence from the earlier applicability phase remains separately valid.

## 6.3 Deterministic method-boundary live evidence

Ordinary Chat, same isolated world and configuration, lesson
`77fcb41c777f45b1bf50e4a6f5644267` rev `1`.

| Case | Result |
|---|---|
| Valid `Qty 2 / Price 7.50 USD` | `completed`; receipt `15 USD`; lesson rev `1` |
| Ambiguous `Price 7.50 or Price 8.00` | `partial`; visible clarification with both candidates; no receipt |
| Confirm `8.00` | original task resumes; receipt `16 USD`; `user_confirmation` provenance |
| `Price 7.50 CAD` with USD method | `partial`; incompatible-unit clarification; no arithmetic |
| Compatible replacement `Price 7.50 USD` | original task resumes; receipt `15 USD` |
| `calculate; then email the quote` | `partial`; receipt `15 USD`; `open_obligations=[email the quote]`; pending `HITLAction`; no send |
| Restart while awaiting operand | pending survives; answer resumes original task; receipt `16 USD`; history outcome `completed` |
| Duplicate confirmation | stored result replayed; no duplicate execution |

The public-route test posts the compound request to `/api/chat/message`,
asserts the receipt, `covered_obligations=["calculation"]`, the open email
obligation, a pending `HITLAction`, and arms `_execute_send_email` to fail if
called.

## 6.4 Parser and compound-continuation live campaign

| Case | Result |
|---|---|
| `Price €7.50` | partial; incompatible-unit clarification; no receipt |
| answer `€8.00` | partial; refreshed incompatible-unit question; no receipt |
| answer `8.00 USD` | completed; receipt `16 USD` |
| ambiguous `7.50 or 8.00` | partial; clarification |
| answer `8.00 or 9.00` | partial; ambiguous; no receipt |
| answer `8.00` | completed; receipt `16 USD` |
| `Price 7.50.5` | partial; malformed-value clarification; no receipt |
| answer `Price 7.50` | completed; receipt `15 USD` |
| compound `email the quote` | partial; receipt + draft + recipient clarification |
| answer `alice@example.com` | partial; draft updated; proposal + HITL pending; no send |
| HITL approval (controlled transport) | `handled=true`, `resumed=true`; proposal executed; no real send |

The controlled transport recorded one call to `alice@example.com`; the
proposal moved to `executed` with `execution_success=true`.

## 6.5 Approval payload-binding live campaign

| Case | Result |
|---|---|
| Recipient changed after review | `payload_changed`; 0 transport calls; proposal `pending_approval` |
| Body changed after review | `payload_changed`; 0 transport calls; proposal `pending_approval` |
| Attachment hash changed after review | `payload_changed`; 0 transport calls; proposal `pending_approval` |
| Matching reviewed payload | `handled=true`, `resumed=true`; 1 controlled transport call; proposal `executed` |
| Duplicate approval | `replayed=true`; still 1 transport call |
| Rejection | proposal `rejected`; 0 transport calls |

The controlled transport is a mock; no real email was sent.

## 7. Consumer audit

| Surface | Established task context | Required-context clarification | Scoped conversation methods | Consumed revision record |
|---|---|---|---|---|
| Chat (`process_chat_message` / `_get_qwen_response`) | Request `task_context`/top-level keys, plus unambiguous allowed values inferred from the original message; answer turn merges only confirmed fields | Yes — typed context or operand clarification before intent analysis; durable in session metadata and active task ledger | Yes — uniquely applicable executable method runs through `apply_lesson_method` after candidate/unit validation | `calculation_receipt.lesson_ref`, `input_evidence`, `covered_obligations`, `teaching_clarification.lesson_refs`, history metadata |
| Memory assembly (`assemble_memory_context` / `_lessons_leg`) | Caller-supplied `task_context`; resolver returns typed `required_context`/`conflicts` separately from rendered prompt | Renders the question; does not decide it | Applies matching lessons to the prompt; never injects missing-context lessons | `consumed_lesson_refs`, `required_context.lesson_ids`, `source_bindings` |
| Canvas co-editor / canvas training | Canvas turn context; `get_agent_lessons` calls without `task_context` exclude context-bound methods | No chat clarification on pure canvas lanes; the chat-first gate applies when the turn is a chat turn | Intentionally not applied to canvas mutations; artifact format/mapping teaching keeps `resolve_artifact_teaching` | Artifact lesson fields / canvas teaching record |
| Review / derivation | Turn/objective context; lesson lookups without `task_context` exclude context-bound methods | Not claimed on these internal lanes | Intentionally excluded; general guidance only | Not claimed |
| Assignment start (`assignment_routes`) | `body.task_context` plus objective | HTTP 409 `teaching_context_unresolved` with missing keys | `applicable_method_lessons` filters by `evaluate_lesson_context` before `build_conversation_calculation` | `effective_lesson_ids` on start and `GET /api/assignments/{run_id}` |
| Goal-run / generic agent | Goal/run context; lesson lookups without `task_context` exclude context-bound methods | Not claimed | Intentionally excluded; general guidance only | Not claimed |

`include_context_bound=True` is used only inside resolvers that immediately
evaluate context (`applicable_method_lessons`, `resolve_artifact_teaching`);
it is never used to inject unvalidated instructions into a prompt.

## 8. Bounds and deferred work

This phase is intentionally bounded:

- only persisted local email-canvas audits are read; no live mailbox access,
  token refresh, real send, credential change or source writeback;
- no arbitrary URL fetching and no recursive resource traversal; coverage
  records a depth limit of 1 and depth reached 0;
- reference detection is deterministic (authored cues + exact catalog
  identity), not an LLM extractor;
- candidate creation is explicit through the UI/API; automatic teaching-cue
  extraction from every email is not claimed;
- only the allowlisted arithmetic operations are executable;
- no currency conversion is authorized or implemented; explicit units are
  validated against the method and incompatible/unknown units clarify;
- a compound request keeps its non-calculation obligations in the approval
  ledger; approval is bound to the reviewed payload/artifact digest, resumes
  only that exact payload through `hitl_resume` and `ProposalService`, and
  refuses drift; tests use controlled transport and no real send runs;
- the existing core tag and its historical evidence are unchanged.

Hosted deployment, publication, source shutdown and additional real sends
remain deferred and unauthorized.
