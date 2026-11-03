# Normal-app controlled provider-lost-confirmation recovery — 9f3c3b8dd

Agent 2 support evidence for the integrated G5 campaign. This runs the real
application backend (`main_api_app`) on a fresh scratch SQLite/LanceDB world
with normal admin bootstrap, normal login and the ordinary upload/assignment
APIs. The environment-gated controlled outbox accepts one local effect, loses
the confirmation, the backend is restarted, the original operation is
reconciled against the outbox, and the assignment completes with exactly one
effect. No live provider was contacted.

## Checks — 11/11

| Check | Observed |
|---|---|
| Normal upload creates authorized document | yes |
| Outbound effect awaits approval | `awaiting_approval` |
| Provider accepted then lost confirmation | `uncertain` |
| Assignment blocked, not complete | `blocked` |
| Exactly one controlled effect | 1 |
| Uncertain operation survives restart | same operation id |
| No second effect after restart | 1 |
| Original operation reconciles applied | `applied` |
| Reconciled assignment completes | `completed` |
| No resend after reconciliation | 1 |
| Original operation identity retained | same id |

The report records the scratch world, serving identity before/after restart,
operation id, outbox hash and durable assignment/outcome records.

## Scope

This is API-level normal-application support for the controlled effect, not
the browser UI journey. The quote/invoice UI campaign, same-job source answer,
waiting restart and artifact remain with the product owner. No new provider,
credential, send, spend or deployment authority. Historical 111/123 unchanged.
