# Phase 1: "Everywhere" Interface (IM Adapters) - Context

## Current State Analysis

**Date**: February 15, 2026
**Completion**: 90% ✅

### What Already Exists

Atom already has comprehensive IM adapter infrastructure:

1. **UniversalWebhookBridge** (`integrations/universal_webhook_bridge.py`)
   - Routes 14+ platforms: Slack, Discord, WhatsApp, Telegram, Teams, Google Chat, Matrix, Facebook Messenger, Line, Signal, SMS (Twilio), Email, Intercom, OpenClaw
   - Slash commands: `/run <agent> <task>`, `/workflow <id>`, `/agents`, `/help`, `/status`
   - Auto-sends responses back to platforms via `agent_integration_gateway`
   - 529 lines, fully implemented

2. **TelegramAdapter** (`core/communication/adapters/telegram.py`)
   - X-Telegram-Bot-Api-Secret-Token verification
   - Message sending with Markdown parsing
   - Voice message support (transcription integration)
   - Media download (voice messages)
   - 106 lines, production-ready

3. **WhatsAppAdapter** (`core/communication/adapters/whatsapp.py`)
   - X-Hub-Signature-256 HMAC verification
   - Message sending via WhatsApp Cloud API
   - Media download (audio, images)
   - 139 lines, production-ready

4. **14+ Platform Adapters** (`core/communication/adapters/`)
   - All major platforms supported
   - Consistent `PlatformAdapter` interface
   - Each adapter implements: `verify_request()`, `normalize_payload()`, `send_message()`, `get_media()`

5. **CommunicationService** (`core/communication_service.py`)
   - Routes messages through adapters
   - User identity resolution via `UserIdentity` model
   - Voice transcription (Telegram voice → text → LLM)
   - Slash command handling
   - Agent processing via `handle_manual_trigger()`

6. **ProactiveMessagingService** (`core/proactive_messaging_service.py`)
   - Agent-initiated messaging with governance
   - Maturity-based routing:
     - STUDENT: Blocked (403)
     - INTERN: Requires approval (PENDING)
     - SUPERVISED: Auto-approved with monitoring
     - AUTONOMOUS: Full access
   - API endpoints: `/api/v1/messaging/proactive/send`, `/approve`, `/reject`

7. **Telegram Routes** (`integrations/telegram_routes.py`)
   - `/api/telegram/webhook` - Webhook endpoint
   - Interactive keyboards (inline buttons)
   - Callback queries (button presses)
   - Inline mode (search in chat)
   - Chat actions (typing indicators)
   - Photos, polls, documents

### What's Missing (10% Gap)

1. **IMGovernanceService** (HIGH Priority)
   - **Problem**: Each adapter implements security independently
   - **Risk**: Inconsistent verification, no rate limiting, no audit trail
   - **Solution**: Centralized security layer for all IM platforms
   - **Impact**: Critical for enterprise-grade security

2. **WhatsApp Webhook Route** (MEDIUM Priority)
   - **Problem**: `WhatsAppAdapter` exists but no `/api/whatsapp/webhook` endpoint
   - **Current Workaround**: Can use `UniversalWebhookBridge` with manual routing
   - **Solution**: Add dedicated WhatsApp webhook route (like Telegram)
   - **Impact**: Convenience, consistency with Telegram

3. **IM Integration Tests** (MEDIUM Priority)
   - **Problem**: No security tests for webhook spoofing, rate limiting
   - **Risk**: Security vulnerabilities undetected
   - **Solution**: Test suite for IM adapters
   - **Impact**: Quality assurance, security validation

4. **Documentation** (LOW Priority)
   - **Problem**: No setup guide, security best practices
   - **Impact**: Slower adoption, security misconfigurations
   - **Solution**: IM_ADAPTER_SETUP.md, SECURITY_GUIDE.md

### Architecture Gap Analysis

**Current Flow** (Fragmented Security):
```
Telegram Webhook → TelegramAdapter.verify_request() → TelegramAdapter.normalize_payload()
                                                                    ↓
WhatsApp Webhook → WhatsAppAdapter.verify_request() → WhatsAppAdapter.normalize_payload()
                                                                    ↓
                                                 UniversalWebhookBridge.process_incoming_message()
                                                                    ↓
                                                 ChatOrchestrator.process_chat_message()
```

**Problems**:
1. Each adapter implements `verify_request()` differently
2. No rate limiting (spam vulnerability)
3. No centralized audit trail
4. No governance checks before routing to ChatOrchestrator
5. Inconsistent error handling

**Target Flow** (Governance-First):
```
Telegram Webhook → IMGovernanceService.verify_and_rate_limit() → IMGovernanceService.check_permissions()
WhatsApp Webhook → IMGovernanceService.verify_and_rate_limit() → IMGovernanceService.check_permissions()
                                                                    ↓
                                                 UniversalWebhookBridge.process_incoming_message()
                                                                    ↓
                                                 ChatOrchestrator.process_chat_message()
                                                                    ↓
                                                 IMGovernanceService.log_to_audit_trail()
```

**Benefits**:
- Centralized security (one place to audit)
- Consistent rate limiting (10 req/min per user)
- Governance checks before any agent execution
- Comprehensive audit trail (all IM interactions logged)

### Dependencies

**Internal Services** (Already Exist):
- `AgentGovernanceService` - Maturity checks (STUDENT → INTERN → SUPERVISED → AUTONOMOUS)
- `GovernanceCache` - <1ms permission lookups
- `UniversalWebhookBridge` - Message routing
- `ChatOrchestrator` - Agent processing
- `AgentIntegrationGateway` - Outbound messaging
- `ProactiveMessagingService` - Agent-initiated messages

**External Services** (Already Configured):
- Telegram Bot API (bot token configured)
- WhatsApp Cloud API (access token configured)
- Signal (unofficial bridge, signal-cli-rest-api)

### Success Criteria (Phase 1 Revised)

**Original Goal**: "User can send 'Run the payroll report' via Telegram and receive response"

**Current Reality**: ✅ **ALREADY WORKS** via:
1. `/api/telegram/webhook` receives message
2. `UniversalWebhookBridge` routes to `ChatOrchestrator`
3. Agent processes request
4. `AgentIntegrationGateway` sends response back to Telegram

**Revised Goal**: "Add governance hardening so IM commands are secure, auditable, and rate-limited"

### Implementation Approach

**Plan 01: IMGovernanceService Implementation**
- Create centralized security layer
- Implement webhook signature verification (Telegram, WhatsApp)
- Add rate limiting (10 req/min per user_id)
- Integrate with `GovernanceCache` for permission checks
- Log all IM interactions to audit trail

**Plan 02: WhatsApp Webhook Route**
- Add `/api/whatsapp/webhook` endpoint
- Implement webhook verification challenge (GET)
- Route POST messages to `UniversalWebhookBridge`
- Add health check endpoint

**Plan 03: IMGatewayService Enhancement**
- Extract response formatting logic from `UniversalWebhookBridge`
- Support rich media (photos, polls, keyboards)
- Handle platform-specific quirks (markdown vs HTML)
- Add error recovery (retry failed sends)

**Plan 04: IM Integration Tests**
- Test webhook signature verification (spoofing attempts)
- Test rate limiting (burst requests)
- Test permission checks (STUDENT blocked, etc.)
- Test audit trail logging

**Plan 05: Documentation & Security Guide**
- IM_ADAPTER_SETUP.md (Telegram + WhatsApp setup)
- SECURITY_BEST_PRACTICES.md (webhook verification, rate limiting)
- TROUBLESHOOTING.md (common issues)

### Timeline (Revised)

**Original Estimate**: 3-5 days
**Revised Estimate**: 2-3 days (90% already built)

**Parallelization Opportunities**:
- Plan 01 (IMGovernanceService) and Plan 02 (WhatsApp Route) can run in parallel
- Plan 04 (Tests) can start after Plan 01 completes
- Plan 05 (Docs) can start anytime

**Optimistic**: 2 days (Plan 01 + 02 in parallel, Plan 03-04 sequential)
**Realistic**: 3 days (sequential execution, buffer for testing)
**Conservative**: 4 days (unforeseen security issues)

### Risk Assessment (Revised)

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| WhatsApp business verification blocks Personal users | Low | Medium | Personal = Telegram only (as planned) |
| Rate limiting false positives (legit users blocked) | Medium | Low | Configurable limits, whitelist override |
| IMGovernanceService breaks existing flows | High | Low | Extensive testing, gradual rollout |
| Webhook spoofing bypasses verification | Critical | Low | Security audit, penetration testing |

---

## Conclusion

Phase 1 is **90% complete** and production-ready for basic IM interactions. The remaining 10% is **governance hardening** to make it enterprise-grade.

**Key Insight**: We're not "building IM adapters from scratch" — we're adding a **security governance layer** on top of existing, working infrastructure.

**Next Steps**: Proceed with revised Plan 01 (IMGovernanceService) as the foundation for enterprise-grade IM security.
