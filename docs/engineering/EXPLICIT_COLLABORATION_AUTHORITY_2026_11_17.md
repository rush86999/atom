# Explicit specialist collaboration — semantic requirement and durable authority

**Bounded offline result: 85 focused checks and 642 existing CI-preservation
contracts passed** with network access denied, an absolute scratch database,
scratch data roots and empty offline model caches. Frozen product/test source:
`d2d6cb2049e7e533c19acc6b3bb0cc85632ddcd2`. The twelve frozen source/test files
are recorded by SHA-256 in the
[filtered result](evidence/explicit_collaboration_authority_20261117/result.json).
This is not live model-quality, browser, whole-app-restart or current-main
acceptance.

## What the turn now carries

The live defect was representational, not lexical. A synthetic Q3 chat asked to
"Analyze these synthetic Q3 facts with finance and sales specialists"; the
accepted decision was `conversation` and the turn answered from one
perspective, with no fleet chain and no specialist contributions. The fix uses
the ONE existing structured interpretation prompt/schema to express a
`collaboration` action (user role labels, `explicit` / `generic` semantics).
There is no second parser, regex detector or phrase list: the deterministic
turn decision, action program, planner and orchestrator only CARRY the
accepted requirement into the existing governed fleet lane.

The collaboration op is a proposal like every other op. Its authorization
fails closed unless trusted facts contain a validated accepted requirement, so
a program constructed directly cannot self-authorize delegation. Role labels
are resolved through the shipped specialist matcher/canonical domains;
requested domains constrain recruitment exactly, and an unknown requested
domain clarifies rather than substituting an available specialist.

### Bounded request material

| Material | Limit | On overflow |
|---|---|---|
| Specialist roles | 10 executed (`COLLABORATION_ROLE_LIMIT`); the structured label list is capped at the first 64 entries (`COLLABORATION_HARD_ROLE_CAP`) | Clarify; the exact original request string is preserved separately, and the label list never carries more than 64 entries. |
| One role label | 200 characters | Clarify and ask for a shorter label; the label is never renamed to fit. |
| Collaboration objective (the whole request) | 4 000 characters | Clarify and ask to shorten/split; execution still uses the turn's original message, which is retained in the requirement. |

Duplicate roles are deduplicated and whitespace-normalized; nothing else is
rewritten. Eight and nine role requests are carried end to end, and an 11-role
request retains all 11 structured labels in its clarification record. Beyond
64 structured labels the label list itself is bounded (`hard_cap_exceeded`
also forces clarification): what is preserved without truncation is the exact
original request string, not an unbounded role-list copy.

## Early route, unchanged operator gates

An accepted collaboration requirement is handled **before** the default reply
leg. The chat boundary must not generate a single-perspective answer first and
hope a later route replaces it. The seam runs after the deterministic
edit/ask lanes and before `_get_qwen_response`.

The gates are unchanged and are evaluated in this order:

1. `ATOM_FLEET_ROUTING_ENABLED` (master; defaults on in shadow since
   2026-08-21, `false` is the full kill switch) — off ⇒ pending reason
   `fleet_routing_disabled`.
2. `resolved_fleet_enforce()` (approved pilot/enforcement) — false ⇒ pending
   reason `fleet_pilot_not_enforced` (shadow).
3. Requirement authorization — an ambiguous/over-limit request ⇒
   `roles_ambiguous`.
4. Remaining turn deadline ≤ 1 s ⇒ `turn_budget_exhausted`.

**A task request is not admin pilot consent.** Naming specialists never flips
the master switch, never approves the pilot and never starts paid specialist
work in shadow. Master-off and shadow both produce an honest pending result
(original request, roles and objective preserved; `objective_pending=true`,
zero chain, zero specialists, no audit row). Only an approved pilot executes
the exact original request through the existing governed agent/fleet lane. A
bare approval resumes the stored original request, not the confirmation
wording.

A pending clarification is not a fleet outcome: it records no
`FleetRoutingAudit` row and no delegation chain, so it earns **no calibration
row and no fleet-success credit**. It also makes no paid model call that could
be mistaken for specialist work.

## Durable pending authority

The durable session-metadata record is authoritative; an in-memory cached
pending cannot override durable state. Load outcomes are explicit:

| Outcome | Meaning |
|---|---|
| `found` | An active durable pending was read and validated. |
| `inactive` | A durable record exists but is no longer active (dispatching/completed/cancelled); it is never resumed. |
| `absent` | The store is readable and holds no pending; a stale cache is cleared. |
| `inconsistent` | The stored record fails its own identity/timestamp contract; it is not dispatched. |
| `unavailable` | The read failed. This is **not** absence and never authorizes using the cached copy. |

A pending record carries `pending_id`, `revision`, `created_at`, a
`request_digest` over the exact request/objective/roles (plus the generic flag)
and the actor/workspace/tenant/session identity. Resume refuses a scope or
digest mismatch, a cancelled/cleared revision, or a stale cached copy.

Save truth is explicit: the durable write happens **first**; the cache is
advanced only after the store confirms. A missing manager, `False` or an
exception becomes `saved=False` / outcome `unavailable` with
`request_preserved=False` (the request and roles remain visible in the
response, and the objective stays pending). The route never hard-codes
`request_preserved=True`.

Dispatch first CAS-transitions `pending → dispatching` in durable metadata, and
nothing dispatches unless that save confirms. In **DB mode** the resume then
also claims the existing `task_operation_records` receipt
(`claim_generic_operation` / `mark_status`) as an independent durable guard: a
second process/turn can only observe the winner, and a completed receipt
blocks a replay even if the later metadata clear failed. **File mode has no
receipt**: `_claim_collaboration_receipt` returns `None` when the session
manager is not DB-backed, so file mode relies on the stable OS file lock plus
the metadata CAS dispatching state, requires no DB and promises no independent
DB receipt or crash recovery. Both storage modes remain first-class. The
durable-clear-vs-stale-cache, cancellation and revision-mismatch controls are
DB-backed (the durable metadata is the authority); the file-mode control covers
cold-manager resume, and the completed-receipt replay guard is DB-mode only.
The task question is resolved only after the durable clear succeeds, and a
stale writer cannot clobber a newer pending (created-at check plus CAS).

## One canonical conversation id

`process_chat_message` resolves `_get_or_create_session` **once** at turn entry
and normalizes `session_id` to its authoritative value before standing
preferences, async-continuation supersede, task lifecycle, teaching/pending
resume, trace, planner, assistant persistence and response composition. Later
lanes no longer re-read the client-supplied id.

This is a general admission fix, not a fleet response rewrite. Reusing another
user's session id gets a fresh own-scope `ChatSession`, and the HTTP envelope,
the durable assistant `conversation_id` and that owned session now agree; the
foreign user's rows are untouched and their pending is never read, cleared or
executed. Ordinary same-user two-turn continuation keeps the same id. Missing
ids, auth/scope checks, transport idempotency and existing handlers are
unchanged.

## Shared session-metadata contract

`ChatSessionManager.update_session_metadata` is a bounded optimistic CAS loop
over a whole raw-JSON snapshot, not a single-key guard. All 2-argument and
`expected=` callers are protected: the guarded statement is
`UPDATE ... WHERE id = :session_id AND metadata_json IS NULL` for SQL `NULL`,
or `... AND CAST(metadata_json AS TEXT) = :raw_snapshot` for a JSON literal
`null`/object — a cast-text comparison, never untyped JSON equality (which
would be misleading on PostgreSQL JSONB). A concurrent commit to any other key
makes that condition miss, and the writer re-reads and re-merges (bounded;
`False` on exhaustion).

- The raw stored JSON is read with `CAST(metadata_json AS TEXT)` and parsed
  locally, so SQL `NULL`, the JSON literal `null`, compact/spaced/pretty text,
  escaped unicode, numeric forms and key order all match the actual bytes.
  PostgreSQL JSONB uses the canonical cast text and JSONB semantics (12
  shared-method checks, not whole-app PostgreSQL).
- `expected=` is a typed JSON-scalar contract evaluated in Python (`str`/`int`/
  `float`/`bool`/`None`, exact type; `True ≠ 1`, `1 ≠ "1"`; `None` matches
  missing/JSON `null`). Composites and non-finite floats are refused. The
  2-argument patch remains a shallow merge where `None` is written as JSON
  null, not a deletion.
- File mode coordinates across processes with a stable sibling `.lock`,
  `flock(LOCK_EX|LOCK_NB)` / `msvcrt.locking`, a bounded wait, a thread
  `RLock` and a unique temp file + fsync + atomic `os.replace`. If neither OS
  lock primitive exists, acquisition fails closed instead of advertising an
  uncoordinated lock. Lock/read/write failure returns `False`; the lock file
  is stable and never unlinked.
- The existing direct `AgentContextResolver.set_session_agent` writer now
  routes through the shared in-session merge (`merge_in_session`) instead of
  its own ORM read-copy-assign-commit, so it cannot overwrite a concurrent
  pending revision or unrelated key. `chat_fork_write_service` only touches
  `updated_at` behind an exact guard; `create_session`/student-training insert
  new rows.

**Cross-caller behavior change.** `update_session_metadata` now returns a
truthful boolean for missing rows and failed commits (previously callers could
not distinguish failure) and accepts optional `expected=`. Existing 2-argument
callers stay source-compatible but now benefit from snapshot CAS; only the
collaboration call sites pass `expected=`. Any future direct existing-row
`ChatSession` metadata writer must use `merge_in_session` /
`update_session_metadata`; no other product writer was found.

## Verification and limits

| Check | Result |
|---|---|
| `test_collaboration_public_http_contract.py` (real ASGI app, real JWT/scope factory/scoped `AtomMetaAgent`, real orchestrator, governance, recruitment, chain/link, `GenericAgent`, synthesis prompt, durable persistence) | 9 passed |
| `test_explicit_collaboration_semantics.py` (structured interpretation, decision/program/planner carry, limits, gate order, pending-before-reply, exact-request execution, child-to-synthesis dataflow) | 28 passed |
| `test_collaboration_pending_authority.py` (durable load/save/claim, scope/revision/digest, concurrent approvals, raw-JSON CAS, typed expected values, real two-process contention, OS-lock truth) | 48 passed |
| Existing CI preservation (lane contract + quickstart matrix) | 642 passed |
| New CI selector (all three complete files) | 85 passed |

**What is proved offline.** The real public HTTP boundary (JWT, scoped agent
factory, child-to-synthesis dataflow), real durable SQLite persistence and
real OS file-lock/CAS behavior. Only external model outputs are doubled at the
`LLMService` boundary; the suite therefore proves routing, authority and
dataflow, **not** model answer quality.

**What is not proved.**

- No live provider/model quality, no browser journey and no current-`main`
  acceptance.
- A fresh manager/orchestrator is not a whole-app restart: it proves cache
  loss, not process/service lifecycle.
- The PostgreSQL evidence is 12 checks on the shared metadata method against a
  socket-only PostgreSQL 14.24 cluster, with the owned PID verified absent
  after cleanup. It is not whole-app PostgreSQL, migration or concurrency
  breadth.
- Fleet cases 6/7/8 remain FAILED with their allowances consumed; nothing here
  is a new real-model pass. Two existing strict XFAILs in
  `tests/test_pending_file_task_resume.py`
  (`test_no_unsupported_workflow_claim_reaches_output`,
  `test_no_unsupported_claim_in_mixed_body`) remain open and are not
  corrected by this release. Separate public-boundary investigation and any
  successor repair are outside this record; these checks are not skipped or
  weakened. The earlier
  collaboration envelope strict XFAIL was removed by the canonical-id fix and
  is now a passing assertion.
- No original audit, 143-claim identity or historical score is modified, and
  no readiness percentage is invented.

## CI addition

One additive `backend-core-extra` step,
`Run explicit collaboration authority controls`, selects the three complete
files with absolute runner-temp scratch `DATABASE_URL` / `ATOM_DATA_DIR`,
`HF_HUB_OFFLINE` / `TRANSFORMERS_OFFLINE` / `HF_DATASETS_OFFLINE=1` and fresh
empty `HF_HOME` / `HF_HUB_CACHE` / `FASTEMBED_CACHE_PATH` directories. It
creates only its own runner-temp root, keeps the standard
`--timeout=300 --timeout-method=thread`, and adds no skip, node-id subset,
continue-on-error or flag flip. The exact step is declared in
`backend/tests/fixtures/ci_backend_additions.json` and listed in
`ci_backend_core_extra.json`; every earlier command, environment, job and
required check name is unchanged.

## Sources

Precedent used by the frozen product commits (public, not private packets):

- SQLAlchemy optimistic concurrency / version counters:
  <https://docs.sqlalchemy.org/en/20/orm/versioning.html>
- PostgreSQL READ COMMITTED conditional `UPDATE` re-check:
  <https://www.postgresql.org/docs/current/transaction-iso.html>
- SQLite transactions (single-writer):
  <https://www.sqlite.org/lang_transaction.html>
- Python `fcntl.flock`: <https://docs.python.org/3/library/fcntl.html#fcntl.flock>
- Python `msvcrt.locking`: <https://docs.python.org/3/library/msvcrt.html>
- OpenAI Agents SDK agents-as-tools (manager owns the conversation and final
  answer; specialists are bounded tools):
  <https://openai.github.io/openai-agents-python/multi_agent/> /
  <https://openai.github.io/openai-agents-python/tools/#agents-as-tools>
