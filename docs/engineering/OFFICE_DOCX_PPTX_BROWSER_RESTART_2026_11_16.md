# DOCX and PPTX browser edits and restart — November 16, 2026

Ordinary browser journeys saved a DOCX paragraph edit and a PPTX title edit at
published source `3316b0fe71a1203a90e0f4ec856d7eb5a08d2f4a`. Fresh logins
reopened the same canvases after both API and frontend processes restarted;
each exported file remained byte-identical to its saved pre-restart version.
This covers two synthetic local document journeys, not every Office operation
or full Goal 5 acceptance.

## Observed boundary

Each journey used normal form sign-in, the exact web session, a new canvas,
native attachment of the launcher's existing Demo Assistant and a real file
chooser. The native blur/save returned 200 and success; readback and export
used the real application. No auth/cookie/app-state injection or HTTP mocking
was used. Each successful upload and edit occurred once. Post-restart checks
were read-only and did not recreate documents.

**DOCX:** The existing synthetic quote has 17 paragraphs, five paragraph styles
and three tables. Editing paragraph 2 preserved exact text/style expectations
for all paragraphs and the complete XML of the 16 unedited paragraphs and
three tables. Independent package inspection found only `word/document.xml`
changed; every other ZIP part stayed byte-identical. Export: 37,542 bytes,
SHA-256 `f8c64e78ae67268be59595f942c0381bfe81e5b780a3b7710f21fbbec04537d3`.
The file has no embedded images; this case does not qualify image preservation.

**PPTX:** The two-slide synthetic deck contains title/body text, a 2×2 table
and two speaker notes. Changing slide 1's title preserved its body, slide 2's
title/table, both notes, shape IDs/names/geometry and core metadata. Independent
inspection found only `ppt/slides/slide1.xml` changed. The native browser
download matched the authorized response bytes. Export: 35,234 bytes,
SHA-256 `ce3ac3cc80509de65284332e11c4f584e3e8b3bbea6b8e8d19a58b44eb0dcc08`.

The supported populated-world launcher restarted both app processes against
the same SQLite database and Office directory. New normal-login contexts
reopened both saved canvases and downloaded identical bytes. Unsigned exports
returned 401. Unsigned canvas navigation showed `/login` with the exact canvas
return path, a visible password form and no export control. DOCX checked these
denials before and after restart; PPTX checked them after restart.

Root independently checked export packages and hashes, per-canvas single
upload/edit requests, new process identities and post-restart absence of any
upload/edit request. All four owned API/frontend PIDs were absent after final
shutdown, with no owned Chrome orphan. Owner app ports and live data remained
outside the test's allowed scope.

## Method and evidence

[The filtered receipt](evidence/office_docx_pptx_browser_20261116/result.json)
records source, file hashes, preservation and limits. Source was clean; the
reused production frontend build had the same entire tracked frontend tree.
The isolated core world used selected-empty provider routes, cached local
FastEmbed and OS network restrictions. No external provider request was made;
local embedding may run during ingestion, so this is not a claim of zero model
computation. Guided agent creation was not exercised.

DeepSeek prepared public-source plans and templates; root reviewed and
strengthened them before runtime: exact web-session identity, real dialog
heading, browser-download requirement, HTTP content type/no-store, paragraph/
table XML preservation and explicit denial UI. All four pre/post browser
processes completed successfully. Preparation-only work was not counted as
acceptance.

## Remaining scope

Neither fixture exercises embedded-image preservation. Cross-user ownership,
live connected sources, unfamiliar/model-generated content, richer Word
features, editable Word tables and arbitrary slide-object editing remain
unqualified. Other Canvas families, full D2, KVM and broader operations remain
separate. Original 143 claims and all 18 goals remain unchanged.
