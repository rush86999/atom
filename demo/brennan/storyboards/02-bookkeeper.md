# Video 2 — Bookkeeper

**Length:** ~2:30 · **Role:** "Your AI Bookkeeper" · **Apps:** Shopify, Zoho Books, Outlook, OneDrive/WorkDrive

## Hook (0:00–0:10)
> "When a website order closes, this shop's bookkeeping is already done — automatically."

## Setup shot (0:10–0:20)
Show the Shopify admin: order **#1001** just came in for a HyperCut Plasma Cutter, paid.

## The command (0:20–0:30)
> "Shopify order #1001 just closed. Invoice it in Zoho Books and email the PDF."

## Live execution (0:30–2:00)
Atom on Canvas:
1. **Fetch** — pulls order #1001 from Shopify (customer, line item, total).
2. **Create invoice** — creates the invoice in Zoho Books with matching line items.
3. **Generate PDF** — fills `Invoice.docx` template:
   - `<<CLIENT_NAME>>`, `<<INVOICE_NUMBER>>` → INV-2024-0301
   - `<<ORDER_ID>>` → #1001
   - `<<AMOUNT_DUE>>` → $18,900.00
4. **Email** — sends the invoice PDF to the customer via Outlook.
5. **Archive** — saves a copy to OneDrive/WorkDrive (Invoices/2024/).

**Memory beat:** Atom recalls ACME's payment terms and shipping data parsed from
earlier emails (the Outlook lifecycle learner ingested order #, tracking #, amounts).

## Result (2:00–2:30)
- Zoho Books shows the new invoice.
- Sent email with PDF attachment visible.
- End card: "Order to invoice to archive — the AI bookkeeper handled it all."
