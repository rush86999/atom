# Conversation learning — approval payload binding closure

Source commit: `e05bc55a6c8402a1eaef9958bdda9865b74f0bc3`

This directory closes the verifier's approval-binding blocker: a chat HITL
approval now authorizes only the exact proposal payload that was reviewed.
The accepted local-core tag `local-core-2026-10-30-final` (`da9cc8b12`) and
all earlier evidence remain unchanged.

## Binding contract

The `chat_request_obligation` HITL params now carry:

- `payload_sha256` over the exact `send_email` action:
  `action_type`, `canvas_id`, `to`, `cc`, `subject`, `body`,
  `attachment_ids`, `attachment_hashes`, `thread_id`, `reply_all`;
- `artifact_revision` = hash of the draft canvas content at review time.

`ProposalService.approve_proposal` accepts `expected_payload_sha256` and
`expected_artifact_revision`:

1. It re-reads the current proposal and compares both values before the claim.
2. It performs the conditional `pending_approval → approved` UPDATE.
3. While holding the row lock, it re-reads and compares again before commit.
4. It executes the action captured from the same reviewed read, so a
   concurrent change cannot alter what is executed.

A changed payload raises `ProposalApprovalInvalidated`; the approval claim is
rolled back, the proposal stays `pending_approval`, and the HITL resume
returns:

```json
{"handled": true, "resumed": false, "status": "payload_changed",
 "fresh_review_required": true}
```

`hitl_resume` preserves rejection (proposal rejected, no transport), duplicate
approval (already executed → replayed, no second transport), missing binding
(fail closed), and terminal proposal states.

## Controlled tests

`test_chat_teaching_route.py` now covers:

- matching payload → one controlled transport call, proposal executed;
- duplicate approval → `replayed=true`, still one transport call;
- recipient changed after review → refused, zero transport calls, proposal
  remains `pending_approval`;
- body changed after review → refused, zero transport calls;
- attachment hash changed after review → refused, zero transport calls;
- rejection → proposal rejected, zero transport calls.

## Live controlled campaign

`approval-binding-campaign.json`:

| Case | Result |
|---|---|
| Recipient changed to `different-recipient@example.invalid` | `payload_changed`, 0 transport calls, proposal `pending_approval` |
| Body changed after review | `payload_changed`, 0 transport calls, proposal `pending_approval` |
| Attachment hash changed after review | `payload_changed`, 0 transport calls, proposal `pending_approval` |
| Matching payload approved | `handled=true`, `resumed=true`, 1 controlled transport call, proposal `executed` |
| Duplicate approval | `replayed=true`, still 1 transport call |

The controlled transport is an `AsyncMock`; no real email was sent.

## Tests

| Suite | Result |
|---|---|
| Targeted backend | **425 passed** |
| Frontend learning | **4 passed** |
| TypeScript `--noEmit` | clean |

The known 14 `test_chat_canvas_editor.py` failures remain the pre-existing
canvas pre-planning authorization refusal documented in earlier evidence.

## Configuration and bounds

`ATOM_TURN_DECISION_ROUTING=0`, local Ollama,
`ATOM_TASK_LIFECYCLE_ENABLED=1`, `ATOM_LOCAL_ONLY=true`; isolated world on
`127.0.0.1:8071`. No real email, external research, deployment, credential
change or live-service restart was performed.
