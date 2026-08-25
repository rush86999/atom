# Atom — Launch & Community Posts (drafts)

> Posting order: **Show HN** first (security/engineering story), then Reddit adapts.
> Titles are the highest-leverage copy on earth — variants included.
>
> **Timing**: publish Mon–Tue morning ET. GitHub evaluation activity peaks on Tuesday
> (168k star events) and drops 33% by Saturday — evaluation is a workday activity
> (FruitfulCode/LeadCognition 2026, n=5.04M events; sourced in `RESEARCH_NOTES.md`).

---

## 1. Show HN (target: front page)

**Title options:**
- `Show HN: Atom – an agent platform where autonomy is earned, not assumed (verified outcomes + sandbox)`
- `Show HN: Atom – I built the agent platform for the 88% of pilots that die (0.027ms governance)`
- `Show HN: Atom – agents that graduate before they act (Rust-style borrow checker for agent permissions)` ← if engineering angle

**Body:**

> tl;dr — [atom](https://github.com/rush86999/atom) is an open-source, self-hosted agent
> platform. The twist: agents don't get permissions because a prompt sounded confident.
> They earn them through **verified** outcomes.
>
> Most agent platforms trust the model's self-report: "tool succeeded ✅". Ours re-derives
> success against the system of record with an independent postcondition oracle
> (`ATOM_ORACLE_VERIFIER_ENABLED`), and splits confidence into self-reported vs
> EXTERNAL_VERIFIED. Graduation from STUDENT → INTERN → SUPERVISED → AUTONOMOUS only
> happens at 10/25/50 verified episodes. Unverified runs can't inflate.
>
> The other half is blast radius. Every tool call — agent loop, workflow, fleet, business
> agents — passes a deterministic sandbox gate: filesystem scope, tool whitelist,
> tripwires, resource caps, kill-run, egress allowlist, provenance tagging. Our own
> security docs put it plainly: the maturity tier is routing, not security — the sandbox
> is where the security lives (`docs/security/TRUST_VS_SANDBOX.md`). The July 2026
> Anthropic CTF incident is why capability ≠ safety. (External facts sourced in
> `docs/marketing/RESEARCH_NOTES.md`; HN comments can challenge anything.)
>
> If you're vending/auditing agents in 2026, you're working through the OWASP ASI Top 10
> (Dec 2025). We mapped all 10 risks onto concrete repo mechanisms — match-confidence,
> oracle verification, capability bindings, sandbox phases, verified-episode graduation,
> provenance — in `docs/marketing/POSITIONING.md#8`. The soundbite: we don't sell the
> agent-security checklist as a subscription dashboard; it ships in our code.
>
> **Numbers we publish (each repo-measured or externally sourced, see RESEARCH_NOTES.md):**
> - 0.027ms P99 per-agent governance checks, 616k ops/s cache throughput (repo benchmark table)
> - 69+ documented TDD hardening rounds; deep security sweep (R18–31) fixed ~1,100 bugs
> - 486-test E2E UI suite (533 statically counted, Aug 2026); 85k+ test functions repo-wide (84,737 across 2,759 files — verify at post time via `rg "def test_" backend/tests/ | wc -l`)
> - ~90% LLM cost reduction via caching tiers + learning router (repo-documented); free fully-local Ollama tier
> - Local-first: embedded LanceDB + SQLite, keys encrypted at rest (Fernet), telemetry opt-in only (SENTRY_DSN)
>
> **Why we built it:** 88% of agent pilots never reach production (Turion 2026); only 21%
> of orgs have mature agent governance (Deloitte 2026). Capability is commoditized;
> *accountability* is the moat. We make no claims about Atom's own deployment outcomes —
> we invite you to run the receipts yourself.
>
> Stack: Python 3.11/FastAPI, SQLAlchemy 2.0, multi-provider LLM routing, Playwright,
> Firecracker/E2B runtime option, GraphRAG memory. AGPLv3, no closed-source "pro" build.
>
> Docs: [README](https://github.com/rush86999/atom) · [trust model](docs/marketing/COPY_README.md) · [sandbox deep-dive](docs/architecture/SANDBOX_LAYER.md)
>
> Happy to go deep on the oracle/verification design, the sandbox phases, or the
> graduation math — AMA in the comments.

**Anticipate in comments:**
- "Why not LangGraph/CrewAI?" → frameworks, not products: no governance, no sandbox, no audit; you build the supervision. Atom's P9 gate covers all dispatch paths.
- "Why not n8n self-host?" → n8n gives control; you build the governance. Atom ships governance default-on with outcome verification.
- "AGPL?" → full features in the OSS build; commercial = same code on your infra.

## 2. Reddit — r/selfhosted

**Title:** `Atom – self-hosted AI agent platform where agents earn autonomy via verified outcomes (not self-report)`

**Body (abridged, link-friendly):**

> We built a self-hosted agent platform where trust is structural, not vibes:
> - Local-first by default: embedded LanceDB + SQLite, no cloud account required, telemetry opt-in only
> - Full Ollama / local-model tier — fully private deployments, zero API bills possible
> - Agents graduate (STUDENT→AUTONOMOUS) only after 10/25/50 **verified** episodes
> - Every tool call sandboxed: FS scope, tool whitelist, caps, tripwires, kill-run
> - Outcome verification: re-derives success against your system of record, not self-report
> - 16+ LLM providers + a ~90%-cheaper subscription gateway; caching tiers
> - AGPLv3, no paid-gated features; commercial = same code on your own infra
>
> r/LocalLLaMA's self-hosting reasons are ours too: privacy AND vendor lock-in avoidance
> (sources in `docs/marketing/RESEARCH_NOTES.md`). Happy to answer deployment questions —
> Docker Compose or daemon mode.

## 3. Reddit — r/AI_Agents (technical)

**Title:** `Postcondition oracle: how we stopped trusting agent self-report (and gates every action with a sandbox)`

**Body:**

> Pattern: instead of trusting the tool's "success" flag, we re-derive success against the
> DB/API of record after the fact (tri-state: PASS / FAIL / AMBIGUOUS). Only
> EXTERNAL_VERIFIED counts toward graduation. `verify_before_retry` prevents duplicate side
> effects on ambiguous timeouts — the classic "Did my tool run?" double-execution bug.
>
> Plus a deterministic blast-radius layer (5 phases: policy → FS scope → tripwires/caps/
> kill-run → Firecracker/E2B runtime + egress proxy → provenance + LLM ActionJudge), all
> default-on since P9 across every dispatch path.
>
> Incidentally, this is the same defense surface the OWASP ASI Top 10 (Dec 2025) asks for
> — we've mapped all 10 risks to repo mechanisms in `POSITIONING.md#8` (goal hijack →
> match-confidence, memory poisoning → verified graduation, rogue agents → kill-run, …).
>
> Questions welcome on failure taxonomy, latency budgets (verification must never eat the
> p99 budget), and what regressions the oracle catches that evals miss.

## 4. Reddit — r/smallbusiness or r/automation (outcome-focused)

**Title:** `We spent 69 rounds making agents that don't blow up your invoices — the 88% problem, productized`

**Body:**

> 88% of agent pilots never reach production. The survivors share one thing: somebody
> could answer "who's accountable?" → audit trails, approval gates on the risky 5% (not
> everything), reversible actions, budget caps. From inside a product team that designed
> for exactly that: what a governed agent could look like day-to-day, and the 6 decisions
> we built in to prevent the same failures (see [the 88% problem writeup →](docs/marketing/COPY_README.md#7)).
> No deployment claims here — full source + docs, you can verify every mechanism.