# Mini-app instance authority — November 16, 2026

Mini-app instance data belongs to its authorized canvas users. Publishing or
sharing an app definition does not grant access to another user's installed
records, files or state; creating the original app does not make its author the
owner of every installed copy.

The previous `mini_app_run` path reached state, assets, guest execution and
writes without a canvas authority check. The separate API instance helper
accepted any authenticated user when the app was public, while record tools
accepted the original app author. An independent signed-in HTTP replay confirmed
that sharing an app exposed an installer's synthetic record to another user.

## Resulting behavior

- Run and state reads use the existing active-user, canvas owner/co-editor,
  current tenant/workspace and non-deleted-canvas policy. The acting user comes
  from durable state, not caller-supplied scope fields or an app-author shortcut.
- Every integration prefetch and guest callback rechecks fresh authority and the
  frozen actor/target scope and instance identity. A deleted canvas, deactivated
  user, or paired user-and-canvas scope move cannot authorize an old-scope call.
  A refusal stops later prefetches; completed earlier effects are not rolled back.
- Record, asset and update-check reads use the same canvas policy. Public app
  flags and approval are not grants to installed-instance data. Historical
  co-editors retain the accepted read policy. Direct record/asset API and
  record-tool mutations remain instance-owner-only and claim the actor/target
  before their effects; stateful runs use the accepted canvas write policy.
- App listing, definition, sharing, publication and approved installation keep
  their existing contracts. Agent maturity floors and record ORACLE receipts,
  material binding, CAS and idempotence contracts are preserved.

Custom callers must provide a real authenticated actor and valid canvas
provenance. Test fixtures now seed actual Tenant, Workspace, User and CanvasAudit
rows instead of relying on imaginary principals. These are the same authority
rows normal registration, scaffold and installation produce.

## Source-bound evidence

Runtime/privacy implementation: `3589a8c8b1e79e87f789a8414dc3e31c1c310ab5`.
The final test-only correction is `2b0695946`; it seeds the existing ORACLE
fixture's missing tenant/workspace and extends the permanent HTTP restart test.
The branch includes verified main `452c509a1` (#966).

- Independent actual-tool/service and peer-session SQLite probes verified owner
  and installer positives, foreign and original-author denial, deactivation,
  deletion and paired scope moves. Denials preserved durable state/version and
  dispatched no simulated integration calls.
- A separate actual record-tool probe permitted the installer to append/read,
  denied the original author both read and write, and verified no record or
  audit count changed on refusal. Its maturity context was controlled; this is
  not a model/graduation quality measurement.
- A real `main_api_app` journey used normal registration/login, scaffold,
  publish, install and public sharing. Owner requests succeeded; foreign record,
  series, single-record, asset-list and update-check reads and record writes
  were refused. RPC state/run denials and owner readback repeated after a new
  backend process and fresh login. Guest execution was forbidden by a tripwire.
- Final independent gate: **147 passed** in 128.93 seconds on Python 3.12/macOS,
  including the permanent real-process restart journey and existing ORACLE
  receipt/material/CAS controls. A verified local-only socket profile blocked
  external services, model ports and owner-app ports; all databases were scratch.
- CI adds only the two focused authority/privacy suites. The already-selected
  restart journey now permanently covers public sharing and authenticated
  negative twins. Earlier jobs, commands and fixture entries remain intact.

Earlier failures remain retained: the cached-user callback counter, the deleted
and paired-scope counters, the original public-record HTTP leak, the first gate's
missing tenant fixture, and a replay request missing its required series field.
No failure was converted into a passing test by relaxing authority or receipts.

Private receipts are under `/private/tmp/atom-authority-root-final-20261116/`,
`/private/tmp/atom-miniapp-auth-http-fixed-v2-20261116/`,
`/private/tmp/atom-instance-record-tool-proof-20261116/` and
`/private/tmp/atom-instance-final-20261116/`.

This is bounded authority and instance-data evidence. It does not qualify real
integration credentials, model selection, a browser journey, Firecracker,
whole-run rollback/retry semantics or every mutating family in the app. Original
143 claim identities, 18 goals and historical scores remain unchanged.
