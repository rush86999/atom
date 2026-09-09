# Pre-Training Checklist — Before You Train an Agent

> **Purpose**: The operational "what to verify BEFORE you run a supervised
> training loop on an agent" checklist. The research *rationale* for these
> items lives in [AGENT_HARNESS_RESEARCH.md](../architecture/AGENT_HARNESS_RESEARCH.md)
> (deterministic guardrails §1, sandboxed + verified execution §5, earned
> autonomy / apprenticeship loop §8); this doc is the *execution* checklist.
> **Audience**: anyone starting a training loop (supervisor, admin, agent dev)
> **Read time**: ~5 minutes

---

## Why this checklist exists

Atom's training model is an **apprenticeship loop**, not a prompt-editing
session: the agent starts STUDENT, proposes, a human approves/denies, and the
agent's scope widens only as **verified** clean episodes accumulate
(10 → INTERN, 25 → SUPERVISED, 50 → AUTONOMOUS — see
[AGENT_MATURITY_GOVERNANCE.md](../guides/AGENT_MATURITY_GOVERNANCE.md)).

If the underlying wiring is broken (mailbox not reachable, LLM key dead,
draft tool errors, send path double-fires), every "training run" produces
**unverified garbage episodes** — the agent looks busy, learns nothing, and
its confidence/graduation counters drift on noise. This checklist closes that
gap: run it once before the first supervised task, and re-run any section
whose environment changed.

> ⚠️ **Training happens in the mailbox/provider drafts, not in code.** A
> "training run" that never touches the real provider surface (Drafts folder,
> live search) does not produce the verified episodes graduation requires.

---

## Phase 0 — Environment (run once per install)

| # | Check | How | Pass = |
|---|-------|-----|--------|
| 0.1 | Dev DB is the one you think it is | `backend/.env` → `DATABASE_URL` | Matches the running store (`atom_dev.db`), not a 0-byte default (`backend/data/atom.db`) |
| 0.2 | Server runs current code | `curl http://127.0.0.1:8000/api/health` → 200 **after a restart** (the API server does NOT `--reload`) | 200 on latest commit |
| 0.3 | Working LLM credential | key in `backend/.env`; verify live (`/auth/key` or a chat call) | 200 / real completion |
| 0.4 | Dead credentials don't burn the ranking cascade | blank out dead keys (`OPENCODE_API_KEY=` etc.) | logs show the working provider picked first |
| 0.5 | Provider connectivity | integration_tokens / oauth_tokens row present + not expired | token refresh path returns a token |

**Email agent example (verified 2026-09-09):** `backend/.env` carries a
working `OPENROUTER_API_KEY`; `OPENCODE_API_KEY` is blank (its key was dead
and every structured step burned the fallback cascade first); Outlook OAuth
token exists for the demo user.

## Phase 1 — The tool surface actually works (boundary = provider, not mock)

> Test at the real boundary the agent will touch. A mocked "draft saved" in a
> unit test does not prove the mailbox Drafts folder received anything.

| # | Check | How | Email-agent example |
|---|-------|-----|---------------------|
| 1.1 | Read path | Run the search tool the agent uses, on the live provider | `search_emails(platform="outlook", query=...)` returns the target thread |
| 1.2 | Draft path **never sends** | Create a threaded draft, then inspect the provider | Draft appears in **Drafts**; **Sent Items untouched** (Graph: use `createReply`, never `/reply` — `/reply` is a SEND) |
| 1.3 | Send path fires exactly once | If a real send is ever part of the loop, send to a scratch/own address first | One Sent Items row per send; no empty shells |
| 1.4 | Approval gate engages | Trigger the action the agent will propose | HITL action row `status=pending`; agent pauses with `requires approval` |
| 1.5 | Approve → resume works | Approve the pending action | Agent resumes and the draft/send completes |

## Phase 2 — Agent wiring

| # | Check | How | Pass = |
|---|-------|-----|--------|
| 2.1 | Agent exists at the intended tier | registry row | STUDENT (read-only + draft-with-approval) is the safe default for a new hire |
| 2.2 | Capabilities match the plan | `agent.capabilities` | Only the tools training exercises (e.g. `search_emails`, `draft_response`) |
| 2.3 | Tier floor does not silently block the loop | `resolve_allowed_tools` / sandbox policy | STUDENT can *draft* (proposal-gated) but cannot *send* — see `core/sandbox_policy.py` |
| 2.4 | Lessons/taught rules are actually injected | run a task; inspect the system/ReAct context | Rule block appears on the live task surface (see `core/student_learning_service.format_lessons_block`) |

## Phase 3 — Rules & guardrails

| # | Check | How | Note |
|---|-------|-----|------|
| 3.1 | Rules are few, bounded, imperative | review lesson log | ≤5, ~1.6k chars max block — bounded memory beats a wall of instructions |
| 3.2 | Human-gated writes only | lessons/changes originate from teach/feedback | Lessons are PERMANENT INSTRUCTIONS at every tier — poisoning must stay human-gated |
| 3.3 | Deterministic gate for the non-negotiables | code gate, not prompt (research §1) | Level-B rules (same-thread, price-verified, alternatives…) should be enforced by a **code gate** at the send/draft boundary, not trusted to the model |
| 3.4 | Kill switch + audit on any gate | flag + log, shadow-first | every policy layer in this repo ships `ATOM_*_ENABLED` + audit rows |

**Email-agent status (2026-09-09):** Level-A lessons stored + injected ✓;
Level-B code gate (`core/email_policy_gate.py` + DB-backed rules) is
implemented on a **separate branch, not merged to main** — until merged, the
business rules are prompt-level only.

## Phase 4 — The first supervised task

| # | Check | How | Pass = |
|---|-------|-----|--------|
| 4.1 | Task pinned to a real record | supervisor picks an ingested/existing thread | task references a real message id |
| 4.2 | Agent searches → finds → proposes | watch the run | search hits the record; proposal carries correct params (message_id/thread_id) |
| 4.3 | Human reviews and responds | approve/reject with feedback | the outcome is recorded, not ignored |
| 4.4 | Outcome is verified | execution row `outcome_verified=true` | oracle/postcondition pass, not self-report |
| 4.5 | Episode recorded | episode row for the run | graduation counters advance on **clean** episodes only |

---

## Known failure modes (learned the hard way)

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Agent repeats the same draft 3× | tool returns an error the model can't see past | Fix the tool (Phase 1), don't blame the model — each retry burns tokens and noise episodes |
| "All structured providers failed" | dead keys in the ranking cascade, or a retry handler that never fires | Phase 0.4 + check the byok recovery chain |
| Draft "created" but Drafts folder empty / email in Sent Items | wrong Graph action (`/reply` sends) | use `createReply` (Phase 1.2) |
| Agent stuck at STUDENT | no *verified* clean episodes | approve good proposals, reject bad ones — that IS the training data |
| Graduation not happening | `outcome_verified=false` rows | ensure the postcondition oracle ran (Phase 4.4) |

---

## Related documentation

- [AGENT_HARNESS_RESEARCH.md](../architecture/AGENT_HARNESS_RESEARCH.md) — why these checks exist (research survey)
- [AGENT_MATURITY_GOVERNANCE.md](../guides/AGENT_MATURITY_GOVERNANCE.md) — tier system + graduation
- [agents/training.md](training.md) — Student training system implementation
- [agents/graduation.md](graduation.md) — promotion criteria
- [TRUST_CALIBRATION_PLAN.md](../architecture/TRUST_CALIBRATION_PLAN.md) — system-side trust calibration over approve/deny streams

*First written 2026-09-09 from the live email-agent training session (search 400
fix, LLM retry-handler fix, `/reply`-sends incident → createReply).*
