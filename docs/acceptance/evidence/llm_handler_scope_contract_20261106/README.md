# LLM handler scope-contract assertion — verification (2026-11-06)

## What this is

A single assertion ported from PR #663 (`codex/ci659-backend-repair-20261105`,
evidence bundle `ci_pr659_backend_4958a7c5f`) onto current main
(`d860072a7`, post-#664).

`TestConcreteModelVisibility::test_generate_completion_returns_concrete_model`
now pins that `LLMService.generate_completion` acquires its handler via
`_get_handler(workspace_id=..., tenant_id=...)` with **explicit scope kwargs**:

```python
assert captured_scope == {"workspace_id": None, "tenant_id": None}
```

Handler acquisition is tenant-aware (`core/llm_service.py:337`, called with
both kwargs at `llm_service.py:813,868` and the generate path). Without this
pin, a lambda accepting the kwargs with defaults would silently pass even if
production stopped forwarding them — collapsing the tenant-scoping surface.
No other test on main pins this contract.

## Provenance

- Improvement originates in PR #663; historical evidence stays attributed to
  its original bundle `docs/acceptance/evidence/ci_pr659_backend_4958a7c5f/`
  (not copied here).
- Everything else in #663 was verified superseded by #664 (merged as
  `d860072a7`): route-catalog fixtures (main's shared `tests/_llm_route_catalog.py`
  is the stricter isolation), skill-delete journey (main asserts 403-refusal
  keeps the skill + tombstone), streaming retry semantics (main's dedicated
  `tests/test_stream_retry_state_contract.py`), UI release-profile assertions.
- New verification lives only in this directory.

## Verification

Environment: local, `TESTING=1` (forced scratch DB), Python 3.14.

1. Affected contract first — `backend/tests/test_routing_feedback_endpoint.py`:
   the modified test PASSES with the new assertion.
   The file's 4 other failures are identical to the pure-main local baseline
   (env-specific, CI-green there).
2. Existing CI selection (the 8 files of the former 39-failure set):
   22 local failure lines vs 24 on the pure-main baseline; the delta is
   journey-fixture `InsufficientPrivilege`/connection noise on files this
   branch does not touch. **Zero new failures attributable to this diff.**
3. Remote CI: successor PR checks (see PR #665+) are the authoritative gate;
   the identical journey code was green in #664's CI run.

## Scope

- `backend/tests/test_routing_feedback_endpoint.py` — capture + assert only.
- No production changes. No journey fixture changes. No historical evidence
  relocated.
