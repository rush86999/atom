# Production-Ready Security Hardening (P0–P9)

> Ten-phase security hardening (Aug 2026) that closes the Cloudflare-style OS
> gaps for self-hosted AI agents: credentials encrypted at rest, per-agent tool
> scoping, an outbound gatekeeper, data-taint tracking, credential-safe sharing,
> a real MCP client, per-canvas sandboxed logic, workspace-scoped context, and a
> default-on deterministic sandbox.

## At a glance

| Phase | What it stops | Key module | Default |
|---|---|---|---|
| **P0** Credential Encryption | Token theft at rest | `core/privsec/token_encryption.py` | on (fail-closed in prod) |
| **P1** Action Registry | Bypassable dispatch seams | `core/action_registry.py`, `POST /api/rpc/{action}` | on |
| **P2** Capability Bindings | Over-privileged agents | `core/capability_resolver.py` | on (`["*"]` = unrestricted) |
| **P3** Outbound Gatekeeper | Ungoverned external calls | `middleware/governance_middleware.py` | on |
| **P4** Data Taint | Sensitive-data exfiltration | `core/data_taint_tracker.py` (`VT_PROVENANCE`) | on |
| **P5** Blueprint Security | Credential leak on share/fork | `core/blueprint_sanitizer.py`, `POST /api/canvas/{id}/fork` | on |
| **P6** Real MCP Client | Hardcoded-only tool surface | `core/mcp_client.py`, `/api/mcp/servers` | on |
| **P7** Canvas Runtime | Unbounded server logic | `core/canvas_logic_service.py` (per-canvas namespace) | on (AUTONOMOUS-gated) |
| **P8** Workspace Context | Cross-workspace knowledge leak | `Workspace.metadata_json`, `workspace_skills` | on |
| **P9** Sandbox Default-On | Prompt-injection blast radius | `core/sandbox_gate.py` (all dispatch paths) | **on** (kill switch) |

## The two headline wins

**1. Every agent tool call is now sandboxed by default.** Previously only the
meta-agent enforced the deterministic blast-radius layer; the legacy dispatch
(generic agents, workflow, fleet, business agents) bypassed it. P9 added a
shared gate (`core/sandbox_gate.py`) at `integrations/mcp_service.call_tool` so
all callers are bounded identically — filesystem scope, tool whitelist,
tripwires, caps, KillRun. `ATOM_SANDBOX_FORCE_ENFORCE=false` restores shadow
mode instantly.

**2. OAuth integration tokens are encrypted at rest, fail-closed.** P0 made
`IntegrationToken` access/refresh tokens Fernet-encrypted with
`BYOK_ENCRYPTION_KEY` (env or persisted key file), and production refuses to
start without a key rather than minting a throwaway that would brick stored
ciphertext on restart.

## Where to read more

- Sandbox layer (P9): [SANDBOX_LAYER.md](SANDBOX_LAYER.md)
- Credential encryption (P0): [../security/DATA_PROTECTION.md](../security/DATA_PROTECTION.md)
- External MCP client (P6): [MCP_SERVER.md §External MCP Client](MCP_SERVER.md#external-mcp-client-p6)
- Per-phase component map: [CLAUDE.md §Cloudflare OS gap-closure](../../CLAUDE.md)
- Trust-vs-sandbox rationale: [../security/TRUST_VS_SANDBOX.md](../security/TRUST_VS_SANDBOX.md)

## Verification

115 phase tests green (`backend/tests/test_{integration_token_encryption,action_registry,capability_resolver,gatekeeper,data_taint_tracker,blueprint_sanitizer,canvas_fork,mcp_client,canvas_logic_service,workspace_context,sandbox_default_on}.py`); migration chain linear and guarded; kill switches documented per flag.
