# Atom — Research Notes (sources for external claims)

> Every external stat used in Atom marketing copy, with its source. If it's not here,
> it doesn't go in copy. Repo-internal claims are grounded in `CLAUDE.md` / `docs/`
> (see each file's own "Grounding" notes).
> Last updated: Aug 20, 2026 (added OWASP ASI Top 10 + NIST agent-standards sourcing).

## The 88% problem

- **88% of AI agent pilots never reach production; production survivors average 171% ROI (192% US).**
  Source: Turion, "State of AI Agents in Enterprise: Adoption Trends and Barriers in 2026"
  (Apr 22, 2026) — cites Gartner (40% of enterprise apps with task-specific agents by 2026),
  McKinsey State of AI 2025, IDC ($10.91B AI agents market 2026).
  https://turion.ai/blog/state-of-ai-agents-enterprise-adoption-2026/

## Governance gap

- **Only 21% of enterprises have a mature governance model for agents.**
  Source: Deloitte AI Institute 2026 State of AI report, as cited in MIT Technology Review,
  "Building agent-first governance and security" (Apr 21, 2026).
  https://www.technologyreview.com/2026/04/21/1136158/building-agent-first-governance-and-security/
- **Only 24.4% of orgs have full visibility into which agents communicate with each other; >50% of agents run without security oversight or logging.**
  Source: Gravitee 2026 State of AI Agent Security survey, cited in Turion (same article as above).
- **51% of enterprises run AI agents in production.** Source: Turion, same article.

## Reliability as the adoption blocker

- **"Agent reliability is now the adoption blocker, not capability" — The Economist (Aug 2026, paywalled) framing agents' "lying, cheating, and cutting corners" as the blocker; 146-point / 181-comment HN thread.**
  Source (secondary summary, verified framing only): Enterprise DNA AI Pulse (Aug 13, 2026).
  https://enterprisedna.co/resources/ai-pulse/ai-pulse-2026-08-13-the-economist-argues-agent-reliability-is-now-the-adoption-b/
  HN thread: https://news.ycombinator.com/item?id=49285604
- **55.4% of organizations (n=820) cite AI agent reliability and hallucination management as a top adoption challenge.**
  Source: Futurum Research data, in Futurum Group, "Agentic AI: LogicMonitor's Autonomous Platform" (Aug 2026).
  https://futurumgroup.com/insights/logicmonitors-ai-driven-approach-redefines-it-operations-management
- **Workers: 38.7% require human approval before AI makes changes; 33.9% need ability to roll back/undo AI actions.**
  Source: Recon analytics survey, cited in TechRepublic (Jul 10, 2026).
  https://www.techrepublic.com/sponsored/ai-adoption-trends-enterprise

## Security incidents / motivation

- **Anthropic: "Claude Mistook the Open Internet for a CTF and Breached Three Organizations" (Jul 2026).**
  Source: The Hacker News (Jul 2026) — used only as a news reference, never as evidence about Atom.
  https://thehackernews.com/2026/07/anthropic-says-claude-mistook-open.html
  HN: "Don't trust AI agents" (344 points) — https://news.ycombinator.com/item?id=47194611
- **Prompt-injected agent at any tier acts at that tier's full scope — tier is routing, not security.**
  Repo-internal: `CLAUDE.md` governance caution; `docs/security/TRUST_VS_SANDBOX.md`.

## Local-first / self-hosted trend

- **Self-hosted/local-first projects occupy 7 of the top 20 AI GitHub repos (was 1 two years ago).**
  Source: ByteByteGo "Top AI GitHub repositories in 2026", cited in paperclipped.de
  "Local-First AI Agents 2026" (Mar 24, 2026):
  https://www.paperclipped.de/en/blog/local-first-ai-agents-privacy
- **Vendor lock-in avoidance is the #2 self-hosting reason on r/LocalLLaMA (after privacy).**
  Source: paperclipped.de survey of r/LocalLLaMA power users (Feb 2026), same article.
- **OpenClaw: 180k–210k stars; EU AI Act data-governance/transparency provisions take effect Aug 2026.**
  Sources: paperclipped.de (same), serenitiesai.com (Feb 2026):
  https://serenitiesai.com/articles/self-hosted-ai-agents-openclaw-privacy-2026

## Competitive landscape (2026)

- **Agent platform market split into 4 layers (consumer / enterprise+governance / orchestration frameworks / vertical). Enterprise layer is sold on governance, not capability; "auditable, scopeable, accountable" is the pitch.**
  Source: FuturePicker, "2026 Agent Platform Landscape: The Four-Layer Split" (Jul 28, 2026).
  https://futurepicker.com/en/agent-platform-landscape-2026-2/
- **Vertical/harness moat: "The moat is the harness — curated tools + hard-won integrations, not the underlying LLM."**
  Source: Stanford, "Defensible Moats for Vertical AI Application Companies" (Jun 2026, Mandal & Sinha).
  https://law.stanford.edu/wp-content/uploads/2026/06/Defensible-Moats-for-Vertical-AI-Application-Companies-in-a-New-Competitive-Landscape.pdf
- **Model access is not a moat; workflow depth, proprietary feedback loops, distribution, trust, switching costs are. Data is only a moat if it improves product behavior.**
  Source: Valtorian, "AI Moats in 2026" (Mar 6, 2026).
  https://www.valtorian.com/blog/ai-moats-2026

## Team-size / cost dynamics (for comparison copy)

- **n8n self-hosted can be up to 1,000x cheaper than Zapier/Make at scale; Lindy/Zapier credit systems "get expensive at scale."**
  Sources: paperclipped.de (Feb 2026), aitoolkitpro.blog, "Best AI Agent Platforms 2026" (Jul 2026).
  https://www.paperclipped.de/en/blog/n8n-vs-make-vs-zapier-ai-automation
- Zapier ~7,000–8,000 integrations · Make ~2,000 · n8n ~400 native + webhooks · Lindy ~80 deep.
  Source: aiagentrank.io "Zapier vs Make vs n8n vs Lindy: 2026 showdown" (May 21, 2026).
  https://aiagentrank.io/blog/zapier-vs-make-vs-n8n-vs-lindy

## OWASP ASI Top 10 for Agentic Applications (2026) — candidacy for copy

- **"OWASP Top 10 for Agentic Applications" (ASI Top 10) published Dec 2025, community-reviewed by 100+ researchers; adopted as a de-facto purchase/audit checklist for 2026. Its two framing principles: "Least Agency" (agents get minimum autonomy, minimum tool access, minimum credential scope — autonomy is **earned, not default**) and "Strong Observability" (goal state, tool-use patterns, decision pathways must be logged).**
  Sources: genai.owasp.org, runesec.dev guide, Palo Alto Networks (2026).
  https://genai.owasp.org/initiatives/agentic-security-initiative/
  https://runesec.dev/learn/owasp-top-10-agentic-ai
  https://www.paloaltonetworks.com/blog/cloud-security/owasp-agentic-ai-security
- **The ASI 10 risks map 1:1 onto Atom's existing controls** (see `POSITIONING.md` §8 mapping): Goal Hijack → match-confidence + oracle verification; Tool Misuse → tool whitelist + sandbox caps; Identity/Privilege Abuse → DIDs/VCs + capability bindings; Memory Poisoning → verified-episode graduation + sensitivity taint on ingest; Cascading Failures → circuit breakers + kill-run; Rogue Agents → hard-skip + maturity revoke. **Uniquely sellable: Atom ships the ASI checklist as code — most 2026 competitors sell it as a subscription dashboard.**
- **"Almost 9 of 10 agent projects stall between proof-of-concept and stable rollout — and the blocker is rarely model quality. It's 'we don't trust this in production without controls.'"**
  Source: Gartner 2026 Hype Cycle for Agentic AI, as summarized in Fleece AI (May 2026).
  https://www.gartner.com/en/articles/hype-cycle-for-agentic-ai

## NIST AI Agent Standards Initiative (2026) — regulatory momentum

- **NIST formally launched the AI Agent Standards Initiative (Feb 17, 2026) under CAISI — the first U.S. government program dedicated to secure/interoperable agentic AI, targeting agent identity, authorization, and accountability. A companion NCCoE concept paper (Feb 5, 2026) identifies the four minimum enterprise requirements for production agents: identification, authorization, access delegation, and logging.** OWASP ASI is cited as the practical threat-model vocabulary while NIST final guidance is pending (Q4 2026).
  Sources: NIST, Cloud Security Alliance research notes (Mar/Apr 2026).
  https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative
  https://labs.cloudsecurityalliance.org/research/csa-research-note-nist-ai-agent-standards-initiative-2026040/
- **EU AI Act (Regulation (EU) 2024/1689) fully applies Aug 2, 2026; high-risk Article 9 requires risk management systems, and ASI Auditors note that agentic AI without documented controls against at least ASI01/ASI03/ASI06 will struggle to demonstrate Article 9 compliance.**
  Sources: Microsoft agent-governance-toolkit OWASP compliance guide; runesec.dev (both map EU AI Act deadlines).
  https://github.com/microsoft/agent-governance-toolkit/blob/main/packages/agent-compliance/docs/OWASP-COMPLIANCE.md

## MCP as the audit chokepoint — architectural positioning angle

- **The Model Context Protocol is becoming the dominant interface for agent tool access, making MCP gateways "natural audit chokepoints": every tool invocation passes through the MCP layer, so enforcement of logging, authorization, and rate limiting belongs there. MCP itself lacks standardized audit logging — production platforms must implement it at the gateway.** Atom's `mcp_service.call_tool` already is exactly that chokepoint (sandbox gate, capability bindings, audit, provenance — P2/P3/P4/P9).
  Source: Zylos Research, "AI Agent Governance and Compliance in 2026" (May 1, 2026).
  https://zylos.ai/research/2026-05-01-ai-agent-governance-compliance-2026/
- Same source: a single agent interaction generates 5–50KB of audit data; at 10k interactions/day that is 36–182GB/year — a quantified reason "local-first audit store" is a real buyer concern.