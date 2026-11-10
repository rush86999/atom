# Email legacy nested-draft precedence — source-bound repair

Bounded repair of the general email-content normalizer. This is the successor
to the ordinary email UI packet `email_draft_ordinary_browser_1d762c2f3`
(commit `013209bfa`, preserved 14/14; not rerun). Root rejected the earlier
"harness-only" classification: `normalize_email_content` really did prefer a
legacy nested `draft` over present canonical top-level fields, while the read
side treated top-level key presence as authoritative.

- Base: `013209bfab6d4d48e1b377e5781ad1be33f12b94` (product
  `1d762c2f3`, matches clean PR829 `7fb2645c9`; evidence/CI deltas only)
- Branch: `codex/email-normalizer-legacy-draft-precedence-20261110`
- Worktree: `/private/tmp/atom-goal11-office-browser-20261110`
- No PR/merge/CI/goal-index edits; root owns integration.

## Defect (source evidence)

`backend/core/chat_draft_classifier.py::normalize_email_content` had two
opposite contracts:

- `backend/api/canvas_email_routes._email_canvas_view` — canonical top-level
  `to`/`cc`/`subject`/`body` wins **by key presence**; a nested `draft` is a
  fallback only for absent keys.
- `normalize_email_content` — whenever a nested `draft` dict existed, it
  rebuilt the canonical fields from that draft, ignoring present top-level
  values (including explicit empty values).

The ordinary CanvasPanel reads the stored dict (including the nested draft
written by the native draft route `_native_email_content`) and spreads it back
on save, so every visible edit was reverted to the stale draft. This matches
the first UI episode's three 200 OK autosaves that persisted the OLD seed.

`diagnosis/pre-fix-negative.txt` runs the exact base-commit function (extracted
from `git show 013209bfa:...`) against realistic CURRENT top-level + stale OLD
draft content and shows OLD precedence. The new function returns CURRENT.

## Producers/consumers traced

- `canvas_email_service.create_email_canvas` (create audit `draft`)
- `canvas_email_service.import_eml` (metadata `draft`)
- `canvas_email_routes._native_email_content` (writes top-level **and** a
  nested `draft`)
- CanvasPanel generic PUT (spreads `state.data`, writes visible top-level)
- `tools.canvas_crud_tool.visible_canvas_material` / `canonical_update_content`
  → `coerce_email_canvas` → `normalize_email_content`
- `integrations/chat_routes.chat_draft_to_canvas`
- acceptance trial helper

## Fix (existing general normalizer)

`backend/core/chat_draft_classifier.py`

- Present canonical top-level key wins, including explicit empty
  (`""`/`[]`/`None`); nested `draft` is used only for absent keys.
- A present draft's canonical view is refreshed from the resolved top-level
  values (and attachments when top-level attachments are present); `draft_id`
  and provenance keys are preserved. Normalization is idempotent.
- Recipient values canonicalize between comma-string and list forms.

`backend/tools/canvas_crud_tool.py::visible_canvas_material`

- The legacy draft bridge fills only absent keys (or a body for the
  legacy Canvas-row content with no content-bearing audit). A
  present-but-empty canonical value is never resurrected from
  `details.draft`.

## Compatibility negative (not merely harness)

Two pre-existing `test_chat_draft_classifier.py` exact-dict tests asserted a
4-key `{to, cc, subject, body}` projection, but the base implementation
already returned `**content` (provenance keys). Those tests were already
inconsistent with the implementation; they are aligned to the
provenance-preserving contract here. `diagnosis/pre-existing-test-negative.txt`
runs the base function on the two exact inputs and shows the extra keys.

The precedence change is also a real compatibility change for any caller that
passed a details dict with a divergent top-level canvas subject and draft
subject; in-repo callers were traced and pass canonical content. See
`diagnosis/compatibility-negative.md`.

## Tests

New `backend/tests/test_email_legacy_draft_precedence.py`:

- top-level + stale nested draft → top-level wins;
- explicit empty top-level → empty wins;
- legacy-only draft → positive;
- provenance/`draft_id` preserved; nested view refreshed;
- idempotency for all three shapes;
- list recipient canonicalization;
- `coerce_email_canvas` uses the same precedence.

Public save/readback twins in `backend/tests/test_email_draft_shared_writer.py`
(real FastAPI routes, real JWT, scratch SQLite; no browser/provider/model):

- generic PUT carrying a stale nested `draft` keeps the visible edits;
- explicit empty fields do not resurrect stale `details.draft` on readback.

## Gate results

Full bounded gate (3 files, `gates/bounded-full-first.log`): first run
`110 passed, 2 failed`; the two failures are the pre-existing exact-dict
tests described above. Focused rerun after aligning those tests
(`gates/bounded-focused-rerun.log`): `9 passed`, `GATE_EXIT=0` (the two
corrected tests plus the seven new normalizer tests). The gate is the shared
serialized `run_bounded_test_gate.py --profile bounded`; no root graduation
test was duplicated or stopped.

## Preserved

- Original Office packet `office_email_ordinary_browser_1d762c2f3/` untouched.
- Original email UI packet `email_draft_ordinary_browser_1d762c2f3/` untouched
  (14/14 Git-verified at `013209bfa`).
- No send/provider/model/browser/live DB. No CI/PR/merge.

## Non-claims

This is one bounded normalizer/readback repair with source-level negatives and
regression tests. Root owns CI inclusion, integration, and final acceptance.
