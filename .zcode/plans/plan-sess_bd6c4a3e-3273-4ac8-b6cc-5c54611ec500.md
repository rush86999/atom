## Goal
Stabilize CI (red→green), fix the concrete bugs found, and push the highest-value modules toward 95% coverage in isolation — the only viable measurement strategy, since the full suite is contaminated (58k errors together; isolated tests pass) and the true aggregate baseline is ~8.5%.

Findings are grounded in: CI's exact backend-test subset (2 failures), the staged `llm_service.py` diff, collection diagnostics, and two parallel codebase investigations (308 covpush wave files; per-module isolated coverage rankings).

---

## Phase 1 — Unbreak CI & the suite (highest priority)

**1.1 Fix the 2 failing CI tests** (`test_openrouter_in_byok_endpoints_allowlist`, `test_glm_in_valid_providers`).
Root cause: they `ast.literal_eval` the assignment `valid_providers = list(byok_manager.providers.keys())` at `byok_endpoints.py:1028` — a function *call*, which `literal_eval` can never parse. Rewrite the tests to verify runtime registration (instantiate `BYOKManager` / read the real provider list) instead of AST-parsing a non-literal. Confirm openrouter + glm are genuinely registered; fix source if not.

**1.2 Undo the unsafe part of the staged `llm_service.py` change.**
The staged diff fixes two real bugs (temperature personalization when caller passes explicit temp; `turn_index` duplicate-keyword `TypeError`) — KEEP those. But it also deletes `stream_completion`, `generate_embedding`, `generate_embeddings_batch`, `transcribe_audio`, which are still called by active code (`embedding_service.py:163/199` OpenAI/Cohere path; `atom_agent_endpoints.py:2012` streaming-chat, which main_api_app loads) → latent `AttributeError`. Restore the 4 methods. Verify `test_covpush_w64i_llm_service.py` stays green.

**1.3 Unblock the 2 collection-broken covpush files.**
`test_covpush_adapters_google_chat.py` & `test_covpush_messtrio.py` hard-fail collection via `google_chat_enhanced_service.py`'s module-level `import google.auth`. Add `pytest.importorskip("google")` at the top of both test files (skip cleanly when the optional enterprise dep is absent — same pattern CI's ubuntu runner hits).

---

## Phase 2 — Fix concrete bugs / broken-test clusters

- **episode_lifecycle_service** (4 fails): `"coroutine consolidate_similar_episodes was never awaited"` — async-signature drift between the test and source. Align the test to the current async API.
- **whatsapp_fastapi_routes** (1 fail, `404==200`): route-registration/wiring bug in the in-progress changes — investigate & fix.
- **byok_handler structured/MoA/stream** (12 fails): `ModuleNotFoundError: instructor` — make `instructor` import lazy or `importorskip`.
- **salesforce_core_service** (1 fail): test assumes `asyncpg` absent but it's installed — fix the assumption.
- **auth (3) / database (9) RecursionError**: MagicMock attribute recursion under isolated runs — fix the mocks so they're isolation-green.

These are real defects surfaced by the wave tests; I'll fix source where the bug is in source, tests where the test drifted.

---

## Phase 3 — Coverage depth toward 95% (isolated), top modules by lines-to-gain

Measurement uses the canonical isolated command (clears pytest.ini's ignore list + random order, neutralizes the 80% gate):
`pytest <test> --cov=<module> --cov-branch --cov-report=term-missing --cov-fail-under=0 -o addopts= -p no:randomly`

- **`core/llm_service.py`** 38% → ~95% (~205 lines; biggest lever): extend `tests/core/test_llm_service.py` — provider routing, structured response, speech, personalization branches, error paths.
- **`core/byok_endpoints.py`** 63% → ~95% (~185 lines; largest file): extend `tests/api/test_byok_endpoints_coverage.py` — store/validate/delete key paths, provider config, edges.
- **`core/policy_search_service.py`** 18% → ~95% (no test file exists): new `tests/core/test_policy_search_service_coverage.py` — quick win.
- **`core/agent_execution_service.py`** 77% → ~95%: extend `tests/core/test_agent_execution_service_coverage.py`.

Each module verified in isolation with a real before/after % (no inflated claims).

---

## Phase 4 — Verify
- Re-run CI's exact backend-test subset → expect all green.
- Re-run each touched module's coverage in isolation → report numbers.
- Confirm the 2 previously-broken covpush files collect/skip cleanly (no hard collection error).

---

## Out of scope
- Full-suite cross-contamination repair (long-standing, multi-session, high-risk; project explicitly works around it via isolated waves + curated CI subset).
- Frontend / Playwright e2e coverage (separate track).
- **Committing/pushing** — per standing rule I'll prepare and locally verify, but won't commit or push unless you ask.

## Integrity notes
- The staged `llm_service.py` change is partly a regression; I'll preserve its genuine fixes and only undo the unsafe deletions.
- Every coverage gain is measured with the real isolated command and reported honestly.