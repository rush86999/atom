# Operator Eval Harness

Measures computer-use operator quality (model × loop × browser) against a
deterministic local site — success rate, steps, wall time per task. This
is the repo-standard evidence base (AGENTS.md §2: "measure, don't guess")
for model-pool and loop changes; numbers go in the commit/PR message.

## Running

```bash
cd backend
BROWSER_ALLOW_PRIVATE_ADDRESSES=1 \
ATOM_COMPUTER_USE_MODEL=gpt-6-astra \
python tests/operator_eval/run_eval.py --model gpt-6-astra
```

- `BROWSER_ALLOW_PRIVATE_ADDRESSES=1` — required: the eval site serves on
  127.0.0.1 and the browser SSRF guard blocks loopback by default. This
  flag is the explicit local-testing opt-in; never set it in production
  deployments.
- `--model` — any computer-use-capable model the BPC router serves
  (gpt-6-astra, claude-sonnet-4-6, claude-opus-4-6, computer-use-preview).
  Needs the provider's key (BYOK or env).
- `--only task_id,task_id` — subset runs while iterating.
- `--max-steps N` — step budget per task (default 15).

The runner needs no DB and never touches the live dev world.

## Tasks (8)

| id | verifies |
|---|---|
| form_fill | real form fill + submit recorded server-side |
| find_code | information retrieval: secret code reported in summary |
| login_flow | credential login → protected dashboard reached |
| search_and_click | search results navigation + content extraction |
| ordered_navigation | multi-page link following |
| extract_headline | reading specific content |
| scroll_find | scrolling to content below the fold |
| form_validation | reading an error response after partial submit |

Verification is server-state-based where possible (the site records what
actually happened — a lying summary can't pass) and summary-based where
the deliverable is information.

## Interpreting

- `pass` requires the verifier, not the loop's own `done` flag — a model
  that declares victory without doing the work fails.
- `steps` near the budget with low pass rates = the model is lost; a
  harness bug usually shows as uniform failures with `done=false`.
- Compare at least two models before changing the default; record the
  table in the PR.
