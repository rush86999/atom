# AGENTS.md — Working Standards for AI Agents in This Repo

Every agent (Claude, Codex, ZCode, Cursor, or human pairing with one) follows
these decision standards. Project specifics live in `CLAUDE.md`; multi-agent
coordination protocol lives in `notes/AGENT_COORDINATION.md` (local, gitignored).

## 1. Decide with the WHOLE repo in context — no narrow fixes

- **Trace the neighborhood before editing.** Find the callers, the consumers,
  and the parallel implementations of anything you touch. A fix that is correct
  for one call site and silently changes behavior for five others is not a fix.
  (Real case: making `LLMService.generate_completion` pass full message lists
  changed behavior for EVERY caller — flagged and audited, not just the chat path.)
- **Look for the existing general mechanism before adding a special case.**
  This repo has 40+ integrations behind `UniversalIntegrationService`, an MCP
  tool surface, registries, and a BPC cost router. If you're about to hardcode
  behavior for ONE integration (a regex that detects "email" requests, an
  Outlook-specific branch), stop: the same need almost certainly exists for
  every other integration. Build or use the general layer instead.
- **Check for the known cross-cutting bug classes before assuming local cause:**
  - **Path anchoring**: anything resolving `./data/...` or relative paths must
    be anchored to `backend/` (root-vs-backend launches already caused
    divergent LanceDB stores, DB URLs, and the pricing cache).
  - **Message flattening**: the LLM layer must receive full message lists;
    anything that reduces to (last-prompt, last-system) destroys multi-turn.
  - **Stale caches shadowing durable state**: file/session caches can lag the
    DB — the durable store is authoritative on conflict.
- **Read the run history.** `git log`, recent commits by other agents, and
  `notes/AGENT_COORDINATION.md` — someone may have already built (or
  deliberately removed) what you're about to add. E.g. the cross-user token
  fallback in `outlook_service` was removed on purpose (security); don't
  reintroduce it to make a test pass.

## 2. Evidence over plausibility

- **Diagnose from runtime evidence**: logs (`backend/logs/uvicorn_*.log`),
  captured request/response payloads (intercept the actual call — don't reason
  about what "should" be in it), DB rows, and live reproduction. Most of this
  session's worst bugs (message flattening, transcript dedup corruption, the
  frozen pricing cache) were invisible until the real payload was captured.
- **Verify fixes end-to-end at the boundary the user touches** (the UI or the
  public API), including across app restarts when persistence is involved.
- **Measure, don't guess, when comparing options**: model quality (recall
  tests), latency, cost — a small benchmark beats an opinion. Keep the numbers
  in the PR/commit message.
- **Unit-test heuristics you add** (classifiers, regex gates, extractors) with
  realistic inputs, and re-run them after changes.

## 3. Research established practice for architectural decisions

- Before designing anything novel (tool selection, memory, routing, agents),
  **web-search how mature harnesses do it** and cite what you found in the
  commit/PR. Prefer patterns with production adoption (e.g. function-calling /
  tool-RAG retrieval over hardcoded intent regexes; MCP-style tool discovery).
- When research and repo constraints conflict, say so explicitly and pick with
  reasons — don't silently follow either.

## 4. Leave the trail navigable

- Commit messages explain WHY (root cause, evidence, verified-how), scoped to
  only the files you actually changed — other agents' in-flight work stays
  unstaged.
- Update `notes/AGENT_COORDINATION.md` when you start/finish work on shared
  files, and log incidents (file clobbering, concurrent edits) there.
- Behavior changes that affect other callers must be flagged in the
  coordination doc and the commit message.
