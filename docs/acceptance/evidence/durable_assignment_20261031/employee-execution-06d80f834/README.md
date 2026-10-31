# Employee execution acceptance — 06d80f834

Evidence source: `06d80f834`; final code/evidence: `18a3b3b94`;
product teaching: `3e344f5b1`; Agent 2 merge: `931892be0`. Preserved tags: core `da9cc8b12`, reviewed successor
`d2b297deb`. Isolated world:
`/Users/rushiparikh/projects/atom-integrated-world-20261031`.

## What was exercised

Both business domains used the same product mechanisms through the browser:

1. create an employee through Agents;
2. teach method, document format, contextual exception, required
   qualification, effective period, conflicting instruction, and email
   protocol through Training;
3. upload a CSV through Data;
4. start an assignment through Assignments;
5. surface a teaching conflict and remove it through Training;
6. surface a missing qualification and refuse the start;
7. confirm an unfamiliar mapping;
8. calculate with source/row citations;
9. reach a durable missing-fact wait;
10. close the browser and restart the backend against the same world;
11. reopen the waiting assignment and deliver a correlated response;
12. approve the exact payload and execute once through the controlled outbox;
13. download the DOCX and reload the assignment;
14. teach a revised format and start new work on a differently shaped source;
15. download the revised DOCX and verify the changed teaching revision.

Grant domain also produced an editable 4-slide PPTX. A separate canvas journey
created a blank canvas, attached an employee, installed a table capability
manifest, bound a CSV, calculated 290.00, edited a row with readback, calculated
325.00, exported XLSX, and reloaded `revision 2 · 4 rows`.

Conversation learning was exercised through `/learning`: a local email thread
was created through the email-canvas API, then a guidance-only candidate was
drafted, confirmed and promoted in the browser. The candidate has
`method_status=not_applicable`, no arithmetic method, a valid email
`format_spec`, and `lesson_id dffc99c4af054fb9a6b3dd55c618b947`.

## Expected vs actual

| Check | Expected | Actual |
|---|---|---|
| Sales calculation | 400.00 USD | 400.00 USD |
| Sales second source | 2225.75 USD | 2225.75 USD |
| Grant calculation | 4250.00 USD | 4250.00 USD |
| Grant revised source | 4250.00 USD | 4250.00 USD |
| Sales mapping | Price → Gross Amount | Price → Gross Amount |
| Grant mappings | Approved Amount → Award Amount / Approved Award | matched |
| Missing qualification | refused with `teaching_context_unresolved` | refused; text preserved in `*/missing-qualification.txt` |
| Teaching conflict | refused naming `font_name`/`font_size` | refused; text preserved in `*/first-conflict.txt` |
| Waiting assignment after restart | same run, same teaching revision | matched; screenshots + `verify.json` |
| Approval | one controlled outbox line | one line per job; duplicate approval replayed |
| DOCX | taught font/headings, stable hash | Arial 11 and Calibri 14; hashes in `verify.json` |
| PPTX | editable slides with result/findings/sources | 4 slides; `presentation/presentation.json` |
| Canvas | 290.00 → 325.00, XLSX, reload | matched; `canvas/canvas.json` |
| Conversation guidance | promoted without dummy method | `method_status=not_applicable`, format spec persisted |
| Negative controls | wrong font/revision/duplicate/protocol/contradiction rejected | all rejected; `*/negative-controls.json` |

## Tests

- Targeted backend: **284 passed** (`logs/targeted-backend.log`).
- Frontend learning: **5 passed** (`logs/frontend-learning.log`).
- TypeScript `--noEmit`: clean (`logs/typescript.log`).

## Harnesses

- `scripts/acceptance/composite_long_running_part1.py`
- `scripts/acceptance/composite_long_running_part2.py`
- `scripts/acceptance/composite_long_running_verify.py`
- `scripts/acceptance/canvas_capability_local.py`
- `scripts/acceptance/launch_integrated_local_candidate.sh`

The composite scripts are parameterized for measure, context, qualification,
mapping candidate, second source/candidate, protocol fields and domain label.

## Preserved limitations

- Canvas assessment was not run: `ATOM_REVIEW_MODEL` is unconfigured. The
  review contract is unit-tested; no live model-quality claim is made.
- Local Ollama is unavailable on this host (external model volume unreadable).
- Large-workbook/formula recalculation and live connectors were not rerun on
  this candidate; historical evidence remains source-bound.
- No real email was sent. The controlled outbox is the only transport.
- One worker per assignment; no multi-day soak or multi-worker campaign.
- Hosted deployment/publication are owner-deferred.

## Manifest

`manifest.json` lists every file in this directory with its SHA-256 and byte
count. Verify with:

```bash
python - <<'PY'
import hashlib, json, os
root='.'
m=json.load(open('manifest.json'))
bad=[]
for name, meta in m['files'].items():
    data=open(os.path.join(root,name),'rb').read()
    if hashlib.sha256(data).hexdigest()!=meta['sha256'] or len(data)!=meta['bytes']:
        bad.append(name)
print('entries', len(m['files']), 'mismatches', bad)
PY
```
