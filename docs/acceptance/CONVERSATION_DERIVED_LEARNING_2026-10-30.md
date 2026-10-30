# Conversation-derived, reference-bound learning

Status: **bounded successor implementation complete; independent verifier
review pending.** Source commit `59464e742` (tree `1ea2b19f`). This is
deliberately separate from the accepted local-core closure at `da9cc8b12` /
tag `local-core-2026-10-30-final`. It does not relabel historical
browser/live evidence or claim a full application journey on this source.

Evidence:
`docs/acceptance/evidence/durable_assignment_20261030/conversation-learning-59464e7/`.

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
- local thread listing and evidence resolution through the public routes.

Two domains are exercised by the method-transfer case: sales pricing
(`quantity × unit price`) and payroll-style units/rates, with independently
expected totals `20.00` and `16.50`.

## 5. Public routes

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

## 7. Bounds and deferred work

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
- the existing core tag and its historical evidence are unchanged.

Hosted deployment, publication, source shutdown and additional real sends
remain deferred and unauthorized.
