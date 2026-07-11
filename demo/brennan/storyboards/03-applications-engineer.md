# Video 3 — Applications Engineer

**Length:** ~2:30 · **Role:** "Your AI Applications Engineer" · **Apps:** Outlook, Telegram, Excel, WorkDrive/OneDrive

## Hook (0:00–0:10)
> "When a customer asks a technical question this shop can't answer, the AI routes it to the vendor — and replies for them."

## Setup shot (0:10–0:20)
Telegram message from **ACME Fab**:
> "Can the SigmaMax fiber laser cut 20mm steel reliably?"

## The command (0:20–0:30)
> "ACME's asking if the laser cutter handles 20mm steel. Check with the vendor and reply."

## Live execution (0:30–2:00)
Atom on Canvas:
1. **Recall** — identifies the product (SigmaMax 2kW Fiber Laser) and its vendor
   (SigmaMax Manufacturing, via the knowledge graph `supplies` relationship).
2. **Draft to vendor** — emails James @ SigmaMax:
   > "Customer asks: does the 2kW fiber laser reliably cut 20mm mild steel?"
3. **Vendor reply simulation** — (or real) vendor reply: "Yes, 20mm mild steel is
   within spec — up to 20mm MS, 12mm SS."
4. **Reply to lead** — composes the answer back to ACME Fab via Telegram/Outlook.
5. **Update PriceList** — if the vendor mentions a price change, updates
   `/PriceList/C5` (SigmaMax row) in `PriceList.xlsx` via `write_excel_cell`.

**Memory beat:** The vendor's spec answer + any pricing is now in memory. Next time
anyone asks about the laser's capacity, Atom recalls it instantly — no re-emailing.

## Result (2:00–2:30)
- Telegram reply to ACME with the answer.
- Updated PriceList.xlsx on Canvas.
- End card: "The AI routed the question, got the answer, and replied — and remembered it."
