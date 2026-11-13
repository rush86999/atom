# Local core acceptance harness

These scripts are acceptance harnesses, not product surfaces. They use the
normal browser UI for user actions and read durable state through the public
API only for assertions.

Fixtures are local CSV uploads, not live integrations:

```csv
# clean_quote.csv (expected 2225.75)
SKU,Quantity,Net Amount,Currency
A-1,2,1250.50,USD
A-2,1,900.00,USD
A-3,4,75.25,USD
```

```csv
# integrated_quote.csv (expected 400.00; Price maps to Gross Amount)
Item Code,Units,Gross Amount,Currency
I-1,2,100.00,USD
I-2,3,250.50,USD
I-3,1,49.50,USD
```

The composite labels these as controlled uploads. The live Outlook/OneDrive
qualification is separate evidence and is not repeated here.

## 1. Clean install / one operation

Follow `docs/acceptance/LOCAL_INSTALLATION_AND_ACCEPTANCE_fda4f2dc9.md` in a
new checkout and data root. Start the backend on `8071` and the standalone
frontend on `3130`. Then:

```bash
python scripts/acceptance/local_clean_install_ui.py \
  --frontend http://127.0.0.1:3130 \
  --password-file /path/to/local-admin-password \
  --csv /path/to/clean_quote.csv \
  --out-dir /path/to/evidence \
  --objective "Sum Net Amount for the final clean install quote" \
  --measure "Net Amount" \
  --expected "2225.75" \
  --mode create
```

Restart the backend without `ADMIN_PASSWORD`, keep the same data root, then:

```bash
python scripts/acceptance/local_clean_install_ui.py \
  --frontend http://127.0.0.1:3130 \
  --password-file /path/to/local-admin-password \
  --csv /path/to/clean_quote.csv \
  --out-dir /path/to/evidence \
  --objective "Sum Net Amount for the final clean install quote" \
  --measure "Net Amount" \
  --expected "2225.75" \
  --mode verify
```

`create.json` / `verify.json` record the result, artifact hash, console
errors, failed assets and page errors. `failed_assets` and `page_errors` must
be empty.

## 2. Composite long-running / complex teaching

Use an isolated root with controlled transport explicitly enabled:

```bash
# backend
export ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT=1
export ATOM_ASSIGNMENT_OUTBOX=/path/to/controlled-outbox.jsonl

# frontend build
NEXT_PUBLIC_API_URL=http://127.0.0.1:8071 \
NEXT_PUBLIC_ALLOW_LOOPBACK=1 \
NEXT_PUBLIC_ASSIGNMENT_TRANSPORT=controlled \
npm run build
# copy .next/static and public into .next/standalone, then start server.js
```

Part 1 teaches the policy, exposes the conflict, removes it, uploads the
source, starts the assignment, confirms the mapping and stops at the wait:

```bash
python scripts/acceptance/composite_long_running_part1.py \
  --frontend http://127.0.0.1:3130 \
  --password-file /path/to/local-admin-password \
  --csv /path/to/integrated_quote.csv \
  --out-dir /path/to/evidence \
  --objective "Sum Price for the composite quote sheet 2026-10-30"
```

It closes the browser and writes `part1.json`. Stop the backend process, start
a new one against the same data root, and run part 2:

```bash
python scripts/acceptance/composite_long_running_part2.py \
  --frontend http://127.0.0.1:3130 \
  --password-file /path/to/local-admin-password \
  --out-dir /path/to/evidence \
  --part1 /path/to/evidence/part1.json \
  --objective "Sum Price for the composite quote sheet 2026-10-30" \
  --second-objective "Sum Price for the revised composite quote sheet 2026-10-30" \
  --outbox /path/to/controlled-outbox.jsonl
```

If part 2 stops after the approval due to a UI locator, preserve its log and
run the verify script; it is idempotent for the completed active run:

```bash
python scripts/acceptance/composite_long_running_verify.py \
  --frontend http://127.0.0.1:3130 \
  --password-file /path/to/local-admin-password \
  --out-dir /path/to/evidence \
  --part1 /path/to/evidence/part1.json \
  --objective "Sum Price for the composite quote sheet 2026-10-30" \
  --second-objective "Sum Price for the revised composite quote sheet 2026-10-30" \
  --outbox /path/to/controlled-outbox.jsonl \
  --negative-controls
```

The verifier enforces the active/second fonts, results, revisions, artifact hashes, one-effect outbox and the taught email protocol. `--negative-controls` proves that wrong font, unchanged revision, duplicate operation, missing protocol and contradictory completion all fail.

A separate runtime negative control checks that a reply denying an established source fact does not complete the wait:

```bash
python scripts/acceptance/composite_wait_negative_control.py \
  --frontend http://127.0.0.1:3130 \
  --password-file /path/to/local-admin-password \
  --out-dir /path/to/evidence \
  --part1 /path/to/evidence/part1.json
```

Positive wait-value twins use a blank-currency upload and an agreeing reply:

```bash
python scripts/acceptance/wait_value_positive_twins.py \
  --frontend http://127.0.0.1:3130 \
  --password-file /path/to/local-admin-password \
  --out-dir /path/to/evidence \
  --part1 /path/to/evidence/part1.json \
  --blank-csv /path/to/blank_currency.csv \
  --mode create

# restart the backend against the same data root, then:
python scripts/acceptance/wait_value_positive_twins.py \
  --frontend http://127.0.0.1:3130 \
  --password-file /path/to/local-admin-password \
  --out-dir /path/to/evidence \
  --part1 /path/to/evidence/part1.json \
  --blank-csv /path/to/blank_currency.csv \
  --mode verify \
  --state /path/to/evidence/positive-twins.json
```

The composite uses controlled external effects only. It does not send a real
email, write to a connected source, or replace the existing service.

## 6. Signed-in settings (WA-075)

Proves the Account, AI, Sessions, Routing and Local Models settings tabs at the
signed-in browser boundary: a real save/reload/restore of reversible controls,
a disposable secondary session, real routing telemetry equality, and a
disposable local-model provider that is registered, reloaded and deleted. The
world is the existing integrated-local scratch world; nothing is installed and
no external provider is contacted. Full detail and the honest non-claims live
in `docs/acceptance/WA-075_SIGNED_IN_SETTINGS_ACCEPTANCE_2026-11-13.md`.

```bash
# preflight only (starts nothing, writes only --report)
python scripts/acceptance/browser_settings_preflight.py \
  --world <repo>/backend/data/acceptance_worlds/wa075_settings \
  --admin-password-file /path/to/0600/wa075-admin-password \
  --report /scratch/wa075/preflight.json

# after the world is serving (see the WA-075 document for the launcher env)
ATOM_WA075_WORLD="$WORLD" \
ATOM_SCOPE_PASSWORD="$(cat /path/to/0600/wa075-admin-password)" \
node scripts/acceptance/browser_settings_acceptance.mjs \
  --out /scratch/wa075/signed-in-settings.json
```

Exit codes: `0` all checks pass, `1` a product failure, `2` fatal (including an
unverified scratch identity), `3` no failures but a capability is missing, `4`
no failures but a required check was skipped (incomplete). The missing and
skipped check ids and reasons are in the JSON; a skip is never a silent pass.
