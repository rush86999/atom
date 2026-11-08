# LEAD REVIEW — BPE current-principal scope (Phase 1, finite)

Branch: `codex/bpe-current-principal-scope-20261108`
Base: `8ded00232c30961a990e675e06ec672ef6a43910`

## Defect

`POST /api/rpc/{action}` supplied `user`/`user_id`/`db`, but the BPE handlers
read `workspace_id` / `agent_id` / `session_id` from the dispatch context and
defaulted a miss to `("default", "atom_main", "")`. Every authenticated RPC
caller appended to one shared buffer. The Generic path had the same
caller-params-as-context exposure (`api/agent_routes.py` passes request params
as the run context).

## Repair (runtime)

- `core/bpe/actions.py` — single scope resolver for all four actions:
  - authenticated `User` row is re-read fresh and must be active;
  - canonical workspace = the row's `workspace_id`, or an isolated
    `personal:<user_id>` namespace for the single-tenant NULL/Personal default;
  - scope key is per-principal (`user:<id>`), so a same-workspace peer still
    never inherits another user's buffer;
  - the principal's raw `tenant_id` is checked against the real Workspace
    row's tenant under the existing NULL/`default` single-tenant policy. A
    contradictory real tenant/workspace pair refuses *before* `get_workspace`
    and before any append (`scope_workspace_tenant_mismatch`); a missing real
    Workspace row refuses too. The principal row and the old buffer are left
    untouched;
  - `note` and `commit` claim the active principal row (and the protected
    Workspace row) with a conditional no-op UPDATE before writing. The claim
    freezes the tenant/workspace binding read during resolution, so a peer
    changing either concurrently makes the claim match zero rows and the append
    is refused (`scope_principal_*` / `scope_authority_changed` /
    `scope_workspace_tenant_mismatch`);
  - a stale presented row that disagrees with the fresh row is refused rather
    than silently moved/merged;
  - bare/shared `default` is refused for caller/legacy contexts; it is only
    accepted as a server-bound agent scope with a real session/run key;
  - read-only `track`/`recall` resolve the same compatible current authority
    (no peer read and no tenant-contradictory read).
- `core/generic_agent.py` / `core/atom_meta_agent.py` — bind the reserved
  server-authority scope after reading caller params. Prompt rendering, episode
  reset and close-out all read the same binding, so the prompt and the action
  handlers address one namespace. A caller-supplied reserved copy is dropped.
- `core/bpe/actions.py` `bpe_scope_from_context` — on a resolution denial it
  returns an empty scope; prompt/close-out callers skip BPE state. It no longer
  falls back to a raw reserved or shared-`default` context value. Legitimate
  server-bound scopes still resolve normally.
- `api/rpc_routes.py` — the action's own `success: false` is no longer wrapped
  in an outer `success: true`.

Original action effects (`read` / `update` / `create`) are unchanged; no
read-only relabel, no model-controlled metadata authority, no blanket
registered-action exemption.

## Tests

- `tests/test_lead_bpe_rpc_scope.py` — root-supplied v2 twins. Test bodies are
  unchanged; the fixture now re-runs the production `@register_action`
  decorators per case. Reason: `tests/conftest.py`
  `_isolate_registered_actions` restores the registry after every case while
  the module import is cached, so without re-registration cases 2+ saw 404s.
  This is test-fixture isolation, not a product failure.
- `tests/test_bpe_current_principal_scope.py` — real-row twins: tampered body
  params, different workspace, NULL/Personal and literal-`default` isolation,
  missing/inactive principal, stale authority change, claim-before-append,
  contradictory tenant/workspace vs matching current-authority twin,
  dispatch-context binding, a bounded **real** `GenericAgent.execute`
  consumer (LLM/step/memory/recording stubbed, no provider), MCP current
  context, all four actions, recall read isolation, scope-helper fail-closed,
  anonymous default refusal.

The `GenericAgent` twin exercises the actual `execute` binding and dispatches
the production action through the loop; it is a controlled bounded consumer,
**not** a qualified full-model/Generic-execute qualification.

Verification is deferred to the root test run (no Python/pytest/server was
executed in this finite task).

## Explicitly open (not claimed here)

- Phase 2 durable harness receipts / producer-owned note identity.
- Oracle honesty for `workspace.note` (the current uncertain/close-out gap is
  **not** fixed in this phase).
- Stable long-wait planning memory.
- Full Generic-execute qualification (the bounded consumer is not that claim).
- Multi-worker / multi-process BPE persistence semantics.
- Legacy `default.json` is left untouched: no owner inference, migration or
  cross-user copy is performed.
