# Reviewer Re-delegation Loop (W3, P4c)

When the REVIEW strategy rejects the winning candidate, the swarm does NOT
swap in another candidate — the originating specialist is re-delegated with
the reviewer's feedback and gets another pass. This is "structured
delegation + review", deliberately NOT multi-round debate (the 2026
literature — Debate-or-Vote martingale, Cost-of-Consensus 85.5% sycophancy —
shows debate degrades accuracy; see `verification/review.py`).

## Flow

```
specialist produces candidate(s)
        │
        ▼
orchestrator resolves REVIEW strategy (explicit step override
`parameters.verification_strategy = "review"`)
        │
        ▼
ReviewerVerifier evaluates winner on addresses-the-question /
evidence-strength / thoroughness
        │
        ├── accept ──► step completes with the winner
        │
        └── reject (winner=None, details.accepted=False)
                │
                ▼
        conductor (ATOM_REVIEWER_LOOP_ENABLED=true)
                │
        workflow RUNNING → WAITING (state machine hooks)
                │
        feedback attached to the step (`_review_feedback` + retry_count+1)
                │
        ▼
        re-delegate to the originating specialist (step re-runs, up to
        MAX_REVIEWER_REDELEGATIONS = 2 re-delegations)
                │
                └── accept ──► WAITING → RUNNING; step completes
```

Exhaustion: after `MAX_REVIEWER_REDELEGATIONS` re-delegations the step
**fails loudly** with the reviewer's feedback in the error (never silently
completes with `None`).

## Components

| File | Role |
|---|---|
| `core/orchestration/reviewer_loop.py` | Flag, `is_review_rejection`, feedback attach/read, WAITING parking (`enter_review_waiting`/`resume_after_review`), RUNNING→WAITING guard/pre/post hooks (default-allow; observability + policy point) |
| `core/orchestration/conductor_agent.py` | `_execute_parallel_consensus` re-delegation loop (flag-gated) |
| `core/orchestration/verification/dispatcher.py` | REVIEW rejections bypass the voting fallback ONLY when the loop is enabled (legacy safety net preserved otherwise) |
| `core/orchestration/verification/review.py` | `ReviewerVerifier` (P4b) — fail-open on no-LLM/timeout/error |

## Kill switches

- `ATOM_REVIEWER_LOOP_ENABLED` (default `false`): off → a REVIEW rejection
  folds into the orchestrator's universal voting fallback (pre-P4c behavior).
- `MAX_REVIEWER_REDELEGATIONS` (constant, `reviewer_loop.py`).

## Notes

- The REVIEW strategy is reached via the explicit step override
  (`parameters.verification_strategy = "review"`); no domain maps to REVIEW
  automatically — it stays an opt-in A/B surface.
- Parking transitions are no-ops when the workflow isn't registered in the
  shared state machine (conductor tests exercise the loop without parking).
- Deterministic (non-stochastic) step executors skip the verification
  cascade entirely (single run), so the loop only applies to stochastic
  LLM-sampling branches.
