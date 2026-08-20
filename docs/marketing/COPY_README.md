# Atom — Marketing Copy Kit (v1)

> Working copy for homepage, README top, landing sections, and comparison messaging.
> **Truth contract:** every claim must trace to `docs/marketing/RESEARCH_NOTES.md`
> (external stats) or `CLAUDE.md`/`docs/` (repo facts). Nothing here is data about
> Atom's *own* deployments or users — we have none to cite. Placeholders `[...]` must be
> filled with verified numbers before publishing; do not ship copy containing them.

---

## 1. Taglines

- **"Autonomy, earned."** ← lead candidate
- "The agent platform that can prove what it did."
- "Your business, automated. Your data, yours. Your agents, governed."
- "AI that graduates before it acts."
- "Trust, by default."
- "Agents that earn their autonomy — and can't lose what they never had."

## 2. Elevator pitch (7 seconds)

> Atom is an open-source agent platform where **autonomy is earned, not assumed**. Agents
> start as supervised interns, graduate only after **verified** outcomes, and run every
> action inside a deterministic sandbox — on your hardware, with your keys. Built for the
> 88% of agent pilots that never make it to production.

## 3. Hero (website)

**H1 options:**
- [A/B 1] **"The agent platform that can prove what it did."**
- [A/B 2] **"88% of AI agent pilots never reach production. *Atom is built for the other path.*"** ← stat + honest framing, no unverifiable survival claim
- [A/B 3] **"Autonomy, earned. Safety, deterministic. Data, yours."**

**Subhead:**
> Atom is an open-source agent platform where agents earn their permissions through
> verified outcomes, every action runs inside a default-on safety sandbox, and your data
> stays on your hardware. Trade the approval-fatigue of yesterday's tools for autonomy
> you can actually answer for.

**Hero proof strip (under CTA) — all values from `CLAUDE.md` perf table / `docs/operations/performance.md`:**
> 0.027ms P99 governance checks · independent outcome verification · local-first by default · no credit meters

**CTAs:**
- Primary: "Deploy in 10 minutes" → quick start
- Secondary: "Read the trust model" → white paper

## 4. The three value props (homepage cards)

### 1. Agents that earn trust
> Permissions grow with verified track records — not confidence and not promises.
> Every mutating action is re-derived against your system of record by an independent
> oracle. An agent that says "done" is checked, not believed. Intervene, approve, or hand
> over entirely — the platform scales the human out as the record scales the risk in.

### 2. A safety net, not a windshield
> Every tool call passes a deterministic sandbox gate: filesystem scope, tool whitelist,
> resource caps, tripwires, egress allowlist, and a kill switch. A prompt-injected agent
> at any tier acts at that tier's *scoped* blast radius — bounded by design, not by hope.
> Shadow mode → enforce mode, on your schedule.

### 3. Local-first by default
> Embedded vector store. Private memory. Keys encrypted at rest on your machine. Full
> Ollama / local-model tier for fully private deployments. No "trust us, we delete it" —
> it never leaves. (EU AI Act data-governance obligations, designed for, Aug 2026.)

## 5. The "we're serious" section (receipts)

> **We publish our receipts.** *(Each line maps to `POSITIONING.md` §8 — repo-measured or repo-documented. No invented numbers.)*
> - 0.027ms P99 per-agent governance checks, 616k ops/s cached throughput — repo benchmark table
> - Outcome-verified graduation: agents advance at 10 / 25 / 50 verified episodes — `docs/agents/graduation.md`
> - 69+ documented rounds of TDD hardening; the deep security sweep (rounds 18–31) alone fixed ~1,100 bugs
> - 85k+ tests (repo CI badge — verify current count before publishing) · 486-test E2E UI suite
> - 16+ LLM providers with cost-aware routing; ~90% cost reduction via caching tiers (repo-documented claim)

## 6. Comparison messaging

**Section headline:**
> Everyone sells approval gates. We sell a system that outgrows them.

| You need | Zapier / Make | n8n | Lindy | OpenClaw | **Atom** |
|---|---|---|---|---|---|
| Agents that reason, not just steps | ⚠️ bolted-on | ⚠️ DIY | ✅ | ✅ | ✅ |
| Verified outcomes, not self-report | ❌ | ❌ | ❌ | ❌ | ✅ oracle, default-on |
| Blast radius bounded on every tool call | ❌ | ⚠️ your config | ❌ | ❌ | ✅ sandbox, default-on |
| Autonomy that grows with a track record | ❌ | ❌ | ⚠️ gates only | ❌ | ✅ maturity tiers |
| Local-first / private by default | ❌ | self-host viable | ❌ | ✅ | ✅ embedded, default |
| Predictable cost at scale | ❌ credit meters | ✅ | ❌ credit meters | ✅ | ✅ caching tiers + local |

**One-liners (anti-comparison):**
- vs Zapier/Make: *"They automate steps. Atom governs outcomes."*
- vs n8n: *"n8n gives you control. Atom gives you governance."*
- vs Lindy: *"Approval gates are a feature. A maturity system is an operating model."*
- vs OpenClaw: *"Local-first is necessary. It's not sufficient — you also need to be accountable."*
- vs ChatGPT agents: *"A great model is a great employee with no supervisor. Atom is the supervisor."*

## 7. Landing page section: The 88% problem

> **Why 88% of agent pilots die** — and the 6 engineering decisions built to prevent it.
> *(Honest frame: these are design decisions in Atom's architecture, not claims about Atom
> deployments — we have no deployment data to cite.)*
>
> Pilot graveyards share the same obituary: agents that can't be verified, can't be sandboxed,
> and can't be audited. Atom was built in reverse: every action attributable, every outcome
> re-verified against the system of record, every failure recoverable with an audit trail.
> The result isn't a smarter model — it's a deployable one.
>
> 1. **Trust is earned** — maturity tiers + verified graduation (no self-report)
> 2. **Failure is contained** — deterministic sandbox (FS scope, caps, tripwires, kill-run)
> 3. **Accountability is instant** — every action auditable, replayable, attributable
> 4. **Costs are bounded** — caching tiers, cheap subscription gateways, free local models
> 5. **Privacy is architectural** — local-first, encrypted keys, no training on your data
> 6. **Humans scale out safely** — human-on-the-loop: approve the risky 5%, not everything

## 8. Social proof / story arc — TEMPLATE (no invented data)

> ⚠️ Do not publish until real pilot data exists. Fill `[...]` from actual deployments.

> "[Customer]'s agent went from STUDENT to AUTONOMOUS in [...] weeks — [...] verified
> episodes, [...] unauthorized actions (0), [...]% cost reduction vs. the previous
> [tool], and our CISO signed off because the audit trail writes itself."
>
> — [Name, Title], [Company] *(needs written permission + verification)*

## 9. Feature-rename pass (dev-facing language → selling language)

| Before (technical) | After (marketing) |
|---|---|
| Maturity tiers / graduation | "Agents that graduate before they act" |
| Sandbox gate (P9 default-on) | "A safety net on every tool call" |
| Postcondition oracle | "Verified outcomes, not self-reported success" |
| Episodic memory + GraphRAG | "Memory that compounds — with citations" |
| Learning LLM router | "Every run makes the next run cheaper" |
| BYOK crypto (Fernet at rest) | "Your keys, encrypted, on your machine" |
| Local-first embedded store | "Your data never leaves the building" |
| 0.027ms governance check | "Governance too fast to feel" |

## 10. FAQ copy (objection handling)

- **"Can't I do this in ChatGPT?"** — A model is capability. Atom is capability *plus* accountability: verification, sandboxing, audit, graduation. "Can GPT send that invoice?" Yes. "Can you prove it was correct, roll it back, and show the trail?" No.
- **"Is full autonomy safe?"** — We don't sell blind autonomy. We sell *earned* autonomy: supervised start, verified graduation, deterministic blast-radius bounds. Human-on-the-loop, not human-out-of-the-loop.
- **"Why self-host?"** — Your workflow data, memory, and keys are the crown jewels. EU AI Act (Aug 2026) makes "data cannot leave the building" a compliance requirement, not a preference.
- **"How is this different from n8n + an LLM node?"** — n8n gives you control; you build the governance. Atom ships governance as the product: maturity, verification, sandbox, audit — default-on, everywhere.