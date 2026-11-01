# Domain- and business-independent product contract

This is mandatory for both [connected-business work orders](brennan/README.md).
Brennan is a reference deployment and acceptance dataset, not the application
architecture. Zoho and Microsoft 365 are initial adapter targets, not required
providers for every installation. This contract defines acceptance requirements;
it does not claim arbitrary business understanding has already been proven.

## Separation of responsibilities

| Layer | Belongs here | Must not be embedded here |
|---|---|---|
| Shared engine | Objectives, typed inputs/evidence, dependencies, teaching resolution, obligations, budgets, permissions, durable execution, effects/reconciliation | Company names, named customer rules, fixed price sheets, specific mailbox IDs, presumed business currency |
| Reusable capabilities | Supported calculations, document composition, retrieval, financial validation, entity matching | A company's private policy presented as a universal default |
| Provider adapters | Zoho/Microsoft API contracts, scopes, paging, versions and response mapping | Employee intent selection or a provider-specific duplicate task engine |
| Installation data and teaching | Organizational identity, connected folders, field mappings, units, governing-source policy, pricing/tax/account mappings, exceptions, document formats | Executable model-generated code or implicit permission expansion |
| Fixtures | Brennan examples and independent business scenarios | Production defaults or private customer data |

A different company using supported capabilities must onboard through data,
connections, editable teaching and explicit authority. It must not require a core
code edit, a new company-name branch or a developer-authored Python plan.
A genuinely new capability may require engineering; implement it once as a reusable
registered capability and document its supported contract.

## Agent 1 requirements

- Derive information requirements from the objective and applicable teaching;
  do not assume every job has a SKU, customer, quantity or price.
- Keep quote/accounting profiles as compositions of generic capabilities.
  A quote is one deliverable type, not the only shape of employee work.
- Resolve aliases and units from authorized schemas/teaching. Do not build
  Brennan-specific regexes or silently normalize distinct identifiers together.
- Support different contextual keys and exception structures through the existing
  context mechanism. Avoid fixed customer/qualification requirements for all jobs.
- Keep dependency scheduling, waiting, invalidation, budget accounting and
  authorization independent of business vocabulary and provider selection.
- Never infer currency, jurisdiction, fiscal rules, margin or source precedence
  from the example business. Require evidence or accepted teaching.

## Agent 2 requirements

- Provider/account/org/site/library identities come from the authenticated
  connection and configuration, never hardcoded source identities.
- Map provider records into typed evidence without dropping raw field identity,
  unit, version or provenance. Do not turn every app record into an invoice or
  every document into a spreadsheet.
- Preserve adapter interchangeability: generic reads and action consumption must
  not depend on a private Zoho object ID or a Microsoft-only storage convention.
- Keep provider permissions separate from business lessons and source content.
- Support local uploaded sources without requiring Zoho/Microsoft login. A
  disconnected optional provider must not prevent unrelated local work.

## Required portability acceptance

Use the same product build and executor for these scenarios. Fixtures must have
independent expected outputs and run in separate owned stores.

1. **Industrial sales:** RFQ, products/packs, customer agreement, quote and
   permitted business-record update; Brennan is the first instance.
2. **Service business:** time/rate or service-line calculation, different source
   names/columns/context, service proposal and an allowed record update.
3. **Non-sales work:** grant/expense policy assessment or reconciliation using
   different subjects, rules and output structure.

At least one additional scenario must run through the normal UI/public routes,
not just an internal helper. Test a previously unseen schema using only normal
onboarding and teaching. Record the exact lesson/evidence references consumed.
No source-code edit is allowed between domains in a portability campaign.

### Discriminating controls

- Rename the company, customer, documents and columns; behavior follows identity,
  schema and teaching, not fixture keywords.
- Change domain context; previous-domain teaching is excluded.
- Use explicit different currencies/units; keep them distinct, and clarify when
  conversion or missing units are not authorized.
- Repeat external IDs across organizations; no cross-business association.
- Present similarly named sources with different governing authority; resolve
  by accepted policy or clarify.
- Disconnect the reference providers; supported uploaded-data work still runs.
- Repeat restart, correction and duplicate-effect controls in a second domain.

## Definition of done and review

Agent 1 owns business-profile portability and shared execution/teaching tests.
Agent 2 owns provider-neutral receipts, connection scope and optional-provider
behavior. Both submit one portability matrix naming configuration-only changes,
exact sources/build, positive/negative results and limitations.

The verifier rejects solutions that pass Brennan fixtures by hardcoding those
fixtures. Do not replace that failure with another sample-specific branch.
Historical evidence and the 111/123 inventory remain unchanged. Cross-domain
success supports bounded portability, not universal reliability for every industry.
