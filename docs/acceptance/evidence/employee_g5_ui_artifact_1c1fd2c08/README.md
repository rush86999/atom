# Requested artifact through the normal Assignments UI — 1c1fd2c08

Runtime candidate: `1c1fd2c08` (branch
`codex/brennan-full-app-20261102`). The serving identity reported
`source_id=1c1fd2c08798`, `dirty=false`, and the isolated world
`g5-ui-remaining-final`. Harness successor: `7b6f39a1f` (the harness bytes
are tracked as `harness.py`).

This is a real browser journey through the ordinary `/assignments` page. It
uses the existing explicit deliverable route: the user asks for a document,
selects the authorized price workbook, and supplies the quote line items.
It does not claim that a served model selected the artifact itself.

## What happened

1. Uploaded `price-book.xlsx` through the page.
2. Entered objective: "Prepare the customer quote document".
3. Selected deliverable kind `Document` and the uploaded price-book source.
4. Supplied the quote calculation:
   `2 x 100.00 + 3 x 50.00 + 20.00 freight = 370.00 USD`.
5. Clicked Start and captured the actual `POST /api/assignments` request and
   response. The returned run id was
   `867bd51a-efc8-4492-bcaa-9a380b0ed8c4`.
6. Clicked that exact assignment summary, not a pre-mounted detail or a
   page-wide total.
7. Waited for completion, then downloaded the artifact through the normal
   `GET /api/assignments/{run_id}/deliverables/{deliverable_id}/download`
   route.

## Assertions (10/10)

- exact returned run captured and matched;
- assignment `completed`;
- deliverable `applied`;
- `artifact_verified` criterion required and met; business outcome
  `satisfied`;
- artifact download HTTP 200;
- downloaded bytes sha256 `7f90fd9e5b73af2170aab33834d189a63fb2a44dcee8e4e43da4ff6ffc8d3adc`
  equals the recorded deliverable sha256;
- DOCX text contains `370.00`;
- DOCX text contains the source name `price-book.xlsx` and both lines `A`
  and `B`;
- the exact-run detail shows the objective, `completed`, and `370.00`.

The screenshots are `start-form.png` and `exact-run-final.png`. The exact
request/response and checks are in `capture.json` and `final.json`.

## Boundaries

- No live provider, credential, consent, send, spend or deployment authority.
- The artifact was explicitly requested by the user through the existing
  deliverable control; served-model artifact selection is not claimed.
- This bundle is the browser artifact journey; the API-level branch,
  retention, cancellation and controlled-uncertainty campaign is
  `employee_g5_remaining_normal_app_55eb68aa3`.
- Historical 111/123, previous tags/sources, planner 5/5, goal router 1/2 and
  alignment gap 3.0 are unchanged.
