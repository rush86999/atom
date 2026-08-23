# Personal → Team Playbook

> The bottom-up pathway: start with a personal agent doing *your* real work, grow into a
> governed team deployment when you're ready. Nothing is thrown away on the way up.
> Last updated: Aug 22, 2026.

## Why this path exists

Atom's free Personal Edition is complete — every agent, integration, and governance
feature (AGPL v3, no gated "pro" build). That makes the natural adoption curve:

```
Solo operator ──► small team ──► organization
   (1 user)        (5–20 users)     (SSO/RBAC/audit)
```

Each phase reuses the previous phase's work: your workflows, your agents' earned
maturity, their verified track records, and the trust-calibration data all carry over.

## Phase 1 — Personal (day 0)

**Goal**: one real workflow running on your actual accounts within ~10 minutes.

1. `make setup && make backend && make frontend` (see README Quick Start), or Docker.
2. Set one LLM key in `backend/.env` (`OPENCODE_API_KEY` for ~90% savings, any major
   provider, or `ATOM_LOCAL_ONLY=true` + Ollama for $0).
3. Connect **one** integration you already use (Gmail is the usual first).
4. Import a starter template from Settings → Workflow Templates:
   - **Personal: Invoice Chase (Freelancer)** — unpaid-invoice scan → draft reminders → approve before send
   - **Personal: Candidate Pipeline (Solo Recruiter)** — application → enrich → score w/ citations → digest; outreach held at approval
   - **Personal: Support Triage (Indie / Small Shop)** — classify urgency/topic → escalate urgent to Slack → drafted replies approved in batch

Every starter ships with an approval gate: nothing reaches a client or candidate
without your OK. Self-notifications (digests, urgent pings) run hands-free — that's
the autopilot you actually want.

**Cost**: $0 (local models) to ~$10/mo (subscription gateway).

## Phase 2 — Small team (when a colleague asks "can I have that?")

The moment a second person wants in, you're doing *governance*, whether you planned
to or not. Atom productizes it:

| What changes | What you do |
|---|---|
| Multiple users, shared agent registry | Add users; assign roles |
| Agents serve several people | Review each agent's maturity tier (STUDENT → …) |
| Someone must answer "who did what?" | Audit trail exists by default — no config |

Key mechanic: **agents carry their verified history across the boundary.** An agent
with 50 clean personal runs doesn't reset to zero when it joins a team — its earned
maturity and trust-calibration record arrive with it. Teams inherit proven agents,
not blank ones.

## Phase 3 — Organization (security review shows up)

When IT/procurement gets involved, the answers are already in the box:

- **Identity & access**: OIDC SSO, SCIM v2 provisioning, 8-role RBAC
- **Blast radius**: default-on sandbox at every tool-dispatch hub (filesystem scope,
  tool whitelist, tripwires, resource caps, kill-run); mini-apps in Firecracker microVMs
- **Accountability**: full audit trail; outcome verification re-derives success against
  your system of record instead of trusting self-report
- **Compliance mapping**: [docs/compliance/COMPLIANCE_MAPPING.md](../compliance/COMPLIANCE_MAPPING.md)
  maps controls to OWASP ASI Top 10 / NIST agent-standards asks / EU AI Act Article 9
- **Data residency**: everything stays on infrastructure you control; BYOK keys
  encrypted at rest (Fernet)

Commercial/managed editions run the same code on your own infrastructure — there is
no closed-source "pro" fork to migrate to.

## What carries over at every step

| Asset | Personal | Team | Org |
|---|---|---|---|
| Workflows & templates | ✅ yours | ✅ shared registry | ✅ |
| Agent maturity tiers | ✅ earned | ✅ **carries over** | ✅ |
| Verified episodes / trust calibration | ✅ | ✅ **carries over** | ✅ |
| Audit trail | ✅ local | ✅ | ✅ |
| SSO / RBAC | — | ◐ basic roles | ✅ full |

## Anti-goals

- No bait-and-switch: features are never removed from the free edition to sell back.
- No "trust us" tier: governance is code you can read, not a dashboard you rent.
- No silent autonomy expansion: agents earn scope through verified outcomes and lose
  it automatically on regression.

## See also

- [Quick Start](quick-start.md) · [Personal Edition operations](../operations/personal-edition.md)
- [Governance overview](../agents/governance.md) · [Trust model](../architecture/TRUST_CALIBRATION_PLAN.md)
