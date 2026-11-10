# Native chat lessons through the existing conversation-learning pipeline

- Branch: `codex/web-learning-native-chat-20261110`
- Frozen product/tests commit: `4c393f284`
- Base: `origin/main` `e2cbff5b989c482040d61c210e74be7f8840668d`
- Scope: one finite native-chat source adapter, not a new memory store.
- No model/provider call, browser run, live DB, install, send, spend,
  deployment, merge or PR.

## What was added

- Explicit typed `source_kind` (`email` default, `native_chat`) on thread
  listing, evidence, candidate create/load/list/confirm/promote/apply/reject.
  Unknown values are refused with `400`; a `nativechat:` prefix is never
  reinterpreted. A legacy email thread whose literal id is `nativechat:<id>`
  and a native chat with `<id>` remain readable only through their own type.
- Native evidence reads `ChatSession` + `ChatMessage`: stored owner, current
  active user, and actual message ids/roles/content. ChatSession has no
  tenant/workspace column, so the adapter reports `source_scope="user_global"`
  and does not claim source-workspace isolation.
- User-authored text is the only authority. Assistant/system/tool bodies stay
  evidence with their real role and are refused as authority. Quoted-only,
  whitespace-only and empty user bodies are also refused, including when the
  caller supplies no `authority_excerpt`; `role=user` alone is not a grant.
- Truthful bounded coverage: exact total, `messages_loaded`, and
  `messages_truncated` from a `limit + 1` read. 199/200/201 boundaries and the
  actual last activity timestamp are tested.
- `source_revision` hashes source kind, opaque id, owner, scope, and each
  message identity/order/role/content hash. Read/updated timestamps are
  excluded. Edit, delete and reorder invalidate review; a promoted lesson is
  marked stale through the existing channel and normal `get_agent_lessons`
  skips it.
- Promotion reuses the existing lesson store, review/confirm/promote path and
  `GenericAgent` consumption. No new schema, memory engine, framework or
  provider.
- UI selection is an explicit composite `[source_kind, thread_id]` with
  `Email` / `Chat` labels; all review calls pass the typed source.

## Root-heldout authority repair

The first root probe failed 2/2: a quoted user line plus an explicit
"not my instruction" statement, and an empty user body, both produced
candidates with `200`.

Root cause was shared, not native-only:

1. native user messages pre-filled `authored_segments=[body]`, bypassing the
   existing `split_authored_quoted` contract;
2. `validate_authority` returned success for an empty excerpt without checking
   that an authored segment actually existed.

Fix: native user messages now go through the shared segmenter; non-user roles
keep their real body but are evidence-only. `validate_authority` now requires a
non-empty authored segment for every source, even with an empty excerpt.

The unmodified root probe was rerun against the repaired bytes:

- `root-authority-probe.py` sha256
  `4abec43680e802bdf92b53c071c6e2972011038e73c1e94f7dc935ac84ab3fbe`
- result: `2 passed`, exit `0`
- root independent repaired review (`root-repaired-review.json`):
  `passed=true`, `assertions_unchanged=true`, `source_unchanged_during_run=true`
- bound core hashes:
  `core/conversation_learning.py`
  `4e3f2a584f13d262e51f4b1306881d29a5cf84f28c12138f576603d64eab3c46`,
  `api/conversation_learning_routes.py`
  `b151e144350f9c5a18b40a4624f371e0d0832d9796a8ac9937a0c9eb651e2a37`

The original failed review (`...negative-review...`) and world are preserved
outside this packet; no probe assertion was changed.

## Positive join and controls

`backend/tests/api/test_conversation_learning_native_chat.py` (10 cases) uses a
real scratch SQL database and JWT public router:

1. native positive, email positive, typed evidence roles
2. typed collision twins, unknown kind, wrong-kind candidate denial
3. foreign/inactive/deleted source handling
4. assistant-not-authority, confirm, promote, fresh-session
   `get_agent_lessons` exact lesson/provenance, edit invalidation and consumer
   absence, deleted-source promotion refusal
5. truthful 199/200/201 counts + actual last timestamp
6. restart readback of typed candidate identity
7. quoted-user refusal, quoted-only, whitespace-only, empty body
8. genuine unquoted user message with empty excerpt accepted
9. reorder changes source revision and invalidates stale review
10. actual role order preserved

The promotion join uses the existing allowed method fixture and real
AgentRegistry; the method is controlled mechanics, not a claim about model
quality.

## Commands and actual results

```text
# native/API, unique scratch DB + JWT
TESTING=1 DATABASE_URL=... ATOM_DATA_DIR=... pytest \
  tests/api/test_conversation_learning_native_chat.py --noconftest -q
10 passed, exit 0

# affected shared-authority selection, rerun after the contract change
TESTING=1 ... pytest tests/api/test_conversation_learning_native_chat.py \
  tests/test_conversation_learning_routes.py tests/test_conversation_learning.py -q
71 passed, exit 0

# exact root heldout probe
TESTING=1 ... pytest root-authority-probe.py --noconftest -q
2 passed, exit 0

# frontend learning/review selection
jest components/learning/__tests__/ConversationLearningReview.test.tsx \
  tests/pages/learning.test.tsx --runInBand --no-watchman
5 passed, exit 0

tsc --noEmit        exit 0
eslint changed files exit 0
```

Logs are retained under `logs/`; hashes are in `MANIFEST.json`.

## Caller impact

- `validate_authority` is shared: a caller that previously named a message with
  an empty excerpt and no authored text now gets
  `authority_no_authored_segment` instead of success. Email positive behavior
  is unchanged when authored text exists; quoted negative behavior is unchanged
  when an authored preamble exists. A body that is entirely quoted now refuses
  with `authority_no_authored_segment` rather than a quoted-specific reason.
- Email APIs and historical candidates keep the legacy default `email`; no
  historical thread ids were renamed.
- Thread listing adds `source_kind`; promote provenance adds
  `source_kind`/`source_scope`/`source_revision`; review payload exposes the
  typed source and coverage.
- The affected email selection (`tests/test_conversation_learning.py`,
  `tests/test_conversation_learning_routes.py`) was rerun after the shared
  change: 71 combined passed, with no test deletion or weakened assertion.

## Honest limits

- `ChatSession` stores owner only. This adapter intentionally treats the
  personal-app session as user-global and discloses that; it does not invent a
  workspace origin or claim per-workspace isolation. Session metadata is
  display-only and is not authority.
- Staleness is not a background watcher. It is applied when the candidate is
  next loaded/reviewed/promoted/applied; once marked, the normal
  `get_agent_lessons` consumer skips the lesson. No automatic edit-time
  invalidation is claimed.
- Native sources above the 200-message bound report truncation and are not
  review-ready.
- GoalRun internal decisions are excluded from this adapter and remain a
  separate future contract.
- This packet proves controlled mechanics and real API/DB behavior, not general
  lesson quality or a whole teaching-system completion claim.

## Research basis

- LangChain memory concepts: short-term memory is thread-scoped, while
  long-term memory is cross-thread and scoped by explicit namespaces, not the
  thread id alone — <https://docs.langchain.com/oss/python/concepts/memory>.
- Anthropic memory tool: memory is client-side and application-owned; the
  handler maps `/memories` onto storage the application controls, such as a
  per-user directory — <https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool>.
- Atom reuses its own lesson store and registry; no library or provider was
  installed for this change.
