# Agent 2 — Zoho/Microsoft knowledge ingestion, bookkeeping and writeback

Read the [shared work order](README.md) first. Base: public integration `587fbc251`.

## Mandatory product constraint

Implement the [domain-independent contract](../DOMAIN_INDEPENDENCE.md).
Brennan supplies initial data and acceptance workflows, not hardcoded engine
behavior. Your submission must include your assigned cross-business portability
controls and identify configuration-only changes between businesses.

## Product mission

Make WorkDrive and OneDrive dependable business knowledgebases, supply Agent 1
with trustworthy customer/product evidence, and complete a Zoho Books bookkeeping
loop. The business must see correct remote state, not only local success messages.
Prioritize Zoho and Microsoft 365; broader provider work follows proven needs.

## Ownership and existing mechanisms

| Area | Files to trace and extend |
|---|---|
| Provider contract | [integration_registry.py](../../../backend/core/integration_registry.py), [universal_integration_service.py](../../../backend/integrations/universal_integration_service.py), [action_registry.py](../../../backend/core/action_registry.py) |
| Reads/cache | [read_query.py](../../../backend/integrations/read_query.py), [read_cache.py](../../../backend/integrations/read_cache.py) |
| Catalog/materialization | [app_dataset_sync.py](../../../backend/core/app_dataset_sync.py), [drive_tree_ingestion.py](../../../backend/core/drive_tree_ingestion.py) |
| Knowledge providers | [zoho_workdrive_service.py](../../../backend/integrations/zoho_workdrive_service.py), [onedrive_service.py](../../../backend/integrations/onedrive_service.py) |
| Business providers | [zoho_crm_service.py](../../../backend/integrations/zoho_crm_service.py), [zoho_inventory_service.py](../../../backend/integrations/zoho_inventory_service.py), [zoho_books_service.py](../../../backend/integrations/zoho_books_service.py) |
| Microsoft | [outlook_service.py](../../../backend/integrations/outlook_service.py), [microsoft365_service.py](../../../backend/integrations/microsoft365_service.py) |
| Accounting | [sync_manager.py](../../../backend/accounting/sync_manager.py), [ledger.py](../../../backend/accounting/ledger.py), [document_processor.py](../../../backend/accounting/document_processor.py), [reconciliation.py](../../../backend/accounting/reconciliation.py) |

Agent 1 owns job execution/teaching and relevant-evidence selection. Coordinate
shared schema/credential changes; do not create another job or retry engine.

## Milestone A — audit actual capabilities, then repair contracts

Build provider×object×action matrix from resolved classes, not catalog labels:
constructability, argument schema, authenticated scope, effect class, pagination,
return shape, cost bound, unsupported behavior and remote verification method.

Turn these source-inspection risks into reproductions before changing behavior:
- Books advertises/implements operations inconsistently across capability lists,
  execute_operation and universal dispatch. Generic invoice reads may name absent
  methods. An implemented create_invoice is not proof of estimate/bill support.
- CRM create_record dispatch passes one dictionary while the implementation
  requires module and data arguments.
- Some Books reads return [] after errors, confusing unavailable with empty.
- Audit generic Zoho token selection for user/workspace/organization binding.
- Honor per-connection Zoho data-center/API domain during refresh and requests;
  do not assume every account uses the same region.
- A Microsoft /me/drive wrapper does not qualify explicit SharePoint libraries.
- File content may be binary; JSON-only response handling is not a download.

Check current official provider docs for required operations and record references.
Fix general dispatch/schema handling rather than teaching the model to avoid bugs.

## Milestone B — WorkDrive/OneDrive knowledgebase

Use authorized folder selections for pricing, agreements, procedures, quote/order
history and supplier documents. Identify real connection, owner, org/site, drive,
folder and item IDs before ingesting. Same-name files remain distinct resources.

Expose discovery/import/index states, last verification time, counts and failures
in normal UI. A successful file listing does not mean documents are searchable.

Pipeline: provider read → durable original/version receipt → existing extractor →
typed catalog/materialization → existing search index → task-consumable reference.
Keep original identity, content hash, provider version, modified time, representation,
coverage and provenance. Handle spreadsheet rows/formulas differently from prose.

Implement restart-safe paging/checkpoints and incremental change tracking where
supported. Checkpoint durable ingestion progress; recover partial extraction/index
work without inventing all-or-nothing success. Use existing sync state/scheduler.
Deletions/tombstones and revocation must affect retrieval and cache authorization;
audit retention is distinct from permission to consume retained content.

### Required ingestion controls

- Multiple pages with duplicated boundary records; exact expected final set.
- Crash after page import before checkpoint; restart without omission/duplication.
- Repeated import, modification, rename/move and deletion.
- Same filename in two folders/providers, same external ID in two organizations.
- Wrong workspace/org/site/library and revoked grant.
- Expired token resolution versus genuinely revoked authority.
- Corrupt/encrypted/unsupported file and index outage: explicit partial/unavailable.
- Source version change invalidating task-time binding.

Follow the existing storage guard before new worlds. Set both LANCEDB_URI and
LANCEDB_URI_BASE plus DB/artifact paths to owned scratch storage. Never seed fake
catalog rows to replace missing genuine connected qualification.

## Milestone C — business read/write actions for Agent 1

Supply registered reads for CRM customers/contacts/deals, Inventory items/units/
observed stock, and governing files. Resolve the intended quote object with Agent 1:
Books estimate versus CRM quote. Use one canonical record and link its external ID.
Implement missing required actions with exact schemas; reject unsupported ones.

Stock observation must include location/time and must not reserve stock. Invoice
creation, quote creation and payment execution are distinct permissions.

For writes, propagate the existing logical operation ID. Bind account/org, target,
allowed fields, expected version, complete prepared payload digest and authority.
Use provider conditional versions where available; read-then-unconditional-write
is not atomic optimistic concurrency. If safe update semantics are unavailable,
limit the supported action explicitly rather than asserting protection.

Persist receipt/object identity and perform authoritative readback. Remote success
with a lost local confirmation is uncertain; reconcile the existing operation.
No adapter-owned automatic retry may bypass the shared effect arbiter.

### Effect controls

| Fault | Expected result |
|---|---|
| Wrong target/org, changed payload, expired/revoked grant | Zero provider effect |
| Changed remote version | Conflict, no overwrite |
| Concurrent same operation | One logical effect |
| Acceptance followed by connection loss | Uncertain, no blind resend |
| Restart before/after dispatch | Correct claim recovery and current-authority check |
| Readback disagrees | Remains unverified/conflicted; never false completion |
| Proven no-effect outcome | A new authorized attempt may be prepared |

## Milestone D — bookkeeping through Zoho Books

Implement one complete supplier-document workflow:
Outlook invoice/receipt → extraction → vendor resolution → duplicate detection →
account/tax mapping → reconciliation → proposed bill/entries → authorized Books
operation → readback. Use the same evidence/operation infrastructure as quotes.

Financial requirements:
- Decimal from original strings or integer minor units; explicit scale/currency.
- Validate line totals, tax, document total and applicable rounding policy.
- Unknown date/currency/vendor stays unresolved. Never default missing facts to
  today or USD merely because a model/constructor has defaults.
- Stable dedupe identity includes provider, organization, entity type and external
  ID; document duplicate identity also needs source evidence. Avoid substring matching.
- An invoice is not proof of payment. Support partial payment, fees and credit
  notes with their correct semantics.
- Validate accounting period, account references and balanced entries before posting.
- Preserve original document, extracted fields, corrections and posting evidence.
- Learned classification is not authority to pay, void, delete or close a period.

Inspect sync_manager's float conversion, fallback dates, JSON substring duplicate
checks and logged-but-ignored indexing errors. Repair semantics with realistic tests.
Reuse existing teaching for accounting mappings; do not invent a parallel lesson store.

Start in a controlled/sandbox organization. Test repeated invoices, same-name
vendors, currency/date gaps, decimal edge cases, credits, partial payments, bank
fees, statement mismatch, closed period and changed remote records. The expected
ledger and provider objects must be independently calculated and read back.

## Autonomy, external boundaries and completion

Deterministic covered drafts/updates can execute under a current bounded grant.
Exceptions clarify; uncovered effects propose. Payments and destructive actions
must have their own explicit authority. Teaching and connector consent alone do
not provide unlimited action permission.

Complete controlled work first. Identify required live account/org/folder/actions,
exact fixture/payload, effect bounds, verification and reconciliation scope in one
reviewable request. Do not spend time on another provider to conceal an inaccessible
Zoho source; report that boundary and continue unaffected work.

Deliver one connected-read handoff early so Agent 1 need not wait for all finance
work. Final submission proves knowledge discovery/ingest/retrieval, the quote
record/update, bookkeeping proposal/posting, authoritative readback and restart
without duplication. Separate controlled, sandbox and live evidence; no registration
count or mocked HTTP success upgrades a business claim. Independent verifier
acceptance remains required.
