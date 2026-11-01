# Agent 2 portability matrix

Base: `587fbc251`. This matrix is a controlled design/acceptance record, not a
claim that three live businesses have been qualified. Brennan is the reference
industrial-sales fixture. The same registered capabilities are selected through
configuration; no domain name, customer, price, account, folder or currency is
embedded in the engine.

## Canonical action names

Use the `connected.*` names below in new plans. `brennan.*` remains as an alias
for plans created during the reference campaign. The implementation module is
`core/connected_actions.py`; `core/brennan_connected_actions.py` is a
compatibility shim for the reference campaign.

| Capability | Canonical action | Optional provider |
|---|---|---|
| Drive page read/index/checkpoint | `connected.workdrive.sync_page`, `connected.onedrive.sync_page` | either drive |
| File evidence read | `connected.workdrive.read_file`, `connected.onedrive.read_file` | either drive |
| Sync coverage/status | `connected.knowledge.sync_status` | either drive |
| CRM identity read/search | `connected.crm.get_record`, `connected.crm.search_records` | yes |
| Inventory item/stock observation | `connected.inventory.get_item`, `connected.inventory.check_stock` | yes |
| Supplier/customer resolution | `connected.books.resolve_vendor` | no (Books) |
| Chart-of-accounts mapping | `connected.books.list_accounts` | no (Books) |
| Quote/bill proposal | `connected.books.propose_bill` | no (Books) |
| Authorized provider write | `connected.books.create_bill`, `connected.books.create_estimate` | no (Books) |
| Outlook draft (never send) | `connected.outlook.create_draft` | yes |

## Domain configurations

| Business shape | Knowledge sources | Identity / product evidence | Financial output | Configuration only |
|---|---|---|---|---|
| Industrial sales (Brennan reference) | WorkDrive price lists, agreements, quote/order history; OneDrive procedures | CRM account/contact/deal; Inventory SKU, unit, pack, observed stock | Books estimate/bill, freight, tax, discount rules | Folder/drive IDs, CRM module names, inventory org, Books org, CoA IDs, currency, tax/freight teaching |
| Professional services | OneDrive/WorkDrive SOWs, rate cards, engagement letters | CRM contact/account; no inventory required | Books estimate/bill for services; disbursements; no stock reservation | Service catalog rows, rate cards, account IDs, currency, tax treatment |
| Non-sales / procurement | OneDrive/WorkDrive policies, supplier contracts | Supplier identity from Books vendors; CRM optional | Books supplier bill, credit note, approval evidence | Vendor list, CoA, approval policy, period bounds; inventory absent |

## What stays data or teaching

- Customer/vendor identities and exact provider IDs.
- Prices, discounts, freight, tax, currency, units/packs and validity.
- Folder/drive/site/library selections and which file is the governing version.
- Account/tax mappings and accounting-period authority.
- Which providers are installed. A missing CRM, Inventory or Outlook integration
  does not block local-only work or the remaining actions.

## Controlled evidence in the Agent 2 branch

- The same estimate action posts the Brennan fixture
  (`A 2x100`, `B 3x50` less 5% on B, freight 20, no tax) and reads back
  `362.50`.
- The same proposal/create path accepts a services fixture (professional fees
  and disbursements, CAD, no inventory, no tax) through
  `connected.books.propose_bill` with different data only.
- Optional-provider actions are independent registrations; a plan that omits
  Inventory/CRM still runs the Books and Outlook actions it names.
- Provider names (`zoho_workdrive`, `onedrive`, `zoho_books`) are adapter
  identities, not business vocabulary.

## Remaining portability proof

One additional domain still needs an end-to-end run through the normal
UI/public routes (not only the action registry). The drive status/page routes
are already public (`/api/document-ingestion/integrations/{id}/sync-status` and
`/sync-page`); the quote/bookkeeping route surface remains Agent 1's employee
workflow. Until that run is recorded, this matrix is a controlled design and
unit-level portability control, not a live multi-business qualification.
