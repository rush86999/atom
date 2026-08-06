## Plan: Push to 95% Bug-Free + Coverage Tracking Doc

### Current State
- **78 bugs fixed** across 16 rounds (BUG-001 → BUG-078)
- **~45% file coverage** (720/1,597 files audited)
- **21/21 nav route tests pass** (all sidebar items work end-to-end)
- **All mock data removed** from production components

### Step 1: Create the coverage tracking doc
Write `docs/AUDIT_COVERAGE_TRACKER.md` documenting:
- Every covered file (backend + frontend) with which bug/round covered it
- Every uncovered file grouped by directory
- The top 20 critical uncovered files ranked by impact
- Round-by-round history table
- Coverage percentages per area

### Step 2: Rounds 17-20 — Hit the top 20 critical uncovered files
Each round probes 5-8 of the top-20 files via TDD (failing test → fix → green):

**Round 17 (security core):** credential_vault, app_secrets, sql_validator, gateway_key_routes, tenant_discovery, enterprise_security  
**Round 18 (payments/banking):** plaid_service, stripe_routes, quickbooks_service, xero_service  
**Round 19 (webhook routes):** slack/shopify/twilio/whatsapp webhook routes, webhook_renewal_service, audit_trail_validator  
**Round 20 (frontend critical):** backendAuth.ts, TwoFactorSettings, CostCalculator, SubscriptionTracker, api-client.ts, sandbox_fs

### Step 3: Update the tracker after each round
After each round, update the tracker doc: move files from UNCOVERED → COVERED, add new bugs, recalculate coverage %.

### Definition of "95% bug-free"
- All **critical-path files** (auth, billing, payments, secrets, webhooks, tenant isolation) audited and tested
- All **sidebar nav routes** pass end-to-end (already done)
- No **mock data** in production (already done)
- No **known security vulnerabilities** (IDOR, auth bypass, injection, replay)
- Test suite green on all touched files

### Out of scope
- Full unit-test coverage of every integration adapter (200+ files) — these are low-risk third-party wrappers
- E2E browser tests (WDIO/Tauri still blocked)
- Performance optimization (N+1 queries documented but not blocking production)