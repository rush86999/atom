# Brennan connected-business engineering work orders

Date: November 1, 2026. Common inspected base: `587fbc25148a6203f3785c46e56992ddcf54bd70`.

These are implementation orders, not claims that the workflows already pass.
The accepted 111/123 feature milestone remains source-bound. These orders add
business-process acceptance without changing its denominator or historical evidence.

## Mandatory domain independence

Read the [domain-independent product contract](../DOMAIN_INDEPENDENCE.md).
Brennan is the initial reference deployment. Business knowledge, rules, identities
and workflow configuration must remain data/teaching; provider-specific behavior
stays in adapters. Both agents must prove portability across other businesses
without changing core code or requiring Brennan's providers.

## Assignments

- [Agent 1: employee knowledge, quotes and durable execution](AGENT_1_EMPLOYEE_WORKFLOWS.md)
- [Agent 2: Zoho/Microsoft ingestion, bookkeeping and writeback](AGENT_2_CONNECTED_OPERATIONS.md)

WorkDrive and OneDrive are the initial business knowledgebases. Outlook provides
requests/conversations; Zoho CRM provides customer/deal identity; Zoho Inventory
provides product/unit/availability; Zoho Books provides accounting/commercial records.
Explicit SharePoint libraries are supported only when their site/drive identity
is handled. Other applications follow demonstrated business needs.

## Collaboration contract

Use separate `codex/` branches/worktrees from the same agreed commit. Agent 1
owns assignment planning/execution, teaching, retrieval selection and employee UI.
Agent 2 owns provider adapters, sync/ingestion, accounting and accounting UI.
Agent 2 is the default editor for action registrations; Agent 1 owns executor
consumption. Name one editor before changing shared models, credential handling,
binding schemas or migrations. Exchange small contract fixtures before integration.
Record ownership and handoffs in the coordinator's shared coordination note;
do not rely on divergent gitignored notes in separate worktrees.

Reuse [action registry](../../../backend/core/action_registry.py),
[task lifecycle](../../../backend/core/task_lifecycle.py),
[resource bindings](../../../backend/core/assignment_resources.py),
[assignment executor](../../../backend/core/assignment_executor.py) and the existing
catalog/teaching stores. No second job engine, knowledge store, permission engine
or independent provider retry loop.

### Boundary data

Extend existing envelopes where needed; these are required semantics, not a new
parallel serialization framework.

| Boundary | Required information |
|---|---|
| Read | Provider, connection/account/org/workspace; resource/object ID; version; retrieved/verified time; typed fields/units; evidence location; coverage; continuation; access outcome |
| Proposed effect | Registered action; target and allowed fields; expected remote version; complete payload digest; attachment hashes; authority reference; stable logical operation ID; cost/time bounds |
| Effect result | Applied, proven-not-applied, uncertain, conflict or unavailable; remote object ID; provider receipt; authoritative readback and reconciliation evidence |

A filename is not identity; a search result is not a fact; HTTP success is not
proof of the intended remote state. Secrets remain inside the credential resolver.
Provider-returned text cannot expand permissions or become teaching automatically.

## Working rules

1. Reproduce concrete failures before repair; trace callers and parallel adapters.
2. Implement a thin controlled vertical slice, then extend the same mechanisms.
3. Continue through tests and integration. Do not pause after fixtures, plans,
   manifests or isolated component passes while assigned work remains executable.
4. Start elapsed campaigns early and perform other useful work while they wait.
5. Batch genuine missing owner inputs into one concrete request. Continue offline
   implementation while live qualification is unavailable.
6. General action authority must be explicit and bounded. Routine covered work
   can execute; ambiguity clarifies, uncovered effects propose, invalid authority
   refuses, and possibly performed effects reconcile without blind resend.
7. Previous one-use Outlook qualification does not authorize another send.
   Do not infer permission for new provider reads, refreshes or writes from this plan.
8. Never connect tests to the live database. Use scratch DB/artifact/memory roots,
   both LanceDB variables, storage guard preflight, owned ports and health identities.
   Never create a replacement worlds root to bypass a missing external volume.

## Integration sequence and acceptance

1. Agent 2 supplies scoped WorkDrive/OneDrive read receipts; Agent 1 consumes them
   for unfamiliar questions with citations and explicit gaps.
2. Integrate one Outlook RFQ → governed sources → quote → permitted Zoho record
   → Outlook draft journey.
3. Integrate invoice → bookkeeping proposal → permitted Books operation → readback.
4. Inject external changes, revocation, crashes, duplicate events and cancellation.
5. Verifier reviews one integrated source/configuration and complete business outputs.

Keep controlled, provider-sandbox and authorized live evidence separate. A blocked
live account does not turn a controlled result into live qualification.

## Submission requirements

Each agent submits scoped commits, exact commands/source/configuration, known
baseline failures, positive and negative controls, independent expected arithmetic,
tracked sanitized evidence and which earlier tests require repetition.
The joint submission includes the user journey, selected source receipts, lesson
revisions, operation IDs, artifacts, remote readbacks and restart agreement.
Do not update marketing/acceptance status until independent verification.

Provider work must consult current official documentation and record the relevant
references in commits. Useful established patterns include
[Graph change tracking](https://learn.microsoft.com/en-us/graph/delta-query-overview)
and [durable effect idempotency](https://docs.aws.amazon.com/durable-execution/patterns/best-practices/idempotency/).
These patterns guide existing mechanisms; they do not require adding another engine.
