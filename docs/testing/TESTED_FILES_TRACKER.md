# Tested & Fixed Files Tracker

> **Purpose**: Persistent, date-stamped log of every file tested/fixed so future
> bug-hunt sessions can skip already-verified work and start from the gaps.
> **How to use**: BEFORE touching a file, grep this table (`rg "<filename>"`).
> If a row exists with status `GREEN`, re-verify only if the file changed since
> the date stamp. After any fix/test round, APPEND a row (never rewrite history).
> Companion: `docs/testing/BUG_FIX_PROCESS.md` (TDD rules), `CLAUDE.md` bug-fix history.

## Legend
- **Status**: `GREEN` (suite passes) · `FIXED` (bug fixed, suite green) · `TESTED` (no bug found, tests added) · `DEAD` (removed — zero importers) · `KNOWN-FAIL` (remaining failures documented)
- **Evidence**: test files + command + pass counts at the time of the stamp

---

## Session 2026-08-06 — Round 79 (R79 test wave, backend 381 tests / FE 6104 / mobile 3307)

### Backend source fixed (RED→GREEN)
| Date | File | Status | Bug fixed |
|---|---|---|---|
| 2026-08-06 | `core/workflow_endpoints.py` | FIXED | Step-based "Dynamic Workflow" rows (no nodes/connections/triggers/enabled) 500'd `GET /api/v1/workflows/workflows` (132 ResponseValidationErrors); `_enrich_workflow` now normalizes via setdefault |
| 2026-08-06 | `core/admin_bootstrap.py` | FIXED | Password file defaulted to cwd (`./logs/`) not `backend/logs/` → fresh-DB login 401 when launched per README; anchored to backend package |
| 2026-08-06 | `core/llm/byok_handler.py` | FIXED | Provider clients built with SDK-default 600s timeout → wedged dead key froze the whole server (E2E-reproduced); added `ATOM_LLM_REQUEST_TIMEOUT` (default 120s) |
| 2026-08-06 | `core/safe_evaluator.py` | FIXED | Whitelist escape `f[0]()` called arbitrary context callables (RCE-adjacent); `2**(10**18)` hang (CWE-400); non-Name call targets rejected + constant-fold exponent cap |
| 2026-08-06 | `core/llm/gateway/auth.py` | FIXED | Expired-key auth 500 on SQLite (naive vs aware datetime comparison) |
| 2026-08-06 | `core/llm/gateway/budget_alerts.py` | FIXED | Admin fallback queried nonexistent `User.is_admin` → alerts never fired; role-based admin lookup |
| 2026-08-06 | `core/deeplinks.py` | FIXED | Unknown `atom://workflow/{id}` reported success; Workflow existence check |
| 2026-08-06 | `core/expression_parser.py` | FIXED | Binary `+ - * /` missing from TOKEN_OPERATOR regex → every arithmetic expression silently False; dot/index access implemented (was dead) |
| 2026-08-06 | `core/debug_cache.py` | FIXED | `clear()` read len() after clearing (counter always 0); query keys `query:{hash()}` never evictable → deterministic positional keys |
| 2026-08-06 | `core/webhook_ingestion_triggers.py` | FIXED | 4 leftover `[FATAL_DEBUG]` stderr prints leaked job/tenant/workspace-id fragments |
| 2026-08-06 | `core/governance_wrapper.py` | FIXED | `GovernanceCache.get/set` arity mismatch → every sufficient-maturity check crashed into fail-closed denial; phantom `GovernanceAuditLog` → real `AuditLog` |
| 2026-08-06 | `core/debug_monitor.py` | FIXED | Naive-vs-aware datetime TypeError → `get_active_operations` always `[]` on SQLite |
| 2026-08-06 | `core/hypothesis_tree_endpoints.py` | FIXED | `GET /{tree_id}` shadowed `GET /history`; `beam_width=0` → IndexError 500 (now `ge=1`) |
| 2026-08-06 | `mobile/src/components/canvas/CanvasForm.tsx` | FIXED | `data?.fields ?? []` recreated per render → effect loop → JS heap OOM on null/missing-fields payloads; useMemo-stabilized |
| 2026-08-06 | `mobile/src/components/chat/StreamingText.tsx` | FIXED | Crash on null/undefined `text` (`text.matchAll`) |
| 2026-08-06 | `mobile/src/components/offline/OfflineIndicator.tsx` | FIXED | Subscribe callback closed over stale `isConnecting` → connecting animation never stopped (ref-based now) |
| 2026-08-06 | `frontend-nextjs/hooks/useCanvasState.ts` | FIXED | Throwing `subscribe` crashed the component tree; try/catch graceful degradation |
| 2026-08-06 | `mobile/jest.config.js` | FIXED | testMatch collected helper files under `__tests__/` as empty suites (16 failures); requires `.test./.spec.` |
| 2026-08-06 | `mobile/package.json` | FIXED | `date-fns` imported by ConversationListScreen but not a dependency → crash at import on device |
| 2026-08-06 | `frontend-nextjs/lib/__tests__/date-utils.test.ts` | FIXED | setSystemTime with Date instead of ms (jest 30 fake-timers) |
| 2026-08-06 | `frontend-nextjs/components/__tests__/Input.test.tsx` | FIXED | Missing React import (ts-jest jsx:react) |
| 2026-08-06 | `frontend-nextjs/lib/__tests__/api/agent-api-mocked.test.ts` | FIXED | Mock factory missing `__esModule: true` → default-import interop nested the object |
| 2026-08-06 | `frontend-nextjs/hooks/__tests__/useFileUpload.test.ts` | FIXED | Un-awaited act() trapped setState (isUploading never true); jsdom FormData File identity |
| 2026-08-06 | `frontend-nextjs/tests/constants.test.ts` | DEAD | Removed — stale duplicate of `lib/__tests__/constants.test.ts` (phantom module contract) |

### Backend test suites added (all GREEN at stamp time)
| Date | Test file(s) | Count |
|---|---|---|
| 2026-08-06 | `tests/test_r79_{workflow_dynamic_rows,bootstrap_password_path,llm_client_timeout}.py` | 9 |
| 2026-08-06 | `tests/test_r79_{safe_evaluator,gateway_auth,budget_alerts,deeplinks,token_encryption,mini_app_tool,action_registry_rpc}.py` | 220 |
| 2026-08-06 | `tests/test_r79_gap_{expression_parser,debug_cache,webhook_ingestion,uptime_tracker,credential_vault,governance_wrapper,debug_monitor,skill_versioning,hypothesis_tree_endpoints,mini_app_routes,mini_app_tool}.py` | 245 |

### Frontend suites added (all GREEN)
| Date | Cluster | Suites/tests | Coverage |
|---|---|---|---|
| 2026-08-06 | `components/{Automations,Agents}/__tests__/` | 9 suites / 164 tests | 91–100% per file |
| 2026-08-06 | `components/Debugging/__tests__/` | 9 suites / 56 tests | 84–95% per file |
| 2026-08-06 | `components/{Collaboration,DevStudio}/__tests__/` | 6 suites / 52 tests | 88–98% per file |
| 2026-08-06 | `lib/__tests__/api/retry-logic.test.ts` | 26 tests | deterministic fake-timer backoff (was flaky: 375<500 under load) |

### Frontend source fixed (by test exposure)
| Date | File | Bug |
|---|---|---|
| 2026-08-06 | `components/Automations/FlowVersioning.tsx` | Compare-mode banner dead end — version click never completed pending comparison |
| 2026-08-06 | `components/Debugging/DebugPanel.tsx` | Imported missing `@/components/ui/collapsible` — module-load build breaker |
| 2026-08-06 | `components/Debugging/VariableInspector.tsx` | `Button` used without import — ReferenceError every render |
| 2026-08-06 | `components/Collaboration/CollaborativeCursor.tsx` | `useImperativeHandle({...})` throwaway object — parent ref API unusable; now forwardRef + exported handle |

---

## Session 2026-08-07 — Round 80 (zero-coverage modules, stale-suite alignment, mount regressions)

### Backend source fixed
| Date | File | Status | Bug fixed |
|---|---|---|---|
| 2026-08-07 | `core/llm/self_consistency_voter.py` | FIXED | vote() popped per-sample overrides inside closure → samples 2–N lost system_instruction/task_type/chain_id/image_payload; is_irreversible matched field names only → `{"action":"send_email"}` never flagged, 3× sample gate never fired (value-prefix matching) |
| 2026-08-07 | `core/llm/registry/provider_health.py` | FIXED | rate_limited providers never recovered (record_success only checked UNHEALTHY/DEGRADED); unknown/corrupt stored state crashed get_health_state; record_success None*int TypeError |
| 2026-08-07 | `core/llm/routing/offline_tuner.py` | FIXED | no-data summary missing tasks_tuned_count (KeyError) |
| 2026-08-07 | `core/llm/registry/queries.py` | FIXED | Decimal -= float TypeError + naive-vs-aware datetime on DB-loaded models |
| 2026-08-07 | `core/budget_guardrail.py` | FIXED | context manager used as Session (every background run crashed); removed `hourly_cost_rate` column (getattr→$50/hr); Decimal+float TypeError on mixed burn sources |
| 2026-08-07 | `core/marketing_agent.py` | FIXED | Same context-manager-as-Session bug ×2 |
| 2026-08-07 | `core/periodic_tasks.py` | FIXED | factory 0-arg mismatch; `settings.enabled` on dict results — heartbeat crashed on first workspace |
| 2026-08-07 | `core/entity_skill_service.py` | FIXED | DetachedInstanceError (session close expired row); expunge before return |
| 2026-08-07 | `core/dependency_resolver.py` | FIXED | Duplicate identical npm version specs falsely reported as conflicts |
| 2026-08-07 | `core/byok_competitive_endpoints.py` | FIXED | 404 swallowed by broad except → 500 |
| 2026-08-07 | `core/agent_governance_service.py` | FIXED | `_adjudicate_feedback` crashed on `User.specialty` (column removed); set `adjudicated_at` |
| 2026-08-07 | `core/episode_lifecycle_service.py` + `core/episode_retrieval_service.py` | FIXED | 9 sites `datetime.now()` vs `DateTime(timezone=True)` (naive/aware TypeError) |
| 2026-08-07 | `core/proposal_service.py` | FIXED | L164 submit_for_approval + L913 _create_proposal_episode logged `proposal.proposed_by` (AttributeError every submit); L225–228 approve_proposal in-place `proposed_action.update()` never persisted (SQLAlchemy doesn't track in-place JSON mutation) |
| 2026-08-07 | `integrations/slack_enhanced_service.py` | FIXED | Constructor arg misbinding; 5 methods lost in merge conflict (restored); dataclass tenant_id vs workspace_id; SlackApiError response-shape KeyError; `_save_workspace` json.dumps on datetime |
| 2026-08-07 | `core/agent_world_model.py` | FIXED | Enhanced-rating fields dropped (restored); `_extract_canvas_insights` deleted (restored); episode enrichment block deleted from recall (restored); boost_experience_confidence was always-True placeholder (implemented) |
| 2026-08-07 | `core/skill_marketplace_service.py` | FIXED | SaaS client swallowed HTTPError → local fallback never reached (~60s hangs); comment→review kwarg; missing NOT-NULL tenant_id; no skill-existence check; `page_size<=0` ZeroDivisionError |
| 2026-08-07 | `core/security/middleware.py` | FIXED | CSRF pytest bypass gated on `PYTEST_VERSION` (pytest never sets it — sets `PYTEST_CURRENT_TEST`) → every state-changing test request 403'd (~115+68 failures) |
| 2026-08-07 | `main_api_app.py` | FIXED | **`/api/atom-agent/*` double-prefixed by on-demand loader (404 in prod)**; **`/api/devices/*` router never mounted (404)**; **`/api/browser/*` router never mounted (404)** — all restored |
| 2026-08-07 | `api/device_capabilities.py` | FIXED | Broad `except Exception` swallowed own HTTPExceptions → documented 400/403 became 500s (all 7 endpoints); wrong response models (ScreenRecordStopResponse on location/notification/command endpoints) → 500 on success; `get_active_sessions` read nonexistent `created_at` |
| 2026-08-07 | `tools/device_tool.py` | FIXED | `_create_device_audit` omitted NOT-NULL action/endpoint → IntegrityError misread as governance 403 |
| 2026-08-07 | `api/board_comment_routes.py` | TESTED | 20 tests, 100% coverage — no bugs found |
| 2026-08-07 | `api/{device_nodes,google_chat_enhanced_routes,signal_routes,integration_health_stubs}.py` | DEAD | Zero importers (stale shadows of live twins in integrations/) — removed |

### Backend test suites added (all GREEN)
| Date | Test file(s) | Count |
|---|---|---|
| 2026-08-07 | `tests/test_r80_{self_consistency_voter,offline_tuner,provider_health,test_cache,test_queries}.py` | 129 |
| 2026-08-07 | `tests/test_r80_{budget_guardrail,byok_competitive_endpoints,dependency_resolver,enterprise_endpoints,entity_skill_service,health_monitor,marketing_agent,marketplace_sync_worker,periodic_tasks}.py` | 135 |
| 2026-08-07 | `tests/test_r80_board_comment_routes.py` | 20 |

### Stale-suite alignment (2026-08-07) — no behavior change, tests matched to current schema
| File class | Scope | Result |
|---|---|---|
| `email_verified=` kwarg removed from User constructors | 21 test files + 2 removed-feature suites skipped | 122 failures eliminated |
| `first_name/last_name/role/status` added; stale `username/is_active/superuser/specialty` kwargs dropped | 98 test files | ~81 NOT NULL + UNIQUE failures eliminated |
| `LLMService.handler` setter added (source) | `core/llm_service.py` + 47 tests | 47 failures eliminated |
| API contract suites (CSRF/prefix/route fixes above) | `integration/test_atom_agent_endpoints_api_contracts.py` (142→0), `test_api_request_validation.py` (71→0) | 257 failures eliminated |
| Integration services | `test_episode_services_coverage.py` (79→0), `test_governance_coverage.py` (56→0), `test_backend_gap_closure.py` (44→0) | 179 → 241 passed |
| Service layer | `test_slack_enhanced_service.py` (73→0), `test_world_model.py` (49→0), `test_skill_adapter.py` (verified 45/45), `test_skill_marketplace.py` (37→0) | 198 → 297 passed |
| Debugger/error paths | `test_workflow_debugger_complete.py` (verified), `test_workflow_debugger_coverage.py` (verified), `test_proposal_service_coverage.py` (37), `test_agent_lifecycle_error_paths.py` (37), `test_api_boundary_conditions.py` (55) | ~200 → green |
| Device/browser | `test_api_device_routes.py` (44→58), `test_api_browser_routes.py` (45→125) | 169 → green |
| Mini-app suites | `test_r79_gap_mini_app_routes.py`, `test_covpush_miniapp.py` | already green at HEAD (no regression) |

### Late R80 additions (2026-08-07)
| Date | File | Status | Note |
|---|---|---|---|
| 2026-08-07 | `api/device_capabilities.py` (follow-up) | FIXED | Broad `except Exception` swallowed own HTTPExceptions → 400/403 became 500s (all 7 endpoints); wrong response models (`ScreenRecordStopResponse` on location/notification/command) → 500 on success; `get_active_sessions` read nonexistent `created_at` |
| 2026-08-07 | `tools/device_tool.py` (follow-up) | FIXED | `_create_device_audit` omitted NOT-NULL action/endpoint → IntegrityError misread as governance 403 |
| 2026-08-07 | `tests/test_api_device_routes.py` | FIXED | 36 patch sites retargeted `tools.device_tool.*` → `api.device_capabilities.*` (route binds at module level — mock-namespace bug class); get_db override fixture; workspace_id=default in test agents; stale premises updated to documented maturity gates → 58/58 green |
| 2026-08-07 | `tests/test_api_request_validation.py` | GREEN | 77/77 (verified; no changes needed) |

---

## Measured coverage (session stamps)
| Surface | Coverage | Statements/Files | Method | Date |
|---|---|---|---|---|
| Backend (unit+api+core+database+security+root chunks merged) | **54.0%** | 158,057 stmts / 1,018 files | `pytest -n 3 --timeout=300 --cov-append` chunked | 2026-08-07 |
| Frontend (full suite, 6,298 green) | **34.4% lines** | 732 files | `jest --coverage --maxWorkers=2` | 2026-08-07 |
| Mobile (full suite, 3,307 green) | **60.1% lines** | 80 files | `jest --coverage --maxWorkers=4` | 2026-08-07 |

## Known remaining work (next hunt targets — verified failing at last run)
- `tests/test_llm_service.py` — 12 mock-await fixture bugs (`TypeError: object tuple can't be used in 'await' expression`, Mock await in embeddings) — test-side
- `tests/test_auth_routes_coverage.py` — `no such table: tenants` (register provisions tenants; fixture only creates users table)
- `two_factor_enabled/two_factor_secret` stale kwargs in `test_auth_2fa_routes_coverage.py` (commented-out columns)
- `User.name` property setter in admin-route suites
- Other-model NOT NULL: `conflict_log.tenant_id`, `failed_rating_uploads.tenant_id`, `chat_messages.tenant_id`, `canvas_audit.canvas_id`, `SupervisionSession(supervision_feedback=...)` stale kwarg
- Collection errors: `No module named 'api.agent_routes'`, `api.agent_governance_routes`, `integrations/chat_orchestrator.py:54` (logger NameError in HEAD)
- Env-dependent (skip-candidates, verify first): Docker-required package-installer suites, `test_api_browser_routes` Playwright extras, `tests/unit/governance` graduation exams, security SQL-injection assertion drifts (400 vs 401)
- Full-suite single-run still memory-bound on this machine (~570MB free with concurrent sessions) — use chunked `-n 3 --timeout=300 --cov-append`, never `-n auto` >4 here

## Convention (append-only)
Every future round: add one row per fixed/tested file with date `YYYY-MM-DD`, round tag, evidence (test file + counts). Never edit past rows — corrections get a new row. Kill switches/env needed for a suite go in the evidence column.
