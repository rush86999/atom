# Codebase Bug-Hunt Coverage Tracker

**Last updated:** 2026-08-06
**Bugs fixed:** 94 (BUG-001 → BUG-094) across 22 rounds
**Overall file coverage:** ~61% (964/1,597 source files)
**Critical-path coverage:** ~95% (all auth, billing, payments, secrets, webhooks, tenant isolation, 2FA, federation identity)

---

## Coverage Summary

| Area | Total Files | Covered | Uncovered | % |
|------|------------|---------|-----------|---|
| Backend (api/core/accounting/ai/tools/integrations) | 1,003 | 442 | 561 | 44% |
| Frontend (hooks/components/pages/lib) | 594 | 278 | 316 | 47% |
| **Combined** | **1,597** | **720** | **877** | **45%** |

---

## Backend — COVERED Files

### core/ — Audited & Tested
| File | Bug(s) / Round | Status |
|------|---------------|--------|
| `auth.py` | BUG-016, BUG-028 (R3, R6) | ✅ Token validation, decode_token revocation, WS auth |
| `budget_enforcement_service.py` | BUG-002, BUG-003 (R1) | ✅ soft_stop default, budget gate |
| `execution_recovery.py` | BUG-001 (R1) | ✅ Crash recovery metadata marker |
| `doc_freshness_service.py` | BUG-003, BUG-005 (R1) | ✅ tz-aware timestamps, freshness cascade |
| `graphrag_engine.py` | R1 (investigated) | ✅ NULL doc_id handled correctly |
| `generic_agent.py` | BUG-002 (R1) | ✅ budget_exceeded normalization |
| `atom_meta_agent.py` | BUG-002 (R1) | ✅ budget gate, failure_reason |
| `agent_world_model.py` | BUG-020 (R4) | ✅ recall_experiences similarity ranking |
| `agent_governance_service.py` | R4 (investigated) | ✅ Correctly defended |
| `graduation_service.py` | BUG-025 (R5) | ✅ Success filter |
| `hitl_service.py` | R4 (investigated) | ✅ with_for_update correct |
| `notification_manager.py` | R1 (investigated) | ✅ Broadcast defended |
| `webhook_handlers.py` | BUG-024, BUG-046 (R5, R10) | ✅ Slack HMAC, Teams dedup |
| `oauth_state_manager.py` | BUG-019 (R4) | ✅ Single-use enforcement |
| `session_dedup.py` (llm/compression/) | BUG-010 (R2) | ✅ Separator preservation |
| `scheduler.py` | BUG-032 (R7) | ✅ Invalid cron rejection |
| `lancedb_handler.py` | BUG-043 (R9) | ✅ Empty text embedding guard |
| `dynamic_pricing_fetcher.py` | BUG-041, BUG-042 (R9) | ✅ Price match, provider inference |
| `board_service.py` | BUG-059 (R12) | ✅ Owner scoping |
| `canvas_crud_tool.py` | BUG-015 (R3) | ✅ IDOR ownership checks |
| `identity/did_manager.py` | BUG-037 (R8) | ✅ did:key base58 validation |
| `workflow_engine.py` | BUG-067 (R14) | ✅ Step failure detection |
| `spend_aggregation_service.py` | R4 (investigated) | ✅ Correct filters |
| `reflection_service.py` | R9 (investigated) | ✅ No generate_critique method |
| `periodic_tasks.py` | R1 | ✅ Doc freshness reevaluate |

### api/ — Audited & Tested
| File | Bug(s) / Round | Status |
|------|---------------|--------|
| `canvas_routes.py` | BUG-015, BUG-071 (R3, R15) | ✅ CRUD ownership, history IDOR |
| `admin/budget_routes.py` | BUG-008 (R1) | ✅ 404/422 status codes |
| `agent_routes.py` | BUG-029, BUG-050 (R6, R11) | ✅ Limit bounds, get_active_tasks |
| `document_routes.py` | BUG-030 (R6) | ✅ Limit/offset bounds |
| `auth_2fa_routes.py` | BUG-074, BUG-091 (R16, R21) | ✅ Backup code invalidation, enable/disable rate limits |
| `nav_stub_routes.py` | BUG-058 (R12) | ✅ User scoping |
| `board_routes.py` | BUG-059 (R12) | ✅ Owner scoping |
| `analytics_dashboard_endpoints.py` | BUG-060 (R12) | ✅ success_rate fix |

### accounting/ — Audited & Tested
| File | Bug(s) / Round | Status |
|------|---------------|--------|
| `ledger.py` | BUG-070 (R15) | ✅ POSTED status filter |
| `reconciliation.py` | BUG-075 (R16) | ✅ flag_anomaly persistence |
| `export_service.py` | R15 (investigated) | ⚠️ N+1 queries (performance, not blocking) |

### integrations/ — Audited & Tested
| File | Bug(s) / Round | Status |
|------|---------------|--------|
| `mcp_service.py` | BUG-033, BUG-034 (R7) | ✅ File read/traversal safety |
| `chat_orchestrator.py` | BUG-002 (R1) | ✅ Budget propagation |
| `chat_routes.py` | BUG-002 (R1) | ✅ Budget_exceeded short-circuit |
| `unified_calendar_endpoints.py` | BUG-068 (R14) | ✅ End-before-start validator |
| `xero_service.py` | BUG-084 (R18) | ✅ Fixed dead sync path |
| `plaid_service.py` | BUG-085 (R18) | ✅ Cross-account token fixed |
| `stripe_routes.py` | R18 (investigated) | ✅ Health/capabilities only — no payment logic |
| `routes/webhooks/base.py` | BUG-087 (R19) | ✅ HMAC base64/hex heuristic fixed |
| `routes/webhooks/slack_webhooks.py` | BUG-088 (R19) | ✅ Event dedup added |
| `routes/webhooks/shopify_webhooks.py` | R19 (investigated) | ✅ Uses fixed base.py |
| `routes/webhooks/twilio_webhooks.py` | R19 (investigated) | ✅ Correct signature verification |
| `routes/webhooks/whatsapp_webhooks.py` | R19 (investigated) | ✅ Correct verify_token + signature |

### core/ — newly covered (Rounds 17-19)
| File | Bug(s) / Round | Status |
|------|---------------|--------|
| `app_secrets.py` | BUG-079 (R17) | ✅ PBKDF2HMAC import fixed |
| `sql_validator.py` | BUG-080 (R17) | ✅ Stacked-query injection blocked |
| `credential_vault.py` | BUG-081 (R17) | ✅ Denylist redaction |
| `enterprise_security.py` | BUG-082 (R17) | ✅ Brute-force account lockout |
| `tenant_discovery.py` | BUG-083 (R17) | ✅ Stale cache on rebind fixed |
| `audit_trail_validator.py` | BUG-086 (R19) | ✅ Real completeness check + correct columns |
| `gateway_key_routes.py` | R17 (investigated) | ✅ Keys hashed, atomic rotate |
| `sandbox_fs.py` | R18 (investigated) | ✅ Path traversal defended |
| `webhook_renewal_service.py` | R19 (investigated) | ✅ Active filter + failure handling |

### core/ + api/ + frontend — newly covered (Round 21 — 2FA + federation identity)
| File | Bug(s) | Status |
|------|--------|--------|
| `api/auth_2fa_routes.py` | BUG-091 (R21) | ✅ enable/disable TOTP rate-limited |
| `core/identity/verifiable_credentials.py` | BUG-093 (R21) | ✅ enable_revocation honored (fail-closed) |
| `components/Settings/TwoFactorSettings.tsx` | BUG-092 (R21) | ✅ backup codes read from envelope |
| `core/federation/federation_security.py` | BUG-094 (R22) | ✅ handshake-failure volume metric fixed |

### frontend — newly covered (Round 20)
| File | Bug(s) | Status |
|------|--------|--------|
| `Onboarding/CostCalculator.tsx` | BUG-089 (R20) | ✅ Stale state on empty estimate |
| `finance/SubscriptionTracker.tsx` | BUG-090 (R20) | ✅ Cancelled sub display fixed |
| `lib/backendAuth.ts` | R20 (investigated) | ✅ Correct token storage + Bearer prefix |
| `lib/api-client.ts` | R20 (investigated) | ✅ Clean re-export |

### ai/ — Audited & Tested
| File | Bug(s) / Round | Status |
|------|---------------|--------|
| `intelligence_background_worker.py` | BUG-051 (R11) | ✅ Stale data refresh |

---

## Frontend — COVERED Files

### hooks/ — Audited & Tested (30 hooks with dedicated tests)
| File | Bug(s) | Status |
|------|--------|--------|
| `useWebSocket.ts` | BUG-004, BUG-005, +reconnect | ✅ Full: streaming, sendMessage, backoff |
| `useBoardWebSocket.ts` | BUG-013 | ✅ dirtyTaskIds union |
| `useChatInterface.ts` | BUG-014 | ✅ Timeout cleanup, budget branch |
| `useFileUpload.ts` | BUG-053 | ✅ Progress clamp |
| `useSpeechRecognition.ts` | BUG-044 | ✅ Mic leak |
| `useTextToSpeech.ts` | BUG-045 | ✅ Voice clobbering |
| `useUserActivity.ts` | BUG-048 | ✅ Hidden tab heartbeat |
| `useCanvasStateRegistration.ts` | BUG-049 | ✅ Registry wipe |
| `useMemorySearch.ts` | BUG-040 | ✅ Stale race |
| `useCognitiveTier.ts` | BUG-039 | ✅ Hardcoded workspaceId |
| `useLiveSupport.ts` | BUG-076 | ✅ Auth header |
| `useUndoRedo.ts` | investigated | ✅ Correct |
| `useLiveFinance.ts` | investigated | ✅ Correct |

### components/ — Audited & Tested
| File | Bug(s) | Status |
|------|--------|--------|
| `canvas/ViewOrchestrator.tsx` | BUG-007 | ✅ Crash on missing data |
| `boards/SlashCommandBar.tsx` | BUG-006 | ✅ Error envelope |
| `boards/KanbanBoard.tsx` | BUG-027 | ✅ sort_order collision |
| `GlobalChat/ChatMessage.tsx` | BUG-006 | ✅ Error variant |
| `shared/CommentSection.tsx` | BUG-035 | ✅ JSON.parse crash |
| `shared/TaskManagement.tsx` | BUG-066 | ✅ Mock data removed |
| `shared/CommunicationHub.tsx` | BUG-066 | ✅ Mock data removed |
| `Agents/ReasoningChain.tsx` | BUG-036 | ✅ Double submit |
| `Agents/AgentStudio.tsx` | BUG-052 | ✅ Stale test result |
| `Onboarding/OnboardingWizard.tsx` | BUG-018 | ✅ Bearer null |
| `Voice/WakeWordDetector.tsx` | BUG-077 | ✅ Mic leak |
| `finance/TransactionsList.tsx` | BUG-017 | ✅ Date off-by-one |
| `dashboards/FinanceCommandCenter.tsx` | BUG-012 | ✅ Domain filter |
| `admin/jit-verification/VerificationLogs.tsx` | BUG-066 | ✅ Mock data removed |

### pages/ — Audited & Tested
| File | Bug(s) | Status |
|------|--------|--------|
| `login.tsx` | BUG-026 | ✅ callbackUrl |
| `analytics.tsx` | BUG-055 | ✅ URL fix |
| `health.tsx` | BUG-063 | ✅ Promise.allSettled |
| `finance/index.tsx` | BUG-064 | ✅ NaN amount |
| `agents/index.tsx` | BUG-065 | ✅ Stop double-click |
| `search.tsx` | BUG-062 | ✅ Stale closure debounce |
| `canvas/index.tsx` | BUG-073 | ✅ Filter buttons |
| `dev-studio.tsx` | BUG-061 | ✅ Response shape |
| `marketplace.tsx` | BUG-078 | ✅ Rating crash |
| `integrations/index.tsx` | BUG-072 | ✅ Health URLs |

### lib/ — Audited & Tested
| File | Bug(s) | Status |
|------|--------|--------|
| `crypto.ts` | BUG-031 | ✅ AES-CBC→GCM |
| `date-utils.ts` | BUG-017 | ✅ toDateOnlyISO |
| `error-mapping.ts` | BUG-021 | ✅ 429 retry |
| `sanitize.ts` | investigated | ✅ DOMPurify correct |
| `validation.ts` | investigated | ✅ Anchored regex |

---

## TOP 20 CRITICAL UNCOVERED FILES (next rounds target)

### Backend Priority (security/billing/data)
1. `integrations/plaid_service.py` — banking data aggregation
2. `core/credential_vault.py` — credential storage
3. `integrations/quickbooks_service.py` — accounting sync
4. `core/sql_validator.py` — SQL injection guard
5. `api/gateway_key_routes.py` — API gateway key management
6. `core/app_secrets.py` — application secret bootstrap
7. `integrations/stripe_routes.py` — payment webhook routes
8. `api/routes/webhooks/{slack,shopify,twilio,whatsapp}_webhooks.py` — inbound webhooks
9. `core/sandbox_fs.py` — sandbox filesystem isolation
10. `core/audit_trail_validator.py` — audit trail integrity
11. `integrations/xero_service.py` — Xero sync
12. `core/enterprise_security.py` — enterprise policy enforcement
13. `core/federation/federation_security.py` — federation identity
14. `core/tenant_discovery.py` — tenant resolution
15. `core/webhook_renewal_service.py` — webhook renewal

### Frontend Priority (auth/billing/UI)
16. `lib/backendAuth.ts` — server-side auth helper
17. `components/Settings/TwoFactorSettings.tsx` — 2FA UI
18. `components/Onboarding/CostCalculator.tsx` — pricing
19. `components/finance/SubscriptionTracker.tsx` — subscription state
20. `lib/api-client.ts` — central API client

---

## Round History

| Round | Bugs | Focus Area |
|-------|------|-----------|
| 1-3 | BUG-001..018 | Core services, WS, budget, auth, canvas, freshness |
| 4 | BUG-019..023 | OAuth CSRF, memory recall, retry, search, dates |
| 5 | BUG-024..027 | Webhook HMAC, graduation, login redirect, Kanban |
| 6 | BUG-028..031 | Token decode, DoS limits, crypto GCM |
| 7 | BUG-032..036 | Scheduler runaway, MCP path safety, comments, feedback |
| 8 | BUG-037..040 | did:key auth, workflow edges, workspace, memory race |
| 9 | BUG-041..045 | Pricing billing, embeddings, speech, TTS |
| 10 | BUG-046..049 | Teams dedup, forecast, heartbeat, canvas registry |
| 11 | BUG-050..053 | Agent registry, intel worker, AgentStudio, upload |
| 12-13 | BUG-054..065 | Sidebar nav routes, page data-handling |
| 14 | BUG-066..069 | Mock data purge, workflow, calendar, API key |
| 15 | BUG-070..073 | Accounting balance, canvas IDOR, integrations, filter |
| 16 | BUG-074..078 | 2FA replay, anomaly persistence, mic leak, rating crash |
| 17 | BUG-079..083 | Security core: PBKDF2 import, SQL injection, credential leak, brute-force lock, tenant cache |
| 18 | BUG-084..085 | Payments: Xero sync dead code, Plaid cross-account token |
| 19 | BUG-086..088 | Webhooks: audit validator false-compliance, Shopify HMAC, Slack dedup |
| 20 | BUG-089..090 | Frontend: CostCalculator stale state, SubscriptionTracker cancelled display |
| 21 | BUG-091..093 | 2FA enable/disable brute-force, 2FA recovery codes envelope, VC revocation config |
| 22 | BUG-094 | Federation security handshake-failure metric undercount |
