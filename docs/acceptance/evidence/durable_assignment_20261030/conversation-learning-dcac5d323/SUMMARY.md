# Conversation learning — atomic approval-binding closure

Source commit: `dcac5d32349ff923be38fa36ed668810dccb62cb`

This directory closes the verifier's final approval-binding blocker: a change
injected immediately before `_claim_proposal()` is now detected from the fresh
database row, not from the captured execution snapshot. The accepted
local-core tag `local-core-2026-10-30-final` (`da9cc8b12`) and all earlier
evidence remain unchanged.

## Atomic claim contract

`ProposalService._claim_proposal` now:

1. Ends any earlier read snapshot when an expected payload binding exists.
2. Re-reads the proposal with `populate_existing()` and a row lock.
3. Compares the **fresh database** `proposal_data` hash and the **fresh**
   canvas content revision to the reviewed binding.
4. Performs the conditional `pending_approval → approved` UPDATE.
5. Re-reads the fresh row again before commit and repeats both comparisons.
6. Executes the captured reviewed action only after the claim passes.

The captured `action_to_execute` is no longer used as the database drift value;
it is only the execution snapshot. `_proposal_artifact_revision` re-reads the
canvas with `populate_existing()` and a row lock.

On drift, the claim is rolled back, the proposal remains `pending_approval`,
`hitl_resume` returns `payload_changed` with `fresh_review_required=true`, and
the controlled transport receives **zero** calls.

## Immutable execution audit

After a successful approval, `execution_outcome_details` stores:

- `executed_action` — the exact action snapshot passed to the transport;
- `executed_action_sha256` — its stable digest;
- `reviewed_payload_sha256` and `reviewed_artifact_revision` — the binding that
  authorized it.

The live positive case shows `executed_action.to == alice@example.com` and the
executed digest equal to the reviewed digest.

## Deterministic regressions

- Change recipient immediately before `_claim_proposal` → `payload_changed`,
  0 transport calls, proposal `pending_approval`.
- Change canvas content immediately before `_claim_proposal` → `payload_changed`,
  0 transport calls, proposal `pending_approval`.
- Matching payload → one controlled transport call, proposal `executed`.
- Duplicate approval → `replayed=true`, still one transport call.
- Rejection → proposal `rejected`, zero transport calls.

## Live controlled campaign

`atomic-binding-campaign.json`:

| Case | Result |
|---|---|
| Recipient changed between read and claim | `payload_changed`; 0 transport calls; `pending_approval` |
| Canvas changed between review and claim | `payload_changed`; 0 transport calls; `pending_approval` |
| Matching payload | `handled=true`, `resumed=true`; 1 controlled call; `executed` |
| Duplicate approval | `replayed=true`; still 1 call |
| Executed snapshot | `alice@example.com`, digest == reviewed digest |

The controlled transport is an `AsyncMock`; no real email was sent.

## Tests

| Suite | Result |
|---|---|
| Targeted backend | **427 passed** |
| Frontend learning | **4 passed** |
| TypeScript `--noEmit` | clean |

The known 14 `test_chat_canvas_editor.py` failures remain the pre-existing
canvas pre-planning authorization refusal documented in earlier evidence.

## Configuration and bounds

`ATOM_TURN_DECISION_ROUTING=0`, local Ollama,
`ATOM_TASK_LIFECYCLE_ENABLED=1`, `ATOM_LOCAL_ONLY=true`; isolated world on
`127.0.0.1:8071`. No real email, external research, deployment, credential
change or live-service restart was performed.
