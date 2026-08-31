# Agent Journey — Round 87 Implementation Summary

**Date**: August 28, 2026
**Status**: ✅ Complete — implemented, tested, verified live
**Scope**: Training completion integrity, agent persona chat, learned-context introspection, file-mention grounding, mini-canvas lifecycle, voice opt-in, session-expiry redirect

---

## Overview

Round 87 hardens the hire journey end-to-end. The through-line: **every
surface tells the truth** — training completion cites recorded work, the
chat persona is the hire (not the platform), "what have you learned?"
answers from the real ontology, a mentioned file is checked against the
actual ingested store, and nothing speaks or acts without an explicit user
gesture.

> Related: Round 86 introduced the multi-signal promotion gate
> (≥3 completed sessions, ≥10 outcome-tracked episodes, ≥0.7 success ratio —
> env-tunable, dynamically tuned per domain). Round 87 closes the loophole
> that made those signals gameable. See [training.md](training.md).

---

## 1. Linked-Evidence Training Completion

`complete_training_session` no longer trusts the supervisor's claimed score
or task counts:

- **Evidence window**: `approve_training()` stamps `session.started_at`;
  evidence = `AgentEpisode` rows the agent recorded after that moment.
- **Floor**: fewer than `ATOM_TRAINING_MIN_EVIDENCE_EPISODES` (default 3)
  recorded runs → `InsufficientTrainingEvidenceError` → HTTP **422** with
  live counts. Nothing mutates on rejection.
- **Score cap**: recorded `performance_score` =
  `min(supervisor claim, evidence success ratio)`; task counts come from the
  ledger; claimed values preserved in `session.outcomes` for audit.
- **Kill switch**: `ATOM_TRAINING_REQUIRE_EVIDENCE=0` restores legacy behavior.
- **New endpoint**: `GET /api/maturity/training/sessions/{id}/evidence` —
  live counts for UIs.
- **Panel**: `MaturityApprovalPanel` shows the evidence counts and keeps
  "Mark completed" disabled until the floor is met; the fabricated
  score input and hardcoded 10/10 tasks are gone.

Details: [training.md](training.md#round-87-2026-08-28-linked-evidence-completion) ·
Tests: `backend/tests/test_promotion_evidence_gate.py`,
`backend/tests/unit/test_student_training_service.py`

---

## 2. Agent Persona Chat (hires speak as themselves)

`ChatOrchestrator._get_qwen_response` previously used a single hardcoded
"You are ATOM…" system prompt. When a chat carries an `agent_id`, the
orchestrator now looks the hire up in `AgentRegistry`
(`_lookup_agent`) and swaps in an employee persona: name, category, and the
role description written at hire time — always first-person as the employee,
never "Atom"/"an AI assistant" — with maturity-tier behavior (student/intern:
honest about unknowns, drafts over final actions, flags supervisor approvals).
Platform agents (`atom_main`, system/Meta) keep the platform persona
(`_is_platform_agent`).

The new-session greeting in `useChatInterface` is agent-aware too
("Hello! I'm {name}, your {category} hire…"), and the chat page renders an
identity bar (`data-testid="chat-agent-identity"`) with the hire's name,
category, and live maturity tier.

---

## 3. Learned-Context Introspection (ontology + relationships)

"what have you learned?" now answers from the graph, not vibes:

- **`_ontology_leg`** (`core/memory_context_assembler.py`): object types and
  counts from `graph_nodes`, live relationship types and counts from
  `graph_edges` (bi-temporal filter: `invalid_at IS NULL`), plus recent
  examples of each — surfaced as an "ONTOLOGY OBJECTS & RELATIONSHIPS" block.
- **`_INVENTORY_RE`** extended: ontology / relationships / knowledge graph /
  entities phrasings trigger inventory mode (ordinary questions keep the
  fast semantic-recall path).

---

## 4. File-Mention Grounding + Mini Canvas

Mention a file in chat ("check the acme_thread.txt data"):

- **`core/agent_file_context.py`** (new): filename detection
  (extension-based, token-fuzzy matching), lookup across the workspace's
  LanceDB stores (`documents`, `integration_*`), context-block and
  canvas-content builders.
- **`_file_mention_leg`** in the assembler injects a "MENTIONED FILE — DATA
  AVAILABILITY" block: found (records + real samples) or honestly not found
  (ingest-first guidance, no invented contents).
- **Mini canvas**: when data exists, `process_chat_message` creates a Canvas
  + CanvasAudit ("{file} — data preview", linked to session/agent/user) and
  broadcasts `canvas:update` on **both** the user and session WS channels so
  the chat pane and the expanded page both present it live.
- **Expand / return**: the mini canvas has an expand button (`⤢`) opening the
  full `/canvas/{id}` app in a new tab (CanvasPanel editing, version history,
  AI accessibility via `useCanvasStateRegistration`); the expanded page shows
  "Back to chat" and its side **agent chat panel continues the same session
  with the same agent** — so turns there are session-linked agent chats and
  record graduation episodes.

---

## 5. Email Canvas — Mini Send Wired

The mini canvas email Send button previously fired an `alert()` stub. It now
mirrors the full-page composer: confirm-first (the click is the policy
authorization), `POST /api/canvas/email/send`, honest success / policy-blocked
/ failure messaging. Policy, audit trail, and live broadcast semantics are
unchanged (see `api/canvas_email_routes.py`, `core/email_policy.py`).

---

## 6. Session-Expiry Redirect (raw-fetch parity)

The axios client's 401 interceptor had a raw-`fetch` blind spot. New shared
helper `handleSessionExpired()` (`lib/auth-headers.ts`): clear stored tokens,
redirect to `/login?callbackUrl=…`, no-op on auth pages. Wired into every
fetch call site on the agents page; available for other fetch-based pages.

---

## 7. Voice Strictly Opt-In

Two auto-speech paths removed:

- `AgentWorkflowGenerator` auto-read defaulted **on** — now defaults muted,
  persisted only after an explicit toggle (`atom_agent_autoread`).
- `VoiceModeOverlay` stayed mounted when closed and spoke every assistant
  message (including the history replay on page load) — the speech effect is
  now gated on `isOpen`.

Speech now requires an explicit gesture: the mic button (voice mode) or the
Voice On toggle (automations).

---

## Environment Knobs

| Knob | Default | Effect |
|------|---------|--------|
| `ATOM_TRAINING_REQUIRE_EVIDENCE` | `1` | `0` disables the linked-evidence completion floor |
| `ATOM_TRAINING_MIN_EVIDENCE_EPISODES` | `3` | Recorded runs required in the session window |
| `ATOM_PROMOTION_MIN_TRAINING_SESSIONS` | `3` | Round 86 promotion gate (unchanged) |
| `ATOM_PROMOTION_MIN_EPISODES` | `10` | Round 86 promotion gate (unchanged) |
| `ATOM_PROMOTION_MIN_SUCCESS_RATIO` | `0.7` | Round 86 promotion gate (unchanged) |

---

## Tests

- `backend/tests/test_promotion_evidence_gate.py` — 14 cases (incl. new:
  unevidenced completion rejected with no mutation, claimed score capped by
  evidence ratio, kill switch).
- `backend/tests/unit/test_student_training_service.py` — 24 cases
  (completion-mechanics tests now seed in-window evidence).
- `frontend-nextjs/components/chat/__tests__/CanvasHost.test.tsx` — email
  Send asserts the real policy-gated endpoint contract.
