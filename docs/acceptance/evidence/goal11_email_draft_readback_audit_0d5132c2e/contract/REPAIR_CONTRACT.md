# FINITE REPAIR CONTRACT — ordinary email draft save/read scope + shared write

Status: **proposed; awaiting root engineering approval. No runtime code was
changed in this audit.**

## Reproduced failures (public JWT + scratch SQLite at 0d5132c2e)

F1. `POST /api/canvas/email/{id}/draft` accepts an inactive actor
(`User.is_active=False`, status still active): 200 and draft mutation.
Expected: refusal before effect (existing `require_active_actor` semantics).

F2. The same route accepts an actor whose current tenant/workspace moved after
the canvas/audit was created: 200 and mutation.
Expected: refusal before effect (current actor scope, exact canvas scope).

F3. The same route accepts a canvas moved to a foreign tenant/workspace: 200
and mutation. The new audit still says `tenant_id="default"`.
Expected: refusal before effect; no audit/mirror mutation.

F4. `save_draft` always writes `tenant_id="default"` (and
`create_email_canvas` writes Canvas/audit `tenant_id/workspace_id="default"`),
so the durable receipt does not carry the current actor/canvas scope.

F5. Two independently authenticated editors can save without any prior
revision token; all three saves return 200 and the stale editor overwrites the
accepted peer body. Expected: the existing ordered/CAS contract refuses a
stale expected-prior save (as generic PUT already does with 409).

F6. Public email `create` under a non-default current user returns 200 but
writes Canvas/audit `default`; the ordinary generic PUT then refuses with 403
(different tenant) and appends nothing. The product can create a draft it
cannot save through its own ordinary path.

F7. After an ordinary generic PUT of an email dict, `GET /api/canvas/email/{id}`
returns 200 with an empty `draft` body, while `GET /api/canvas/{id}` returns
the exact saved `content.body`. The email-specific read does not project the
generic update shape.

## Proposed minimal implementation (reuse; choose one with root)

Preferred: make the email-specific route a **thin adapter over the existing
shared verified write**:

1. `POST /api/canvas/email/{id}/draft`
   - Resolve current actor via existing `core.canvas_authority.
     require_active_actor` / `require_canvas_read`.
   - Accept optional `expected_prior_audit_id` (and, if root requires, make it
     mandatory for guarded frames).
   - Build the native email dict (to/cc/subject/body plus preserved
     thread/attachment metadata) and call the existing
     `core.canvas_write_service.update_canvas_verified` with the actor's
     current tenant/workspace.
   - Return the shared verified envelope/audit id; no direct Canvas/Audit
     mutation in `save_draft`.
   - Keep `save_draft` as a private compatibility shim only if another caller
     cannot be migrated; otherwise remove the duplicate write path.
2. `POST /api/canvas/email/create`
   - Use existing `core.personal_scope.resolve_tenant_id` /
     `resolve_workspace_id` from the current user (or pass route-resolved
     scope) for Canvas and audit rows. Never hardcode `default`.
3. `GET /api/canvas/email/{id}`
   - Read through the existing `visible_canvas_material` and project the
     generic `content` dict into the email `draft` shape (or return one
     consistent shape). No second store/read engine.
4. Preserve existing attachment/review/send rules. No send/provider/model
   call in this repair.

Alternative (root choice): explicitly deprecate/refuse the legacy `/draft`
route and direct clients to the generic PUT; keep create/read scope fixes.
Do not build a parallel email engine, store, CAS, or approval lifecycle.

## Acceptance controls (scratch, real JWT, no send/provider/browser)

1. Owner positive: generic and email-specific saves each return truthful
   durable draft; exact to/cc/subject/body after fresh SQL session, fresh OS
   process and reopen; verification/audit receipt carries current scope.
2. Inactive actor, moved actor, foreign user and moved target refuse before
   effect: no Canvas mirror or CanvasAudit row changes, typed 4xx.
3. Stale expected-prior save returns the shared conflict (409); accepted peer
   content is not overwritten silently.
4. Email `create` under a non-default current scope writes matching Canvas and
   audit scope and the ordinary generic save succeeds.
5. Generic GET and email-specific GET agree after both write paths.
6. Existing attachment/import/send tests and prior connected-core generic
   draft/reopen evidence remain green; no send/provider call.
7. No new store/router family/engine/schema/approval; no CI/PR/merge.

## Non-goals / preservation

- Keep full 143-claim / 18-goal scope and original negative evidence.
- No live DB/provider/send/model/browser/install/new dependency.
- Existing frontend worker owns graduation files; this branch touches no
  graduation files.
- Root approves the adapter choice before runtime repair; this packet is
  diagnosis + contract only.
