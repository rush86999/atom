# Integrated full-app candidate — oracle + evolution + taught artifacts + invoice-to-Books

Status: **submitted for independent verification; not self-accepted.**

This candidate supersedes the `2b5db4b98` consolidated bundle. It keeps the
accepted frozen-request/connected-oracle line, the taught-artifact and
identity-persistence fixes, and the single Memento evolution lifecycle, then
adds shared local effect-family postconditions, controlled Books transport,
document-backed assignment sources, and a normal-app invoice-to-Books journey.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` |
| Executed source | `f8f8de387bfb8979bf9e2d17779f71b53bcb982d` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Quote world | `full-app-quote-20261102` on `8096` / `3137` |
| Bookkeeping world | `full-app-bookkeeping-integrated-f8f8de387` on `8099` / `3140` |
| Runtime identity | both journeys: `source_id=f8f8de387bfb ... dirty=False` |
| Transport | controlled canvas action; controlled Zoho Books ledger; no live provider |

Integration commits on this line:

- `b049c0761` — accepted connected-oracle protections merged with taught artifacts;
- `55fff94f2` — one canonical Memento candidate lifecycle;
- `2ebcf9353` — effect counter and pending identity across restart; service/queue documents;
- `2b5db4b98` — action-registry isolation between tests;
- `f8f8de387` — shared local postconditions, controlled Books, invoice journey, document sources.

## What is integrated

- **Accepted frozen-request oracle:** before-dispatch deep request snapshots,
  canonical provider/operation/organization/target bindings, six connected
  mutation verifiers, fail-closed readback, uncertainty/no-resend.
- **Canvas audit + local effect families:** shared postconditions for
  `canvas.present_markdown`, `canvas.present_chart`, `canvas.update`,
  `canvas.restore_version`, `goals.create`, `goals.evaluate`,
  `goals.decompose`, `goal_runs.start`, `tasks.create`, plus the existing
  `trigger_workflow`. All 9 local durable mutation classes in the inventory are
  now covered; no bespoke per-route checker was added.
- **Taught artifacts and identity:** receipt-derived document deliverables,
  applied-operation `remote_id`/`provider_ref`, duplicate approval does not
  dispatch, pending operation/payload identity survives a real process restart.
- **One evolution lifecycle:** the parallel HITL candidate store is gone.
  GenericAgent tool failures feed the existing event/episode/ReflectionEngine/
  Memento path; review uses the existing Auto-Dev candidate routes.
- **Invoice-to-Books:** real invoice bytes are uploaded and parsed through the
  normal document route; extracted facts drive the real assignment planner;
  vendor and complete CoA are resolved; the proposal is exact and balanced;
  the governed registered Books action runs once; complete material readback
  is verified; restart preserves the pending approval; duplicate continuation
  and the same invoice both refuse without another create.

## Journeys

### Normal quote/service/exception — 17/17

`quote-journey-result.json` records the full normal-app journey: promoted
lesson, quote receipt, real backend restart with identical pending operation
and payload digest, DOCX artifact `350.00`, Georgia 18 consumption, action
readback / audit count 1 → 1, source change `450.00` + `409 stale_revision`,
service `630.00 CAD`, exception `3 / 170.00`, and cancellation.

### Invoice-to-Books — 12/12

`bookkeeping-result.json` records: invoice parse/upload, extracted facts,
normal assignment start, vendor/CoA/proposal resolution, exact `120.00`
proposal, real backend restart with the same pending approval, one governed
create (`bill-controlled-1`), verified material readback, provider effect count
1, duplicate approval 404 with count unchanged, and same-invoice duplicate
refusal with count unchanged.

All three document fixtures are in this bundle with their hashes:
`quote-document.docx`, `service-document.docx`, `queue-document.docx`.

## Oracle coverage

`oracle-registry.txt` lists the 16 loaded verifiers. The regenerated inventory
(`oracle-whole-app-inventory/`) reports:

- 90 registered actions;
- 6 external mutations, **6 covered**;
- 9 local durable mutations, **9 covered**;
- 827 mutating HTTP route declarations and 311 provider-adapter write methods
  remain **unqualified** discovery candidates.

This is not whole-app ORACLE-01 closure. The 827 HTTP declarations are not
proven reachable writes, and no percentage of application correctness is
claimed.

## Tests

| Scope | Result |
|---|---|
| Combined backend matrix | **269 passed** |
| Frontend canvas panels | **7 passed** |
| Normal quote/service/exception journey | **17/17** |
| Invoice-to-Books journey | **12/12** |

## Open

- Whole-app HTTP/provider mutation coverage beyond the registered families.
- TEAM-05 real LLM sweep transport; MEM-07 approval/apply and later consumption.
- ORCH/GOAL model-backed planning; MINI Linux/KVM; INT/ROUTE live authorization.
- No 24-hour soak, multi-worker, model-quality or live-provider claim.

## Exclusions

No live provider lookup, refresh, write, send, credential, consent or spend.
Controlled canvas action and controlled Books ledger only. Historical 111/123,
connected `6431bcb78`, typed-canvas `4859b0ce2477`, canvas assignment/teaching
`a87882526323` and earlier evidence bundles are unchanged.
