# Substantive assessment — external blocker

The grant journey's calculation is valid cross-schema evidence, but it is not a
discretionary assessment. A current, model-backed assessment was attempted on
an unfamiliar six-record grant dataset with a declared policy, decision labels,
source snapshot and row evidence.

The assessment could not be completed because no usable model infrastructure is
available on this host:

1. **DeepSeek direct** — the env file contains `DEEPSEEK_API_KEY` but its value
   is empty; no deepseek client was built (`pin_unavailable`).
2. **OpenRouter / `deepseek/deepseek-v4-pro`** — the scoped pin resolved and the
   dispatch was attempted, but OpenRouter returned HTTP 402 "requires more
   credits" for the 6000-token review request; fallback models also returned
   402. The assessment failed closed with `empty_payload`.
3. **Local Ollama** — model storage is on an unreadable/unmounted external
   volume; `/api/tags` returns a permission error.

This is recorded as an **external blocker**, not completed coverage. The
smallest required input is a funded provider key with a declared review model,
or a readable local Ollama model store. No assessment-quality claim is made
until that input exists.

Preserved artifacts: `assess-failed-openrouter.json` (full failed-closed
response), `openrouter-402-sanitized.log` (provider errors with user/org IDs
redacted), and `blocker.json` (configuration attempts, dataset hash, policy and
expected decision schema).
