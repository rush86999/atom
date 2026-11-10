# Private native-chat candidate ownership guard

- Branch: `codex/web-learning-native-chat-20261110`
- Successor product/tests commit: `33b8e9931`
- Predecessor frozen commit: `4c393f284` (product/tests) and `a66ee49c8`
  (evidence); both are preserved unchanged.
- This packet covers a finite access-control repair, not a new memory engine.

## Root negative preserved

The root's independent public-API real-JWT/SQL probe
`root-owner-probe.py` (unchanged copy, sha256
`e34af065f4c7f6dd6ddfeae5f8e7e9b48e6389af0a0793b925b00115ad9c7b90`) failed 2/2 against the predecessor:

- same-tenant/same-workspace active member with access to the same agent
  `GET` an owner's private chat candidate -> `200`;
- the same peer `POST .../reject` -> `200`;
- each attempt appended a `ConversationEvent` (`1 -> 2`) for a source the
  peer did not own.

The root withheld evidence is retained as `root-negative-review.json` and
`logs/root-negative-probe.log`; it was not edited.

## Repair

- `LearningCandidate.source_owner_id` is bound server-side from
  `ConversationEvidence.account_id` (which is `ChatSession.user_id` for
  native threads). It is never taken from caller input or mutable email
  `created_by`.
- The owner is included in candidate digest when present, in source identity
  (`_source_revision` already hashes the owner), in `review_payload`, in
  `LearningCandidate.model_dump`, and in the promoted lesson's
  `details.conversation_learning` provenance.
- One shared guard, `candidate_visible_to_user`, requires the current user to
  match the persisted owner for native/private candidates. A missing owner
  fails closed, so old or ambiguous rows require fresh review rather than
  being blessed by a workspace peer.
- The route-level `_require_candidate_access` guard runs before serialization,
  source revalidation, or any event write on: single candidate GET, thread
  candidate list, revise, dependency resolve, confirm, reject, promote and
  apply. The list filters private candidates instead of returning a count.
- Owner access after source deletion still works from the persisted owner;
  the foreign peer is denied before `_revalidate_source` can append an
  invalidation event.
- Email/workspace candidate policy is intentionally unchanged. Explicit human
  promotion keeps the existing agent-level lesson audience; the private
  pending candidate is a separate pre-promotion surface.
- No new lesson store, router, review engine or schema.

## Exact root probe now passes

The unmodified root probe was rerun against the successor bytes:

- result: `2 passed`, exit `0` (see `logs/root-owner-probe-positive.log`);
- the same probe covers peer read denial with unchanged event count and peer
  reject denial with unchanged event count.
- Root must independently rerun the probe before acceptance; this packet is
  not self-acceptance.

## Added focused controls

`backend/tests/api/test_conversation_learning_native_chat.py` now has 13
scratch SQL + JWT cases. New cases:

- exact peer single-GET and peer reject denial with zero new events;
- peer thread candidate list is empty, and peer revise/resolve/confirm/
  promote/apply all return `404` with zero new events, followed by a
  successful owner read;
- missing `source_owner_id` fails closed for the owner too.

Retained coverage: typed collision twins, quoted/empty/whitespace authority
refusal, genuine unquoted positive, truthful 199/200/201 counts, source
revision edit/reorder/delete staleness, restart readback, and the owner
promotion -> fresh-session `get_agent_lessons` exact lesson/provenance join.

## Commands and actual results

```text
# exact root owner probe, unique scratch DB + JWT
TESTING=1 ... pytest root-owner-probe.py --noconftest -q
2 passed, exit 0

# native/API focused controls
TESTING=1 ... pytest tests/api/test_conversation_learning_native_chat.py \
  --noconftest -q
13 passed, exit 0

# affected email + native selection after the shared change
TESTING=1 ... pytest tests/api/test_conversation_learning_native_chat.py \
  tests/test_conversation_learning_routes.py tests/test_conversation_learning.py -q
74 passed, exit 0

# frontend learning/review selection (unchanged surface, rerun)
jest components/learning/__tests__/ConversationLearningReview.test.tsx \
  tests/pages/learning.test.tsx --runInBand --no-watchman
5 passed, exit 0

tsc --noEmit         exit 0
eslint changed files exit 0
```

Retained logs are under `logs/`. `MANIFEST.json` records
`executed_source` (the product/tests commit and bytes), `source_files` (all
product/test/UI files touched by this slice) and `artifacts` (every tracked
file in this packet except `MANIFEST.json` itself).

## Honest limits

- `ChatSession` still stores owner only; this remains an explicitly
  user-global source. No workspace isolation is claimed.
- The guard governs private candidates before promotion. Once a human
  explicitly promotes a lesson, normal agent-level consumption (including
  shared approved standing lessons) is intentionally unchanged.
- Missing-owner rows are denied rather than migrated; they need fresh review.
- Staleness is applied on the next candidate touch, not by a background
  watcher.
- No model/provider, browser, live DB, install, send, spend, deployment,
  merge or PR was used.
- This packet proves the finite authority/ownership mechanics and the
  existing promotion join; it does not claim whole-system teaching
  completion.
