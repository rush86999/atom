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
| 2026-08-07 | `tests/api/test_admin_routes_part2.py` | GREEN | 38/38: NOT-NULL fixtures (`tenant_id` on 4×FailedRatingUpload + 7×ConflictLog + SkillCache); `count_unresolved_conflicts` mock (int(MagicMock())==1); order-insensitive asserts; ws_url/reconnect-message/governance-patch-target drift; `get_current_user` override key; rating-sync 503 body shape |
| 2026-08-07 | `tests/api/test_admin_routes_coverage.py` | GREEN | 72/72: same NOT-NULL class + `AdminUser.hashed_password`→`password_hash` (6 sites); ws_url/reconnect-message drift; `get_current_user` override; governance patch target |
| 2026-08-07 | `api/admin_routes.py` (test-exposed) | FIXED | stale `GovernanceCache` import path ×2 (dead `agent_governance_service` → `core.governance_cache`); `router.api_error`→`error_response` (missing method); `validation_error` missing `field` arg ×2 (TypeError→500); disable/enable didn't persist `websocket_enabled` (response said False, row stayed True) |
| 2026-08-07 | `tests/test_error_guidance.py` + `core/error_guidance_engine.py` (test-exposed) | GREEN | 42/42: engine wrote `CanvasAudit(canvas_id=None)` + `OperationErrorResolution` w/o `tenant_id` → NOT NULL + poisoned session (swallowed-exception PendingRollback cascade); fixed writes + `db.rollback()` on failure; test: `alternative_used` stale kwarg dropped, `error_code` positional, name-based suggestion assert, deterministic no-history test |
| 2026-08-07 | `tests/concurrent_operations/test_episode_concurrency.py` | GREEN | 8/8: `ChatMessage(workspace_id=...)` → `tenant_id` (7 sites; 8th was `Episode` needing `tenant_id`); service returns dicts (not AgentEpisode rows) — `r["id"]`, dict episodes for `_archive_to_lancedb`, per-agent counts from dicts; CanvasAudit `canvas_data`→`details_json`+NOT-NULL fields; sync `add_document` mock (async side_effect never awaited); graceful-degradation assert for LLM failure; per-op memory-leak bound |
| 2026-08-07 | `tests/core/test_communication_service_coverage.py`, `tests/test_graduation_integration.py` | GREEN | verified green already (23/23, 13/13 — prior round b0ca8b16b); no changes needed |
| 2026-08-07 | `tests/concurrent_operations/test_concurrent_agent_operations.py` | KNOWN-FAILING | 8 pre-existing failures, different class (AgentExecution `user_id` kwarg, CanvasAudit `canvas_data`, governance mocks, SQLite tx concurrency) — not in NOT-NULL scope |
| 2026-08-07 | `tests/test_auth_routes_coverage.py` | FIXED | 17 failing → 60/60. Root causes: (1) register provisions Tenant+Workspace → fixture only created users table (`no such table: tenants`) → `Base.metadata.create_all(tables=[User, Tenant, Workspace])`; (2) process-wide auth rate-limit singletons (login 10/min, register 3/5min) exhausted by suite → 429s → autouse `bypass_auth_rate_limits` patching `_login_limiter/_register_limiter/_refresh_limiter.check`; (3) refresh endpoint contract is `Body(..., embed=True)` — tests sent token as query param → 422 → switched to JSON body |
| 2026-08-07 | `tests/api/test_auth_2fa_routes_coverage.py` | GREEN | 35/35 (verified; `two_factor_*` columns still present in User model — tracker item stale, no changes needed) |

---

## Measured coverage (session stamps)
| Surface | Coverage | Statements/Files | Method | Date |
|---|---|---|---|---|
| Backend (unit+api+core+database+security+root chunks merged) | **54.0%** | 158,057 stmts / 1,018 files | `pytest -n 3 --timeout=300 --cov-append` chunked | 2026-08-07 |
| Frontend (full suite, 6,298 green) | **34.4% lines** | 732 files | `jest --coverage --maxWorkers=2` | 2026-08-07 |
| Mobile (full suite, 3,307 green) | **60.1% lines** | 80 files | `jest --coverage --maxWorkers=4` | 2026-08-07 |

## Known remaining work (next hunt targets — verified failing at last run)
- `tests/test_llm_service.py` — 12 mock-await fixture bugs (`TypeError: object tuple can't be used in 'await' expression`, Mock await in embeddings) — test-side
- `User.name` property setter in admin-route suites
- Other-model NOT NULL: `conflict_log.tenant_id`, `failed_rating_uploads.tenant_id`, `chat_messages.tenant_id`, `canvas_audit.canvas_id`, `SupervisionSession(supervision_feedback=...)` stale kwarg
- Collection errors: `No module named 'api.agent_routes'`, `api.agent_governance_routes`, `integrations/chat_orchestrator.py:54` (logger NameError in HEAD)
- Env-dependent (skip-candidates, verify first): Docker-required package-installer suites, `test_api_browser_routes` Playwright extras, `tests/unit/governance` graduation exams, security SQL-injection assertion drifts (400 vs 401)
- Full-suite single-run still memory-bound on this machine (~570MB free with concurrent sessions) — use chunked `-n 3 --timeout=300 --cov-append`, never `-n auto` >4 here

## Convention (append-only)
Every future round: add one row per fixed/tested file with date `YYYY-MM-DD`, round tag, evidence (test file + counts). Never edit past rows — corrections get a new row. Kill switches/env needed for a suite go in the evidence column.

---

## Session 2026-08-07 — Bug-Hunt Campaign (waves 1–4 + parallel stale-suite wave)

Campaign: 26 agent rounds (6 + 6 + 7 + 5 waves, then 8 parallel stale-suite agents + survey).
3,251 new tests (`tests/test_bughunt_*.py` + `tests/test_covpush_*.py`) — 0 failures combined at stamp time.

### Wave 1 — TDD bug hunt (47 real bugs fixed, 175 tests)
| Date | File | Status | Bug fixed |
|---|---|---|---|
| 2026-08-07 | `core/advanced_workflow_system.py` | FIXED | ParameterValidator optional-None/bool/multiselect bugs, start_workflow no type-validation, step-failure left COMPLETED, resume re-ran completed steps, create_parallel/conditional never persisted, duplicate-start TOCTOU |
| 2026-08-07 | `core/workflow_security.py` | FIXED | Critical-tool gates case/whitespace-sensitive → bypass (mixed-case Terminal_Command etc.) |
| 2026-08-07 | `core/sandbox_{fs,gate,tripwire,caps,policy}.py`, `core/provenance.py`, `core/llm/action_judge.py` | FIXED | `..` FS escape, killrun fail-open, spotlight injection, exfil regex bypass, cap TOCTOU, whitelist kill-switch dead, circuit breaker never re-opened, judge never-raises contract |
| 2026-08-07 | `core/llm/byok_handler.py`, `core/llm/cognitive_tier_service.py` | FIXED | cache_probability positional arg (learned caching never applied), wildcard-plan tool filter bypass, static-fallback phantom method, tier-string crash, stream str(e) leak |
| 2026-08-07 | `core/llm/gateway/gateway_service.py`, `api/openai_gateway_routes.py` | FIXED | body `model` ignored (auto-routed), ATOM_GATEWAY_DEFAULT_MAX_TOKENS dead, empty messages accepted, routing failures unaudited |
| 2026-08-07 | `core/capability_resolver.py`, `integrations/mcp_service.py`, `core/mcp_client.py` | FIXED | empty-whitelist allow-ALL, dotted-tool-name bypass, entity-context gate bypass, unbounded MCP response, kwargs-splat TypeError |
| 2026-08-07 | `core/graphrag/multi_hop_expansion.py`, `core/turn_fact_{extractor,vector_store}.py`, `core/entity_type_service.py` | FIXED | active_paths never advanced, SQL leak, workspace_id ignored (cross-workspace leak), float("high") drop, close() of caller session |
| 2026-08-07 | `tests/test_bughunt_{workflow,sandbox,byok,gateway,mcp,graphrag}.py` | TESTED | 79 tests (RED→GREEN) |

### Wave 2 — TDD bug hunt (24 bugs, 96 tests)
| Date | File | Status | Bug fixed |
|---|---|---|---|
| 2026-08-07 | `core/office_service.py` | FIXED | write_cell/modify_document/modify_slides arbitrary path write/create (route-only containment) |
| 2026-08-07 | `middleware/governance_middleware.py`, `core/data_taint_tracker.py`, `core/blueprint_sanitizer.py` | FIXED | service-name case bypass, masking case gap, HITL phantom pause, rate_limit=0 lifted, required_scopes unenforced, PII false negatives, credit-card over-tagging, denylist bypasses |
| 2026-08-07 | `core/identity/verifiable_credentials.py`, `core/federation/zero_trust_security.py` | FIXED | subject spoofing, borrowed-credential impersonation, deactivated DID auth, required_credentials dead |
| 2026-08-07 | `core/{episode_segmentation,episode_retrieval,episode_lifecycle}_service.py`, `core/agent_graduation_service.py` | FIXED | cross-session execution leak, cross-agent consolidation, LanceDB rank discarded, str(e) leaks ×3, graduation 50-floor unreachable |
| 2026-08-07 | `api/auth_routes.py` (mobile login) | FIXED | mobile login not wired to AuthRateLimiter |
| 2026-08-07 | `tests/test_bughunt_{gatekeeper,auth,episodes,federation,office}.py` | TESTED | 96 tests (RED→GREEN) |

### Wave 3 — coverage push (all modules ≥90%; 2,031 tests)
| Date | Module family | Status | Result |
|---|---|---|---|
| 2026-08-07 | `core/atom_meta_agent.py` (94%), `atom_agent_endpoints.py` (90%), `agents/{queen,king,autoresearch,skill_creation}` (94–98%) | FIXED | 11 bugs: WORKFLOW route TypeError, audit ImportError, parallel-branch unreachable, search_emails no-op stub, template_manager phantom import, ChatMessage .get crash, complexity enum .lower() 503, ownership 403 swallowed, SSRF obfuscation |
| 2026-08-07 | `core/agent_world_model.py` (100%), `agent_graphrag_service.py` (100%), `agent_social_layer.py` (100%), `agent_learning_enhanced.py` (100%) | FIXED | 13 bugs: un-awaited GraphRAG query, phantom success_rate, SQLite JSON ops crash ×4, canvas outcome always False, social attr drift ×3 |
| 2026-08-07 | `core/fleet_orchestration/*` (82–100%), `agent_promotion_service` (98%), `background_agent_runner` (100%), `agent_request_manager` (91%) | FIXED | 20 bugs: phantom-schema crashes ×10, tenant_id NOT NULL ×6, naive/aware datetime ×4, status-case mismatch |
| 2026-08-07 | `core/board_*` (100%), `core/ai_trigger_coordinator.py` (100%), `core/advanced_workflow_system.py` (100%) | FIXED | cursor pagination broken, self.db never init (triggers dead), job_queue phantom import, flush-rollback re-raise |
| 2026-08-07 | `core/auto_dev/*` (94–100%), `agent_evolution_loop` (98%), `burnout_detection_engine` (98%) | FIXED | seg.metadata class-object crash, fitness JSON in-place mutation (silent loss), tz-aware deadline crash, trace evolution_type NOT NULL |
| 2026-08-07 | `core/ingestion_pipeline.py` (95%), `hybrid_data_ingestion` (92%), `lancedb_handler` (85%), `ingestion_webhooks` (87%) | FIXED | 9 bugs: logger kwargs TypeError (webhook path dead at INFO), 18+34 debug prints, phantom is_active column, invalid kwargs, zoho list 500, Outlook handshake 405, dual_vector missing |
| 2026-08-07 | `backend/tools/` (96% layer) | FIXED | media/smarthome never registered (ImportError), ffmpeg loop crash, FeatureFlags phantom attr |
| 2026-08-07 | `tests/test_covpush_{meta,endpoints,agents,world,graphrag,learning,social,fleet,fleet_scaling,board,board_workflow,autodev*,ingestion*,miniapp,skill_registry,tools_*}.py` | TESTED | 2,031 tests (all green) |

### Wave 4 — workflow/ingestion/mini-app/integrations/learning (1,108 tests)
| Date | File | Status | Bug fixed |
|---|---|---|---|
| 2026-08-07 | `core/workflow_engine.py` (6.9→89%), `workflow_debugger` (83%), `workflow_analytics_engine` (89%), `workflow_versioning_system` (94%) | FIXED | 18 bugs: connection_id positional (9 services crashed), self.db never init, 3 phantom service imports, error-dict dead check, continue_on_error infinite loop, JSON in-place mutation loss, ~/. path crash, cache freshness, wrong columns ×2 |
| 2026-08-07 | `core/ingestion_pipeline.py` + webhooks (see wave 3 row) | FIXED | (listed above) |
| 2026-08-07 | `core/mini_app_service.py` (96%), `api/mini_app_routes.py` (98%), `core/skill_registry_service.py` (95%) | FIXED | 7 bugs: asset upload authz bypass (write-what-where), db.enabled gate gap, governance fail-open, tenant_id NOT NULL, npm analyzer 2-arg, LLM scaffold phantom import, record get-op id |
| 2026-08-07 | `backend/integrations/` — **8 unparseable files repaired** (enterprise_security/unified/quickbooks/video/voice/workflow_automation/zendesk/whatsapp) | FIXED | root cause: commit d99541d82 deleted `try:` lines + injected junk (103 handlers); ~100 methods restored; 49% avg coverage after |
| 2026-08-07 | `core/learning_llm_router.py` (99%), `episode_service` (94%), `conductor_agent` (98%), `per_model_router` (97%) | FIXED | retry-then-fail marking, failed-dict COMPLETED, compensation steps stuck RUNNING, RLHF feedback broken (missing model columns), capability lowercase parse, readiness denominator |

### Follow-up rounds (after waves)
| Date | File | Status | Bug fixed |
|---|---|---|---|
| 2026-08-07 | `core/governance_engine.py` | FIXED | `db = self.db or get_db_session()` = context manager not Session → every external-contact governance check crashed; `_session_scope()` (nullcontext for injected) |
| 2026-08-07 | `core/skill_adapter.py` | FIXED | analyze_package_scripts 2-arg TypeError (every npm install); langchain-absent BaseTool stub plain class → pydantic BaseModel (CommunitySkillTool unconstructable) |
| 2026-08-07 | `core/models.py` (`UUID`) | FIXED | SQLite result str→uuid.UUID mismatch → INSERT..RETURNING sentinel KeyError (batch board inserts crashed) |
| 2026-08-07 | `core/autonomous_supervisor_service.py` | FIXED | monitor hardcoded poll/max-duration (30-min suite hangs); `execution.output_summary` phantom column → every completed run yielded monitoring_error |
| 2026-08-07 | `core/mini_app_integration_dispatch.py` | FIXED | execute_operation not awaited → coroutine in data (native dispatch dead); module was untracked while tracked code imported it |
| 2026-08-07 | `core/models.py` (`User` 2FA columns) + `20260807c` migration | FIXED | 2FA columns commented out Apr 29 → every 2FA endpoint AttributeError; login TOTP silent-off |
| 2026-08-07 | `alembic/versions/20260807_merge_heads.py` | FIXED | 6 divergent heads → `upgrade head` failed on PG |
| 2026-08-07 | `core/productivity/notion_service.py` | FIXED | OAuth used OAuthToken (server model) — provider/access_token don't exist → Notion OAuth dead; now IntegrationToken + encrypt/decrypt |
| 2026-08-07 | `core/models.py` (`ScalingOperation`) + `20260807d` | FIXED | model missing → fleet scaling persist silent no-op |
| 2026-08-07 | `core/models.py` (`AgentExecution.output_summary`) + `20260807e` | FIXED | column in DB (4ea149ecf75f) but not model → 5 writers silently lost data |
| 2026-08-07 | `tests/test_bughunt_{governance,skill_adapter,uuid_sqlite,supervisor,miniapp_dispatch,notion_oauth,scaling_operations}.py` | TESTED | 24 tests (RED→GREEN) |

### Parallel stale-suite wave (8 agents + survey — ~44 suites + 28 files)
| Date | Cluster | Status | Result |
|---|---|---|---|
| 2026-08-07 | auth/agent cluster (6 files) | FIXED | 2fa_routes 17F→35P · auth_routes 17E→30P · agent_routes_coverage 146E→75P · api_agent_endpoints 28F→41P · enterprise_user_mgmt 34F→34P · atom_agent_endpoints_core 13F→52P |
| 2026-08-07 | agent-execution cluster (5 files) | FIXED | execution_service 35E→36P · unit execution 13E→17P · coordination 10E→15P · agent_routes 30F→63P · guidance_routes 42P |
| 2026-08-07 | debug/api cluster (5 files) | FIXED | debug_routes 35E→43P · debug_alerting 20E→21P · api_database_transactions 5E→18P · canvas_routes 23F→24P |
| 2026-08-07 | ab/rating cluster (6 files) | FIXED | ab_testing 55F→55P · rating_sync 27P · dashboard 28→29P · feedback_phase2 17P · apar_engine 29P+32P |
| 2026-08-07 | unit/board cluster (7 files) | FIXED | core_services_batch 44→45P · browser_tool 20F→106P · proactive_messaging 14P · productivity_tool 20P · fleet_scaler 10F→20P · board_comment/decomposer 37P |
| 2026-08-07 | ingestion/workflow cluster (5 files) | FIXED | auto_doc_ingestion 31F→47P · industry_workflow 20F→34P · round19_security 17F→20P · advanced_wf_coverage 14F→45P · formula_memory 17F→29P |
| 2026-08-07 | byok/meta cluster (5 files) | FIXED | byok_handler 67F→197P · expanded 10F→29P · atom_meta_agent 12F→39P · integration_gateway 10F→34P · provider_registry_api 10F→11P |
| 2026-08-07 | episodes/startup cluster (4 files) | FIXED | graduation_integration 13E→13P · communication_coverage 12E→23P · graduation_exam 10F→26P · dead debug_log_aggregator startup hook removed (17 boot errors) |
| 2026-08-07 | survey 20-file sweep (+8 database neighbors) | FIXED | 135 failures → 1 (fixed: margin_service getattr, resource_manager else-branch, staffing_advisor phantom column, fpa datetime, spotify OAuthToken→IntegrationToken, sonos unbound, media_tool phantom resolver/governance, recording_review canvas_id, custom_components stale columns) |

Real product bugs from parallel wave (highlights): **11 unauthenticated analytics_dashboard routes** · PATCH /agents 500 (duplicate schema) · get_operation 500 (wrong column) · APInvoice dataclass missing fields (AP flow dead) · business_agents phantom import · formula_memory saas.models ImportError · graduation_exam dead import · proactive_messaging TypeError · canvas governance 500→403 · chat_orchestrator logger NameError · byok keys unvalidated · device_capabilities router unmounted (restored next commit).

### Test-infra fixes (session-wide)
| Date | File | Status | Fix |
|---|---|---|---|
| 2026-08-07 | `tests/test_skill_adapter_{npm,cli}.py`, `tests/test_skill_adapter.py` | FIXED | module-level `sys.modules[...]=MagicMock()` leaked for the whole session, breaking ANY suite collected after (e.g. covpush_skill_registry 32/32 alone, 8F after adapter files) → per-test autouse save/restore fixtures |
| 2026-08-07 | `tests/conftest.py` | FIXED | db_session nested-transaction rollback could not undo explicit commit()s → cross-test DB pollution; per-test table wipe added |
| 2026-08-07 | `tests/test_autonomous_supervisor_service.py` | FIXED | fixture used read-only properties proposed_action/reasoning as kwargs; stale output_summary kwarg; 30-min hangs → 15s |

## Known remaining work (verified at last run — updated 2026-08-07)
- `core/models.py` `OAuthToken` — server-side model; verify `api/oauth` routes don't use stale columns (Notion/Spotify moved to IntegrationToken; sweep remaining writers)
- `tests/test_cognitive_tier_e2e.py` — 11 collection ERRORS remain after the survey-sweep alignment (23 pass / 11 error; the stale `CognitiveTierPreference` kwargs were fixed but 11 tests still fail at setup — next target)
- Full-suite run: still memory-bound with concurrent sessions — chunked `-n 3 --timeout=300 --cov-append`

### Resolved 2026-08-07 (late R81 wave — pushed `5ed9746a9`)
| Item | Result | Evidence |
|---|---|---|
| `tests/test_llm_service.py` (12 mock-await bugs) | FIXED → 86/86 | AwaitableResult dual-mode shape asserted; embedding seam retargeted to handler; ranked-provider asserts on wrapper |
| `tests/test_auth_routes_coverage.py` (17F, no tenants table) | FIXED → 60/60 | fixture create_all [User, Tenant, Workspace]; autouse rate-limit bypass; refresh body `embed=True` contract |
| `tests/test_auth_2fa_routes_coverage.py` | VERIFIED-OK | already green (35/35) — two_factor_* columns still exist; tracker item was stale |
| `conflict_log/failed_rating_uploads/SkillCache tenant_id` NOT NULL | FIXED → 38/38 + 72/72 | + real admin_routes bugs: dead GovernanceCache import path ×2, nonexistent `router.api_error`, `validation_error` missing `field` arg, `websocket_enabled` not persisted |
| `canvas_audit.canvas_id/tenant_id` NOT NULL | FIXED → 42/42 | real bug: `error_guidance_engine._create_audit` wrote canvas_id=None + track_resolution omitted tenant_id → poisoned session |
| `chat_messages.tenant_id` | VERIFIED-OK | already green (23/23, prior round) |
| `SupervisionSession(supervision_feedback=)` | VERIFIED-OK | already green (13/13, real field is supervisor_feedback) |
| `ChatMessage(workspace_id=)` concurrency | FIXED → 8/8 | workspace_id→tenant_id (8 sites), dict-shaped service contracts |
| `chat_orchestrator.py` logger NameError / `api.agent_routes` imports | VERIFIED-OK | in HEAD; real collection failure was `test_chat_attachment_flow.py` sys.modules mock (fixed) |
| `User.name` setter | FIXED (test-side) | 3 Mock-fixture files → first_name/last_name |
| `advanced_workflow_system.ParameterValidator` ReDoS | FIXED | MAX_REGEX_LENGTH=256 cap before re.match (still dead code, not wired — kept as guard) |
| Combined verification | **222 passed / 0 failed** | llm_service + auth_routes + 2fa + episode_concurrency + error_guidance + graduation_integration |

### Chat-orchestrator collection sweep (known-remaining-work #2/#3 verification)
| Date | File | Status | Evidence |
|---|---|---|---|
| 2026-08-07 | `integrations/chat_orchestrator.py` | VERIFIED-OK | logger defined at module level (line 17); `python -c "import integrations.chat_orchestrator"` clean — no NameError in HEAD |
| 2026-08-07 | `api/agent_routes.py`, `api/agent_governance_routes.py` | VERIFIED-OK | both modules exist + import clean; 17-file sweep of all `api.agent_routes|agent_governance_routes` importers → 0 collection errors |
| 2026-08-07 | `tests/standalone/test_chat_attachment_flow.py` | FIXED (test-side) | was the only collection failure (SyntaxError via `Optional[LLMModel]`): removed `sys.modules['core.database']=MagicMock()` (mocked Base breaks LLMModel class-def → registry service import); patch target → `core.chat_session_manager.get_chat_session_manager` (lazy import); `ChatIntent.AI_ANALYTICS`→`DATA_ANALYSIS` (enum has no AI_ANALYTICS). 1/1 pass, exit 0 |
| 2026-08-07 | `tests/test_user_templates_endpoints.py`, `tests/test_learning_plan_routes.py`, `tests/test_competitor_analysis_routes.py` | FIXED (test-side) | `User.name` is read-only property (no setter, `core/models.py:485`); 3 decorative `user.name=` Mock-fixture hits → `first_name`/`last_name`; behavior-neutral (failure sets unchanged: 3F/8P, 4F/13P, 1 skipped) |

### Round 2026-08-07 late — tracker-gap items (canary + OAuth sweep + e2e)
| Date | File | Status | Bug fixed |
|---|---|---|---|
| 2026-08-07 | `core/advanced_workflow_system.py` | FIXED | ReDoS canary closed: `ParameterValidator` pattern rule passed user regex to `re.match` uncapped → `MAX_REGEX_LENGTH=256` guard; test_round19 canary RED→GREEN (128 workflow tests green) |
| 2026-08-07 | `tests/test_cognitive_tier_e2e.py` | FIXED | 17F/6E → 32/32 stable (hermetic in-memory fixture): HEAVY/COMPLEX enum drift, `record_cache_outcome(provider=)` → prompt-hash API, `should_escalate(workspace_id=)` → `(bool, reason, target)`, removed methods, `monthly_budget_usd` → `monthly_budget_cents` |
| 2026-08-07 | `core/llm/escalation_manager.py:387` | FIXED | HIGH: `EscalationLog(tenant_id=...)` — model has no such column → every escalation log silently lost (exception swallowed) |
| 2026-08-07 | `core/llm/cognitive_tier_service.py:369` | FIXED | `monthly_budget_cents` dead knob — only `max_cost_per_request_cents` was enforced; now a ceiling |
| 2026-08-07 | `api/learning_plan_routes.py:519` | FIXED | Notion token lookup queried `OAuthToken` (server model, no `provider`) → AttributeError on every plan-with-notion export; now `IntegrationToken` + decrypt (sweep: spotify fixed earlier, social_media_routes comments only, oauth_routes correct client_id usage) |
| 2026-08-07 | `tests/test_bughunt_learning_plan_oauth.py` | TESTED | source-inspection regression test (1 test, RED→GREEN) |
| 2026-08-07 | `tests/test_llm_service.py` | GREEN | 86/86 (verified — fixed by e25f1859f sweep; AwaitableResult + embedding seams) |

### Round 2026-08-07 — stale-unit-test alignment (episode lifecycle/retrieval, student training, promotion)
| Date | File | Status | Fix |
|---|---|---|---|
| 2026-08-07 | `tests/unit/test_episode_lifecycle_service.py` | FIXED (test-side) | 1F/3P/26E → 30/30. Shared-dev-DB fixture → fresh temp SQLite (unit conftest pattern); AgentRegistry fixtures missing NOT NULL `module_path`/`class_name`; stale decay assertions: access_count no longer bumped by maintenance decay (5 not 6), formula `min(1, days/90)` saturates at 1.0 for 100-day episodes (not <1.0, not 0.5 at 90d) |
| 2026-08-07 | `tests/unit/test_episode_retrieval_service.py` | FIXED (test-side) | 4P/19E → 23/23. Temp-SQLite fixture; Episode kwargs stale (`summary`/`metadata`/`user_id`/`ended_at` don't exist) → `task_description`/`metadata_json`/`completed_at` + NOT NULL `tenant_id`/`maturity_at_time`/`outcome`; `retrieve_contextual(query=, context=)` → `current_task=`; `patch(..., new_callable=AsyncMock())` (instance → bare coroutine, TypeError) → `new_callable=AsyncMock`; nonexistent `_calculate_contextual_score` patch removed; ordering assertion uses serialized-dict `["started_at"]` |
| 2026-08-07 | `tests/unit/test_student_training_service.py` | FIXED (test-side) | 3F/5P/16E → 24/24. Temp-SQLite fixture; BlockedTriggerContext/TrainingSession/AgentProposal fixtures rebuilt to real columns + NOT NULL fields (agent_name, agent_maturity_at_block, trigger_source, tenant_id, proposal_id, supervisor_id…); `create_training_proposal(blocked_trigger_id=)` → object arg, not-found → `pytest.raises(ValueError)`; `approve_training(approved_by=)` → `user_id=`, status `scheduled` not `in_progress`; TrainingOutcome new ctor (performance_score/supervisor_feedback/errors_count/tasks_completed/total_tasks/…) + dict result; `estimate_training_duration(scenario_type=)` → `(capability_gaps, target_maturity)`, `estimated_hours`/`confidence` fields; `_identify_capability_gaps(agent, trigger)` + `_generate_learning_objectives(agent, …)` signatures; learning-rate tests now seed real TrainingSession rows (old patch target `_get_similar_agents_training_history` was dead), slow-learner floor 0.5 clamp → `rate < 1.0`; `_select_scenario_template` returns category-mapped template (General Operations/Process Automation), not "streaming" |
| 2026-08-07 | `tests/unit/test_agent_promotion_service.py` | FIXED (test-side) | 8P/13E → 21/21. Temp-SQLite fixture; sorted-suggestions test seeded a 2nd agent (side_effect consumed per DB candidate); patch target `get_feedback_summary` → `get_agent_feedback_summary` with real contract keys (`total_feedback`/`positive_count`/`average_rating`/`feedback_types`); result key `gaps` → `criteria_failed`; readiness_score is 0–1 fraction not 0–100; kwargs `agent_id=` assertion; time-at-level test has no service criterion → asserts criteria_failed non-empty |
| 2026-08-07 | `tests/test_bughunt_episodes.py` | VERIFIED-OK | 9/9 still green after alignment (read-only suite) |
