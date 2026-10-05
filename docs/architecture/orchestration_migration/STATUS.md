# Orchestration migration — current status

**This is the single status document.** It supersedes the accumulated
resume/coordination narratives for deciding what is done and what is next.
Those files remain as evidence and history; do not reconstruct state from them
before reading this.

Last verified: 2026-09-27, integration session (25/26 re-confirmed on the live
candidate; B7 root cause corrected; fallback shipped and evidenced).

---

## 1. Read-oriented preview — USABLE NOW

**URL: http://localhost:3102** (login `admin@example.com` / `preview-only-local-2026`)

Chat → workbook lookup → replacement → formatting → re-search → reload are
browser-verified on one frozen candidate. Artifact editing and background
actions remain disabled by design and are not advertised.

### The candidate

| | |
|---|---|
| World | `candidate_fix1` |
| Backend | http://127.0.0.1:8071 — pid 50248, frozen immutable code export |
| source_id | `a8bc48dc13e5-dirty.e2323daaad44` |
| Base commit | `a8bc48dc1` (worktree dirty — see §4) |
| Frontend | farm `.preview-instance/candidate_fix1`, separate distDir |
| DB | `backend/data/acceptance_worlds/candidate_fix1/runs/run-7325767729a0/data/atom.db` |

Freeze integrity re-checked 18:52: all six chat-path frontend files plus the
farm's own pinned `next.config.js` still hash-match what was browser-verified.
The candidate is genuinely frozen. (The *live worktree's* `next.config.js` has
drifted; the farm pins its own copy, so the running preview is unaffected.)

### Browser sequence: 25 / 26 pass

Evidence: `acceptance/preview_handoff/browser_correction_chain.json`
Screenshots: `acceptance/preview_handoff/screenshots/` (B0…B7)

Passing: real login form, browser talks only to this candidate, 8-row lookup in
order, lookup creates no task, displayed set is the revised one, outgoing item
gone, incoming item present and labelled absent with no invented value, previous
answers unchanged, no task row anywhere in the chain, formatting does not
resurrect the outgoing item, earlier answers unchanged, bubble count +1,
re-search returns the revised set, reload returns the same answers byte-exact,
streamed turn adds exactly one bubble, settles non-empty, matches durable history.

### The single failure — and why it does not block

`B7_bubble_text_grew_progressively`. **Re-run 2026-09-27: 25/26 still holds**
(`acceptance/preview_handoff_rerun/browser_correction_chain.json`, 17 samples,
distinct `[27, 86, 325]`, 2 intermediate).

**This is NOT a frontend paint gap — that earlier diagnosis was wrong.**
It is backend token *pacing*. The transport contract re-passes 16/16 and its
step `S1_frames_arrive_as_a_burst_not_a_sparse_drip` **passes** with
`frames 20, largest_gap_ms 98`: 287 chars arrive in 20 frames with no gap over
98 ms. There is no progressive growth to paint, so no frontend edit can create
it. The frontend path was traced and is lossless — synchronous per-frame
listener (`useWebSocket.ts:104-110`), functional `setMessages` updater
(`useChatInterface.ts:772-778`), `ChatMessage` not memo'd, no streaming gate in
`MessageList`. Full analysis, including the rejected fixes:
`acceptance/preview_handoff_rerun/B7_ROOT_CAUSE.md`.

**Shipped behaviour = the sanctioned fallback**, both halves measured on the
live candidate: HTTP delivery with an explicit visible loading state
(`Agent is thinking…` + spinner + stop button, present 51/580 polls ≈ 7.6 s of
the ~9.5 s turn, then cleared — `screenshots/B7b_loading_state.png`) and a
clear completion state (full answer + reasoning trace, matching durable
history — `screenshots/B7_streaming.png`).

Flag trap, re-checked and NOT the cause: `ps eww 50248` shows
`ATOM_CHAT_STREAMING=true` and the leg demonstrably ran (20 frames).

---

## 2. Advanced reliability — NOT STARTED, NOT BLOCKING

Background edits, notifications, crash recovery, mutation races, and broader
acceptance remain open. They are a separate milestone. Nothing in track 1
depends on them, and they must not gate the preview handoff.

C16 (controlled planner, authorized edit) is **not** a preview blocker. Its case
accounting is in `acceptance/lane3/CASE_ACCOUNTING_C00_C26.md` and
`WRITE_PATH_STATUS.md`. Artifact editing is promoted only when both controlled
effect coverage and the real-planner browser path pass — it is not promoted now.

---

## 3. Reuse, do not rebuild

| Need | Path |
|---|---|
| Browser sequence harness | `acceptance/lane3/browser_correction_chain.py --world candidate_fix1 --out <dir> [--headed]` |
| Streaming contract | `acceptance/lane3/streaming_contract.py` |
| Candidate freeze | `acceptance/lane3/freeze_candidate.py` |
| Frontend farm | `acceptance/lane3/frontend_farm.py` |
| Launch descriptor (frozen) | `acceptance/lane3/candidate_58293b7b2484/launch_descriptor.json` |
| Required case IDs | `acceptance/cases.json`, `acceptance/LIFECYCLE_ACCEPTANCE_MANIFEST.json` |

Rebuild the harness only when the tested source changes.

**Storage precondition — check before any run:**
`./scripts/drive_status.sh`. Worlds currently resolve to a local directory,
preflight passes, no maintenance lock. If that root is ever a plain local
directory while the external drive is meant to hold it, a run can "pass"
against an empty world. `core/world_storage_guard.py` is the guard; do not
bypass it and never hand-create the directory.

---

## 4. Open risks

1. **Dirty base.** `a8bc48dc1` plus ~96 dirty files. The candidate is frozen by
   world export, but the *repository* is not. A later `git checkout`/clean could
   invalidate the frontend farm, which symlinks the live worktree.
2. **Unverified WebSocket guard.** Commit `59f6ca6d5` is
   "wip(ws): socket generation guard — HAZARD IDENTIFIED, FIX NOT TEST-VERIFIED",
   and `4c272d677` reverted the workspace-scoped route fix. The browser console
   still logs a WebSocket connection warning. Treat as an open hazard, not a
   known-good. Left exactly as found this session.
3. **Half-frozen by design.** Backend is frozen by export (re-verified intact
   2026-09-27: `export_intact True`, `export_mismatches []`); frontend is a
   **hardlink** farm over the live worktree — the six chat-path files share
   inodes with `frontend-nextjs/`, so a worktree edit changes the running
   preview underneath the evidence. The farm pins its own `next.config.js`
   (separate inode). No frontend file was edited this session, so no re-freeze
   was required; re-verify hashes before trusting any future rerun.
4. **B7 is pacing, not paint.** Recorded here so it is not re-investigated as a
   frontend bug: the backend delivers 287 chars in 20 frames with a 98 ms
   maximum inter-frame gap, and the acceptance suite currently *asserts* that
   burst is correct. Evidence and rejected options:
   `acceptance/preview_handoff_rerun/B7_ROOT_CAUSE.md`.

---

## 5. Next action

**Track 1 is delivered.** The preview is live and browser-verified at 25/26 on
the frozen candidate, with the fallback behaviour shipped and evidenced
(§1). Do not re-open the B7 repaint work on the frontend — it is pacing, and
the only real fixes are product-level (see §4.4).

Track 2, as a separate milestone: C16, the ranking benchmarks, the full
lifecycle matrix, and a product decision on whether token streaming is a
requirement at all. If it is, the fix is on the generation side and
`S1_frames_arrive_as_a_burst_not_a_sparse_drip` must be re-specified as a
failure rather than a pass.

Detailed narratives go in evidence files, not here.
