# Tool Planner Routing & Evidence Stack

How a chat turn decides WHICH service to query, WHAT evidence leads the
reply, and what keeps each decision honest. Shaped by the canvas
`a1a13834` incident family (Sep 13–15, 2026): a pasted vendor line
("$ 5,350.00 - 10 % in stock") was routed to the inventory app, its
lookup 400-aborted on a value-length cap, the reply narrated a timeout
that never happened, and five follow-up turns each exposed the next
layer. Full incident history: `AGENT_COORDINATION.md` (root), commits
`924b70792` → `1dafa9b5c`.

Design rule (repo standard): **deterministic layers extract and gate;
the LLM decides.** Extractors (`_distinctive_figure_phrases`,
`_product_tokens`, `_stated_date_window`, the provenance menu) are
fast, unit-pinned, and fail safe — a miss leaves prior behavior
untouched. The LLM layers (tool planner, repair passes, action
planner) make the actual choices, and deterministic floors correct
them only when evidence contradicts the choice.

## 1. Planner inputs — nothing decides blind

`core/chat_tool_planner.plan_tool_use(message, history, user_id,
llm_service, canvas=None, provenance="")`:

- **Canvas block** (`_planner_canvas_block`): type, title,
  participants and a hard-capped body head (`ATOM_PLANNER_CANVAS_CHARS`,
  default 700). "this one" / "the draft" resolve against what is on
  screen. Without it a question about an OPEN email was planned into a
  record app.
- **Provenance menu** (`_provenance_menu`, ≤6s, best-effort): before
  planning, the message's distinctive tokens are probed against the
  workspace's OWN ingested stores — mail containment (figures, then
  quoted phrases) and the dataset catalog. The menu states what store
  already HOLDS the content, with hedged no-match semantics ("not found
  by this check" never "not ingested").
- **TODAY line**: the planner resolves relative dates against it and
  returns `ToolPlan.mentioned_date` (see §4) — no extra LLM call.
- **History transcript**: user turns only (assistant refusal walls
  biased the planner; documented in `_history_transcript`).

## 2. Routing rules — whose data, not keyword overlap

- **WHOSE data** (prompt rule): record apps (inventory, books, CRM)
  hold YOUR OWN company's state; mailboxes and memory hold messages
  OTHERS sent. A price, discount, "in stock" or lead time inside a
  message is the SENDER's claim — plan the message lookup.
- **Pasted/quoted text is mail**: a verbatim quoted line is a stored
  message, even when it contains "stock".
- **Value lookups without a named source** go to `datasets`; the
  identifier net (`_context_identifier_net`, `skip_pathlike=True` for
  item searches — URL paths are not catalog codes) appends codes the
  draft query dropped.
- **Provenance floor**: quote-lookup shape + verbatim mail provenance +
  a live record-app plan → one repair pass → deterministic memory rung.
  Narrow by construction: a genuine own-stock question trips neither
  condition (`TestProvenanceFloor`).
- **Action gate**: `plan_canvas_action` returns None before any LLM
  spend unless the message carries a send verb in imperative/present
  voice (`_ACTION_IMPERATIVE_RE`) — past-tense narration ("the thread
  chandrakant forwarded") and noun uses ("the email thread") can never
  become send proposals.

## 3. Evidence — where content verifiably lives leads

`integrations.chat_orchestrator._verbatim_mail_evidence` runs
independently of the planner's choice (concurrently with fresh lookups,
and as an overlay on singleflight-reuse turns — canvas turns included).
Resolution order, each leg gated and fault-isolated:

1. Distinctive figures (amounts, model codes) — separator-insensitive
   matcher, own-text tier (the amount at the top of a body outranks
   quoters), html-body pass for styled-only mail.
2. Quoted phrases — verbatim containment ("put 25 percent only").
3. Participant names — matched against the store's OWN sender/recipient
   strings (role aliases excluded; communication-referent gated; ranked
   by topic overlap).
4. Inherited figure (the previous turn's amount) — LAST, so an old
   figure never hijacks a new question.

`_compose_lookup_evidence` renders the block: participant-referent and
quote-lookup asks are MAIL-LED with full bodies ("answer from them;
never report a result count"); the live block is the trailing note.

**Stated dates tier matches** (`_stated_date_window` +
`_match_rows_by_figure_tokens(date_window=...)`): "sent 9/11 friday"
parses to day bounds (M/D only with a day-word context — "7/8-inch"
never becomes July 8; weekdays = most recent past; future M/D = last
year) and in-window matches form the leading tier. The window comes
from the current message (regex) or the planner's `mentioned_date`
(piggyback — see §4), because the query rewrite keeps codes but drops
dates. 17 F-5216 matches fought over 3 slots; the date tier is why the
Sep 11 pair surfaces.

**Provider search ladders** (`core.identifier_search.run_search_ladder`):
value-level 4xx (e.g. Zoho's 100-char `search_text` cap, code 15,
validated before auth) skip the rung; transport/auth/rate-limit/5xx
fail fast. Hyphenated codes tokenize whole; values are capped to the
provider's limits (`_cap_search_value`).

## 4. mentioned_date piggyback

`ToolPlan.mentioned_date` (optional, lenient validator: ISO kept,
`9/11/2026` and bare `9/11` coerced — future bare M/D reads as last
year, prose dropped) covers the messy relative expressions the regex
cannot ("end of last month", "two Tuesdays ago") at ZERO extra LLM
calls — the planner reads the same message. Window precedence:
message regex > plan field > recency. Reaching plan-less paths:
the fresh branch passes `plan.mentioned_date` directly; the reuse
branch reads it from the DONE shared plan task (instant); the memory
lane reads it from the execution context (stashed by
`execute_tool_plan`).

## 5. Reply-leg survival

- `ATOM_CHAT_TURN_BUDGET_SECONDS` (95) bounds the whole reply leg.
- `ATOM_STREAM_FALLBACK_RESERVE_SECONDS` (40; dev .env uses 55): the
  primary stream's slice is the remaining budget minus the reserve —
  a reasoning model that ends with zero visible chunks
  (finish_reason=length) cannot consume the fallback's window.
- On a zero-visible stream the non-streaming fallback PINS
  `model=` to the next-ranked model instead of re-rolling the failed
  one. Visibility: log lines "reuse-branch mailbox overlay: N evidence
  line(s)" and "non-streaming fallback pinned to next-ranked model M"
  — if either is missing from a turn trace, that chain is broken.

## 6. Testing conventions

- Extractor fakes must accept the current signatures
  (`_search_ingested_by_tokens(..., date_window=None)`,
  `_match_rows_by_figure_tokens(..., date_window=None)`) — a stale
  fake raises inside fault-isolated legs and silently degrades to other
  lanes (leaking live-store rows into assertions).
- New detector shapes: pin both directions (what fires AND a realistic
  non-fire — "is WG-350DSAV in stock?" for the floor, "7/8-inch" for
  the date parser).
- Test batteries: `tests/test_verbatim_evidence_generalization.py`,
  `tests/test_planner_natural_routing.py`,
  `tests/test_chat_tool_planner_figure_tokens.py`,
  `tests/test_canvas_editor_grounding.py`,
  `tests/test_explicit_web_research_floor.py`,
  `tests/test_identifier_search.py`,
  `tests/test_zoho_inventory_search.py`.
