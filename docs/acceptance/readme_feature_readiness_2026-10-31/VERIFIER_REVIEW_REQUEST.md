# Independent verifier review request — README feature readiness

**Date:** 2026-10-31
**Prepared by:** Agent 2 (README breadth + common-data surface)
**Status requested:** agreement on the denominator and the verified set, not a
release approval.

## 1. Claims

| Question | Proposed answer |
|---|---|
| Is the denominator frozen and defensible? | 123 eligible functional claims, split from the 17 README capability categories; 143 total rows including 20 tracked-separately non-functional/comparative claims |
| Is the score the agreed measure? | **100 / 123 = 81.3%** verified functional claims |
| Are partial/failed/unverified claims excluded from the numerator? | Yes — 23 functional claims are not counted |
| Are security/performance/compatibility/marketing separate? | Yes — security 8/8, performance 1/3, compatibility 0/4, comparative 0/5 |
| Is any category entirely untested? | No, but orchestration/routing/mini-apps/integrations are the thin areas |
| Is "46+ integrations" verified live? | **No.** 67 providers are registered and evidenced; live qualification is `blocked_external` (INT-09) |

## 2. What to check first

1. **Denominator freeze** — `CLAIM_INVENTORY.json`: `readme.commit`,
   `readme.sha256`, `denominator.eligible_functional == 123`, and no claim text
   edits after the run. The generator refuses to build if README moves.
2. **Method vs boundary** — every claim's `entry` and `acceptance` fields name
   an HTTP/WS route, action, command or service boundary. Controlled-provider
   evidence (local OpenAI/Anthropic/OAuth/MCP servers) is labelled as such; it
   is not presented as live provider qualification.
3. **Merged evidence** — `evidence/merged-results.json` records the strongest
   status per claim and every source world. The durable copies are:
   `all-groups.json`, `data-graph-memory.json`, `core-chat-episode.json`,
   `agent-radio.json`, `install-restart.json`.
4. **Defect fixes** — the coverage report §5 lists each fix with the failing
   boundary and targeted tests. The verifier should reproduce at least:
   - workflow conductor + rollback on a node-based workflow;
   - a nonsense document search returns no results;
   - external MCP register → execute;
   - GraphRAG neighbors/query use the supplied query;
   - episode creation from a real chat execution.
5. **Gaps** — coverage report §4 lists the 23 functional claims that are not
   counted. Confirm none were silently dropped or re-scoped.

## 3. Specific concerns for the reviewer

- **CORE-01** was verified in a world where the provider existed at process
  start. A key stored after `LLMService` construction is not picked up by the
  cached chat service (gateway works). This is recorded as a shared defect for
  Agent 1, not hidden as a pass.
- **ORCH-08** is recorded `inaccurate`: `DelegationChain.max_depth` is stored
  but `AgentFleetService.recruit_member` does not enforce nesting depth.
- **MINI-03/04/05** are environment-limited/architecture-only on macOS
  (Firecracker requires KVM). They are not counted.
- **INST-01** is unverified: the full `make setup` from a pristine clone was not
  run. The documented backend process, password file, restart and frontend dev
  server were run.
- **Performance** `0.027 ms P99` and `616k ops/s` were not measured (no
  reproducible benchmark script found); the test-function count (93,825) is
  above the README's 85k+ claim.
- **Live integrations / opencode-go** remain externally unqualified; no
  credentials were requested.

## 4. Reproduction

See `COVERAGE_REPORT_2026-10-31.md` §9. Worlds are isolated under
`/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/readme-*`;
the local stub is `backend/scripts/readme_acceptance/mock_llm_server.py`.
No deployment, real send, credential change or connected-system write was
performed.

## 5. Decision requested

Please reply with one of:

- **Agree** — denominator and 100/123 verified set accepted as reviewed.
- **Disagree** — name the claim(s) and the boundary/evidence problem; I will
  re-run or downgrade rather than argue a number.
- **Conditional** — specify the additional worlds/checks required (frontend,
  live provider, Firecracker host, model-backed orchestration).
