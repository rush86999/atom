# Integrated local employee journey — post-repair, clean source

This is the required post-repair rerun on one clean serving identity. The
pre-repair run is preserved separately in
`../employee-execution-integrated-local-journey/` and is not evidence for this
source.

## Serving identity

| Phase | Source | Dirty | Backend PID |
|---|---|---|---|
| part 1 (teach/start/wait) | `31ba9725e02a` | false | 64333 |
| part 2 (restart/resume/finish) | `31ba9725e02a` | false | 64859 |

`health-after-restart.json` and `serving-identity.txt` record the runtime
identity; the source is the same clean commit across the real restart.

## Executed workflow

- employee created/taught through the normal application (conflict and missing
  qualification refused before the licensed start);
- CSV uploaded through **Data**, source selected through the assignment picker;
- `Price → Gross Amount` mapping confirmed; assignment reached the external-fact
  wait;
- backend process restarted; the active run was still `waiting` with the same
  teaching revision;
- correlated response delivered through the Assignments page; DOCX completed
  and downloaded (**Arial 11**, **550.00 USD**);
- revised teaching applied only to new work; second dataset
  (`clean_quote.csv`, `Price → Net Amount`) completed **Calibri 14**,
  **500.00 USD**;
- controlled outbox: exactly **1** line with greeting/signature/`[Quote]`.

`verify.json`: **passed**, including negative controls. `part1.json`/`part2.json`
record run ids, steps, teaching revisions, artifact hashes and the restart.

## Scope

Local single-worker app, controlled outbox, no live provider/send. The UI
teaching path was stabilized by the acceptance harness (attached-state waits,
overlay dismissal, empty optional fields skipped); product behavior was not
changed for this run.
