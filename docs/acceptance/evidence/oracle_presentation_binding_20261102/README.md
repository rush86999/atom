# ORACLE presentation-binding repair — evidence bundle

Status: **submitted for independent verification; no claim verdict changed.**

This repairs the three reproduced false passes that withheld the consolidated
`f8f8de387` candidate. It is a new frozen source; older bundles are unchanged.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Executed source | `0d8767e3ac2494dd7a4b88ffc790f898035e8586` |
| Tree at execution | clean (`0 modified, 0 untracked`) |
| Runtime identity | `source_id=0d8767e3ac24 ... dirty=False` |
| World | `full-app-quote-20261102` (durable world on `8096/3137`) |
| Frontend build | `SAOb9wYp1j8dBc4h_u5dn` |
| Transport | controlled canvas action; no live provider |

## What was wrong

The presentation oracle read the **latest** `canvas_audit` row for a canvas
and compared only title, component type and point count. It never bound the
material or the current operation. Three probes therefore passed:

1. markdown with the right title but wrong total (`999.00` vs `350.00`);
2. a chart with the right type/count but wrong point values (`y=999`);
3. an old audit certifying a new operation when the handler wrote no new row.

## Repair

- `core/presentation_material.py` is the single canonical material/digest
  source used by both the executor and the canvas tools.
- The executor deep-freezes the complete authorized presentation material and
  operation/workspace/tenant identity **before dispatch**; missing markdown
  content or chart type/data refuses before the handler runs
  (`presentation_binding_unavailable`).
- `tools/canvas_tool.py` persists the material, its digest, the governed
  `operation_id`, workspace and tenant on the audit row and returns the exact
  `audit_id`. Title, length and point count remain diagnostic.
- `_canvas_present_postcondition` requires that exact audit id, safe scope,
  the frozen operation id and the frozen material digest. It recomputes the
  digest from the persisted material, so a forged returned digest cannot
  rescue a wrong audit.
- A post-dispatch refutation keeps the remote id and original operation and
  settles `uncertain`; the existing blocked-dependent/reconcile-once path is
  unchanged.

Adjacent classification: `goals.decompose` is **structural plan-output
validation** (1/1), not durable execution proof. Durable local mutations are
8/8 and external mutations 6/6. 827 HTTP mutation declarations and 311
provider writes remain explicitly unqualified.

## Controls run on this source

- The verifier's three supplied negative probes: **3 passed**
  (`negative-probe.log`).
- 28 focused presentation controls: exact positive twins, same-title wrong
  content, same-count wrong chart values, old audit with identical content,
  missing audit, wrong workspace, exact audit wins over a newer latest row,
  forged returned digest, handler argument mutation, pre-dispatch missing
  material, concurrent presentations, plan-output classification
  (`focused-controls.log`).
- Backend combined matrix: **470 passed** (`backend-tests.log`).
- Frontend canvas panels: **7 passed** (`frontend-tests.log`).
- Normal-app campaign: **17/17** (`campaign-result.json`). The declared
  presentation's audit row carries the same operation id as the pending
  approval (`3fbb4144…`); duplicate approval leaves the audit count at 1;
  pending operation/payload identity survives a real restart; all three DOCX
  files carry their totals, provenance and Georgia 18.

## Books rerun on this source

The invoice-to-Books journey was rerun on the same source in a separate world
(`full-app-bookkeeping-presentation-fix`, API 8100): **12/12 passed**. One
governed create with verified readback, provider `creates=1/readbacks=1`, and
both duplicate controls leave `creates=1` (second step `failed` with a
duplicate message). The connected readback path is unchanged by the
presentation pre-dispatch freeze; its focused suites are also inside the
470-test matrix.

## Open

Whole-app HTTP/provider coverage, TEAM-05 real sweep transport, MEM-07
approval/apply consumption, ORCH/GOAL model work, MINI Linux/KVM and
INT/ROUTE live authorization. No live action, credential, spend or reseed.
Historical 111/123 and the 123-feature denominator are unchanged.
