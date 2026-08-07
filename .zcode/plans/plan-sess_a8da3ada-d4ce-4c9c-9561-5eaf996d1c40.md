# Unified Integration Dispatcher — native + Activepieces + MCP for mini-apps

## Goal

Mini-apps reach only **one** of three integration surfaces today (Activepieces). Extend `fetch_integration` into a 3-way auto-resolving dispatcher so guest code does `fetch_integration("notion", "search", {...})` and the host routes to the best backend: **native → piece → MCP → not_found**. One guest API, all three surfaces, credentials resolved host-side.

## The three backends (resolution order)

| Order | Backend | Probe | Credentials |
|---|---|---|---|
| 1 | **native** (`IntegrationRegistry`) | `service in DEFAULT_SERVICE_REGISTRY` (in-memory dict; 63 entries) | `IntegrationToken(tenant_id, provider=service)` → `config={"access_token": ...}` at construction |
| 2 | **piece** (`ExternalIntegrationService` → Node bridge) | `node_bridge.get_piece_details("@activepieces/piece-{service}")` is not None | same `IntegrationToken` row, reshaped to `{access_token, refresh_token, token_type, instance_url}` as `credentials=` |
| 3 | **mcp** (`core/mcp_service` → `MCPClient`) | tool name found in `mcp_service.tools_cache` (scan servers) | server-config-scoped (no per-call creds); just needs `server_id` + tool name |

## Files

### 1. NEW `core/mini_app_integration_dispatch.py` — the dispatcher

The single resolution + execution engine, reused by both the callback handler and the manifest pre-fetch. Pure async functions:

- `_to_piece_name(service) -> str` — `"slack"` → `"@activepieces/piece-slack"` (fixes the latent bug where the friendly name was passed where the package name is required).
- `_resolve_native(service, action) -> bool` — `service in DEFAULT_SERVICE_REGISTRY` (+ optional `get_capabilities()` check).
- `_resolve_piece(service) -> bool` — `await node_bridge.get_piece_details(piece_name) is not None`.
- `_resolve_mcp(service, action) -> Optional[str]` — scan `mcp_service.tools_cache` for a tool named `{service}_{action}` or `{service}.{action}`; return the `server_id` that hosts it.
- `resolve_backend(service, action) -> ("native"|"piece"|"mcp"|None, Optional[server_id])` — the ordered probe.
- `execute_native(service, action, params, tenant_id, db) -> dict` — load creds from `IntegrationToken`, construct `service_class(tenant_id, config={"access_token":...})`, call `execute_operation(action, params, context)` or the matching method. Returns `{"ok":..., "data":...}`.
- `execute_piece(service, action, params, tenant_id, db) -> dict` — load creds, call `ExternalIntegrationService.execute_integration_action(piece_name, action, params, credentials)`.
- `execute_mcp(server_id, tool_name, args) -> dict` — `mcp_service.call_external_tool(server_id, tool_name, args)`.
- `dispatch(service, action, params, *, tenant_id, db) -> dict` — resolve_backend → execute_* → uniform `{ok, data, backend, service, action}` result (or `{ok:False, error}`).

### 2. MODIFY `core/mini_app_service.py` — route the callback + pre-fetch through the dispatcher

- **`_make_callback_handler`**: the `fetch_integration` branch replaces the hardcoded `ExternalIntegrationService` call with `dispatch(service, action, params, tenant_id=tenant_id, db=db)`. **Scope gate**: `integrations.<service>` permits native+piece; `mcp.<server_id>` permits MCP (resolved server_id). Keep `*` as unrestricted.
- **`_inject_integration_sources`**: each manifest entry resolves through `dispatch` (try native → piece → mcp at pre-fetch time; inject the result under `data_sources[service]`). Same cap/failure semantics.
- **`_STARTER_LOGIC`**: document that `fetch_integration` auto-resolves across native/piece/mcp.

### 3. Tests — NEW `tests/test_mini_app_integration_dispatch.py`

Mock each backend and verify resolution order + execution + fallback:
- native wins over piece when both exist for "notion"
- piece used when native absent, piece present ("slack")
- mcp used when neither native nor piece, tool found in tools_cache
- not_found when none resolve
- native creds threaded from IntegrationToken (mock) — service constructed WITH access_token
- piece friendly→package-name translation (`slack` → `@activepieces/piece-slack`)
- mcp scope gate: `mcp.<server_id>` required (not `integrations.<server_id>`)
- failure isolation: backend throws → `{ok:False, error}`, dispatch continues
- end-to-end: `run_stateful` with a `fetch_integration` call dispatches through the resolver (mock all three)

## Backward-compatible
- The guest API (`fetch_integration(service, action, params)`) is unchanged — only the host-side routing changes.
- Existing manifest `integrations` entries (`{service, action, params}`) work identically — they now resolve through the dispatcher instead of only Activepieces.
- The `mcp_servers` alias is unaffected.
- Scope gating: `*` still permits everything; `integrations.<service>` still permits native+piece; the new `mcp.<server_id>` is additive.

## Out of scope
- Tool/action introspection UI (the dispatcher probes at call time; no catalog endpoint in this pass).
- MCP server registration UX (admin route already exists at `POST /api/mcp/servers`).
- Credential refresh/expiry handling (the dispatcher loads whatever `IntegrationToken` holds; refresh is a separate concern).

## Verification
- `pytest tests/test_mini_app_integration_dispatch.py tests/test_mini_app_callback_channel.py tests/test_mini_app_marketplace.py tests/test_mini_app_integrations_rename.py tests/test_mini_app_*.py -q` → all green.
- `import main_api_app` clean.
- Regression: existing mini-app + canvas + action_registry suites green.