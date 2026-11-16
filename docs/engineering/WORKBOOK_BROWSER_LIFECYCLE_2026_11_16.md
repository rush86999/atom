# Workbook browser lifecycle and restart — November 16, 2026

An ordinary browser uploaded the existing 24-sheet synthetic workbook, edited
a quantity on Data20, observed the recalculated cross-sheet total, and reopened
the same workbook after both API and frontend processes restarted. The result
is source-bound to `3316b0fe71a1203a90e0f4ec856d7eb5a08d2f4a` and covers a
local XLSX journey, not live WorkDrive or model-driven spreadsheet analysis.

## Observed boundary

Normal form sign-in established the exact web session. The user created a new
canvas, attached the launcher's existing Demo Assistant through the real
dialog, and uploaded the workbook using the native file chooser. No auth,
cookie, app-state or HTTP-response injection was used. The workbook's 24 tabs,
including its later sheets and Summary, were checked in the real grid.

The existing fixture has 20 data sheets and four supporting sheets, with 521
formulas. Independent arithmetic across all data rows confirmed the initial
34,533 total. The native edit changed Data20!B2 from 2 to 9; the fresh save
returned complete recalculation with no formula gaps, and the grid's Summary
changed to 34,610. Reload preserved the edit.

The downloaded XLSX preserved all sheet names/order, leading-zero IDs, formula
strings and their computed caches. Independent file inspection performed
1,133 individual value/formula checks; these are assertions, not 1,133 test
cases. It verified Data20!D2 = 99, Summary's Data20 subtotal = 1,802, and the
grand total = 34,610. The export was 34,479 bytes with SHA-256
`4a45d134e4467f29c4e4972b2d359fa6e490a364d0d5888097589bce25a63c36`.

Fresh normal-login browser contexts reopened the same canvas, read every tab
and re-exported identical bytes. Both the API and frontend were then stopped
and relaunched through the supported populated-world launcher. Another fresh
login repeated the read-only checks against the same account/canvas/workbook,
without another upload or edit. Unsigned download returned 401; unsigned page
navigation showed the shipped `/login` form with the exact canvas return
path and no workbook download control. All four owned app processes were
confirmed absent afterward, with no owned Chrome orphan.

## Evidence and retained verifier failures

[The filtered receipt](evidence/workbook_browser_lifecycle_20261116/result.json)
records the source, fixture/export hashes, checks and limits. Backend source
was clean; the reused production frontend build had an equal entire tracked
frontend tree. Runtime used an isolated local SQLite world, local FastEmbed
cache and local spreadsheet engines, with an empty selected-provider policy
and OS network restrictions. No paid app-model request or live dev DB was used.

This is composite evidence, not a retroactively successful single run. The
first run timed out on an attachment test attribute before upload; read-only
inspection found the actual dialog/heading and an available agent. An initial
diagnostic had a syntax error before browser startup; its corrected diagnostic
passed. A new mutation case completed edit/reload/download but its verifier
compared raw formula text with a cached number. Independent inspection corrected
that comparison; its first numeric check also exposed a string-versus-number
comparison error before exact numeric equality passed. A read-only continuation
then expected `/auth/signin` while the shipped middleware uses `/login`; a new
source-matched continuation passed. Original failures remain retained. The
successful upload and edit each occurred once and were not replayed.

## Remaining scope

The fixture is synthetic and local. This does not requalify connected-source
freshness, model-driven sheet selection/citations/grounding, ambiguous-request
refusal, every formula/edit operation or every Canvas family. Attaching an
existing seeded agent does not prove guided agent creation or model selection
quality. Original 143 claims and 18 goals remain unchanged.
