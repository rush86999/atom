# DeepSeek Flash screening — 2026-10-28 — PASS

The fixed seven-case screening (preserved full context + six minimal cases)
was repeated once with the repaired transport, using the existing authorized
DeepSeek credential and the same policy, vocabulary, output contract and
expected decisions.

- actual model: `deepseek-flash` / `deepseek`
- substantive correctness: **7/7**
- product reference/certification validity: **7/7**
- semantic retries: 0; transport retries: 0
- tokens: 8,542 input + 2,586 output = 11,128
- estimated cost: **$0.0057** at DeepSeek direct flash rates
- latency: 1.8–3.6 s per case, average **2.3 s**

This qualifies Flash for the core UI loop. It is not permission for a silent
Pro or local fallback. Evidence: `results.json`, `run_stdout.text`,
`SCREENING_MANIFEST.json`.
