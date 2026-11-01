# Integrated local employee journey — normal application

This is the merged candidate running the normal product UI (backend
`127.0.0.1:8071`, frontend `127.0.0.1:3130`) in an isolated world. It exercises
teaching, conflict, missing qualification, connected-data upload, mapping,
durable waiting, a real backend restart, resume, a DOCX artifact, a revised
teaching scope, a second dataset, and the controlled outbox.

## What the user did

1. Created an employee through **Agents → describe a job**.
2. Taught method, document format, expedited format, email protocol, an expired
   lesson and a conflicting lesson through the **Training** surface.
3. Uploaded a CSV through **Data** and confirmed it appeared in the assignment
   source picker.
4. Started the first assignment. The UI refused with the equally-applicable
   `font_name` conflict; after the conflicting lesson was removed through the
   product teaching endpoint, it refused again for the missing
   `qualification`; with the qualification supplied it started.
5. Confirmed the unfamiliar mapping `Price → Gross Amount`, reached the
   external-fact wait, and closed the browser.
6. Restarted the backend process. On return the active run was still
   `waiting` with the same teaching snapshot. A new, more-specific lesson was
   taught; the active run did **not** adopt it.
7. Delivered the correlated response. The active run completed; the DOCX was
   downloaded with **Arial 11** and the expected summary/sources.
8. Started new revised-scope work on a second uploaded dataset
   (`clean_quote.csv`, `Price → Net Amount`); it completed with **Calibri 14**
   and **500.00**.

## Results

| Check | Result |
|---|---|
| First assignment after restart | `waiting` → `completed` |
| Active result | **550.00 USD** (Gross Amount rows 2–4) |
| Revised result | **500.00 USD** (Net Amount rows 2–4) |
| Active artifact | DOCX, Arial 11, SHA-256 recorded |
| Revised artifact | DOCX, Calibri 14, SHA-256 recorded |
| Controlled outbox | exactly **1** line, `[Quote]` subject, greeting/signature |
| Teaching revision changed for new work | true; active snapshot unchanged |
| Page errors | none |

`verify.json` also ran the negative controls. `part1.json`/`part2.json` capture
run ids, steps, mapping, teaching revisions and artifact hashes;
`sources.json` shows the uploaded CSV and the multi-sheet Office workbook in the
normal catalog. `screenshots/` shows waiting, reopen-after-restart and both
completed states.

## Scope

- controlled local outbox; no live provider/send;
- single worker and one isolated world;
- the employee's calculation/formatting paths are deterministic; discretionary
  model judgment is not used for this job and remains separately qualified;
- no claim of arbitrary domains, schemas or universal reliability.
