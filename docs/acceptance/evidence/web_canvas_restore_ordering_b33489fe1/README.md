# Canvas restore ordering repair — b33489fe1

Executed source: `b33489fe1` on `codex/web-canvas-restore-ordering-20261110`,
created from evidence head `79b47bc27` (authority repair `82b29cfcc` and its
evidence remain unchanged).

## Repair

`restore_canvas_version` selected its latest row with `created_at DESC` only.
Same-second rows tied, so the no-op guard could select the older requested
version and report `no_change` without appending, while `read_canvas` served
the newer tied row. That is the observed “bad edit” vs requested “good draft”
failure.

- Use the established `_latest_canvas_audit` helper (`created_at DESC, id
  DESC`) for the current revision.
- Use the existing `latest_canvas_content_audit` helper for the no-op guard,
  so a contentless/event-only latest row cannot hide the actually visible
  content. Fall back to `Canvas.content` only when the audit history has no
  body.
- Preserve append-only history, strict-recency append, type pin/canonical
  restore content, delete refusal, `restored_from` provenance, scope/authority
  and replay behavior.
- No new version engine, store or migration.

The parallel HTTP consumer `POST /api/canvas/{id}/restore` calls
`restore_canvas_verified`, which calls this same `restore_canvas_version`; no
separate ordering logic exists.

## Failure-first proof

Predecessor (`79b47bc27` / source `82b29cfcc`) with explicit opaque ids and
real SQL:

- same-second good/bad rows: authoritative read `bad edit`, restore returned
  `no_change`, fresh read stayed `bad edit` — **FAILED as expected**.
- contentless latest with genuine no-change: restore appended instead of
  returning zero effect — **FAILED as expected**.
- 2 passed, 2 failed, exit 1.

Post-fix (`b33489fe1`): **4 passed, exit 0**.

Focused affected group: **286 passed, exit 0** — version/restore/oracle/
lifecycle/crud/list/present/fork/receipt/form/feedback.

Raw logs and scratch DBs remain private under `/private/tmp`.

## Limits

- No browser, live provider/model, install, deployment, PR or merge.
- No Python 3.14 or broad-suite claim.
- Deterministic tests use explicit ids; random-UUID-only tie ordering is not
  relied on.
- The previous authority evidence packet at
  `docs/acceptance/evidence/web_canvas_authority_82b29cfcc` is unchanged.
