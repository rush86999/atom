# Preserve inline pictures when editing DOCX text — November 16, 2026

Editing a paragraph could remove its inline picture even though the DOCX still
contained the image bytes. The paragraph helper assigned `Run.text` to entire
runs, which replaces their content. The repair replaces only text children in
mixed runs, leaving drawings and other non-text XML in place. It reuses
python-docx's text appender for escaping, tabs and line breaks; no dependency
or authorization change is required. [The upstream run API](https://python-docx.readthedocs.io/en/latest/_modules/docx/text/run.html)
and [mixed run-content model](https://python-docx.readthedocs.io/en/latest/dev/analysis/features/text/run-content.html)
explain why assigning run text can remove non-text content.

## Decisive controls and browser verification

Independent offline production-method counters used fully decoded PNG inputs.
On original source `3316b0fe7`, both a same-run text/picture and a later
picture-only run lost their drawing and embed reference; orphaned media stayed
in the ZIP. On repaired source `8d98b0689`, exact drawing XML, references,
image bytes and replacement text survived. Merely counting media parts would
have falsely accepted the original defect.

A new isolated browser world then exercised both layouts through normal form
login and the exact web session, native attachment of an existing agent, real
file chooser, paragraph edit/blur save, reload and download. Fresh normal
logins reopened the same canvases after both API and frontend restarted.
Every upload and edit occurred once; restart checks did not repeat them.

All four downloaded DOCX files preserved one actual inline drawing, its embed
reference and exact drawing XML. Independent image verification and full
pixel decoding passed. Both cases used a 32×32 checkerboard PNG with SHA-256
`b4fd54b80df8ed1874e0076828c3e367ef25c01e103054d028b4cea564463307`.
Unedited paragraphs and every ZIP part except `word/document.xml` were
unchanged. Exports remained byte-identical across restart:

| Layout | Bytes | Export SHA-256 |
|---|---:|---|
| Text and picture in one run | 37,160 | `ff54f77e824615f8e1a9f7d724d7af7cc29d85357f369ea6173389a653aff9f8` |
| Later picture-only run | 37,157 | `e8881737a8f1cd5911cfbfe83d1a311807257bfb0fc2dcba573c34d9e57b80c2` |

Unsigned download returned 401. Unsigned canvas navigation showed `/login`
with the exact canvas return path and password form. Root independently
confirmed request counts, decoded exports and all four app PIDs absent after
shutdown, with no owned Chrome orphan. Source/build parity, isolated SQLite,
selected-empty provider routes and cached local embedding were used. No
external provider request or live dev database was involved.

## Regression and CI coverage

Five realistic drawing regressions cover same-run, later picture-only,
drawing-only, tab/text and truncation cases. An existing explicit-canvas test
had incorrectly expected a new arbitrary id to bypass ownership. Its fixture
now establishes an owned active canvas, and missing/foreign-id controls require
exact 404 responses with no rebinding. Production ownership remains unchanged.

The whole coediting file is now selected by one additive backend-core step
with isolated SQLite/data/Office paths. Every earlier workflow step, job,
command/environment and inventory entry is preserved. Final local verification
at `6cbc5412a` passed **674 checks in 75.82s**: all 32 coediting tests plus
642 CI/quickstart contracts. Earlier adjacent ownership, tombstone and path
coverage passed in a 77-control gate. The production helper's SHA-256
`826b49cf68943bff9ba32278c5ecdc02a671edd5897bda440aa9cbc0c59e46fe`
is identical to the browser-tested source; later changes were test-data and
CI-only. The runtime uses the supported cached python-docx 0.8.11, matching
the repository's `<1.0.0` requirement range.

## Retained fixture failure and limits

The first synthetic PNG had a bad IDAT checksum. Its successful drawing/XML
roundtrips remain drawing-only evidence, not valid-image acceptance. Those
cases were stopped and retained. The unit fixture was corrected to an
independently decoded PNG with CRC/decompression assertions. Fresh browser
inputs were generated and fully decoded before the new world was launched;
no old upload/edit or claim was replayed.

[The filtered receipt](evidence/docx_inline_image_20261116/result.json) retains
these distinctions. This covers two synthetic inline-PNG layouts, not floating
or external drawings, rich field/hyperlink behavior, page-layout fidelity,
cross-user breadth, model-generated quality or full Goal 5. Original 143
claims and all 18 goals remain unchanged; app completeness is not asserted.
