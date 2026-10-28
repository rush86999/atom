# Core UI acceptance loop — 2026-10-28 — FAILED

Candidate: `whole-app/successor-f5f` at `8b2f6cfcf` (clean worktree).
World: `core_release_ui_final_20261028`, API-seeded fixture, isolated run
`run-d427fd5e3b04`, export `0664beba91d2…`.
Configuration: `ATOM_LOCAL_ONLY=true`, `ATOM_CHAT_STREAMING=false`,
`ATOM_CHAT_TURN_BUDGET_SECONDS=180`, `ATOM_TURN_INTERPRET_TIMEOUT_S=20`,
`ATOM_REVIEW_STRUCTURED=0`, Ollama `llama3.1:8b`.
Frontend: the candidate production build (core profile); `preview_stack`
`verify` confirmed the running backend had `ATOM_CHAT_STREAMING=false` from
its own process environment. The stale `.preview-instance` symlink farm was
not used for this run; a dedicated candidate frontend was started on :3113.

## Result: failed

Passed through the UI:

- grants and vendor CSVs uploaded (both HTTP 200);
- blank canvas created and agent attached;
- policy taught, then corrected in place (same teaching point, one recorded);
- first assessment validated and delivered
  `GR-2026-014 FUND`, `GR-2026-021 HOLD`, `GR-2026-033 DECLINE`;
- different unfamiliar assessment on `vendor_loop.csv` validated and
  delivered `IN-7301 DECLINE`, `IN-7302 HOLD`, `IN-7303 HOLD`;
- real backend restart succeeded; corrected policy and vendor history
  survived;
- zero unauthorized side-effect writes (tasks/boards/messages/events all
  zero).

Failed:

1. **Calculation.** Two UI asks for the open-invoice total returned
   `AGGREGATION NOT PLANNED — the planner did not return a usable
   dataset/query; no total was computed.` No total was delivered. The
   explicit-sheet binding repair did not help because the local planner
   produced no SQL plan at all.
2. **Fresh post-restart judgment.** The fresh vendor assessment was
   structurally certified but substantively wrong:
   `IN-7301` (3200) came back `HOLD` instead of `DECLINE`; the model's own
   basis said the policy requires DECLINE. The validator certifies
   references and labels, not whether the label follows the policy.

Because the loop did not pass, the core readiness ledger is not upgraded and
no release package is prepared. CR-009 (cross-domain judgment) and CR-019
(restart generation reliability) remain as recorded.

## Evidence

- `pre_restart_final.json` — first assessment, correction, different
  assessment and calculation failure, with review contracts.
- `history_after_restart.json` — fresh public history after the restart:
  both the correct pre-restart `DECLINE/HOLD/HOLD` and the wrong fresh
  `HOLD/HOLD/HOLD` are preserved.
- `fresh_after_restart_ui.text`, `fresh_after_restart.png` — the fresh
  post-restart UI result.
- `post_restart_canvas.png` — canvas/training state after restart.
- `calculation_try2_ui.text` — second calculation ask and its refusal.
- `db_check.json` — zero unauthorized writes.

The earlier 120-second client timeout was observed on a local 8B review turn;
the candidate now allows 300 seconds, and this run received the validated
vendor result. The remaining failures are the missing deterministic
calculation plan and the model's substantive judgment, not transport.
