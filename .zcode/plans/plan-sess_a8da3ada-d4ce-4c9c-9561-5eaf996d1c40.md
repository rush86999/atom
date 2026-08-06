# Mini-App Integrations: Rename + Host-Callback Channel + Marketplace Gaps

Three sequential workstreams.

---

## Workstream 1 — Rename `mcp_servers` → `integrations` (honest naming)

The field is misnamed: it routes through `ExternalIntegrationService`/Node bridge (Activepieces), not MCP. Rename across the mini-app surface, with backward-compat.

**Files:**
- `core/mini_app_service.py`: `validate_manifest` accepts `integrations` (preferred) AND `mcp_servers` (legacy alias, deprecated). `_inject_mcp_sources` → `_inject_integration_sources`, reads `manifest["integrations"]` (falls back to `mcp_servers`). `_build_starter_manifest` + `_STARTER_LOGIC` use `integrations`. `status_probe` reports `integrations`.
- `api/mini_app_routes.py` / `tools/mini_app_tool.py`: no field-name change needed (they pass manifest dicts through), but update comments.
- **Tests**: `validate_manifest` accepts both names; run pre-fetches via `integrations`; `mcp_servers` still works (alias) with a deprecation log.

**Migration of existing manifests:** none needed at the DB level — `manifest` is a JSON column; `integrations` is additive. The alias keeps every existing app working.

---

## Workstream 2 — Host-callback channel (conditional mid-run integration calls)

The big one. Today integration data is pre-fetched once before the run; the guest can't make conditional/iterative calls. This adds a **user-code-initiated blocking callback** over the existing vsock socket.

### Design (grounded in the vsock mechanics investigation)

**Protocol — multiplexed on the single existing vsock socket:**
```
Host → Guest:  {"type":"exec", "code": "...", "inputs": {...}}          # initial
Guest → Host:  {"type":"callback", "kind":"fetch_integration",
                 "service":"notion", "action":"search", "params":{...}}  # mid-run, 0..N times
Host → Guest:  {"type":"callback_result", "ok":true, "data": {...}}      # host services it
Guest → Host:  {"type":"final", "stdout":"...", "stderr":"...",          # terminal
                "exit_code":0, "state_envelope": {...}}
```
The host `_exchange` becomes a loop: send exec → read lines → service callbacks → break on final. Backward-compat: a guest that replies with a non-`type`-tagged line (old agent) is treated as `final`.

**Guest agent changes (`core/sandbox_runtime/firecracker_guest/agent.py`):**
- `main()` keeps the socket OPEN (don't close after reply); stashes it + a `send_request(req) -> reply` helper into the `inputs` dict before `run_code`.
- `run_code` injects a `fetch_integration(service, action, params)` callable into exec globals (`g`). When called by user code, it writes a `{"type":"callback","kind":"fetch_integration",...}` line and blocks on `readline()` for the reply — user code is already blocking inside `exec`, so this is natural. Returns the result payload or raises on error/timeout.
- A separate vsock port is NOT required (multiplexing on one socket is less invasive than teaching `_write_vm_config` two UDS paths).

**Host runner changes (`core/sandbox_runtime/firecracker_runner.py`):**
- `_exchange` → loop: after sending exec, `while True: line = await reader.readline()`. If `type=="callback"` → service it (await the callback handler) → write `callback_result` line. If `type=="final"` or untagged → break, return `(stdout, stderr, exit_code, envelope, callbacks)`.
- Callback time counts against the existing `overall_timeout` (no separate budget).
- Collect `callbacks: List[{service, action, params, ok, duration_ms}]` into `SandboxExecResult.metadata["callbacks"]`.

**Host callback handler (`core/mini_app_service.py`):**
- `run_stateful` passes a `callback_handler` kwarg to `execute_python` that resolves credentials (`_resolve_integration_credentials`, reusing the exact path), calls `ExternalIntegrationService.execute_integration_action`, applies the 5 MiB cap + scope gate (`tool_whitelist` must permit `integrations.<service>` or `*`). Failures return `{ok:false, error}` so user code can react.
- The `execute_python` signature gains an optional `callback_handler: Optional[Callable]` param (backward-compat — None disables callbacks; Docker/E2B/null runners ignore it).

**What this enables:** a mini-app can now do `data = fetch_integration("notion", "search", {"query": state["topic"]})` — conditional, parametrized by computed state — and iterate/paginate. This is what real "3rd party app" support needs.

**Tests:**
- Guest agent: `run_code` with a `fetch_integration` call (mocked socket) returns the host-served result into user code; absence of socket → helper raises a clear error.
- Host runner `_exchange`: mocked UDS — services a callback then receives final; callback time counts against timeout; scope-denied callback returns error.
- `run_stateful`: a logic body that calls `fetch_integration` gets the result; `metadata["callbacks"]` logged; scope gate denies unauthorized service.

---

## Workstream 3 — Marketplace gaps A–G

After 1+2 land. All additive except the two security fixes.

**Gap A — install authz.** `install_mini_app` route + `mini_app_install` tool: add `_require_owner(app, user) OR app.is_public` gate. Non-owner + non-public → 403.

**Gap B — installer-tenant ownership.** `install()` uses the **viewer's** `tenant_id`/`workspace_id` (from `viewer`), not `app.tenant_id`/`app.workspace_id`. Instance canvas + CanvasState + CanvasRecord + MiniAppAsset all land in the installer's namespace. Test: install a cross-tenant app → instance.tenant_id == installer's tenant.

**Gap C — `is_public` + `share_token` activation.** `publish()` accepts an optional `public=True` arg: sets `is_public=True` + mints a `secrets.token_urlsafe(32)` share_token. New route `POST /api/mini-apps/{app_id}/share` (owner-only) toggles public + returns the token. New route `POST /api/mini-apps/by-token/{share_token}/install` installs a public app via token (no app_id needed; tenant = installer's). Existing `install_mini_app` route now requires owner-or-public (from Gap A).

**Gap D — review/approval gate.** Add `is_approved` Boolean column to `MiniApp` (default False). Migration `20260807_add_mini_app_marketplace.py`. Public install requires `is_public AND is_approved` (an admin/moderation gate); owner-installs unaffected. New admin route `POST /api/mini-apps/{app_id}/approve` (admin-only — reuse existing admin dependency). The list endpoint surfaces `is_approved`.

**Gap E — marketplace metadata in browse.** `list_mini_apps` returns `{id, name, description, version, status, is_public, is_approved, declared_scopes, dependencies, integrations_count, created_by, created_at}` — enough to see what an app does and what permissions/integrations it needs before installing. Add optional `?q=` search over name/description.

**Gap F — installed-version tracking + update signal.** Add `MiniAppInstallation` model: `(id, app_id FK, canvas_id FK, tenant_id, installed_version String, installed_at, source: owned|marketplace|share_token)`. `install()` writes a row. New endpoint `GET /api/mini-apps/instances/{canvas_id}/update-check` compares `installed_version` to `app.version` + `app.runtime_version` → `{update_available: bool, latest_version}`.

**Gap G — remove dead stubs.** Delete the empty "External Marketplace" + "Public Marketplace v1 API" try/except shells in `main_api_app.py:1898-1916`.

**Migration `20260807_add_mini_app_marketplace.py`:** adds `mini_apps.is_approved` + `mini_app_installations` table. `down_revision = "20260806_canvas_records"`. Guarded.

**Tests:** install authz matrix (owner ok / non-owner+public ok / non-owner+private 403 / non-owner+unapproved-public 403); cross-tenant install lands in installer's tenant; share-token install; browse metadata includes scopes/deps/integrations; update-check signal; admin approve flow; dead stubs removed.

---

## Build order + verification

1. **WS1 (rename)** — small, isolated, backward-compat alias. Tests: manifest validation both names.
2. **WS2 (host-callback)** — the core protocol change. Guest agent + host runner + run_stateful wiring + scope gate. Tests: guest helper, host loop, end-to-end fetch_integration in run_stateful.
3. **WS3 (gaps A–G)** — security fixes first (A, B), then features (C–F), then cleanup (G). Migration + model + routes + tests.
4. **Full verification:** `pytest tests/test_mini_app*.py -q` all green; `import main_api_app` clean; regression on canvas/sandbox/action_registry suites.

## Backward-compatible
- WS1: `mcp_servers` alias preserved.
- WS2: `callback_handler` is optional (None → no callbacks); old single-turn agents still work (untagged reply = final).
- WS3: new columns have defaults; `is_approved=False` default doesn't block owner-installs; new routes are additive; dead-stub removal is cosmetic.

## Out of scope
- Frontend browse/install UI (API-complete; UI is follow-up).
- Full moderation workflow (just the `is_approved` gate + admin route; review queue UI is follow-up).
- MCP protocol support for real (the rename + callback channel make the pre-fetch model honest; if true MCP tool-server support is later needed, that's a separate effort).