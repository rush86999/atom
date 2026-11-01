# Sample workspace — first governed employee job

This is the documented first-use fixture. It is deliberately small, local and
deterministic: five fictional equipment rows, one numeric measure (`Price`), and
a document deliverable. No connector, cloud key or outbound send is involved.

## Run it

With the app started (`make dev`):

```bash
make sample
```

The loader uses only the public product API:

1. sign in as the local admin;
2. create/reuse **Sample Quote Analyst** in the authenticated scope;
3. upload `sample_quote.csv` through the normal document path;
4. record two editable lessons — the quote method and the document format;
5. start one assignment: sum `Price`, cite the source, render a DOCX;
6. resolve the single compatible `Price` mapping if the planner asks.

It prints the completed run id, result (`232990.00`) and the artifact download
URL. Open **Assignments** at http://localhost:3001 to inspect the run, or
**Agents → Sample Quote Analyst → Training** to edit the lessons and run new
work.

## What is intentionally limited

- `Price` is already a column in the sample; this first job does not exercise
  unfamiliar-schema transfer. The two-domain campaign does that through the
  normal UI.
- The deliverable is a local document. The sample has no outbound step, so there
  is no approval or controlled effect.
- The sample is a deterministic policy demonstration, not evidence of
  discretionary model judgment.
