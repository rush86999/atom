# Real-provider send qualification — prepared, not authorized

Status: **plan prepared; no transport call, credential change or recipient
invention.** The frozen release remains draft-and-approval only
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

## Required owner inputs — still missing

1. **Sending account**: exact mailbox/UPN and tenant; confirmation that it is
   the account whose delegated grant will be used.
2. **Permission**: current `Mail.Send` delegated grant on that account, or a
   separately reviewed application-permission design. The existing code uses
   delegated `/me/sendMail`; a missing scope is refused, not widened.
3. **Test recipient**: one owner-approved external recipient address. Do not
   use a real customer or an invented address.
4. **Exact payload approval**: subject, body (verbatim), attachment file(s),
   attachment SHA-256, and whether the attachment is the rendered artifact.
5. **Approver identity and window**: who may approve the exact payload and the
   bounded test window.
6. **Provider receipt source**: how the owner will expose the Sent Items /
   Graph message id for reconciliation.
7. **Reconciliation window**: how long to wait before classifying an ambiguous
   transport result, and who decides a retry.
8. **Data handling**: whether the test message/attachment may remain in the
   mailbox and where the evidence is stored.

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
