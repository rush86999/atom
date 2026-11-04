# Test results — normal Assignments UI artifact journey

Executed source: `1c1fd2c08` (clean serving identity `1c1fd2c08798`).
Harness successor: `7b6f39a1f`.

## Browser journey

Command:

```
python scripts/acceptance/employee_g5_ui_artifact.py \
  --base http://127.0.0.1:3136 \
  --api http://127.0.0.1:8085 \
  --out /private/tmp/g5-ui-artifact2 \
  --fixtures /private/tmp/atom-g5-fixtures
```

Result: exit 0, **10/10 checks passed**. Full harness output:
`harness-run.log`; exact request/response and checks: `capture.json`,
`final.json`.

Exact run: `867bd51a-efc8-4492-bcaa-9a380b0ed8c4`.

Checks:

1. captured exact run;
2. selected source scope (the explicit artifact route does not require the
   three-source employee scope);
3. assignment completed;
4. artifact applied;
5. artifact criterion required and met / outcome satisfied;
6. artifact download succeeded;
7. artifact sha256 matches the recorded deliverable;
8. artifact contains `370.00`;
9. artifact contains the source and both lines;
10. the exact-run UI detail shows the objective, completion and `370.00`.

## Artifact bytes

`customer-quote.docx` is the downloaded artifact. Its sha256 is
`7f90fd9e5b73af2170aab33834d189a63fb2a44dcee8e4e43da4ff6ffc8d3adc`, the same
value recorded on the deliverable.

Independent DOCX text includes:

```
Prepare the customer quote document
Summary
2*100.00 + 3*50.00 + freight = 370.00 USD
Sources
price-book.xlsx
```

## Scope

This bundle verifies the normal UI artifact path. The API-level campaign
`employee_g5_remaining_normal_app_55eb68aa3` separately verifies independent
branch progress, selective retention, cancellation/late response and
controlled uncertainty recovery on source `55eb68aa3`. No live provider or
external effect authority is used.
