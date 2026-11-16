# PDF canvas ordinary-browser lifecycle

Qualified source: public PR971 `bb7017af311312fec03318feac516266ade05e60`. The isolated backend reported that exact clean revision. A reused production frontend built at `97e43a6b18a676a867b4e1e86f3b0c22da74461d` has the identical entire tracked frontend tree; no new frontend build is claimed. Full original scope remains 143 claims / 18 goals, app incomplete.

A new two-page synthetic PDF was strictly parsed and visually inspected before use. The old published mock-bank PDF was rejected during fixture validation before upload because of malformed cross-reference data and no extracted text. That fixture failure is not an app failure and was not hidden by weakening validation.

Actual ordinary-browser cases:

1. Normal sign-in and authenticated session identity; onboarding dismissed with supported Escape; real gallery Upload PDF file chooser; upload200 and navigation to its returned canvas. Both pdf.js page canvases had non-white rendered content. Visible Download returned2252bytes with SHA256 `2442682c3183c2d1e16618d5730b885dcf739ea07f086b03376679fd7f821002`, identical to the uploaded PDF. Reload returned identical bytes. A signed-out context received401 from the file endpoint and the canvas URL redirected to a visible sign-in form with no session.
2. A new ordinary sign-in reopened that existing PDF from its gallery card; no second upload. The native Rotate right control changed page1; Download was disabled while unsaved. Native Save returned200. The viewer rendered the rotated first page. Download returned1798bytes, SHA256 `d8d6a8385ef5dd77b84f0a95c50a69f6e1857b7db25b10cb1a84aff144e7a2e5`; a reload downloaded those same edited bytes. Signed-out file and UI denials passed again.
3. Independent strict parsing of the edited browser download confirmed two pages, absolute rotations90/0 and both original per-page text markers. Both edited pages were rendered and visually inspected: only the intended first-page rotation changed.

No auth injection, token extraction, route interception, fake HTTP, JS state mutation, DB/log secret lookup or app model calls. Actual keys, user data and external integrations were not involved. Only synthetic credentials passed through an anonymous pipe. The browser helpers were independently reviewed and strengthened before execution; native-worker preparation alone is not acceptance. Both owned app services stopped and absence was verified.

Limits: this is one small synthetic PDF and one page edit, not PDF form filling, signing, redaction, merge, approval/archive, original Office families, backend restart, production profiles, model quality, accessibility or all of Goal5. Persistence here means fresh browser readback/reload of the server-saved version, not a database/server restart. Filtered evidence accompanies this document at publication. Preserve the original source; a later merge alone must not be labeled a new runtime execution.

[Filtered result](evidence/pdf_canvas_browser_lifecycle_20261116/result.json).
