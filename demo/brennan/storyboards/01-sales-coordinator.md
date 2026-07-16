# Video 1 — Sales Coordinator

**Length:** ~2:30 · **Role:** "Your AI Sales Coordinator" · **Apps:** Outlook, Zoho Books, Word, OneDrive/WorkDrive, Telegram

## Hook (0:00–0:10)
> "This is how a small fabrication shop turns an emailed inquiry into a professional quote — without typing a single line."

## Setup shot (0:10–0:20)
Show the Outlook inbox with an email from **Sarah Chen @ ACME Fabrication**:
> "Hi — we need a quote on the 50-ton AccurPress press brake. Budget around $80K, delivery within 8 weeks. — Sarah"

## The command (0:20–0:30)
Type/speak to Atom:
> "ACME Fab asked for a quote on the 50-ton press brake. Create a quote and email it."

## Live execution (0:30–2:00)
Atom (on Canvas) shows each step as it runs:
1. **Recall** — finds ACME Fab in memory (seeded contact), recalls budget + timeline.
2. **Template** — pulls `Quote.docx` from OneDrive/WorkDrive, opens it on the Canvas.
3. **Fill** — uses `modify_word_document` to replace:
   - `<<CLIENT_NAME>>` → ACME Fabrication Inc.
   - `<<PRODUCT_DESCRIPTION>>` → AccurPress 50-Ton CNC Press Brake
   - `<<UNIT_PRICE>>` → $84,500.00
   - `<<QUOTE_NUMBER>>` → Q-2024-0142
   - `<<QUOTE_DATE>>` → today
   - `<<TOTAL>>` → $84,500.00
4. **Email** — sends via Outlook to sarah.chen@acmefab.com.
5. **Follow-up** — schedules a Telegram nudge in 3 days.

**Memory beat (the "wow"):** Highlight that the quote line items are now in Atom's
memory — the next time ACME Fab is mentioned, Atom recalls the exact quote.

## Result (2:00–2:30)
- Show the sent email in Outlook.
- Show the filled quote on the Canvas.
- End card: "Atom remembered the quote, the budget, and the 8-week deadline."
