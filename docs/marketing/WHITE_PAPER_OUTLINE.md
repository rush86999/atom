# Atom — "Governance & Trust" White Paper (outline)

> Purpose: the marketing artifact that converts the repo's security/engineering depth into
> buyer evidence. ~90% of the raw material already exists in docs — this outline maps each
> section to its source files so assembly is copy-editing, not writing.
>
> Format: 8–12 pages PDF + HTML landing mirror. Tone: institutional crisis → mechanism →
> receipts. Audience: ops/IT leads + CISO-adjacent buyers mid-pilot-graveyard.

---

## Working title

*"Why 88% of Agent Pilots Die — and the Engineering Decisions Designed to Keep the Rest Alive"*

> Note: title expresses Atom's design intent, not claimed deployment outcomes (we have no
> deployment data). External stats cited in the paper, sourced to `RESEARCH_NOTES.md`.

## Section map

### 1. The trust gap (the hook) — *new, short, sourced*
- 88% never reach production (Turion), 21% mature governance (Deloitte 2026), 55.4% cite
  reliability as top challenge (Futurum), The Economist "lie, cheat, cut corners" (Aug 2026)
- The real failure taxonomy: not capability — *accountability*: unverifiable runs,
  unbounded blast radius, audit that stops at "the model said it worked"

### 2. Why self-report is not verification — `docs/architecture/ORACLE_VERIFICATION.md`, `core/oracle/`
- Tri-state outcomes (PASS/FAIL/AMBIGUOUS), EXTERNAL_VERIFIED-only graduation
- `verify_before_retry` vs dual-execution bug; timeout ambiguity handling

### 3. Earned autonomy: the maturity ladder — `docs/agents/governance.md`, `docs/agents/graduation.md`
- STUDENT → INTERN → SUPERVISED → AUTONOMOUS; 10/25/50 verified episodes
- Training, supervision, proposals (4-tier routing) — `docs/agents/training.md`
- What the tier is NOT: routing, not security (hard boundary → section 4)

### 4. Deterministic blast-radius: the sandbox layer — `docs/architecture/SANDBOX_LAYER.md`, `docs/security/TRUST_VS_SANDBOX.md`
- 5 phases: policy → FS scope → tripwires/caps/KillRun → Firecracker/E2B runtime + egress
  proxy → provenance + LLM ActionJudge
- Default-on across ALL dispatch paths (P9) via `sandbox_gate.evaluate_tool_call`
- Multi-layered defense elsewhere: capability bindings, data taint (restricted-data exfil
  blocking), outbound gatekeeper, match-confidence, self-consistency voter

### 5. Privacy by architecture — `docs/security/DATA_PROTECTION.md`, `docs/operations/personal-edition.md`
- Local-first embedded store; BYOK encrypted at rest (Fernet); DIDs/VCs zero-trust federation
- EU AI Act (Aug 2026) mapping table — `docs/compliance/COMPLIANCE_MAPPING.md`
- Why "we delete your prompts after 30 days" is not a privacy model

### 6. The compounding loop — `docs/intelligence/episodic-memory.md`, `docs/architecture/LEARNING_LLM_ROUTER.md`
- Verified episodes → memory (citations) → better routing (~90% cost reduction) → more autonomy
- The feedback loop is the moat: data that improves the product only through verified usage

### 7. Receipts — from repo + `/health/metrics`
> All repo-measured or repo-documented; no invented data. Re-verify "85k+ tests" badge
> count before publishing.
- 0.027ms P99 governance · 616k ops/s cache · 95% hit rate (repo benchmark table)
- 69+ documented TDD hardening rounds; deep security sweep (R18–31) fixed ~1,100 bugs
- 486-test E2E suite; mypy-gated core suite
- Readiness: `/health/{live,ready,metrics}`; audit trail emission points

### 8. Decision checklist for buyers (the actionable close)
- How to evaluate an agent platform: verification independence, blast-radius determinism,
  key ownership, cost shape at scale, path out of HITL-forever (graduation exists?)
- Appendix: comparison grid (Zapier/Make/n8n/Lindy/OpenClaw vs Atom) per `POSITIONING.md §6`

## Assembly plan
1. Copy section 2–6 openings from source docs (they're already well-written)
2. Write new: §1 hook, §7 receipts page, §8 checklist
3. Design: receipts as data-dense tables; one diagram (maturity ladder + sandbox phases)
   — reuse `docs/architecture/SANDBOX_LAYER.md` assets
4. Distribute: landing mirror + PDF · gate behind email capture or free link (test both)

## Related follow-ups (once whitepaper ships)
- "Reliability receipts" feature: one-click exportable governance report per agent run
- `Autonomy report card` in UI: maturity score + verified/failed ratio
- Public `/about/reliability` page with live /health/metrics numbers