# Gap Analysis: Atom vs. Block's Berd

**Date:** 2026-08-19 · **Compared against:** [github.com/block/berd](https://github.com/block/berd) (Apache-2.0, ~483★, 71 commits, no releases yet — early-stage)

**What Berd is:** a desktop app for working with AI agents, built by a small Block team in the open. Tauri 2 shell + React 19 UI; the agent runtime is **Goose, bundled as a pinned sidecar binary** (`goose-backend.lock.json`) speaking **ACP (Agent Client Protocol) over a WebSocket** (`goose serve`). Enterprise "distribution seams" let companies fork a custom distribution (managed provider settings, private agents, companion CLI, signing/update infra) without polluting the public tree. Notably: outside PRs are not accepted — issues only.

**Framing:** Berd and Atom are barely competitors today — Berd is a single-user desktop client for one agent; Atom is a multi-user, server-first agent *workforce* platform. The value of this comparison is not "who wins" but **what Berd gets structurally right that Atom's desktop story lacks.**

---

## Where Atom is ahead (context, not complacency)

| Dimension | Atom | Berd |
|---|---|---|
| Multi-user / team | Core design: orgs, roles, governance, HITL approvals, org-sharing | Single-user desktop |
| Agent model | Multi-agent workforce: maturity tiers, fleet orchestration, episodic memory, GraphRAG + unified turn-time recall | One general-purpose agent (Goose) |
| Governance | 4-tier maturity, sandbox, audit trail, approvals queue | Not evident in repo scope |
| Integrations | 46+ business integrations, ingestion pipelines, org-sharing | Goose's MCP ecosystem via sidecar |
| Memory | Durable facts, episodes, knowledge graph, hybrid retrieval (just unified) | Goose's session/memory model |
| Surface breadth | Web UI, Telegram/IM bridges, mobile app, LLM Gateway | Desktop only |

## The gaps — what Berd gets right that Atom doesn't have

### 1. A standard agent↔client protocol (ACP) — the biggest structural gap
Berd doesn't own its agent protocol: Goose speaks **ACP**, an emerging open standard, over a WebSocket. Any ACP-compatible agent could slot in; any ACP client could drive Goose. Atom's agent surfaces are all first-party protocols (internal REST/WebSocket, the OpenAI-compatible LLM Gateway). **Consequence:** no third-party client can drive Atom agents, and Atom can't be driven FROM standard tools. **Action:** expose the agent loop (sessions, turns, tool calls, approvals) as an ACP-compatible endpoint. This is also a SaaS-readiness move — standard clients reduce onboarding friction and make the "AI employee" drivable from tools employees already have.

### 2. Pinned, versioned agent runtime (sidecar + lockfile)
Berd bundles the agent binary and **pins it with a lockfile** — the UI and the runtime version together, always reproducible. Atom's equivalent relationships (frontend ↔ backend API, agent definitions) are coupled only by living in one repo; nothing pins the API contract the desktop client was built against. **Action for SaaS:** an API-version/compatibility lock (the frontend build records the backend API version it was tested against; mismatch warns or blocks).

### 3. Desktop packaging, signing, and updates — Atom has none
Berd treats distribution as a feature: signing/update infrastructure as an enterprise seam, bundling via Tauri. Atom's `menubar/` (Tauri) is a dev-quality companion with hardcoded dev URLs; there is no signed, notarized, auto-updating desktop distribution of anything. **Action:** if the desktop companion matters post-pilot, adopt Berd's baseline: Tauri bundling + updater + notarization, versioned releases. Until then, the browser UI + Telegram remain the employee surfaces (correct for the pilot).

### 4. Frontend engineering hygiene
Berd: small surface, Vitest + Playwright E2E + Biome + type-safe end-to-end, `just check` gates. Atom's frontend: ~100 admitted TS errors ignored at build, multiple divergent next configs, two parallel auth systems, no E2E suite. The P2 lesson from the memory work applies directly: **you can't safely refactor what you can't measure** — Atom's frontend has no tripwire. **Action:** (a) `tsc --noEmit` gate on changed files, (b) Playwright smoke suite over the ten employee-critical flows (login, chat+memory drawer, approvals, admin users, settings), (c) delete the duplicate next configs.

### 5. Experiment system (feature flags with UX)
Berd ships a user-local experiment system — unstable behaviors flagged, auto-on in dev, off in production. Atom's equivalent is scattered env vars with no uniform on/off/dev-default semantics. **Action:** consolidate the growing env-flag surface (MEMORY_*, TELEGRAM_*, ATOM_*) into one experiment registry with dev/prod defaults — cheap now, expensive later.

### 6. Distribution seams as a design pattern
Berd's enterprise story isn't a fork; it's **seams** — defined extension points where a distributor injects managed settings, private agents, a CLI, signing — while the public tree stays clean. This maps exactly onto Atom's AGPL-free-edition / client-hosted-paid-edition split, which today is handled by env flags and discipline. **Action:** formalize the edition seams (provider settings, agent registry, gateway keys, branding) so the paid edition is a distribution, not a divergence.

## What NOT to copy

- **No-PR contribution model** — Atom's community story (AGPL, contributions welcome) is an asset; keep it.
- **Single-agent scope** — Atom's workforce model is the differentiator.
- **Desktop-first architecture** — Atom's server-first design is what makes multi-user, governance, and the pilot possible. Berd's shape would undo it.

## Priority ordering (for the roadmap after pilot Phase 1)

1. **Frontend hygiene gate** (#4) — prerequisite for everything else; directly de-risks Phase 3.
2. **ACP endpoint** (#1) — highest strategic value; makes Atom agents client-agnostic and pre-positions the SaaS.
3. **Experiment registry** (#5) — cheap, do before the flag count grows further.
4. **Edition seams** (#6) — before the first paid client-hosted deployment.
5. **Desktop packaging** (#3) + **runtime pinning** (#2) — only when/if the desktop companion becomes a real surface.


---

## Closure status (2026-08-19, "close all gaps" pass)

- ✅ **#1 ACP endpoint**: `api/acp_routes.py` — ACP v1 baseline over authenticated WebSocket (`/acp/ws?token=<jwt>`): initialize (capabilities incl. loadSession), session/new, session/load, session/prompt (streams spec-shaped `agent_message_chunk` updates, then `stopReason`), session/cancel. **Live-verified with a real ACP client conversation** (initialize → new → prompt → memory-backed answer → end_turn). Later slices (tool_call/plan updates, request_permission) are additive on the same wire shapes.
- ✅ **#2 API version pin**: `/api/meta/version` + frontend `lib/apiVersion.ts` checks at startup and warns loudly on mismatch (build pins via NEXT_PUBLIC_API_VERSION).
- ✅ **#3 desktop cleanup (implementable part)**: menubar's hardcoded `localhost:8000` URLs replaced with the configured server URL (localStorage `atom_server_url`); packaging/signing requirements documented in menubar/README (needs Apple Developer ID — certs are the blocker, not code).
- ✅ **#4 frontend hygiene**: duplicate next configs deleted; `scripts/typecheck-changed.sh` gate (fails only on type errors in changed files); Playwright smoke suite (`e2e/smoke.spec.ts`, 10 employee-critical flows, auto-skips without backend/credentials) + `npm run e2e` / `e2e:install` / `typecheck:changed`.
- ✅ **#5 experiment registry**: `core/experiments.py` — declared defaults + dev/prod semantics + env override; adopted by the memory-assembly, conversations-leg, rerank, consolidation, and telegram-polling call sites; `registry_summary()` for settings UI. Test caught (and the resolution fixed for) NODE_ENV/ENVIRONMENT precedence.
- ✅ **#6 edition seams**: `core/edition.py` — `distribution.json` overrides (branding, provider_policy, agent_catalog, gateway_keys, feature_flags) with unknown-seam rejection and community defaults when absent; the paid edition is now a distribution file, not a fork.

Tests: 11 new (ACP handshake/prompt/auth-reject, registry defaults/override/unknown, edition seams ×4) + 43 across affected suites. All pushed.
