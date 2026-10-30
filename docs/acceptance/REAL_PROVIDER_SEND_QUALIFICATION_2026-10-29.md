# Real-provider send qualification — prepared, not authorized

Status: **qualified live on 2026-10-30; no recipient delivery inferred.** The frozen release remains draft-and-approval only
(`ATOM_EMAIL_SEND_DISABLED=1`, `ATOM_ASSIGNMENT_ALLOW_LIVE_SEND=0`).

This qualification reuses the existing send path. It does not add a second
sending framework and does not enable sending globally.

## Existing mechanisms traced

| Boundary | Existing mechanism |
|---|---|
| Planning refusal | `core/assignment_planner.py::_send_step` refuses `email.send_outlook` unless `ATOM_ASSIGNMENT_ALLOW_LIVE_SEND=1` |
| Trusted release gate | `core/email_send_policy.py` blocks every transport before the wire call while `ATOM_EMAIL_SEND_DISABLED` is truthy |
| Provider adapter | `integrations/outlook_service.py::OutlookService.send_email` uses `/me/sendMail` (or draft + attachment + send) and checks delegated `Mail.Send` |
| Canvas send | `core/canvas_email_service.py::EmailCanvasService.send_email` evaluates the existing email policy, attachments, grounding and records the attempt |
| Approval binding | `core/assignment_executor.py::_prepare_effect` hashes the exact payload; `backend/api/assignment_routes.py::approve_assignment_step` checks run/step/operation/payload/artifact/authorization bindings before approval |
| Operation identity | `core/task_lifecycle.py` binds an idempotency key and `operation_binding_sha256`; an outbound operation always has a key |
| Provider reconciliation | `TaskLifecycle.reconcile_outbound` maps `sent` → applied, `not_sent` → failed, `unknown` → explicit uncertain without blind retry |
| Outcome fields | `provider_state`, `provider_ref`, `sent_record_confirmed`, `delivery_confirmed` are separate in executor projections |

## Local engineering now implemented

The successor adds the last local send-boundary control:

- staged attachments carry a SHA-256 in their durable record;
- assignment planning refuses attachment ids without an exact hash map;
- the approval payload includes the attachment hash map, so a changed
  attachment invalidates the existing approval;
- `EmailCanvasService.send_email` re-hashes the bytes actually resolved and
  blocks before provider transport on a mismatch;
- the existing payload/artifact/authorization revisions, operation binding,
  pre-effect vs uncertain-effect classification, reconciliation and
  no-duplicate controls remain in force.

Local tests cover the hash binding, planner refusal, approval-payload change
and pre-transport block. No real transport is attempted.

## Sender identity and permissions — verified presence-only

- Authenticated mailbox: `rish@brennan.ca` (`Rish Maniar`), established via a
  read-only `/me` check during the authorized research qualification.
- Delegated scopes include `Mail.Send` and `Mail.ReadWrite`; the refreshed
  access token is valid until `2026-10-30T13:04Z`. `Mail.ReadWrite` covers the
  Sent Items read needed for receipt reconciliation.
- Existing code path: `OutlookService.list_emails(folder="sentitems")` and
  `get_latest_conversation_message_id` read Sent Items; the send path uses
  delegated `/me/sendMail`.

## Minimal owner inputs

Only three inputs are still needed:

1. Confirm sender `rish@brennan.ca` is the intended mailbox.
2. Supply one approved recipient address.
3. Supply the send window start/end.

The receipt and reconciliation mechanism is proposed below; the owner does not
need to design it.

## Proposed receipt and reconciliation policy

- **Receipt:** after provider acceptance, read Graph Sent Items and match the
  exact `internetMessageId` (or provider message id), subject, recipient and
  attachment SHA-256. Record the Sent Items message id, conversation id and
  sent timestamp.
- **Provider acceptance vs delivery:** a 2xx `/me/sendMail` or Sent Items match
  proves provider acceptance, not recipient delivery. `delivery_confirmed`
  stays false without independent recipient evidence.
- **Ambiguous outcome:** if the transport times out or the response is
  uncertain, do not resend. Perform up to three read-only Sent Items checks
  over a 10-minute window. If the exact message appears, reconcile as applied;
  if not, leave the operation `uncertain` and stop for owner review.
- **Restart/no-duplicate:** the operation binding and idempotency key prevent a
  second send; after restart, verify the operation status, provider reference
  and attachment hash before any further action.
- **Data handling:** the test message and attachment remain in Sent Items; the
  evidence record contains ids/hashes, not credentials or message bodies beyond
  the approved payload.

Drafting permission is **not** send permission. Approval of a draft is **not**
approval of a real provider send.

## Qualification stages (after separate authorization)

1. **Read-only preflight** — verify account identity, `Mail.Send` scope
   presence, draft-only gate still active, and provider policy. No send.
2. **Controlled transport twin** — run the exact payload through the existing
   controlled outbox/operation binding. Verify payload hash, approval
   invalidation after a body/recipient/attachment change, idempotent replay,
   and no duplicate operation.
3. **One real-provider send** — in an isolated runtime only, disable the
   release gate for that run, approve the exact bound payload, send once to the
   approved recipient, and capture Graph acceptance (2xx / provider reference).
4. **Uncertain outcome control** — with a disposable controlled adapter,
   simulate timeout after request dispatch. The operation must remain
   `unknown`/uncertain, must not be retried blindly, and must be reconciled
   against Sent Items before any retry decision.
5. **Restart/no-duplicate** — restart the isolated backend after the send.
   The applied operation, provider reference and artifact/hash must agree; no
   second send may occur.
6. **Classification** — provider acceptance is not recipient delivery. Report
   `provider_accepted`, `sent_record_confirmed` and `delivery_confirmed`
   separately. Do not claim delivery without independent evidence.

## Explicit stop conditions

- missing/expired `Mail.Send` or account mismatch;
- any payload/recipient/attachment change after approval without reapproval;
- provider timeout before effect vs uncertain after effect not distinguished;
- any attempt to retry an uncertain operation without reconciliation;
- any second send or duplicate operation after restart;
- any real send outside the exact approved payload/window.

No credential is changed by this plan. No real transport is attempted here.

## Observed qualification result

- Sender `rish@brennan.ca`; recipient `rish.maniar@gmail.com`.
- Exact approval payload SHA-256 `4a91227a3bf1f896f807d1118e3ea5218318b7aa31d24e1dc8248bcc9bd3bf66`.
- Provider accepted at `2026-10-30T12:13:30Z`.
- Exact Sent Items message `<YQBPR0101MB47483FC0A197D506B4D7F1C1AC6D2@YQBPR0101MB4748.CANPRD01.PROD.OUTLOOK.COM>`;
  attachment SHA-256 `7b736fb16ca66f9a84a9d41dad49d7d0470d5b904aa3504ddc5a67ee257ff1f6` matched.
- Restart: one sent message before/after, no duplicate; operation applied.
- `delivery_confirmed` remains false; provider acceptance/Sent Items is not
  recipient delivery.
- Evidence: `docs/acceptance/evidence/durable_assignment_20261030/successor-package-fda4f2dc9/send-qualification/`.
