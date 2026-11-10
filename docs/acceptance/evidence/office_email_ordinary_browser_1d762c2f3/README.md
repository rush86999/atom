# Office ordinary browser continuation — integrated 1d762 source

Source: `1d762c2f3daee7746cf2430cd3ae37e8971364f7` (root-integrated
7319 scope + PR827 email source). Worktree/branch:
`/private/tmp/atom-goal11-office-browser-20261110` /
`codex/office-email-ordinary-browser-20261110`.
World: `office_ordinary_browser_1d762c2f3d_1794309563`, fresh marked child of
the root-verified canonical worlds root. Immutable code snapshot
`b75055f7407e34de0c7fb2730fcb48b05f9228c36c14af6edafe93346004728f`.

## Preserved negative / partial

The initial ordinary browser campaign at this source downloaded both DOCX and
PPTX from the visible controls; UI/API bytes matched and package semantics
passed (headings/list/table; two slides/titles/body/table/notes). The initial
one supported UI edit committed (`NEW-4242`, table 9/8; OLD absent), but the
visible `Save Changes` locator detached while CanvasPanel `onBlur`
`flushAutosave` ran; the click observation timed out. Root readback
(`root_readback.sanitized.json`) independently proved the save committed and
the latest audit carries NEW. This is classified as a harness/observation
timeout, **not** a failed save. The original timeout trace and initial result
are preserved under `partial/`.

## Authorized same-run continuation

No fresh world, no new campaign, no edit/save click, no API edit. The exact
retained run `run-b25cb62b465c` was resumed with the existing
`run_isolated.launch_server(reuse_run_dir=...)`; same DB/descriptor and same
1d762 immutable source. Ordinary bootstrap admin (raw NULL/NULL) API/UI login
and already-durable onboarding passed. The exact saved canvas
`9bdfe77a-c44b-44e6-8bee-8210388a9573` was opened; one visible Download DOCX
returned:

- browser and API bytes equal, SHA-256
  `54a56ad39838bee306a606e59eec51694d49932d95084b33554122685211a038`
- current source audit `cf0fd722-49b4-42b0-a06a-d8e89d7f328b`
- package contains `NEW-4242`, not `Intro paragraph OLD.`, table `9/8`
- request 200, correct DOCX type/filename/ETag, current audit in URL

Resume required an existing-bootstrap fixture password reset for the retained
run because the generated password file had been overwritten by a later
attempt. It changed only the admin User credential; canvas content, latest
audit `cf0fd...`, raw NULL scope and all package bytes were unchanged
(verified read-only). This is disclosed, not a product/API edit.

## Evidence

- `capture/continuation.result.json` — resumed steps/checks/stops
- `capture/package.semantic.json` and `capture/requests.json`
- `capture/canvas-current.png`, `capture/canvas-current.page.txt`
- `capture/root_readback.sanitized.json`
- `partial/` — initial DOCX/PPTX positives + Save-click timeout trace
- `root_integrated/` — root 12-control review/controls at 1d source

No model/provider/send/live DB/credentials. No product code edit. No PR/merge/
CI/goal-index. Root owns final review.

## Non-claims

This is one supported generated document download/continuation at the integrated
source, not general Office/browser/whole-GOAL-11 acceptance. The initial PPTX
positive is retained as partial evidence; the continuation exercised DOCX only.
