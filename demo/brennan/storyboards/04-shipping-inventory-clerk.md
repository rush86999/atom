# Video 4 — Shipping & Inventory Clerk

**Length:** ~2:00 · **Role:** "Your AI Shipping & Inventory Clerk" · **Apps:** Zoho Inventory, Shopify, Outlook, Telegram

## Hook (0:00–0:10)
> "This shop never oversells a machine that's out of stock — and always knows when to reorder."

## Setup shot (0:10–0:20)
Zoho Inventory shows: press brake stock = 1 (at reorder point), laser cutter = 2.

## The command (0:20–0:30)
> "Sync press-brake stock to Shopify and tell me on Telegram if anything's low."

## Live execution (0:30–1:40)
Atom on Canvas:
1. **Fetch inventory** — reads Zoho Inventory levels for all brennan products.
2. **Sync to Shopify** — updates the "available" quantity on each Shopify product
   listing so the website is accurate (no overselling).
3. **Low-stock alert** — sends a Telegram message:
   > "⚠️ Low stock: AccurPress 50-Ton Press Brake (1 left, reorder point 1). Reorder?"
4. **Parse shipping email** — finds a shipping confirmation email in Outlook,
   extracts the tracking number, and updates the relevant Zoho order (the Outlook
   lifecycle learner ingests order # + tracking # + vendor into the knowledge graph).

**Memory beat:** Live inventory levels + reorder thresholds are now in memory. When
the owner asks "what needs reordering?", Atom answers from current data.

## Result (1:40–2:00)
- Shopify product pages show updated stock.
- Telegram low-stock alert on screen.
- End card: "Stock synced to the website, reorder alert sent — the clerk never sleeps."
