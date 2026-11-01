# Conversation learning — parser and compound-email boundary closure

Source commit: `dfa940ee5ee248d5bde3fda5a367fc454ce84dc8`

This directory closes the verifier's remaining bypasses and the dead-end
compound workflow. It preserves the accepted local-core tag
`local-core-2026-10-30-final` (`da9cc8b12`) and all earlier evidence.

## 1. Currency prefixes are preserved

`core/method_operands` now captures prefix (`$`, `€`, `£`) and suffix units
through the same candidate record and validation path. A prefix is no longer
consumed and discarded.

- `Qty 2 and Price €7.50` → `incompatible_unit`; no arithmetic.
- `Qty 2 and Price 7.50€` → `incompatible_unit`; no arithmetic.
- `Qty 2 and Price €7.50 USD` → conflicting units; no arithmetic.
- Clarification answer `€8.00` → `unit_incompatible`; the pending question is
  refreshed to show `Price 8.00 is in €`, and no calculation runs.
- `8.00 USD` then resumes the original task with `user_message` unit
  authority.

## 2. One candidate-validation contract for answers

`parse_operand_answer` no longer uses a separate first-match `.search()`.
Labeled answers use `extract_candidates`; bare answers collect every numeric
token; both go through `validate_candidates`.

- `8.00 or 9.00` → ambiguous; no calculation.
- `Price 8.00 or Price 9.00` → ambiguous; both candidates retained.
- `Price 7.50.5` → malformed token `7.50.5`; no repaired `7.50`.
- `8.00` / `Price 8.00 USD` → one confirmed candidate.
- Failed answers replace the pending question's candidates/reason instead of
  reverting to the original input's candidate.

## 3. Compound email work is resumable

The compound path now continues to a real draft and actionable approval:

1. The calculation receipt is produced.
2. An email draft canvas is created with the receipt as the body.
3. If no recipient is present, a durable `email_draft` clarification asks for
   one; the draft is retained.
4. The recipient answer updates the draft, creates a concrete `AgentProposal`
   (`action_type=send_email`, to/subject/body/canvas), and files a
   `chat_request_obligation` HITL row.
5. `core.hitl_resume.resume_after_hitl_decision` now handles
   `chat_request_obligation` by approving/rejecting the prepared proposal
   through `ProposalService`. Approval executes the existing email path, not a
   second send path.

The live controlled probe returned:

```json
{"handled": true, "resumed": true, "kind": "chat_obligation",
 "proposal_id": "3d2cad7a-…",
 "result": {"success": true, "status": "draft_only"}}
```

The controlled transport was an `AsyncMock`; it recorded one call to
`alice@example.com` and no real email was sent. The proposal moved to
`executed`, `execution_success=true`.

## Live bounded campaign

| Case | Result |
|---|---|
| `Price €7.50` | partial; incompatible-unit clarification; no receipt |
| answer `€8.00` | partial; refreshed incompatible-unit question; no receipt |
| answer `8.00 USD` | completed; receipt `16 USD` |
| `Price 7.50 or Price 8.00` | partial; ambiguous clarification |
| answer `8.00 or 9.00` | partial; ambiguous; no receipt |
| answer `8.00` | completed; receipt `16 USD` |
| `Price 7.50.5` | partial; malformed-value clarification; no receipt |
| answer `Price 7.50` | completed; receipt `15 USD` |
| compound `email the quote` | partial; receipt + draft + recipient clarification |
| answer `alice@example.com` | partial; draft updated; proposal + HITL pending; no send |
| HITL resume (controlled transport) | handled/resumed; proposal executed; no real send |

Artifacts: `boundary-campaign.json`, `boundary-db-verification.json`,
`boundary-hitl-resume.json`.

## Tests

| Suite | Result |
|---|---|
| Targeted backend | **421 passed** |
| Frontend learning | **4 passed** |
| TypeScript `--noEmit` | clean |

The public-route test now uses the actual continuation machinery:
`test_compound_email_draft_clarification_and_approval_resume` exercises
draft → recipient clarification → `AgentProposal` → `chat_request_obligation`
→ `resume_after_hitl_decision` with a controlled `EmailCanvasService.send_email`
mock. The earlier route test also asserts a concrete pending proposal/HITL
payload and no send.

The known 14 `test_chat_canvas_editor.py` failures remain the pre-existing
canvas pre-planning authorization refusal documented in earlier evidence.

## Configuration and bounds

`ATOM_TURN_DECISION_ROUTING=0`, local Ollama,
`ATOM_TASK_LIFECYCLE_ENABLED=1`, `ATOM_LOCAL_ONLY=true`; isolated world on
`127.0.0.1:8071`, frontend `127.0.0.1:3130`. No real email, external research,
deployment, credential change or live-service restart was performed.
