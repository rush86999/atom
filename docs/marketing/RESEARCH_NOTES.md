# Atom — Research Notes (sources for external claims)

> Every external stat used in Atom marketing copy, with its source. If it's not here,
> it doesn't go in copy. Repo-internal claims are grounded in `CLAUDE.md` / `docs/`
> (see each file's own "Grounding" notes).

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