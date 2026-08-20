# Atom Security & Compliance Control Mapping

**Date:** 2026-08-20 · **Scope:** self-hosted AGPL edition (this repository)

This document maps Atom's implemented features to the control frameworks most
often requested in enterprise procurement. It is a capability mapping, **not a
certification**: SOC 2 / ISO 27001 attestations are the deploying organization's
responsibility, and Atom's controls are the technical evidence you build on.

---

## SOC 2 (Trust Services Criteria)

| Criterion | Atom control | Implementation |
|---|---|---|
| CC6.1 — Logical access | Multi-user auth, 8-role RBAC enforced at route level; OIDC SSO; SCIM v2 user provisioning (automated joiner/mover/leaver from your IdP) | `backend/core/rbac_service.py`, `core/security_dependencies.py`, `api/auth_routes.py`, `api/sso_oidc_routes.py`, `api/scim_routes.py` |
| CC6.1 — Credential protection | OAuth/integration tokens encrypted at rest with Fernet; production fails closed without a key | `core/privsec/token_encryption.py` |
| CC6.6 — Boundary protection | Outbound Gatekeeper: per-provider rate limits, response masking, fail-closed HITL approval for mutations, data-taint egress blocking | `middleware/governance_middleware.py`, `core/data_taint_tracker.py` |
| CC6.8 — Malicious-code / execution controls | Tool whitelists, filesystem scope, tripwires, resource caps, KillRun at all tool-dispatch hubs; Firecracker microVMs for mini-apps | `core/sandbox_gate.py`, `core/sandbox_policy.py`, `core/sandbox_runtime/firecracker_runner.py` |
| CC7.2 — Monitoring | Audit logging (agent runs, canvas/browser/device activity, sandbox violations) with retries | `core/audit_service.py`, `core/sandbox_audit.py` |
| CC7.3 — Incident evaluation | KillRun registry stops live runs; HITL queue surfaces anomalies for review | `core/sandbox_killrun.py`, `core/hitl_service.py` |

## EU AI Act (high-risk / GPAI obligations in force since mid-2026)

| Obligation | Atom control |
|---|---|
| Art. 12 — Record-keeping / logging | Audit trail records agent actions, tool calls, approvals, and sandbox events with actor identity and timestamps |
| Art. 14 — Human oversight | HITL approval gates (including 2FA for urgent actions), 4-tier autonomy maturity caps what agents may do without review |
| Art. 13 — Transparency | Agent-authored outputs carry provenance; two-tier confidence marks INTERNAL (self-reported) vs EXTERNAL_VERIFIED results |
| Art. 10 — Data governance | Data-taint tracking prevents restricted data observed in a run from leaving the infrastructure |
| Risk management documentation | This mapping + `docs/architecture/CLOUDFLARE_OS_SECURITY.md` as the technical baseline |

## NIST AI RMF

| Function | Atom control |
|---|---|
| GOVERN | Role-based administration, governance config surfaces (`api/gatekeeper_routes.py`), org-level policy via edition distributions (`core/edition.py`) |
| MAP | Specialist matcher and capability registry document which agent/tool combinations are permitted |
| MEASURE | Oracle verification re-derives outcomes against systems of record (opt-in enforcement); per-agent verified-success counters drive graduation |
| MANAGE | Maturity tiers constrain autonomy; stuck-detection and definition-of-done terminate runaway loops; KillRun for immediate stop |

## GDPR-relevant data controls

- Self-hosted deployment: data residency is entirely the operator's (no vendor telemetry).
- `ATOM_LOCAL_ONLY=true` blocks all cloud egress (`core/privsec/local_only_guard.py`).
- `memory_forget` tool supports erasure of stored agent memory facts.
- BYOK: LLM inference uses the operator's provider accounts; no vendor-managed key pool.

## Known gaps (tracked honestly)

- Sandbox enforcement is in-process policy checking (not container/seccomp) outside mini-app Firecracker VMs, and fails open on internal errors by documented design.
- SSO is OIDC and provisioning is SCIM v2; SAML is on the roadmap (SAML IdPs work today via an OIDC-bridging proxy).
- Audit trail completeness is validated for finance workflows (`core/audit_trail_validator.py`); no platform-wide completeness invariant yet.
- Oracle enforcement is **on by default** (since 2026-08-20: refuted self-reports are stamped UNVERIFIED on the observation; `ATOM_ORACLE_ENFORCE=false` reverts to pass-through). The reviewer loop remains opt-in.
- Office editing is agent-driven with live preview broadcast — real multi-user CRDT co-editing is intentionally not built (decision 2026-08-20: that is ChatGPT Canvas'/emerging CRDT editors' race, not Atom's wedge; revisit only if office-native becomes the primary differentiator).
- The bespoke three-layer policy engine (`core/governance/`) was removed as dead code (never wired into dispatch). For centralized policy-as-code, the roadmap is OPA/Cedar sidecar integration rather than a bespoke engine.

## Decision log (2026-08-20, web-researched)

| Open question | Decision | Rationale |
|---|---|---|
| Oracle enforcement default | **Complete** (default ON) | Zero-trust-for-agents is the 2026 trust narrative (CSA Agentic Trust Framework; Gartner's projection that ~40% of agent projects get demoted for missing verification). Verified outcomes are Atom's differentiator — leaving enforcement off was backwards. |
| CRDT multi-user co-editing | **Remove** (aspiration dropped) | The CRDT-agents-as-peers wave is real, but it's ChatGPT Canvas / dedicated collaborative editors' race; not Atom's wedge. |
| Bespoke 3-layer policy engine | **Remove** | Policy-as-code trend is OPA/Cedar integration; a bespoke default-allow engine that was never wired in is liability, not capability. |
| SAML + SCIM | **SCIM shipped** (2026-08-20); SAML **roadmap** | SCIM covers the IdP joiner/mover/leaver loop with OIDC; SAML needs XML-stack deps and is increasingly bridged anyway. |
