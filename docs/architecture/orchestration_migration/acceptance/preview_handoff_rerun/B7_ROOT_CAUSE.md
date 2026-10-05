# B7 `bubble_text_grew_progressively` — root cause and the shipped fallback

**Date:** 2026-09-27, integration session
**Candidate:** `candidate_fix1` — backend `http://127.0.0.1:8071` (pid 50248),
frontend `http://localhost:3102`, source_id `a8bc48dc13e5-dirty.e2323daaad44`
**Outcome:** 25/26 on the browser sequence. B7 not landed. Sanctioned fallback
shipped and verified. No frontend file was modified.

---

## 1. Summary

The prior status note recorded B7 as "a frontend paint gap, not a transport
failure". **That diagnosis was wrong, and this session disproves it.** B7 does
not fail because the UI drops repaints. It fails because the backend delivers
the whole answer as a *burst*: 287 characters in 20 frames with a **largest
inter-frame gap of 98 ms**. There is no progressive growth to observe, so no
frontend change can make the bubble grow progressively.

This is now proven from three independent directions: the transport contract,
the token pacing, and the frontend render path.

---

## 2. Evidence

### 2.1 The transport is healthy (re-verified this session)

`streaming_contract.py --world candidate_fix1` re-run against the live
candidate — **16/16 PASS**
(`preview_handoff_rerun/streaming_contract_rerun/streaming_contract.json`):

| step | detail |
|---|---|
| `S1_tokens_were_actually_emitted` | `chat_token: 20` frames |
| `S1_every_token_is_bound_to_this_turn` | one distinct `execution_id` |
| `S1_no_foreign_frame_was_attributed_here` | `foreign: []` |
| `S1_streamed_text_equals_the_delivered_answer` | `streamed_chars == answer_chars == 287` |
| `S1_a_single_final_event_closed_the_turn` | `chat_token_done: 1` |
| `S1_tokens_precede_the_final_event` | `last_token_ms 7453`, `done_ms 7843` |
| **`S1_frames_arrive_as_a_burst_not_a_sparse_drip`** | **`frames: 20, largest_gap_ms: 98`** |

That last row is the finding. It is a **passing** step, which means the
acceptance suite has already codified burst pacing as the *expected, correct*
behaviour of this backend. B7's "grew progressively" expectation contradicts a
contract the suite already enforces.

The flag trap from the previous note was re-checked and is **not** the cause
here: `ps eww 50248` shows `ATOM_CHAT_STREAMING=true` on the live process, and
the leg demonstrably ran (20 frames observed).

### 2.2 The frontend render path is lossless — there is no drop to fix

Traced end to end, in the order a token takes:

1. **`hooks/useWebSocket.ts:104-110`** — a `Set` of per-message listeners,
   invoked **synchronously for every frame in arrival order**. The comment at
   `:95-103` records the measured behaviour: *50 frames in one commit reach a
   listener 50 times*, whereas a `[lastMessage]` effect sees them once. The
   streaming consumer already uses the lossless path.
2. **`hooks/chat/useTurnStream.ts:224-232`** — every `chat_token` frame calls
   `renderStream` synchronously.
3. **`hooks/chat/useChatInterface.ts:772-778`** — `setMessages(prev => …)` with
   a **functional** updater, so no frame is lost to a stale closure.
4. **`hooks/chat/turnBinding.ts:145-177`** (`applyToken`) — appends the delta,
   keyed on `executionId`, creating the bubble on the first frame.
5. **`components/chat/MessageList.tsx:40-50`** → **`components/GlobalChat/ChatMessage.tsx:181`**
   — the bubble renders `msg.content` directly. **`ChatMessage` is not
   `React.memo`'d and has no streaming branch**, and `MessageList` gates
   nothing on `streaming`. So the DOM is a pure function of `messages` state:
   every committed state is painted.

There is no throttle, no memo barrier, no early return and no dropped frame
anywhere on this path. The paint is faithful; the *input* is bursty.

### 2.3 Why the harness saw what it saw

`browser_correction_chain.py:533` requires **≥3 distinct intermediate lengths**
sampled every 300 ms. This session's run saw `distinct_lengths [27, 86, 325]`,
`intermediate_lengths 2`.

- `27` — the bubble exists, body empty; the visible characters are the
  reasoning-drawer chrome (`Reasoning Process (1 steps)`). The bubble is opened
  on demand by `applyStep` (`turnBinding.ts:227-254`), not by a token.
- `86`, `325` — the burst landing.

Against a 98 ms-max-gap burst there is nothing to sample between. The previous
run's `22 samples, distinct [27, 283], 1 intermediate` is the same shape.

---

## 3. Decision: bounded effort stopped here

The directive caps effort on the repaint fix and sanctions falling back to HTTP
delivery with a visible loading state and a clear completion state. That bound
was reached: the remaining options were all ways to *fake* a stream, not fix
one.

Rejected, and why:

- **Throttle/reveal text client-side** to manufacture intermediate lengths.
  This would make B7 report a stream the system does not produce, and would
  make the real UI worse — a fake typing effect. Dishonest evidence.
- **Change the backend to pace tokens.** The backend is frozen by the world's
  code export; editing it would invalidate the candidate. Out of scope by the
  freeze, and explicitly not this handoff.
- **Loosen the harness threshold.** Rewriting the harness to pass is exactly
  the thing the harness's own comment (`"A bubble that sits at 27 chars and
  then jumps straight to the finished answer has not rendered a stream"`)
  exists to prevent. Not done.

---

## 4. The shipped behaviour (fallback), verified

HTTP delivery, explicit visible loading state, clear completion state. Both
halves were measured on the live candidate, not assumed.

**Loading state** — `loading_state_probe.py`, 150 ms polling, 580 polls:

| | |
|---|---|
| polls with loading indicator present | **51 / 580** (~7.6 s, matching the ~9.5 s turn) |
| indicator cleared on completion | **yes** (0 at end) |
| screenshot | `screenshots/B7b_loading_state.png` |

The screenshot shows `Agent is thinking…` with a spinner, and the send button
swapped to a stop button. That is the `MessageList.tsx:69-78`
`isProcessing && !currentStreamId` branch — an explicit, visible state.

**Completion state** — `screenshots/B7_streaming.png` from the harness run:
full answer rendered, reasoning trace attached, model badge (`glm-5.3-flash`)
and timestamp present. Corroborated by two passing steps:

- `B7_bubble_settled_on_non_empty_text` — `final_chars: 325`
- `B7_final_bubble_matches_durable_history` — durable history text is
  contained in the rendered bubble

So the user-visible contract is: **ask → visible "thinking" state → complete,
correct answer matching what was durably stored.** That is a usable
read-oriented preview.

---

## 5. Freeze integrity

**No frontend file was edited in this session**, so the freeze hazard
(`.preview-instance/candidate_fix1` sharing inodes with the live worktree)
never triggered and no re-freeze was required.

Confirmed by inode, farm vs live worktree:

| file | farm inode | worktree inode | |
|---|---|---|---|
| `hooks/useWebSocket.ts` | 468430167 | 468430167 | same |
| `hooks/chat/useChatInterface.ts` | 468427767 | 468427767 | same |
| `hooks/chat/useTurnStream.ts` | 468438517 | 468438517 | same |
| `hooks/chat/turnBinding.ts` | 468438302 | 468438302 | same |
| `components/chat/MessageList.tsx` | 451267692 | 451267692 | same |
| `components/chat/ChatInterface.tsx` | 447189669 | 447189669 | same |
| `next.config.js` | 468419532 | 458489647 | **separate — farm pins its own** |

The six chat-path files are **hardlinked**, not symlinked, so a worktree edit
*would* have changed the running preview underneath the evidence. Their mtimes
are 09-27 10:59–11:38, hours before this session — untouched.

Backend export re-verified intact: `export_intact: True`,
`export_mismatches: []`.

Repo hygiene: nothing staged, nothing committed, no `git checkout` / `clean` /
`stash` / reset. The 101 dirty files and 7 pre-staged files are other agents'
in-flight work, left alone. `backend/data/atom.db` untouched — all acceptance
traffic went through the world's own DB. `./scripts/drive_status.sh` run first;
worlds preflight passed, no maintenance lock; nothing under
`backend/data/acceptance_worlds` hand-created.

---

## 6. Where B7 should go next

Not a preview blocker, and not a frontend bug. The honest next step is
product-level: decide whether streaming is a requirement at all. If it is, the
fix is on the **generation side** — the upstream LLM producing a 287-char
answer in under two seconds means there is no drip to display, and
`S1_frames_arrive_as_a_burst_not_a_sparse_drip` should then be *re-specified*
as a failure rather than a pass. That is a milestone decision, deliberately not
taken here.

Secondary, carried forward unchanged: commit `59f6ca6d5` (socket generation
guard) remains **unverified**, and `4c272d677` reverted the workspace-scoped
route fix. Both were left exactly as found.

---

## 7. Files

| artifact | |
|---|---|
| this note | `preview_handoff_rerun/B7_ROOT_CAUSE.md` |
| browser sequence, 25/26 | `preview_handoff_rerun/browser_correction_chain.json` |
| streaming contract, 16/16 | `preview_handoff_rerun/streaming_contract_rerun/streaming_contract.json` |
| loading-state proof | `preview_handoff_rerun/screenshots/B7b_loading_state.png` |
| completion-state proof | `preview_handoff_rerun/screenshots/B7_streaming.png` |
