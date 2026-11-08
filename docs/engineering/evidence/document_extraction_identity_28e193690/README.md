# Document extraction and scoped content identity repair

Executed source: `28e193690bc3f896cb7a5b9c1232251aa40946e0`.
This packet qualifies scratch public-API parsing/storage/export controls, not normal-browser format acceptance or whole-app completion.

## Runtime defects and corrected behavior

- Real malformed and empty DOCX uploads previously returned 200 and exported parser placeholder text as authoritative. The original failed controls and captures remain unchanged. Empty/unavailable extraction now refuses before upload storage/index/SQL/side-effect dispatch. Empty direct-text ingestion also refuses. Missing parser branches return absent extraction rather than invented prose; folder sync skips blank extraction.
- Identical extracted content in two authorized workspaces previously reused a global document identity, changed the peer SQL owner and made one export unavailable. The independent real factory/two-physical-store probe remains unchanged. New document identities bind authenticated workspace, tenant and content; body-supplied identity fields cannot override them. Legacy identifiers are reused only for matching authoritative SQL scope; existing stored identities are not migrated.
- The newly added SQL identity lookup records only stage/exception class on failure. Its independent error-hygiene test proves the synthetic private error phrase is absent from response/logs.

## Verification

- Namespace source `b7bd0540a`: 22 focused controls passed on Python 3.14, including real python-docx parsing and separate workspace stores.
- Final source above: 710 passed and 10 failed across 15 selected affected modules on each Python 3.14 and 3.11. These are identical failed test identities. The exact ten failures were rerun on pre-repair source `ffd934e2f`; all ten failed there too on each Python version with matching assertion/error summaries. This is a failed-subset baseline comparison, not a complete baseline run.
- Final independent error-hygiene control: 1 passed on Python 3.14 (also included in both broad runs).
- No tests were deleted, skipped or xfailed to obtain these results. Existing stale assertions, constructor/mock assumptions and token-free child-environment failures remain disclosed in raw logs. General parser truncation and unrelated SaaS client tests are not silently repaired here.

## Isolation and reproducibility

Specs and launchers retain exact source, commands, isolated database/data/office/output/Lance paths and exit states. Both broad runs disable outbound Python IP connections with the included pytest plugin; offline model-library settings are set, and API/access-token/AWS environment values are removed from the child. Embedding is doubled by the existing export fixture; no model/provider inference is claimed. The original failing DOCX proof uses the real python-docx fallback with optional Docling disabled. The baseline disables pytest-rerunfailures because its localhost coordination socket is unavailable under the local restriction; it does not retry tests. The 3.11 helper is included. Private scratch DBs are retained separately, not published.

## Limits

No browser run has qualified these DOCX changes yet. No general extraction/grounding, binary round-trip, search, all-format, large-file or live-provider claim. Cross-store atomicity, SQL-mirror failure behavior, upload authority races, general path anchoring, legacy placeholder cleanup and manual-upload freshness remain separate unresolved boundaries. No live account, connected effect, spend, send or deployment occurred. This repair does not close general TASK-WAIT-01 or the app-wide goal.
