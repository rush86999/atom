# Chat session fork — verified authority, source snapshot and durable receipt

Status: **submitted for independent verification.** PR
[#670](https://github.com/rush86999/atom/pull/670). No merge or deployment was
performed.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/oracle01-chat-fork-20261106` |
| Base main | `d860072a787e6460d83260e9cb629cfa5d5ea14b` |
| Executed source | `371cb197b9f5b69e6b1ef3b75580b501b1f7f575` |
| Prepared provenance | `/private/tmp/atom-chat`, branch `codex/oracle01-chat-20261105`, tip `eede11a8f` |
| Runtime | real scratch SQLite with fresh sessions and committed two-session interleaving; no live model/provider |

Main's `chat_routes.py` and the existing fork tests are unchanged between the
prepared base `9d73552d2` and the port base `d860072a7`, so the prepared route
patch and new service port without behavior drift. This submission adds one
repair found during the port review: the post-claim message-snapshot recheck.

## User outcome

An authenticated session owner can fork the exact conversation they just read
(or an inclusive prefix through a specific message). The effect binds the
current caller authority and the exact source material, inserts one new
session plus copied messages, writes one durable `AuditLog` receipt in the same
transaction, replays idempotently, and refuses a changed source or another
owner with zero effect.

## Route and scope

| Method | Path | Handler | Service |
|---|---|---|---|
| POST | `/api/chat/sessions/{session_id}/fork` | `integrations.chat_routes.fork_chat_session` | `core.chat_fork_write_service.fork_chat_session` |

Rename, delete, message send/cancel, feedback, history/list and LanceDB chat
storage remain out of scope. No new table, migration or second chat engine.

## Authority and scope

- Mandatory `get_current_user` plus the existing in-memory session ownership
  gate remain.
- The service re-reads the current `User` row, requires active status, and
  claims current `is_active`/`status`/`role`/raw tenant in a guarded no-op
  `User` UPDATE in the fork transaction.
- The source `ChatSession.user_id` must be the caller. A foreign owner is
  refused with no fork or audit; unknown/no-message sources keep the legacy
  `200 success=false` shape.
- The source row is claimed with an exact guarded no-op `ChatSession` UPDATE
  (id, user, title, metadata, message count).
- The message snapshot is read in chronological order, then re-read after the
  claim. The claim holds the SQLite write lock, so a concurrent message edit
  between the snapshot and the claim changes the digest and returns 409
  `STALE_SOURCE` with no fork, no copies and no audit.
- The copied messages keep tenant, role, content, agent id and metadata with
  fresh ids. Channel/thread bindings are not inherited.

## Effect contract

- One new `ChatSession`: generated id, caller user, `Fork: <source title>`
  title, `metadata_json={forked_from, forked_at}`, copied message count.
- One `ChatMessage` per source row in the snapshot prefix.
- One `AuditLog` receipt in the same transaction. Metadata contains operation
  id, action, event type, source session id, target fork id, prior/request/
  result digests and actor id/role/tenant. No raw message content, prompt,
  secret or SQL parameter enters the receipt or logs.
- `verified`: legacy success shape plus additive verification/operation_id/
  audit_id.
- `already_applied`: same operation/material; one receipt.
- `no_effect`: empty/unknown source or missing boundary; legacy
  `success=false`, no audit.
- `conflict` (409): stale source/message snapshot, changed operation/material
  or authority change; `effect=none`.
- `not_applied` (409): confirmed rollback; `effect=none`.
- `committed_unverified` (503): post-commit readback failed/refuted.
- `effect_unknown` (503): lost confirmation with original identity; no
  exception text.

## Caller / parallel-writer map

| Caller or consumer | Action |
|---|---|
| `fork_chat_session` route | verified fork service |
| source `ChatSession` | guarded no-op claim |
| source `ChatMessage` rows | chronological snapshot + post-claim digest recheck |
| new `ChatSession` + `ChatMessage` rows | inserted once per operation |
| in-memory orchestrator registration | after a verified commit, existing behavior |
| history/list/rename/delete | unchanged and out of scope |
| `AuditLog` | additive safe receipt |

## Verification

| Gate | Result |
|---|---|
| Focused chat-fork gate, Python 3.14 | **38 passed** |
| Focused chat-fork gate, Python 3.11 | **38 passed** |
| Affected chat selection, 3.14 | **314 passed, 7 failed** |
| Affected chat selection, 3.11 | **314 passed, 7 failed** |
| Main `d860072a7` baseline, 3.14 | 290 passed, 7 failed |
| Main `d860072a7` baseline, 3.11 | 289 passed, 8 failed |

The 7 failures are identical on main and the candidate. Main 3.11 additionally
fails one `test_covpush_w115_chat_orchestrator` flake that the candidate does
not reproduce. The candidate adds 24 passing contract controls and zero new
failures.

## Boundaries

- No live model, provider, credential, spend, send, download, deployment or
  external messaging operation.
- No production authority, scope, provider or audit gate weakened.
- No test deleted, skipped or xfailed.
- PostgreSQL runtime/soak and multi-worker remain unqualified.
