# Browser UI Gap Analysis — Employee-Facing Desktop Experience

**Date:** 2026-08-19 · **Scope:** `frontend-nextjs` (primary), `menubar/` (Tauri companion) · **Benchmark:** what the brennan.ca pilot needs at Phase 3 — remote employees logging in through a browser (behind Cloudflare Access), chatting with memory-aware teammates, approving actions, managing their own settings.

**Method:** full code trace of ~100 pages, ~50 BFF proxy routes, auth plumbing, config. Maturity calls are per-code, not per-marketing.

---

## Verdict

The browser UI is a **capable single-user console** one hardening pass away from being a **multi-user employee app**. Chat (streaming, feedback, cancel, model badge), agents (maturity tiers, live logs), canvas, and AI-key settings are genuinely wired. But two defects disqualify it for multi-user use *as-is* — every employee shares one chat identity, and the client bundle hardcodes localhost — and the pilot's three employee-critical surfaces (approvals, user management, memory transparency) are missing or orphaned.

---

## Tier 1 — Disqualifying for Phase 3 (fix before any employee logs in)

| # | Gap | Evidence | Impact | Fix sketch |
|---|---|---|---|---|
| 1 | **Shared chat identity** — `user_id: "default_user"` hardcoded | `hooks/chat/useChatInterface.ts:54,137,190,414`; `ChatHistorySidebar.tsx:37`; `canvas/[id].tsx:25` | Every employee sees the same session list, same workspace stream, same history. Privacy and usability both broken. | Thread the authenticated user (already in the JWT) through chat sends/history/canvas; delete the fallback constant. |
| 2 | **Localhost baked into the client bundle** | `next.config.js:14-18` (`NEXT_PUBLIC_API_BASE_URL: http://127.0.0.1:8000` into `env`); per-page fallbacks `|| 'http://localhost:8000'` (`login.tsx:6`, `lib/api.ts:12`, `agents/index.tsx:23`, `NotificationsBell.tsx:15`) | Breaks on first load from any non-local hostname — i.e., the moment we deploy behind the tunnel. | Make `NEXT_PUBLIC_API_URL` required at build (fail fast), remove hardcoded fallbacks, rebuild with the public api hostname (already in the pilot plan §2). |
| 3 | **No admin user management** | No page creates accounts/roles; only self-registration on `login.tsx:46` | You can't provision the four employees; self-registration on an internet-exposed app is an open door. | Admin Users page (list/create/disable/role) over the existing backend user routes; disable self-registration for the pilot. |

## Tier 2 — Employee-critical for the pilot story (fix during Phase 3)

| # | Gap | Evidence | Impact |
|---|---|---|---|
| 4 | **No approvals/HITL page** — pending `hitl_actions` only surface one-at-a-time inside the floating chat widget (`GlobalChatWidget.tsx:63`) or AgentStudio | No dedicated route | The governance story ("approve before send") is invisible at the exact moment it matters; approvals are easy to miss. Note: backend queue consumer also unfinished (see pilot plan ops notes) — UI + consumer should land together. |
| 5 | **Memory transparency absent** — `hooks/useChatMemory.ts` is fully built but never imported outside tests | Chat UI | Employees can't see *what the agent remembered* — the pilot's trust story. Cheap win: a collapsible "context used" drawer fed by the assembler. |
| 6 | **Auth hardening** — JWT in localStorage + JS-forged `next-auth.session-token` cookie; middleware checks cookie presence only | `lib/backendAuth.ts:58-66`, `middleware.ts:66-73` | Fine on LAN; weak for internet exposure. Mitigated short-term by Cloudflare Access in front (pilot plan); fix properly (HttpOnly cookie, validated middleware) before any SaaS. |
| 7 | **Two parallel auth systems** — custom login (`login.tsx`) and NextAuth (`auth/signin`) both live, different post-logout destinations, NextAuth falls back to direct Postgres from the Next server | `lib/auth.ts`, `lib/db.ts` | Confusing UX, two sources of truth, Postgres path dead on SQLite Personal Edition. Pick one (NextAuth w/ credentials) and retire the other. |
| 8 | **Settings page half-disabled with orphaned sub-pages** — Workspace/Account tabs disabled; `/settings/ai`, `/settings/account` (password+2FA), routing, local-models are URL-only | `settings/index.tsx` | Employees can't find password change or AI settings; admin can't find key management. Navigation pass, one day. |
| 9 | **Team chat is a placeholder** ("under maintenance") | `team-chat.tsx` | Cut it from the pilot narrative (Telegram is the channel) or finish it post-pilot. Don't demo it. |

## Tier 3 — Real but deferrable

| # | Gap | Notes |
|---|---|---|
| 10 | **Office co-editing is custom approximations** — no real Excel/Word editor or CRDT in `package.json` (only Monaco); `Collaboration/*` cursors exist for workflow builder only | Canvas is genuinely functional for agent artifacts; storyboard template-fill works through the agent, not the editor. Real co-editing is a post-pilot/SaaS feature. |
| 11 | **Integrations catalog static; OAuth coverage narrow** — hardcoded list on `integrations/index.tsx`; real connect flows only for HubSpot/Zoom/Salesforce/Slack/Jira; Azure/Zoho have health/ingestion UI but no OAuth flow; **Telegram has no UI at all** | Pilot uses env-configured connections (documented); a Zoho/Azure "Connect" button would improve the demo but isn't blocking. Telegram status card is a 1-hour add. |
| 12 | **`handleActionClick` stub** (suggested actions `console.log` only) | `ChatInterface.tsx:61-63` |
| 13 | **No PWA** (no manifest/service worker); responsive Tailwind otherwise; separate Expo mobile app exists | Employees on phones → Telegram; browser on desktop. PWA post-pilot. |
| 14 | **`dashboard.tsx` hardcodes `workspaceId = "default-workspace"`** (a workspace that doesn't exist — the real one is `default`) + `intelligence/memory.tsx` hardcodes `'default'` | Part of gap #1's identity cleanup. |
| 15 | **Build hygiene** — ~100 admitted TS errors ignored at build; multiple alt configs; `.env.local` port 8001 vs config's 8000 drift | Tighten when we do the Phase 3 deploy build. |

## Menubar (Tauri) desktop companion — one-paragraph state

Real code (tray, hotkeys, QuickChat, agent list, login, notifications) but a **companion gadget**, not the employee surface: single-user assumptions throughout, dev-mode `localhost:1420` wiring, and none of the Phase-3 needs (approvals, settings). Treat as owner's toy; revisit post-pilot.

---

## Recommended sequence for Phase 3

1. **Identity pass** (gaps 1, 14): authenticated user through chat/canvas/dashboard/memory — ~1 day.
2. **Deploy build** (gap 2): require `NEXT_PUBLIC_API_URL` at build, purge localhost fallbacks, build against the tunnel hostname, add CORS origin — pairs with the Cloudflare Access setup already planned.
3. **Admin Users page + disable self-registration** (gap 3) — ~half day.
4. **Approvals page + backend HITL queue consumer** (gap 4) — together; this is also the demo's governance beat.
5. **Memory-transparency drawer** (gap 5) — small, high demo value.
6. Settings navigation + auth consolidation (7, 8) — before widening beyond the pilot.

Items 1–3 are the minimum to put a browser URL in front of an employee; 4–5 make the demo tell the full story.
