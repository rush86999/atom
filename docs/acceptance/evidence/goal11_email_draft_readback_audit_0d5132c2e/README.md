# GOAL-11 ordinary email draft readback — runtime audit

Source: `origin/main 0d5132c2e060a5f2ac338bca143c5e138e607658` (resolved current).
Worktree: `/private/tmp/atom-goal11-email-draft-audit-20261110`.
Scope: read-only public-boundary audit of ordinary email draft save/open/
reload/fresh-process. No provider, send, model, browser, live DB or code
repair is included.

## Verdict

The **ordinary frontend path** uses the shared generic canvas write and behaves
correctly in this scratch baseline:

- `CanvasPanel` saves email through `saveCanvasAuditReceipt` /
  `saveCanvasAudit` → `PUT /api/canvas/{id}?canvas_type=email`, with
  `expected_prior_audit_id` on guarded frames.
- `/canvas/[id]` reloads through `GET /api/canvas/{id}` and reads
  `content`.
- Public JWT positive: generic PUT 200 with `verification.status=verified`;
  generic GET returned the exact saved body; stale prior audit 409; moved
  target 403; inactive actor 403; no audit append on refusals.
- The prior accepted connected-core email draft/reopen evidence used this same
  generic PUT/GET path (`write_outcome=committed`, `action_type=update`).

A **concrete parallel-writer gap** is reproduced on the public email-specific
API (`POST /api/canvas/email/{id}/draft` and its read/create siblings):

| Case | Baseline |
|---|---|
| `/draft` owner positive | 200, exact email + generic read, exact fresh SQL, exact fresh OS process |
| `/draft` foreign user | 403 |
| `/draft` inactive actor (`is_active=False`, status active) | **200 and mutation** |
| `/draft` actor moved to another tenant/workspace | **200 and mutation** |
| `/draft` target canvas moved to foreign tenant/workspace | **200 and mutation** |
| `/draft` saved audit scope | **tenant hardcoded `default`** while canvas is `<tenant>` |
| Two independent editors save without any prior-revision token | **200/200/200; stale body overwrites accepted peer** |
| Public email `create` under non-default current actor | 200 but Canvas/audit written `default`; ordinary generic PUT then **403**, audit unchanged |
| Email-specific GET after generic PUT | 200 but `draft.body` **empty**; generic GET returns `shared body` |

The `/draft` writer checks only “is this the first audit author”, then directly
mutates the Canvas mirror and appends an audit row. It does not use the
current active-actor/scope gate or the shared verified write/CAS. This is the
same class of issue the generic path already solves, not a reason to build a
new mail engine.

## Traced consumers and parallel writers

See `trace/CONSUMERS.md`. In short:

- Frontend ordinary save: generic `PUT /api/canvas/{id}` (shared authority +
  optional expected-prior CAS).
- Frontend ordinary reload: generic `GET /api/canvas/{id}`.
- Email-specific API: `/create`, `/{id}/draft`, `/{id}`, `/{id}/message`,
  attachments and `/send` route through `EmailCanvasService`.
- `EmailCanvasService.save_draft` and `create_email_canvas` write Canvas/Audit
  directly and hardcode `tenant_id="default"` / `workspace_id="default"`.
- `GET /api/canvas/email/{id}` returns the newest `CanvasAudit.details_json`;
  a generic update audit carries `content`, not the email `draft` projection,
  so the two read surfaces disagree after an ordinary save.
- Prior accepted connected-core evidence covers the generic path only; it does
  not exercise `/draft` or the email-specific GET after a generic save.

## Baseline artifacts

- `baseline/result.summary.json` — sanitized status/material facts.
- `baseline/commands.txt` — exact command, source and exit.
- `probe/` — sanitized test-only public-route probe and fresh-process child.
- `contract/REPAIR_CONTRACT.md` — finite repair proposal reusing existing
  shared mechanisms, awaiting root engineering approval.

No real addresses, tokens, DB files, raw errors or provider output are
included. Test addresses use `example.invalid`.

## Non-claims

- This is not a browser/UI campaign, a provider/send test or a whole-GOAL-11
  claim.
- The alternative “ordinary UI is already safe” result is explicitly preserved;
  the failing surface is the public email-specific parallel API and its
  create/read split.
- No PR/merge/CI/goal-index/new dependency. Full 143/18 scope and prior
  evidence remain unchanged.
