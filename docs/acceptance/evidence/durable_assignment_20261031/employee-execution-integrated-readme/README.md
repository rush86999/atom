# Integrated README feature-readiness rerun

Command (from `backend/`):

```bash
TESTING=1 /Users/rushiparikh/projects/atom/backend/venv/bin/python \
  -m scripts.readme_acceptance.run --groups all
```

The run executed all 17 groups against an isolated world with a bounded local
OpenAI/Anthropic/OAuth/MCP stub. `product_profile=full`; schedulers/pollers off;
no cloud credentials, no real send, no connected-system write.

Result on the merged employee-execution + README-readiness candidate:

- 128 result rows total (functional + separately tracked categories).
- **100 / 123 eligible functional claims verified (81.3%)**.
- 23 functional claims not counted: partial 14, unverified 7, inaccurate 1,
  blocked_external 1, environment_limited 2, architecture_only 1 (some
  categories overlap; see `results.json`).
- Security 8/8 verified.
- No group errors.

This is the same frozen denominator and inventory as Agent 2's
`readme_feature_readiness_2026-10-31` package, re-executed after the merge. It
is a self-assessment pending independent verifier agreement; it is not a
release approval.

The only merge-introduced test failure was a GraphRAG URL entity retaining a
trailing sentence period. `backend/core/graphrag_engine.py` now strips
`.,;:!?` from extracted URLs; the focused GraphRAG/MCP/workflow/search suites
are 254 passed.
