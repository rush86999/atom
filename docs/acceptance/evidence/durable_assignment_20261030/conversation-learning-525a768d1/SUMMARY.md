# Conversation learning — deterministic Chat method boundary repair

Source commit: `525a768d1a2f7f28e2f2e61d7fd2205d05f66eef`

This directory closes the verifier's three deterministic-shortcut defects:
operand ambiguity, unit substitution and premature whole-task completion. It
preserves the accepted local-core tag `local-core-2026-10-30-final`
(`da9cc8b12`), the teaching-clarification flow, and all prior evidence
directories.

## Four explicit stages

1. **Extraction** — `core/method_operands.extract_candidates` collects every
   explicit candidate for each declared input, retaining `concept`, `column`,
   `raw_value`, Decimal `value`, `raw_unit`, span and source.
2. **Validation** — `validate_candidates` rejects missing values, malformed
   numbers, multiple conflicting values, explicit units that differ from the
   method's unit, and unknown units. It never chooses first/last/nearest.
3. **Execution** — `execute_method_lesson` runs only validated inputs through
   the existing `conversation_learning.apply_lesson_method` allowlist and
   Decimal arithmetic.
4. **Settlement** — the result is a `calculation_receipt` with
   `covered_obligations=["calculation"]`. The caller submits it to the existing
   obligation/finalization path; the calculator never returns a whole-task
   completed verdict.

## Operand and unit evidence

- `Qty 2 and Price 7.50` → `15 USD`; absent units use the method-declared
  unit with `unit_authority="method_declared"`.
- `Qty 2 and Price 7.50 USD` → `15 USD`; `unit_authority="user_message"`.
- `Qty 2 and Price 7.50 CAD` → no arithmetic; `incompatible_unit`; the
  clarification explicitly says no currency conversion is authorized.
- Unknown explicit unit → no arithmetic; `unknown_unit`; clarification.
- `Price 7.50 or Price 8.00` → no arithmetic; `ambiguous_value`; both
  candidates and spans retained.
- `Qty 2 and quantity 3` → no arithmetic; aliases checked together.
- Missing operand → targeted clarification.
- Malformed `7,50` → no arithmetic; malformed-value clarification.

The receipt and response show the units actually validated, their authority,
and the lesson id/revision. No implicit currency conversion exists.

## Durable operand clarification

Operand questions reuse the teaching-clarification carrier with
`kind="operands"`. The pending record stores the original objective, method
id/revision, accepted task context, competing/missing operands and units,
request identity, and completed work. Session/user/workspace/employee bindings
are validated. A confirmed answer becomes an operand override and resumes the
original objective; duplicate confirmation replays the stored result; a
changed method revision ignores the old override and reassesses. The pending
record survives refresh and backend restart.

## Compound request settlement

`Qty 2 and Price 7.50; then email the quote` now returns:

- `outcome="partial"`;
- the calculation receipt (`15 USD`, lesson `77fcb41c…` rev `1`);
- `covered_obligations=["calculation"]`;
- `open_obligations=[{"kind":"action","text":"email the quote"}]`;
- a pending `HITLAction` (`action_type="chat_request_obligation"`) with the
  receipt and obligation in its params.

No outbound send runs. The email obligation remains awaiting approval.

## Public-route and browser evidence

| Case | Result |
|---|---|
| Valid calculation through ordinary Chat | `completed`, receipt `15 USD` |
| Ambiguous price | visible clarification; no receipt |
| User confirms `8.00` | original task resumes; receipt `16 USD`; lesson rev `1` |
| Explicit CAD with USD method | blocked; no arithmetic |
| Compatible replacement `Price 7.50 USD` | original task resumes; `15 USD` |
| Compound calculation/email | `partial`; receipt retained; email obligation pending approval; no send |
| Restart while awaiting operand | pending survives; answer resumes original task; `16 USD`; history outcome `completed` |
| Duplicate confirmation | replays the stored result |

Artifacts: `chat-operand-journey.json`, the journey script, compound/restart
screenshots, restart part1/part2 JSON/scripts, and
`operand-compound-final.json`.

## Tests

| Suite | Result |
|---|---|
| Targeted backend (conversation learning, public chat route, assignments, memory, teaching, chat orchestrator) | **420 passed** |
| Frontend learning suites | **4 passed** |
| TypeScript `--noEmit` | clean |

The public-route test is `test_public_chat_compound_request_keeps_email_obligation`:
it posts to `/api/chat/message`, asserts `outcome="partial"`, the receipt and
open email obligation, asserts a pending `HITLAction`, and arms
`_execute_send_email` to fail if called.

The known 14 `test_chat_canvas_editor.py` failures remain the pre-existing
canvas pre-planning authorization refusal documented in earlier evidence.

## Configuration and bounds

`ATOM_TURN_DECISION_ROUTING=0`, local Ollama,
`ATOM_TASK_LIFECYCLE_ENABLED=1`, `ATOM_LOCAL_ONLY=true`; isolated world on
`127.0.0.1:8071`, frontend `127.0.0.1:3130`. No real email, external research,
deployment, credential change or live-service restart was performed.
