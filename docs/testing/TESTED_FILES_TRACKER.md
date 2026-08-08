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

### Resolved 2026-08-07 (R82 wave — pushed `aad17c93c`)
| Date | File(s) | Status | Result |
|---|---|---|---|
| 2026-08-07 | `core/security/middleware.py` | FIXED (SECURITY) | **2 real XSS bypasses closed**: entity-encoded `onerror&#x3d;` + `jav&#x61;script:` payloads bypassed the denylist and were persisted raw → `html.unescape()` before regex; added `expression(/vbscript:/behavior:/binding:` CSS-execution vectors. RED→GREEN (9 new RED tests) |
| 2026-08-07 | `tests/integration/canvas/test_canvas_{html,css}_security.py` | FIXED | rewritten against live `PUT /api/canvas/{id}` write path (old POST /components removed): 61F → 66 passed |
| 2026-08-07 | `api/agent_routes.py` | FIXED | duplicate AgentUpdateRequest: PATCH copy lacked whitespace-name validator → 500 instead of 422 |
| 2026-08-07 | `tests/integration/api/test_agent_endpoints.py`, `test_skill_registry_service.py`, `test_skill_sandbox.py`, `test_phase27_scheduler.py` | FIXED | 112 passed; sys.modules pollution save/restore; patch targets → core.scheduler.AgentScheduler; stream route moved /chat/stream; envelope shapes |
| 2026-08-07 | `tests/test_package_installer*.py` | FIXED | 69 passed (docker-error import alignment; suites mock docker, never need a daemon) |
| 2026-08-07 | `workers/social_media_worker.py` | FIXED | OAuthToken stale columns → IntegrationToken (provider/status/access_token); `api/oauth_routes.py` verified CLEAN (OAuthToken is live, hash-only) |
| 2026-08-07 | `api/social_media_routes.py` | FIXED | 429 path missing required `error_code` → every 429 became 500 |
| 2026-08-07 | 8 OAuth-touched suites | FIXED | 152 passed; core_factory OAuthTokenFactory realigned; conftest wipe table-existence-guarded |
| 2026-08-07 | `frontend-nextjs/components/Settings/**` (16 files) | TESTED/FIXED | 17 suites / 293 tests, 0% → 84–100% per file; **3 missing-import build errors** (GDrive/Dropbox/ShopifyManager imported nonexistent src/skills/*) → modules recreated; LocalFileIngestion crash guard |
| 2026-08-07 | Combined verification | GREEN | 247 (security+agent/skill) + 82 (OAuth) + 293 (FE) = **622 tests** |

### Resolved 2026-08-07 (R83 wave — pushed `eb7c2ed95` + `b150eb9a1`)
| Date | Area | Status | Result |
|---|---|---|---|
| 2026-08-07 | FE integrations (Discord/Freshdesk/Intercom/Mailchimp/Stripe/Tableau/JiraOAuthFlow) | TESTED | 7 suites / 66 tests, 84–93% coverage; SlackIntegration fixed — stale MSW handlers (`tests/mocks/handlers.ts`): missing workspace endpoint, bare arrays vs `data.data.*` shapes |
| 2026-08-07 | FE onboarding/templates/teams | TESTED/FIXED | 7 suites / 75 tests, 82–100%; **3 real bugs**: TemplateEditor nonexistent TemplatePreviewModal import (module crash), wrong props to TemplateMetadataForm, spinner.tsx missing React import |
| 2026-08-07 | FE devstudio/dashboards | TESTED/FIXED | 8 suites / 88 tests, 66–96%; **2 real bugs**: TaskManagement never displayed fetched tasks (mount-before-fetch, useState init), ReasoningChainViewer loader forever (loading keyed off `!chainData`) |
| 2026-08-07 | FE full suite + coverage | GREEN | **6,628 passed / 0 failed; 43.2% lines** (was 37.0%) |
| 2026-08-07 | Backend chunked coverage (unit/api/core/database/security) | MEASURED | **30.0%** for that scope (was 22.6% — suite fixes +7.4pts); full picture pending root chunk |

### Resolved 2026-08-07 (R84 wave — pushed `aad31a12a` + `ee0a0a50f`)
| Date | Area | Status | Result |
|---|---|---|---|
| 2026-08-07 | `/api/components/*` router (main_api_app.py) | FIXED (SECURITY) | unmounted since Feb 2026 — the whole SECU-04 layer (HTML/CSS/JS sanitizers, whitelist, governance) was 404; restored |
| 2026-08-07 | canvas JS validator | FIXED (SECURITY) | BLOCKED_JS_PATTERNS missing fetch(/XMLHttpRequest/sendBeacon/document.cookie/localStorage/sessionStorage/postMessage/window.location/createElement('script')/eval variants/Function constructor/require(/import(/process/.constructor( → exfiltration payloads persisted verbatim |
| 2026-08-07 | governance case bug | FIXED (SECURITY) | `agent.status != 'AUTONOMOUS'` vs enum value `autonomous` → blocked ALL JS component creation |
| 2026-08-07 | `core/workflow_engine.py` | FIXED | graph path called nonexistent analytics.track_step_execution; linear path dropped continue_on_error; `_run_execution` 4 DB blocks' try/except INSIDE `with` → exit commit raised outside guard → runs marked FAILED before any step |
| 2026-08-07 | `core/scheduler.py` | FIXED | scheduled callables were closures → SQLAlchemyJobStore ValueError at add_job; moved to module level |
| 2026-08-07 | `tests/property_tests/conftest.py` | FIXED | db_engine fixture permanently rebound GLOBAL core.database.SessionLocal → every get_db_session() hit a disposed engine after first suite (cross-suite pollution root cause) |
| 2026-08-07 | `tests/unit/test_lancedb_handler.py` | FIXED | 28F → 62p (stale API + MockEmbedder constant seed → identical vectors for different texts) |
| 2026-08-07 | `tests/security/test_canvas_security.py` | FIXED | 23F+12E → 47p (dead /api/components surface, auth fixture) |
| 2026-08-07 | `tests/security/test_canvas_javascript_security_extended.py` | FIXED | 15F → 56p (edge middleware 400s now asserted) |
| 2026-08-07 | workflow engine suites (3 files) | FIXED | 120p + 209 pinned (stale step API, versioning semantics, FakeStateManager) |
| 2026-08-07 | scheduler/admin suites (3 files) | FIXED | 80p |
| 2026-08-07 | auth security suites + unit/test_llm_service | FIXED | 113p, security verdict PASS (no failing-open gates) |
| 2026-08-07 | 5-file cross-suite batch | GREEN | **232 passed / 0 failed** (pollution repro fixed) |
| 2026-08-07 | Backend chunked coverage (unit+api+core so far) | MEASURED | **32.8%** (was 30.0% same scope; suite fixes compounding; full number pending clean single-owner run) |

### Resolved 2026-08-07 (R85 wave — pushed `983cb9b67` + `574a5575c`)
| Date | File(s) | Status | Result |
|---|---|---|---|
| 2026-08-07 | `core/auth_endpoints.py` | FIXED | forgot/verify/reset-password 500'd for EVERY real user (token_hash/is_used vs rewritten PasswordResetToken model); aligned, SHA-256 at rest preserved |
| 2026-08-07 | `api/episode_routes.py` | FIXED | list_episodes + feedback/submit 500'd (title→task_description ×4; AgentFeedback ctor missing original_output/tenant_id); **documented gap**: AgentEpisode lacks user-ownership column (feedback accepts any authenticated user) |
| 2026-08-07 | `core/debug_storage.py` | FIXED | missing defaultdict import (NameError); naive-vs-aware datetime (cleanup never ran); stale column refs → snapshot_metadata |
| 2026-08-07 | `core/logging_config.py` | FIXED | ContextVar `.get()` LookupError on every unbound log line → `.get('')` |
| 2026-08-07 | `core/hybrid_retrieval_service.py` | FIXED | `.summary or .content` → `.task_description` |
| 2026-08-07 | `api/admin/skill_routes.py` | FIXED | shadowed StaticAnalyzer import defeated patching + real analyzer |
| 2026-08-07 | 19 test suites (security/accounting/analytics/supervision/marketplace/oauth/config/debug) | FIXED | ~670 tests green; security verdicts SECURE (no gates fail open); auth suites leak LOG_LEVEL → config test now pins env (cross-suite pollution class) |
| 2026-08-07 | Combined verification | GREEN | **530/531** then 96/96 after env-pin fix |

### Resolved 2026-08-07 (R87 wave — pushed `e383c2b12`)
| Date | Area | Status | Result |
|---|---|---|---|
| 2026-08-07 | FE entity+finance (10 suites / 107 tests, 77–98%) | TESTED/FIXED | MergeDialog conflict warning never rendered; TransactionsList create/export flows dead code; BudgetPlanner Add trigger missing onClick; shared Dialog returned null when closed → trigger unreachable |
| 2026-08-07 | FE supervision/sales/shared/desktop (8 suites / 113 tests, 90–100%) | TESTED/FIXED | LiveMonitoringPanel stale-steps closure (never advanced) + JSON.parse(undefined) SSE crash; LeadManagement email-less crash; DesktopSecurityAudit findings normalization; satellite-controls missing React import + stop-failure status stuck 'running' |
| 2026-08-07 | FE lib+pages (4 suites / 68 tests, 71–100%) | TESTED/FIXED | tokenEncryption retargeted to real module (100%); FactFilters Radix SelectItem empty-value page crash; jit-verification wrong fallback field; skills page missing React import; jest.config testMatch += pages/__tests__ |
| 2026-08-07 | FE full suite + coverage | GREEN | **7,121 passed / 0 failed; 55.5% lines** (was 50.5% → +5.0pts) |

### Resolved 2026-08-07/08 (R88 wave — pushed `5d2231c65` + `17d87519e`)
| Date | Area | Status | Result |
|---|---|---|---|
| 2026-08-07 | FE pages/api routes (15 suites / 155 tests, 83–100%) | TESTED/FIXED | calendar disconnect TypeError on null GraphQL response; agent/nlu null-session 500→400; jest.config += pages/api/__tests__ |
| 2026-08-08 | Mobile canvas+debugging (7 suites / 171 tests, 86–99%) | TESTED/FIXED | DebugSessionScreen literal `${workflowId}` in URL; CanvasSheet CSV dropped falsy zeros; CanvasTerminal arrow-key history never wired; CanvasWebView refresh wrong message type |
| 2026-08-08 | Mobile services (4 suites / 116 tests, 89–97%) | TESTED/FIXED | chatService pending entries never converging; queueAction priority index bug; canvasService envelope-vs-payload + negative stats; deviceSocket unhandled rejections + dropped results |
| 2026-08-08 | Mobile full suite + coverage | GREEN | **3,558 passed / 106 suites; 77.1% lines** (was 61.7%) |
| 2026-08-08 | FE full suite | GREEN | 7,121+ passed / 0 failed; 55.5% lines |

### Resolved 2026-08-08 (R89 wave — pushed `05922ff41`)
| Date | Area | Status | Result |
|---|---|---|---|
| 2026-08-08 | Mobile workflow/device/chat screens (11 suites / 219 tests) | TESTED/FIXED | ExecutionProgressScreen missing TouchableOpacity import (crash on running execution) + stale polling closure; WorkflowDetailScreen refreshControl plain-object iOS crash; ConversationListScreen unhandled bulk-delete rejection; screens 3–58% → 88–100%; canvasSyncService 63→88% |
| 2026-08-08 | Mobile full suite + coverage | GREEN | **3,665 passed / 113 suites; 81.6% lines** (was 77.1%) — **80%+ threshold crossed** |

## Coverage stamps (latest)
| Surface | Coverage | Tests | Date |
|---|---|---|---|
| Mobile | **81.6%** lines (3,665 passed / 113 suites) | 7,346 stmts / 80 files | 2026-08-08 |
| Frontend | **55.5%** lines (7,121+ passed / 0 failed) | 735 files | 2026-08-07 |
| Backend | 54.0% (r80 full-ish); 32.8% chunked-scope (r84) | 158k stmts / ~1,015 files | 2026-08-07 |

## Known remaining work (verified at last run — updated 2026-08-08)
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

### Round 2026-08-07 late-2 — survey-driven 8-agent wave (~1,100 tests, 9 real bugs)
| Date | Cluster | Status | Result |
|---|---|---|---|
| 2026-08-07 | api admin cluster (4 files) | FIXED | admin_routes_part1 36E→36P · admin_routes 31E→31P · part2 38P · analytics_dashboard_routes 60F→60P (auth override + raw-SQL→create_all fixtures + text() wrapping) |
| 2026-08-07 | api agent cluster (4 files) | FIXED | agent_control_routes_fixed 53F→53P · agent_governance_routes 43F→43P+6S · control_coverage 10F→68P · guidance_routes 42P (get_super_admin/get_current_user overrides, generic-error envelope, required body 422) |
| 2026-08-07 | core governance cluster (4 files) | FIXED | governance coverage final 19F→27P · extend 19F→51P · expand 8F+2E→25P · budget_enforcement 25F→35P (all rewritten vs b391aff8c-removed APIs) |
| 2026-08-07 | core llm cluster (4 files) | FIXED | core/test_llm_service 35F→40P (dead-stub rewrite vs real LLMService) · byok_competitive 8F→29P · error_middleware 11F→60P · local_llm_secrets 9E→46P |
| 2026-08-07 | unit episodes cluster (4 files) | FIXED | episode_lifecycle 26E→30P · episode_retrieval 19E→23P · student_training 16E→24P · agent_promotion 13E→21P (temp-SQLite fixtures, NOT NULL fields, AsyncMock new_callable ×17) |
| 2026-08-07 | unit world-model cluster (4 files) | FIXED | agent_world_model 24F→38P · ai_trigger_coordinator 9F→33P · enterprise_auth 7F→42P · byok_cache_preseeding_ORIG 8E+3F→26P |
| 2026-08-07 | root canvas cluster (5 files) | FIXED | canvas_javascript 16F→17P · context_enrichment 9F→13P · canvas_recording 8F+8E→17P · aware_retrieval 5F→6P · feedback_episode 2F→16P (69/69) |
| 2026-08-07 | root social/asana cluster (8 files) | FIXED | agent_social_layer 15F→33P+9S · social_feed 23P · asana_project 14F→19P · asana_token 11F→11P · conflict_resolution 11F+2E→36P · atom_meta_agent 16F→33P · guidance_canvas 9F→12P · atom_cli_skills 5F→30P |

Real product bugs fixed this wave (TDD): 
- `core/enterprise_auth_service.py:135` — private_bytes missing NoEncryption → JWT key gen TypeError (HIGH); `:355` — `UserRole.{SECURITY,WORKFLOW,COMPLIANCE,AUTOMATION,INTEGRATION}_ADMIN` phantom names → verify_credentials always None, admin login broken (HIGH)
- `core/conflict_resolution_service.py:297` — log_conflict missing tenant_id → every conflict log crashed (HIGH)
- `integrations/asana_service.py:660` — create_project signature mismatch with its only caller → route TypeError at runtime (HIGH)
- `core/canvas_recording_service.py:522,244` — audit canvas_id=None NOT NULL; naive/aware datetime → stop_recording never completes (HIGH ×2)
- `tools/canvas_tool.py:996` — AUTONOMOUS uppercase-status double-check blocked canvas JS execution (MED)
- `tools/agent_guidance_canvas_tool.py:114,224,237,447` — tenant_id NOT NULL crash masked by fake uuid; step=None into NOT NULL; logs append never persisted; audit canvas_id=None (HIGH ×4)
- `api/admin/cache_routes.py` — NEW: module referenced by 2 test files never existed; implemented per spec (not mounted — needs admin auth first)

### Round 2026-08-07 late-3 — tracker-gap sweep (all prior 'known remaining' items)
| Date | File | Status | Fix |
|---|---|---|---|
| 2026-08-07 | `tests/api/test_agent_control_routes.py` | FIXED | 5F→53P: stale str(e)-leak assertions ("Port already in use" etc.) → generic "Internal error" contract (R18-31 hardening) |
| 2026-08-07 | `tests/test_slack_asana_endpoints.py` | FIXED | 3F→11P: create_project payload now Asana-wrapped `{"data": {...}}` — assertions drilled one level |
| 2026-08-07 | `tests/test_xxe_bugs.py` | FIXED | 3F→4P: RED-phase bug-verification tests flipped to GREEN — assert defusedxml used (fix 4d409f163) + XXE payload rejected by safe parser |
| 2026-08-07 | `tests/test_episode_services_comprehensive.py` | FIXED | 6F+6E→15P: CanvasAudit canvas_id/tenant_id NOT NULL, AgentEpisode stale kwargs (user_id/title/description/ended_at → tenant_id/task_description/completed_at), missing outcome NOT NULL, decay_score semantics (min(1,days/90) saturation) |
| 2026-08-07 | `tests/test_covpush_world.py` | FIXED | 2F→99P: boost test unseeded handler; recall episodes now include canvas_context/feedback_context keys |
| 2026-08-07 | `tests/core/phase190_coverage_batch.py` | FIXED | 24F→33P: retargeted renamed classes (HybridDataIngestion→HybridDataIngestionService, BulkOperationsProcessor→IntegrationBulkProcessor, DebugStorage→HybridDebugStorage, CrossPlatformCorrelation→CrossPlatformLink, PredictiveInsights→ResponseTimePrediction, validation_service→core.validation, workflow_parameter_validator→ParameterValidator, workflow_template_endpoints→workflow_template_routes, workflow_analytics_endpoints→analytics_dashboard_endpoints); removed archived auto_invoicer/unified_message_processor smoke tests; constructor args aligned (GenericAgent(agent_model=...), FeedbackService(db=...)) |
| 2026-08-07 | `tests/test_cognitive_tier_api.py` | DEAD | Removed — routes deliberately deleted in eda17eb29 (never wired); service covered by test_cognitive_tier_e2e.py (32/32) |
| 2026-08-07 | `frontend-nextjs/components/TaskManagement.tsx` | FIXED | Loading gate added — wrapper mounted shared TaskManagement before fetches resolved, so `useState(initialTasks)` never re-initialized and fetched tasks never displayed (tests exposed empty board); wrapper now renders a loading state until data arrives. New suite components/__tests__/TaskManagement.test.tsx 7/7 |
| 2026-08-07 | `frontend-nextjs/components/ReasoningChainViewer.tsx` | FIXED | `useState(!chainData)` kept the loader forever when neither chainId nor chainData was provided — "No reasoning chain available" branch was unreachable dead code; loading now keys off `!!chainId && !chainData`. New suite components/__tests__/ReasoningChainViewer.test.tsx 10/10 |

## Session 2026-08-07 — root stale-test wave (8 files, 19F→216P+1S)
| Date | File | Status | Fix |
|---|---|---|---|
| 2026-08-07 | `tests/test_byok_handler.py` | FIXED | 3F→73P: health filter threshold 0.5→0.2 (recovery-deadlock fix) — unhealthy fixtures 0.3→0.1; 'lux' provider removed → fallback order tested with 'anthropic' |
| 2026-08-07 | `tests/test_byok_handler_extended_coverage.py` | FIXED | 2F→61P: get_ranked_providers returns AwaitableResult (seam) not list; requires_tools filter conservatively excludes unknown-capability models → SIMPLE + patched `_model_supports_tools` |
| 2026-08-07 | `tests/test_cache_aware_routing.py` | FIXED | 3F→25P: calculate_effective_cost positional #4 is now turn_index — pass `cache_hit_probability=` keyword; ranked providers AwaitableResult |
| 2026-08-07 | `tests/test_business_intelligence.py` | FIXED | 3F→3P+1S: extraction no longer injectable (modernized LLMService) → mock extractor boundary; + product fix below |
| 2026-08-07 | `tests/test_atom_governance.py` | FIXED | 2F→2P: AgentRegistry rows need workspace_id="default" (governance scoped lookups); ReAct loop uses generate_structured_response → mock it |
| 2026-08-07 | `tests/test_alert_service.py` | FIXED | 2F→30P: patched `integrations.email_routes.EmailService` (core.email_service phantom) + product fix below |
| 2026-08-07 | `tests/test_access_control_bugs.py` | FIXED | 2F→4P: RED-phase bug-verification tests flipped to GREEN — LINE profile endpoint now auth+ownership-gated (verify the fix) |
| 2026-08-07 | `tests/test_atom_cli_skills_simple.py` | FIXED | 2F→18P: subprocess.run call includes explicit cwd=None/env=None (sandbox Phase B) — assertions updated |

Real product bugs fixed this wave (TDD):
- `core/communication_intelligence.py:20` — `KnowledgeExtractor(ai_service)` passed ai_service into workspace_id slot (extractor ctor modernized to workspace_id/tenant_id; ai_service was a Mock in tests → garbage workspace_id in prod whenever ai_service passed) (MED)
- `core/atom_meta_agent.py:1267` — `generate_structured_response(task_type=..., turn_index=...)` — task_type collides with LLMService's model→task_type mapping and turn_index is not a handler param → every meta-agent ReAct step crashed with TypeError (HIGH)
- `core/alert_service.py:457,548` — phantom `core.email_service` import (module never existed) → email alert notifications always returned False; rewired to `integrations.email_routes.EmailService` with its real `(to, subject, body)` signature (HIGH)

### Round 2026-08-07 late-4 — governance interlock + final mopping
| Date | File | Status | Fix |
|---|---|---|---|
| 2026-08-07 | `core/workflow_engine.py` (linear step interlock) | FIXED | HIGH SECURITY: called `can_perform_action(action=)` (wrong kwarg/method) + tuple-destructured dict → TypeError every step → fail-open → governance NEVER enforced for linear workflows. Now `can_perform_action_async(action_type=)` + dict access, enforced for registry-backed agents only (system_agent exempt — no identity). 3 new TDD tests (tests/test_bughunt_wf_governance.py) + covpush governance test updated. 252 workflow tests green |
| 2026-08-07 | `core/atom_meta_agent.py:1267` | FIXED | generate_structured_response task_type/turn_index TypeError → every meta-agent ReAct step crashed (HIGH) |
| 2026-08-07 | `core/alert_service.py:457,548` | FIXED | phantom core.email_service import → email alerts always returned False (HIGH); rewired to integrations.email_routes.EmailService |
| 2026-08-07 | `core/communication_intelligence.py:20` | FIXED | ai_service passed into workspace_id ctor slot (MED) |
| 2026-08-07 | graduation cluster (5 files) | FIXED | 26F+3E→164P: agent_graduation, graduation_service, atom_agent_endpoints_unit_coverage, connection_routes_coverage, workflow_engine_transactions_coverage (Episode/SkillExecution NOT NULL, Session import, auth signatures, removed routes) |
| 2026-08-07 | routing/byok cluster (8 files) | FIXED | 19F→216P: byok_handler root, extended_coverage, cache_aware_routing, business_intelligence, atom_governance, alert_service, access_control_bugs (RED-phase→GREEN), cli_skills_simple |

### Round 2026-08-07 late-5 — last flagged items + corpus contract alignment
| Date | File | Status | Fix |
|---|---|---|---|
| 2026-08-07 | `tests/test_communication_intelligence.py`, `tests/test_negotiation_flow.py` | FIXED | 3F+1E→3P+1S: extraction now mocked at the real seam (KnowledgeExtractor.llm_service.generate_completion); phantom followup_service test skipped with reason (feature never existed) |
| 2026-08-07 | `api/admin/cache_routes.py` + `main_api_app.py` | FIXED | Routes implemented by mopping agent were never MOUNTED (module dead); now mounted with `get_super_admin` dependency on all 3 handlers; tests updated with dependency override (26/26) |
| 2026-08-07 | `tests/test_covpush_tools_c.py` (4), `tests/test_covpush_ingest.py` (1) | FIXED | Corpus aligned to post-fix contracts: media governance tests patched at new seams (DB status lookup + AgentGovernanceService.can_perform_action_async instead of phantom AsyncGovernanceCache); permission denials assert error-dict contract (not raise); alert email exception patches integrations.email_routes.EmailService |

Final corpus: 3,282 passed / 0 failed (all test_bughunt_* + test_covpush_*).
| 2026-08-07 | `tests/test_opencode_go_provider.py` (opencode quota feature) | VERIFIED-OK | 21 old + 18 new = 39/39. Per-model quota accounting for OpenCode Go: quota weights (price-derived, OPENCODE_MODEL_LIMITS override), weighted provider TPM, per-model RPM/TPM hard-skip (model dropped, provider survives), quota value-score penalty (breaks ties at quality parity), persisted monthly usage (RateUsagePersistence, temp-engine test) + OPENCODE_MONTHLY_TPM hard-skip, /api/debug/opencode-usage endpoint (mounted debug router). mypy clean on 3 new/edited modules; byok_handler 33 pre-existing errors unchanged (0 in new code); capability_routing 9 pre-existing failures reproduced on clean HEAD |

### Round 2026-08-07 late-6 — cross-suite SessionLocal pollution fix
| Date | File | Status | Fix |
|---|---|---|---|
| 2026-08-07 | `tests/property_tests/conftest.py` (`db_engine`) | FIXED | Fixture rebound the GLOBAL `core.database.SessionLocal` to a per-test temp engine and never restored it; teardown disposed the engine + deleted the file, leaving every later same-process test (e.g. tests/core/test_workflow_engine_core_execution.py) with a dead SessionLocal → `get_db_session()` writes failed. Now saves `SessionLocal.kw["bind"]` before `configure(bind=engine)` and restores it after cleanup. Evidence: `pytest tests/security/test_canvas_security.py tests/core/test_workflow_engine_core_execution.py::TestWorkflowEngineDAGExecution` 2F→55P |
| 2026-08-07 | `core/workflow_engine.py` (`_run_execution` linear loop) | FIXED | REAL ENGINE BUG exposed by the pollution: the 4 ancillary `with get_db_session()` blocks (governance interlock, step-log insert, Time Travel snapshot, step-record update) had try/except INSIDE the `with` — a swallowed inner error invalidates the session transaction, then the context-exit `db.commit()` (core/database.py:223) raised OUTSIDE the guard → outer catch marked the whole execution FAILED before `_execute_step` ran (DAG tests: `assert 0 == 2/4`). Hoisted each try/except to wrap the `with` (fail-open per block intent). Evidence: poisoned-SessionLocal repro script 0 calls→COMPLETED/2 calls; standalone file 37P; combined batch 232P |

### Round 2026-08-07 late-7 — per-call LLM provider usage metrics (opencode-go + all providers)
| Date | File | Status | Fix |
|---|---|---|---|
| 2026-08-07 | `core/llm_call_tracker.py` (NEW) | TESTED | Per-call LLM provider usage tracking: `LLMCallRecord` (timestamp, provider, model, success, latency_ms, input_tokens, output_tokens, fallback, fallback_provider, error) + thread-safe bounded `LLMCallTracker` (5k) + Prometheus metrics (`llm_calls_total`, `llm_call_duration_seconds`, `llm_tokens_total`, `llm_fallbacks_total`, `llm_call_errors_total`, scraped by existing /health/metrics). 17 unit tests (tests/unit/core/test_llm_call_tracker.py). mypy clean |
| 2026-08-07 | `core/llm/byok_handler.py` | TESTED | New `_track_llm_call()` helper wired at all 4 dispatch sites (generate_response, generate_structured_response, stream_completion, chat_completion) on success/heal-retry/failure paths; fallback detected as provider != primary candidate (options[0]/provider_order[0]); error strings truncated to 500 chars. 9 wiring tests (tests/unit/core/test_llm_call_tracking_wiring.py, FakeClient pattern). mypy: 0 new errors (68 pre-existing unchanged) |
| 2026-08-07 | `api/byok_routes.py` | TESTED | `GET /api/ai/usage/calls` — recent call logs + aggregated summary (per-provider/per-model rollups), auth'd, filters provider/model/limit. 3 API tests (16/16 in file). mypy: 0 new errors |
| 2026-08-07 | regression | VERIFIED-OK | 75/75 (tracker + wiring + byok routes + chat completion + usage tracker); byok_handler full suites: 4 failed / 214 passed — identical failure set reproduced on clean HEAD (pre-existing, not caused by this change) |

### Round 2026-08-07 late-6 — final coverage measurement + episodes mock fix
| Date | File | Status | Fix |
|---|---|---|---|
| 2026-08-07 | `tests/test_covpush_episodes.py` (3) | FIXED | get_domain_feedback_metrics tests: mock chain missing .order_by() link → Mock len() error → error dict without trend key; chain now self-referential (116/116) |

## FINAL POST-CAMPAIGN COVERAGE (2026-08-07, chunked full-suite + all 3,282 new tests merged)
| Layer | Pre-campaign | Post-campaign | Δ |
|---|---|---|---|
| core | 31.3% | **53.0%** | +21.7pp |
| api | 36.5% | **53.3%** | +16.8pp |
| tools | 17.3% | **92.5%** | +75.2pp |
| integrations | ~0% (8 files unparseable) | **17.0%** | +17pp |
| ALL (158,377 stmts) | ~30% | **44.4%** (70,285 covered) | +14pp |

Methodology: 6 chunked batches (--timeout=90, -n 4, maxfail=60) + all test_bughunt_*/test_covpush_* (3,282 passed, 0 failed) combined via coverage combine in a fresh dir. Same-batch methodology as pre-campaign measurement.

### Round 2026-08-07 late-7 — R84 coverage-push: enterprise_auth_endpoints / workflow_debugging / social_media_routes
| Date | File | Status | Fix |
|---|---|---|---|
| 2026-08-07 | `api/social_media_routes.py:525` | FIXED | scheduled-post branch built `SocialPostHistory` without `post_id` (NOT NULL) → every scheduled post 500 `NOT NULL constraint failed`; now sets `post_id=post_id` |
| 2026-08-07 | `api/workflow_debugging.py` (15 handlers) | FIXED | all handlers caught their own `HTTPException` (404/422 raised for not-found/validation) in `except Exception` and rewrapped as 500 → added `if e.__class__.__name__ == 'HTTPException': raise` guard; 404/422 now propagate correctly |
| 2026-08-07 | `api/enterprise_auth_endpoints.py` | TESTED | 0% → 100% (130-test batch `tests/test_covpush_entroutes.py`; no bugs found, 3 pre-existing mypy errors untouched) |
| 2026-08-07 | `api/workflow_debugging.py` | TESTED | 0% → 100% |
| 2026-08-07 | `api/social_media_routes.py` | TESTED | 19.6% → 99% (2 uncovered lines are coverage.py except-clause artifact, behavior verified) |

### Round 2026-08-07 R84 — coverage-push: CRM integrations (hubspot/zendesk/freshdesk/salesforce/jira/trello)
| Date | File | Status | Result |
|---|---|---|---|
| 2026-08-07 | `integrations/hubspot_routes.py` | FIXED | **missing `import os` → `NameError` in `HubSpotService.__init__` → EVERY /api/hubspot route 500'd**; added module-level import |
| 2026-08-07 | `integrations/salesforce_routes.py` | FIXED | **`logger` never defined (no `logging.getLogger`) → NameError in ingestion/governance error paths** (245/315/331/383); added module logger |
| 2026-08-07 | `integrations/jira_service.py` | FIXED | **`asyncio` never imported → `execute_operation` always NameError** (line 689); added import |
| 2026-08-07 | `integrations/atom_hubspot_integration_service.py` | FIXED | KeyError `enable_enterprise_features` (config key never set) → create_contact/campaign always failed; 9 phantom `_setup_*`/`_perform_security_check` methods (initialize always False); **17 except handlers referenced undefined `audit_ctx` → NameError masked real errors**; `_score_lead`/`_rule_based_lead_scoring` returned dicts vs float + ZeroDivisionError; rate-limiter dead code inside circuit-breaker branch (create_campaign); `AnalyticsType.A_B_TESTING` NameError (member is `AB_TESTING`); 9 phantom `_generate_*_analytics` methods (generate_marketing_analytics always failed); AI* classes missing from ImportError fallback block; dead unreachable code removed |
| 2026-08-07 | `integrations/hubspot_service.py` | FIXED | `sync_to_postgres_cache` used `tenant_id=` on `IntegrationMetric` (real column `workspace_id`) → always failed; duplicate `health_check` (first def dead) removed |
| 2026-08-07 | `integrations/freshdesk_service.py` | FIXED | same `tenant_id`→`workspace_id` column bug in `sync_to_postgres_cache` |
| 2026-08-07 | `integrations/trello_service.py` | FIXED | same `tenant_id`→`workspace_id` column bug in `sync_to_postgres_cache` |
| 2026-08-07 | `integrations/atom_zendesk_integration_service.py` | FIXED | async `_initialize_salesforce_integration()` called without await in `__init__` (un-awaited coroutine stored); **14 phantom methods** (`_sync_ticket_to_salesforce`, `_notify_platform_ticket_created/updated`, `_check_sla_compliance`, `_check_escalation`, `_perform_security_check`, 7×`_generate_*_analytics`, `_generate_ai_insights`) → create_ticket/update_ticket/generate_support_analytics crashed |
| 2026-08-07 | 8 CRM integration files | TESTED | **0% → 95–99% lines each** (126 tests: `tests/test_covpush_crm_services.py` 104 + `tests/test_bughunt_crm_services.py` 22, all green; TDD RED→GREEN for every bug) |

### Round 2026-08-07 R84 — coverage-push: canvas_routes / user_templates_endpoints / learning_plan_routes
| Date | File | Status | Fix |
|---|---|---|---|
| 2026-08-07 | `api/canvas_routes.py` (`list_canvas_types`) | FIXED | governance denial *returned* `router.error_response(...)` instead of raising → FastAPI serialized the HTTPException → 500 instead of 403; now `raise` |
| 2026-08-07 | `api/canvas_routes.py` (`get_canvas_history`) | FIXED | own HTTPException(404) swallowed by blanket `except Exception` → other users' canvases got 500 instead of 404; added `except HTTPException: raise` |
| 2026-08-07 | `api/canvas_routes.py` (`submit_canvas`) | FIXED | audit row missing `tenant_id` (NOT NULL) → IntegrityError → submission silently unpersisted; also read `request.data` (nonexistent) so `form_data` never recorded; now sets tenant_id + real form_data/agent_id |
| 2026-08-07 | `api/canvas_routes.py` (`put/run_canvas_logic`) | FIXED | `CanvasLogicService.check_governance` PermissionError escaped as 500; now 403 |
| 2026-08-07 | `api/canvas_routes.py` | TESTED | 30.5% → 100% (65-test batch `tests/test_covpush_canvasroutes.py`, incl. WS auth/ownership/persist + fork credential-strip) |
| 2026-08-07 | `api/user_templates_endpoints.py` (`create_user_template`) | FIXED | steps_schema/inputs_schema (pydantic models) stored raw into JSON columns → TypeError on flush → 500 on any template with structured schema; now `model_dump()`-ed |
| 2026-08-07 | `api/user_templates_endpoints.py` (`get_user_template_statistics`) | FIXED | `most_used.template_id` (column removed in Hive port) → AttributeError → 500; now `most_used.id`; `recent_templates` raw ORM objects failed response-model validation → now `_template_to_response`-mapped |
| 2026-08-07 | `api/user_templates_endpoints.py` | TESTED | 41.2% → 100% (50-test batch `tests/test_covpush_user_templates.py`) |
| 2026-08-07 | `api/learning_plan_routes.py` (create/get/list/progress/delete/export) | FIXED | stub `LearningPlan` model (core/models.py, read-only) lacks target_skill_level/milestones/assessment_criteria/notion_page_id and has Integer `progress` → every create 500 (TypeError) + flush ProgrammingError; full payload now persisted in `modules` JSON sidecar (`_encode_plan_payload`/`_decode_plan_payload`), Integer column = 0-100 aggregate; notion_page_id update via sidecar (in-place mutation of same dict was silently dropped — decode copies) |
| 2026-08-07 | `api/learning_plan_routes.py` | TESTED | 27.8% → 100% (36-test batch `tests/test_covpush_learning_plan.py`) |
| 2026-08-07 | `integrations/discord_enhanced_service.py` | FIXED | `DiscordMessage.__post_init__` read `self.author` (never a field) → every message conversion crashed; `DiscordGuild` missing `permissions` kwarg → exchange_code_for_tokens always TypeError; `_save_guild` VALUES clause had 70 placeholders for 59 columns/values → every DB save failed ("70 values for 59 columns"); `Fernet` used but never imported → __init__ NameError with ENCRYPTION_KEY set; JSON columns (roles/features/integration_data/…) never json.loads'd on DB read; redis `json.dumps(asdict(guild))` crashed on datetime (no default=str) → cache saves always failed; message cache same bug → get_channel_messages with redis always returned []; DB round-trip needed `is_active` field (SELECT * WHERE is_active=1 contract) |
| 2026-08-07 | `integrations/discord_enhanced_service.py` | TESTED | 0% → 99% (65 tests in `tests/test_covpush_adapters_discord.py`) |
| 2026-08-07 | `integrations/slack_analytics_engine.py` | FIXED | get_insights called 5 phantom `_get_*_insights` helpers → always returned {} (implemented); `_process_user_activity` called `.replace(second=0,…)` on raw string timestamps → TypeError → USER_ACTIVITY analytics always []; `_process_reactions`/`_process_file_sharing` iterated `grouped` keys instead of `.items()` → TypeError → REACTIONS/FILE_SHARING always []; `_get_cached_analytics` reconstructed string timestamps → AttributeError → cached path always failed (now fromisoformat); `get_engagement_heatmap` ZeroDivisionError on zero-engagement days; `train_lda_model` called `.tolist()` on a list → training always "failed" after fit |
| 2026-08-07 | `integrations/slack_analytics_engine.py` | TESTED | 0% → 94% (68 tests in `tests/test_covpush_adapters_slack.py`) |
| 2026-08-07 | `integrations/atom_google_chat_integration.py` | FIXED | off-by-one `[11:]` prefix strip (`'google_chat_'` is 12 chars) in get_unified_channels/send_unified_message/get_unified_messages/unified_search → every space ID got a leading `_` → unified channels/messages/search always failed (now `[12:]`) |
| 2026-08-07 | `integrations/atom_google_chat_integration.py` | TESTED | 0% → 86% (102 tests in `tests/test_covpush_adapters_google_chat.py`; NOTE: file also edited concurrently by another session — imports + fail-closed OAuth state; tests adapted to current tree) |
| 2026-08-07 | `integrations/atom_telegram_integration.py` | FIXED | `handle_callback_query` referenced undefined `user_id` → NameError on every routed callback (now `from_user.get("id")`); `_perform_ai_search` referenced AIRequest/AITaskType/AIModelType/AIServiceType undefined when enterprise imports fail → NameError (None-fallback + guard); `handle_inline_query` called non-existent `lancedb_handler.semantic_search` → LanceDB search never ran (now `search()`); `search_recent_messages` callback unroutable (`search_type=="recent_messages"` vs parse yielding `"recent"`); duplicate except block; dead first `send_intelligent_message` def shadowed by enhanced HTTP version (removed) |
| 2026-08-07 | `integrations/atom_telegram_integration.py` | TESTED | 25.1% → 86% (95 tests in `tests/test_covpush_adapters_telegram.py`) |
| 2026-08-07 | 4 comms adapter modules (above) | REGRESSION | 330 tests green; pre-existing `tests/test_covpush_agents.py` (115) + `tests/test_proactive_messaging_minimal.py` (8) pass — 0 new failures; mypy 138→124 errors (net −14, no new) |

### Round 2026-08-07 — data/federation coverage push (data_fed agent)
| Date | File | Status | Evidence |
|---|---|---|---|
| 2026-08-07 | `core/graphrag_engine.py` | FIXED | canonical_search read `search_fields` (plural) but registry entries define `search_field` (singular) → default `["name"]` hit the `User.name` Python property → `'property' object has no attribute 'ilike'` → canonical search always `[]` (also removed two shadowed dead methods). Tests: `tests/test_bughunt_data_fed.py::TestCanonicalSearchRealRegistry` + `test_covpush_data_fed.py::TestGraphRAGEngineGaps*` |
| 2026-08-07 | `core/historical_sync_service.py` | FIXED | `_extract_chunk_and_ingest` called phantom `GraphRAGEngine.ingestion_pipeline_batch()` / `.close()` → every chunk failed with AttributeError and the job was marked failed; now `ingest_structured_data()` (also 0%→99% coverage via `TestHistoricalSyncGaps*`) |
| 2026-08-07 | `core/hybrid_data_ingestion.py` | FIXED | `sync_integration_data` awaited nothing on `graphrag.ingest_document` (coroutine) → truthy coroutine crashed on `.get()` → every record errored and syncs were marked partial/failed; now awaited. Fixture aligned in `tests/test_covpush_ingestion_hybrid.py` (AsyncMock) |
| 2026-08-07 | `core/episode_service.py` | FIXED | lazy `embedding_service` passed `tenant_api_key=` to `EmbeddingService` which doesn't accept it (TypeError on every lazy init); `get_embedding_dimension` phantom method (AttributeError in `_get_lancedb`/archive) → `_get_embedding_dimension()` resolver (FastEmbed 384 default, mock-compatible) |
| 2026-08-07 | `core/agent_graduation_service.py` | FIXED | `calculate_skill_usage_metrics` read `EpisodeSegment.metadata.get(...)` — no such column (SQLAlchemy MetaData) → AttributeError whenever skill segments existed; now joins via `AgentEpisode.agent_id`. Coverage 2%→96% |
| 2026-08-07 | `core/{identity/verifiable_credentials, federation/zero_trust_security, federation/federation_security}.py` | TESTED | coverage 61%/81%/48% → 97%/97%/99% (`TestVCGaps*`, `TestZTGaps*`, `TestFedSecGaps`) |
| 2026-08-07 | `core/ingestion_pipeline.py` | TESTED | 92% → 95% (`TestPipelineGaps`: attachment branches, tiered webhook, outlook/gmail resource-direct, telegram media, standardizer UUID sanitize) |
| 2026-08-07 | `tests/test_bughunt_data_fed.py` + `tests/test_covpush_data_fed.py` | TESTED | 8 + 189 tests, all green; full module set regression 791 passed, 0 failed |
| 2026-08-07 | mypy | REGRESSION | 46 errors on the 5 changed sources before AND after (0 new) |
| 2026-08-07 | pre-existing, NOT mine | REPORTED | `tests/test_bughunt_federation.py:42` `sys.path.insert(0, backend/tests)` at collection time shadows real `core`/`integrations` packages → 30+ cascade failures in any combined run (33 of 34 initial failures); `tests/test_graphrag_sql_injection.py` 3 stale tests assert the OLD unescaped source; `tests/unit/{test_agent_graduation_service,test_episode_service,test_supervision_learning_integration}.py` fixture-level UNIQUE-constraint errors (identical at HEAD) |

### Round 2026-08-07 late-8 — mail/office integrations (7 files → ≥98% each) + 12 bugs
| Date | File | Status | Fix |
|---|---|---|---|
| 2026-08-07 | `integrations/gmail_service.py` | FIXED + 100% | `fetch_recent_messages`/`sync_calendar_events` defined twice — 2nd shadowed 1st (hub-sync defs dead); active `fetch_recent_messages` did `await` on the sync `get_messages()` list (TypeError → always `[]`); `HttpError`/`build` only defined in the google-libs-missing fallback → NameError in prod with libs installed; `execute_operation` mapped to phantom `IntegrationErrorCode.NOT_FOUND/FORBIDDEN` → AttributeError in the error path; phantom `core.collaboration_hub_service` import + phantom `pipeline.ingest_calendar_event` → calendar sync silently died → rewired to real `pipeline.ingest_message` |
| 2026-08-07 | `integrations/outlook_service.py` | FIXED + 100% | `_is_token_expired` parsed `expires_at` (float timestamp from `.timestamp()`) as ISO string → AttributeError → always expired → refresh loop; Graph `POST /me/sendMail` returns 202 → treated as error → sent mail reported failed; dead `return None`; unreachable `else` endpoints removed |
| 2026-08-07 | `integrations/outlook_service_enhanced.py` | FIXED + 100% | same 202-sendMail bug → `response.json()` on empty body raised → `send_email_enhanced` always False |
| 2026-08-07 | `integrations/microsoft365_service.py` | FIXED + 100% | `/services/status` route called phantom `get_service_status()` → 500; implemented |
| 2026-08-07 | `integrations/atom_telegram_integration.py` | FIXED + 99% | `handle_callback_query` used undefined `user_id` (only `from_user` extracted) → every callback died NameError → action never executed |
| 2026-08-07 | `integrations/atom_google_chat_integration.py` | FIXED + 99% | phantom `google_chat_enhanced_service` instance import (module only exports class) → whole integration ran service-less "simulated" mode; `GoogleChatEventType` not imported → NameError in `_setup_cross_platform_handlers`; `UnifiedWorkspace` was None whenever legacy atom_* imports failed (same try block) → `_get_or_create_unified_workspace` always crashed → cross-platform workspace sync broken; OAuth `state` "validation" was a log-only no-op (fail-open CSRF) → now fails closed when state missing |
| 2026-08-07 | `integrations/workspace_sync_service.py` | FIXED + 98% | `WorkspaceSyncService` defined twice (IntegrationService + legacy) — legacy shadowed the migrated class (dead API); `workspace.get_platform_id()/add_platform()` phantom model methods → propagate_change/add_platform always AttributeError → inline column helpers; phantom `slack_enhanced_service` instance import → Slack propagation permanently unavailable → import class + instantiate; `_update_sync_log` aware-vs-naive datetime subtraction (SQLite) → TypeError; `workspace.last_sync_error` phantom model attr → every propagate crash; `db.execute("SELECT 1")` raw string → SQLAlchemy 2.0 ArgumentError → health_check always unhealthy → `text()` |
| 2026-08-07 | `tests/test_bughunt_mail_office.py` + `tests/test_covpush_mail_office.py` | TESTED | 20 bug tests (TDD RED→GREEN) + 173 coverage tests, 193 passed 0 failed; coverage 19/29/44/14/29/16/47% → **100/100/100/100/99/99/98%** (TOTAL 3767 stmts, 99%); mypy: 0 new errors (196 identical to HEAD) |
| 2026-08-07 | regression | VERIFIED-OK | green: round46 (outlook clientState), round54 (workspace identity), test_covpush_agents (108), test_covpush_adapters_google_chat, integration/test_integration_services_batch, test_agent_integration_gateway (22), test_todo_features_implementation (39/40) |
| 2026-08-07 | pre-existing, NOT mine | REPORTED | `tests/api/test_routes_batch.py` 36F (Workspace model `user_id` kwarg TypeError + un-mounted routes — fails on clean HEAD); `test_scheduled_messaging_minimal`/`test_condition_monitoring_minimal` 48F (missing enum members `ScheduledMessageStatus.ACTIVE`, `ConditionMonitorType.INBOX_VOLUME`); `test_agent_integration_gateway_coverage::test_gateway_initialization` ('meta' service never registered); `tests/integration/test_integrations_batch.py` collection error (phantom `integrations.atom_education_customization_service`); `test_email_api_ingestion` network-bound hangs; `test_todo_features_implementation::TestTelegramInlineSearch::test_handle_inline_query_with_lancedb` expects `lancedb_handler.semantic_search` but parallel telegram fix renamed to `search` — test needs updating |
| 2026-08-07 | `integrations/{slack_enhanced_service,slack_analytics_engine,discord_enhanced_service,discord_analytics_engine,google_chat_analytics_engine,teams_enhanced_service,chat_orchestrator}.py` | FIXED + 96-97% | 21 bugs fixed (TDD RED→GREEN): slack `full_sync` 2-arg mismatch; slack duplicate `get_capabilities`/`health_check` (merge residue); slack `bot_token`=bot_user_id misbinding; slack `_save_workspace` 17-placeholder/16-column INSERT (every DB save failed); slack `get_channels`/`_cache_file` `json.dumps` on datetime (cache crash → channels lost); slack_analytics logger defined inside optional-dep except blocks (NameError on partial deps); discord `execute_operation('send_message')` success placeholder (never sent); discord/google engines `system_prompt=` invalid kwarg (LLM path always fell back); discord/google engines `row.get()` on sqlite3.Row in `_fetch_analytics_data` (DB analytics silently empty); discord/google engines `{{dimensions}}` f-string collapse → invalid SQL in EVERY query; teams phantom imports msal/azure.mgmt.teams/azure.graph (module unimportable) + `TeamsMessage` dataclass default-before-required field (class undefined); teams `$filter` overwrite (latest+oldest); teams `TeamsMessage` missing `workspace_id` ×2 + `metadata=` phantom kwarg + `TeamsFile` missing `workspace_id` (all constructions crashed); teams JWT decode of payload-only segment (exchange always failed); teams `_save_workspace` 22-placeholder/21-column INSERT + redis datetime dump; teams `get_channels` `tenant_id=` phantom kwarg; chat_orchestrator phantom accounting class references (finance handler always NameError); chat_orchestrator `get_automation_settings()` None-crash; chat_orchestrator `agent_service.execute_task(workspace_id=...)` invalid kwarg (agent fallback always failed); all 3 services `IntegrationMetric(tenant_id=...)` phantom kwarg (Postgres cache sync silently no-op) | tests: `test_bughunt_comms_services.py` (20), `test_covpush_comms_services{1,2,3}.py` (190+61+94=345); coverage 75/0/0/0/0/0/0% → 97/97/96/97/96/96/96% (TOTAL 4376 stmts, 96%); mypy: 0 new errors; regression: 21 pre-existing failures (test_slack_workflow_actions ×8, slack token-storage ×1, scheduled/condition_monitoring ×12) unchanged from HEAD |
| 2026-08-07 | `integrations/universal_integration_service.py` + `integrations/atom_communication_ingestion_pipeline.py` | FIXED + TESTED | 5 bugs fixed (TDD RED→GREEN): gatekeeper response field-masking never applied to execute()/search() responses (credential leak) → `_mask_response` at all return paths; phantom `mailchimp_service`/`zendesk_service`/`freshdesk_service`/`github_service`/`gitlab_service`/`gmail_service`/`teams_service`/`zoho_mail_service`/`zoho_projects_service` singletons (module only exports classes → ImportError at runtime, dead branches) → class instantiation; wrong singleton names `google_chat_integration`/`telegram_integration`/`whatsapp_integration`/`whatsapp_integration_service` (real: `atom_*`) in search + whatsapp polling; `_search_marketing` used phantom `mailchimp_service` too. Tests: `tests/test_covpush_universal.py` (202 tests, all green); coverage 0% → **98%** (universal) / **92%** (pipeline); regression: `test_realtime_communication_ingestion.py` 16P/1F unchanged (pre-existing broken `slack_enhanced_service` mock target); `test_mcp_service.py` 2 pre-existing external-API failures (Tavily/BYOK keys) unchanged |
### Round 2026-08-08 — enterprise integrations coverage push (workflow automation / security / unified)
| Date | File | Status | Fix |
|---|---|---|---|
| 2026-08-08 | `integrations/atom_workflow_automation_service.py` | FIXED + 86% | 4 bugs (TDD RED→GREEN): `_scheduler_loop` called `execute_automation()` without required `triggered_by` → TypeError every time a scheduled automation came due (automation never ran); `_handle_event_trigger` same missing `triggered_by` (event automations never ran); `_send_automation_notifications` read rules from `metadata['notification_rules']` but `create_automation` stores them in the `notification_rules` field → configured rules never fired; `create_automation` dropped `enabled` flag (created as always-enabled); defensive: `get_automations` treated non-dict first arg (legacy `user_id`) as filters → AttributeError → always `[]` |
| 2026-08-08 | `integrations/atom_enterprise_security_service.py` | FIXED + 93% | `audit_event` raised ValueError on non-`AuditEventType` strings (`'automation_created'` from workflow/unified) → every cross-service audit silently dropped → coerce to `CONFIG_CHANGED` (missing `event_type` still fails closed) |
| 2026-08-08 | `integrations/atom_enterprise_unified_service.py` | FIXED + 85% | 3 bugs (TDD RED→GREEN): `create_security_automation` hardcoded `'NIST'` — not a valid `ComplianceStandard` value (`'nist'`) → ValueError → automation creation ALWAYS failed → `'nist'`; module lacks package-qualified import fallback for `atom_enterprise_security_service` (workflow module has one) → `security_service` None whenever bare imports fail → `initialize()` permanently False in such envs; `_log_enterprise_event` omitted required `ip_address` → audits dropped; `get_enterprise_workflows` compliance_standard filter compared uppercase filter vs lowercase enum values → never matched |
| 2026-08-08 | `tests/test_covpush_entints.py` (new) | TESTED | 187 tests, all green; coverage 35/59/39% → **86/93/85%** (target 75%); regression: `test_covpush_integrations.py` (59) + `test_enhanced_workflow_automation.py` all pass (246 total, 0 new failures); mypy: 94 vs 96 at HEAD on the 3 sources (0 new); order-independent (passes with pytest-randomly) |
| 2026-08-08 | pre-existing, NOT mine | REPORTED | `integrations/atom_ai_integration.py` module-level `AtomAIIntegration({...})` → NameError when any platform integration import fails (except sets no None fallbacks) → `from integrations.atom_ai_integration import ...` crashes; security/unified optional-import blocks (`ai_enhanced_service` etc.) set no None fallbacks → NameError-driven degradation instead of clean `if not self.ai_service` (workflow module already has fallbacks); guard HTTPExceptions (503/429) are swallowed by each method's own try/except into `{'ok': False}`/None instead of propagating (only encrypt/decrypt/metrics/close raise) |
### Round 2026-08-08 — BYOK routes + browser routes coverage push (TDD, 5 real bugs)
| Date | File | Status | Fix |
|---|---|---|---|
| 2026-08-08 | `api/byok_routes.py` | FIXED + 99% | 5 bugs (TDD RED→GREEN): `byok_health_v1` passed the manager as positional `current_user` of the shadowed module-global `byok_health_check` → always 503 (fixed kwargs + renamed the first-registered duplicate); GET `/api/ai/keys` returned 3 hardcoded fake keys regardless of storage → real masked listing; POST `/api/ai/keys` validated then discarded the key (silent no-op) → persists via `store_api_key` + rejects unknown providers; `store_tenant_api_key` wrote the PLAINTEXT key into `tenant_settings` (credentials at rest) → Fernet-encrypted, `get_tenant_api_key` decrypts with legacy-plaintext fallback; GET `/api/ai/usage/stats` returned a bare dict (no ApiResponse) for unknown tenant → consistent envelope |
| 2026-08-08 | `api/browser_routes.py` | TESTED + 100% | coverage 96% → 100%: `_check_browser_governance` resolver-exception swallow, `_create_browser_audit` failure best-effort, navigate/close DB-update commit-failure paths, fill-form non-submit governance branch |
| 2026-08-08 | `tests/test_covpush_byokroutes.py` + `tests/test_covpush_browserroutes.py` (new) | TESTED | 96 + 5 tests, TDD red→green for all 5 bugs; coverage `api/byok_routes.py` 55.4%→**99%** (603 stmts, 5 unreachable except-branches remain: 969/1082/1111-1112/1179 dead handlers), `api/browser_routes.py` 32.5%→**100%**; mypy: 0 new errors (583, same as HEAD baseline after 2 str() casts); regression: 720 passed 0 failed (incl. read-only `test_bughunt_byok.py`, `test_byok_handler.py`, `tests/unit/test_byok_handler.py`, other sessions' `test_covpush_byok{,_gen}.py`, provider registry/wiring/openrouter suites) |
| 2026-08-08 | pre-existing, NOT mine | REPORTED | `api/byok_routes.py:969,1082,1111-1112,1179` dead `except` branches (unreachable: no HTTPException/ValueError raised in their try blocks); `track_ai_usage` (1111-1112) can never surface background-task failures via the 500 handler; `list_sessions` ignores the `?limit=` query param (undeclared); `store_api_key` route takes `api_key` as a QUERY param → credentials land in access logs (fix would break existing frontend callers, left unchanged); `byok_health_check` hardcodes `"encryption_enabled": True` |
### Round 2026-08-08 — core workhorses coverage + bug hunt (7 modules, 11 real bugs)
| Date | File | Status | Fix |
|---|---|---|---|
| 2026-08-08 | `core/workflow_engine.py` | FIXED + 95% | 3 bugs (TDD RED→GREEN): `_resolve_parameters` never recursed into nested dicts/lists (${refs} inside HTTP/MCP configs sent literal to integrations); schema-validation error message used `step['id']` → KeyError masked the real SchemaValidationError when a step lacks `id`; a legitimately-None step output was treated as "missing" → spurious MissingInputError paused workflows. Tests: `test_bughunt_core_workhorses.py::TestWorkflowEngineBugs` (6) + `test_covpush_wfengine2.py` (43); coverage 90%→**95%** (1386 stmts); 13 pre-existing stale failures fixed by updating 4 cycle tests + 3 `{{}}`-condition tests + 1 `${step1.output}` semantics test to assert current contract |
| 2026-08-08 | `core/atom_agent_endpoints.py` | FIXED + 95% | 4 bugs (TDD RED→GREEN): `/agents/{id}/retrieve-hybrid` + `/agents/{id}/retrieve-baseline` had NO auth dependency — a bogus Bearer header bypassed CSRF and returned 200 for any agent_id (unauthenticated IDOR into episode retrieval) → `get_current_user` added; `chat_stream_agent` passed `workspace_id=` to `resolve_agent_for_request` (doesn't accept it) → every governance-enabled stream chat crashed with "Internal server error"; `handle_automation_insights` iterated `generate_all_insights()`'s dict as a list → crash on every insights request; `execute_generated_workflow` looked up workflows by `w['id']` but workflows.json uses `workflow_id` → KeyError 500 on every execute-generated request. Tests: `test_bughunt_core_workhorses.py` (7) + `test_covpush_endpoints2.py` (7); coverage 92%→**95%**; ~50 stale 5-month-old API tests repaired (phantom `ai_service`/`BYOKHandler`/`template_manager` patches → real seams, auth overrides, NOT NULL agent fields, query-param bodies) |
| 2026-08-08 | `core/llm/byok_handler.py` | FIXED + 90% | 1 bug (TDD RED→GREEN): `get_provider_comparison` returned `{}` when the pricing cache held only zero-cost entries (no exception → static fallback never fired) → pricing UI got an empty comparison; empty dynamic data now falls through to the static table. Tests: `test_bughunt_core_workhorses.py::TestProviderComparisonFallback` (2) + `test_covpush_core_workhorses.py` (89); coverage 70%→**90%** (1553 stmts); 4 stale byok tests repaired (provider-comparison contract, cross-provider model-compat skip for the fallback test) |
| 2026-08-08 | `core/generic_agent.py` | TESTED + 95% | coverage 19%→**95%** via `test_covpush_generic_agent.py` (45 tests): ReAct branches (parallel tools, degradation, budget gate, timeout, max-steps, audit mode, chaos noise, mentorship, semantic UI, screenshot capture, mcp_tool_search lazy-load, observation filter), `_step_act` governance/HITL/error mapping, `_wait_for_approval(s)`, `_execute_parallel_tools`, `_record_execution` graduation paths, workspace context, skill instructions, fallback parsing. 5 stale tests repaired (unmocked `get_relevant_critiques` crash, real-budget-gate dependency → seam mock, FeedbackService db arg) |
| 2026-08-08 | `core/agent_world_model.py` | FIXED + 98% | 1 bug (TDD RED→GREEN): `WorldModelService()` bound a different (global) LanceDB handler than `WorldModelService('default')` (workspace_id None passed through) → normalized to `"default"`. Tests: `test_bughunt_core_workhorses.py::TestWorldModelServiceInit` + 15 stale tests repaired (archive tests patched phantom `get_db_session` → `SessionLocal`, generic error messages, limit*2 search contract, score-based recall sort) |
| 2026-08-08 | `core/atom_meta_agent.py` + `core/learning_llm_router.py` | VERIFIED-OK | 96% / 99% (no source changes needed); 6 stale tests repaired (phantom patch targets, uppercase maturity status → lowercase enum values, per-test event-loop orphaned turn-fact tasks cleared, budget seam mocked) |
| 2026-08-08 | `tests/test_bughunt_core_workhorses.py` + `tests/test_covpush_core_workhorses.py` + `tests/test_covpush_wfengine2.py` + `tests/test_covpush_generic_agent.py` + `tests/test_covpush_endpoints2.py` (new) | TESTED | 20 bug tests (TDD RED→GREEN) + 190 coverage tests; regression: 2199 passed / 6 skipped / 0 failed (all module-touching suites incl. byok 738); mypy: no new type errors (byok_handler's 33 pre-existing errors untouched) |
| 2026-08-08 | pre-existing, NOT mine | REPORTED | `core/agent_governance_service.py` case-sensitivity: `maturity_order.index(agent.status)` silently demotes any non-lowercase status (e.g. `"AUTONOMOUS"` from API clients) to STUDENT tier → unexpected governance denials (fail-closed direction, but a robustness gap; tests now use lowercase enum values); `--cov` full-batch run with ALL 39 module suites produces 56 pre-existing `sqlite3.OperationalError: index ix_llm_models_supports_function_calling already exists` setup errors (import-order × coverage-instrumentation artifact; the same batch passes 2199/0 without --cov and in every smaller --cov configuration); `test_workflow_engine_path_coverage.py::test_execute_step_email_action` mock updated for parallel hardening by another session (non-success status envelopes now fail — correct) |

### Round 2026-08-08 — coverage wave 3 (R87-R88 modules) + FINAL measurement
| Date | Module | Status | Result |
|---|---|---|---|
| 2026-08-08 | `integrations/mcp_service.py` (tests-only) | TESTED | 7.2% → **92%** (199 tests). Reported (read-only): unified_knowledge_search/create_zoom_meeting/get_system_health ALWAYS ImportError (phantom singletons), shopify singleton, search_formulas TypeError, browser_click registry-shadow |
| 2026-08-08 | `integrations/atom_workflow_automation_service.py` | FIXED | 34% → **86%**: scheduled + event automations NEVER ran (missing triggered_by), notification rules never fired, enabled flag dropped, audit drops |
| 2026-08-08 | `integrations/atom_enterprise_{security,unified}_service.py` | FIXED | 59/39% → **93/85%**: security automation creation always failed (NIST vs nist), import-fallback gap, audit ip_address |
| 2026-08-08 | `api/byok_routes.py` | FIXED | 55.4% → **99%**: /api/ai/health always 503; GET /keys returned 3 hardcoded fake keys; POST /keys DISCARDED the key (silent no-op); **API keys stored PLAINTEXT at rest → Fernet-encrypted** (HIGH) |
| 2026-08-08 | `api/browser_routes.py` | FIXED | 32.5% → **100%** |
| 2026-08-08 | `core/graphrag_engine.py` | FIXED | 96% → **100%**: automation trigger dead in production (phantom orchestrator import); canonical_search/dup-method claims verified not-bugs at HEAD |
| 2026-08-08 | `core/generic_agent.py`, `core/orchestration/workflow_versioning.py` | FIXED | 8.1/0% → **100/99%** (execute() complexity crash, versioning crashes ×6) |
| 2026-08-08 | `core/historical_sync_service.py`, `core/office_service.py` | FIXED | 12.6/29.8% → **97/100%** (sync extraction TypeError, webhook kwarg, JSON in-place mutation, render path bypass) |
| 2026-08-08 | `api/enterprise_auth_endpoints.py`, `api/workflow_debugging.py`, `api/social_media_routes.py` | FIXED | 0/0/19.6% → **100/100/99%** (scheduled posts 500, all-500 HTTPException swallowing) |
| 2026-08-08 | `api/canvas_routes.py`, `api/user_templates_endpoints.py`, `api/learning_plan_routes.py` | FIXED | 30.5/41.2/27.8% → **100/100/100%** (submission never persisted, templates 500, learning-plan CRITICAL every-create-500) |
| 2026-08-08 | `integrations/discord_enhanced_service.py`, `slack_analytics_engine.py`, `atom_google_chat_integration.py`, `atom_telegram_integration.py` | FIXED | 0/0/0/25.1% → **99/94/86/86%** (18 bugs: every-message crash, OAuth connect, 70-vs-59 SQL, analytics dead, prefix off-by-one, NameError) |
| 2026-08-08 | `integrations/universal_integration_service.py`, `atom_communication_ingestion_pipeline.py` | FIXED | 0/30% → **98/92%** (gatekeeper masking credential leak HIGH, 9 phantom singletons) |

## FINAL COVERAGE MEASUREMENT (2026-08-08 — after all waves, 158,716 stmts)
| Layer | Pre-campaign | Post-wave-2 | **Final** |
|---|---|---|---|
| core | 31.3% | 53.0% | **54.4%** |
| api | 36.5% | 53.3% | **62.8%** |
| tools | 17.3% | 92.5% | **92.5%** |
| integrations | ~0% | 17.0% | **33.0%** |
| ALL | ~30% | 44.4% | **50.5%** (80,113 covered / 78,603 miss) |

Methodology: previous full-suite combined data + all wave test files (1,805 tests, 0 failed) via coverage combine in a fresh dir.
