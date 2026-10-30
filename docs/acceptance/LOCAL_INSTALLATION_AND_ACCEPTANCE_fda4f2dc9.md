# Local installation and acceptance — bounded local core

Status: **bounded local core complete for the documented supported
workflows.** Hosted deployment, public release and publication remain
**deferred separately**. This procedure requires no production approval file,
deployment launcher or source-service shutdown.

## Tested identity and scope

| Item | Value |
|---|---|
| Final local source tag | `local-core-2026-10-30-final` |
| Runtime source commit | `e27ec63abcbd5accd8bc085f06ea2242d0930633` |
| Runtime source tree | `dc67a86e89e95ea6df11561df14156c851a54f59` |
| Functional baseline | `fda4f2dc9376f20a6e10de6d7d1e55cf16eeffd4` |
| Frontend build (clean install) | `jDccLkCOwPIvfD8dW-mSz` |
| Frontend build (controlled composite) | `DAyJPdxkcutCPtDNO1645` |
| Python | `3.11.16` |
| Node | `v20.19.6` |
| npm | `10.8.2` |
| Platform used for the recorded run | macOS 26.5.2, x86_64 |
| Local API / frontend | `127.0.0.1:8071` / `127.0.0.1:3130` |
| Audience | `single_user` |
| Sending | disabled by default; controlled transport only for labelled acceptance |

The existing source service on port `8001` was not stopped, replaced or
reconfigured. The clean-install run used a separate checkout, a separate
Python virtual environment, a separate `node_modules`, and a new empty data
root.

## What is required, and what is deferred

Required for local readiness:

- reproducible local install and startup;
- normal browser authentication and usable core surfaces;
- durable user data, teaching, assignments and artifacts;
- supported workflows through the local UI;
- restart and recovery against the same stores;
- accurate setup, troubleshooting, backup and recovery documentation.

Deferred separately and **not** required here:

- hosted deployment and public release;
- publication;
- production approval files;
- source-service shutdown or cutover;
- standing authorization for live sending.

## Prerequisites

- Python 3.11 (the recorded run used 3.11.16).
- Node 20 (the recorded run used v20.19.6) and npm 10 (10.8.2).
- Git and a C toolchain only if a Python wheel is unavailable for your
  platform. `lancedb`, `cryptography` and `schemathesis` are pinned to
  wheel-backed versions so the documented Intel-mac install does not try to
  compile Rust through a local LLVM/z3 toolchain.
- Several GB of free disk space for the Python environment, `node_modules`
  and the frontend build.

## Exact install and first start

### Terminal A — backend install and first start

```bash
git clone --branch local-core-2026-10-30-final <repo-url> atom-local
cd atom-local/backend

python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install --prefer-binary -r requirements.txt
```

Create the durable data root **before** starting SQLite or LanceDB:

```bash
export ATOM_HOME="$HOME/atom-local-data"
mkdir -p "$ATOM_HOME"/{config,office/assignments,email_attachments,atom_memory,backups}
chmod 700 "$ATOM_HOME"
```

Create a local secrets file. It is loaded explicitly below; it is not a
magic file that uvicorn reads by itself:

```bash
cat > "$ATOM_HOME/config/secrets.env" <<EOF
SECRET_KEY=$(openssl rand -base64 48)
# Optional provider keys, for example:
# DEEPSEEK_API_KEY=...
# OPENAI_API_KEY=...
EOF
chmod 600 "$ATOM_HOME/config/secrets.env"
```

Export the durable paths and local policy. Keep these values identical on
every restart:

```bash
set -a
. "$ATOM_HOME/config/secrets.env"
set +a

export ATOM_DATA_DIR="$ATOM_HOME"
export DATABASE_URL="sqlite:///$ATOM_HOME/atom.db"
export LANCEDB_URI="$ATOM_HOME/atom_memory"
export LANCEDB_URI_BASE="$ATOM_HOME/atom_memory"
export ATOM_OFFICE_DIR="$ATOM_HOME/office"
export ATOM_ASSIGNMENT_OUTPUT_DIR="$ATOM_HOME/office/assignments"
export ATOM_EMAIL_ATTACHMENT_DIR="$ATOM_HOME/email_attachments"
export BYOK_CONFIG_FILE="$ATOM_HOME/byok_config.json"
export BYOK_KEYS_FILE="$ATOM_HOME/byok_keys.json"
export BYOK_ENC_KEY_FILE="$ATOM_HOME/byok_encryption_key"

export ATOM_DEPLOYMENT_AUDIENCE=single_user
export ATOM_PILOT_USER_EMAIL=admin@example.com
export ATOM_EMAIL_SEND_DISABLED=1
export ATOM_ASSIGNMENT_ALLOW_LIVE_SEND=0
export ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS=0
export ENABLE_SCHEDULER=false
export ENABLE_INGESTION_SYNC=false
export ALLOWED_ORIGINS=http://127.0.0.1:3130,http://localhost:3130
```

The tested model configuration used DeepSeek. Add these only if you have your
own DeepSeek key; deterministic data jobs, teaching and artifact rendering do
not require a model:

```bash
export ATOM_LLM_PROVIDER_POLICY='{"mode":"selected","allowed_providers":["deepseek"],"preferred":{"provider":"deepseek","model":"deepseek-flash"}}'
export ATOM_PREFERRED_LLM_PROVIDER=deepseek
export ATOM_PREFERRED_LLM_MODEL=deepseek-flash
export ATOM_REVIEW_MODEL=deepseek-flash
export ATOM_REVIEW_STRUCTURED=1
```

First start only — this creates the admin account. `ADMIN_PASSWORD` **resets**
an existing admin password whenever it is set, so do not leave it exported:

```bash
export ADMIN_PASSWORD='<your-local-only-password>'
.venv/bin/python -m uvicorn main_api_app:app --host 127.0.0.1 --port 8071
```

Wait until `http://127.0.0.1:8071/api/health` returns `"status":"healthy"`.
First startup creates the database and tables.

### Terminal B — frontend install, build and standalone start

```bash
cd atom-local/frontend-nextjs

npm ci

NEXT_PUBLIC_API_URL=http://127.0.0.1:8071 \
NEXT_PUBLIC_ALLOW_LOOPBACK=1 \
npm run build
```

`NEXT_PUBLIC_ALLOW_LOOPBACK=1` is required. Without it, `next.config.js`
refuses to bake a loopback API origin into a production build.

The Next.js standalone output does **not** include `.next/static` or `public`.
Copy them before starting, exactly as the packaging helper
`scripts/deployment/assignment_successor_2026-10-30_fda4f2dc9/prepare_release.py`
does in `copy_frontend_build`:

```bash
mkdir -p .next/standalone/.next
rm -rf .next/standalone/.next/static .next/standalone/public
cp -R .next/static .next/standalone/.next/static
if [ -d public ]; then
  cp -R public .next/standalone/public
fi

PORT=3130 HOSTNAME=127.0.0.1 node .next/standalone/server.js
```

Open `http://127.0.0.1:3130/login` and sign in as
`admin@example.com` with the password from first start.

## Normal restart (do not repeat first-start provisioning)

Stop both processes with `Ctrl-C`. Then:

**Terminal A — backend**

```bash
cd atom-local/backend
set -a
. "$ATOM_HOME/config/secrets.env"
set +a
# Re-export the same durable paths listed above.
# DO NOT export ADMIN_PASSWORD here.
.venv/bin/python -m uvicorn main_api_app:app --host 127.0.0.1 --port 8071
```

**Terminal B — frontend**

```bash
cd atom-local/frontend-nextjs
PORT=3130 HOSTNAME=127.0.0.1 node .next/standalone/server.js
```

No rebuild and no `npm ci` are needed on restart. Keep `SECRET_KEY` stable or
existing browser sessions will be invalidated. Keep every data path stable or
the app will look empty.

## Configuration and credentials

### Supported ways to provide credentials

1. **Settings → AI Providers** (recommended for a person using the UI):
   save a provider key, test it, and choose the provider/model policy. Keys are
   stored in the BYOK files under the data root.
2. **`backend/.env`** (supported for a direct source launch): copy
   `backend/.env.example` to `backend/.env` and set provider keys. The backend
   loads `backend/.env`, the project-root `.env`, and `.env.local` at startup.
3. **`$ATOM_HOME/config/secrets.env`**: this is the packaging convention. A
   direct `uvicorn` launch does **not** read it automatically; source it in the
   shell as shown above. The packaged `release_tool.py` loads
   `config/env.release` and `config/secrets.env` itself.

Never copy another machine's `secrets.env`, BYOK key files or database.

### Microsoft OAuth

Use the product's normal integration pages:

- Outlook: `http://127.0.0.1:3130/integrations/outlook`
- OneDrive: `http://127.0.0.1:3130/integrations/onedrive`
- Or open **Integrations** in the sidebar and choose Microsoft 365 / Outlook /
  OneDrive.

Click **Connect**, sign in with the account that owns the data, and grant the
read scopes. The connection is per user/workspace; there is no cross-user token
fallback. After connecting, ingest or refresh the source in the integration
page, then use **Data → Refresh data** in Assignments to pick it up.

### Equivalent Settings workflow for the tested model

The packaged acceptance used `deepseek` / `deepseek-flash` with structured
review. In the UI, open **Settings → AI Providers**, save your own DeepSeek key,
and select DeepSeek with `deepseek-flash` as the preferred model. If the review
feature is used, set `ATOM_REVIEW_MODEL=deepseek-flash` in the backend
environment. A different provider/model is allowed, but it is a different
configuration from the one recorded here.

## Using the supported local surfaces

| Job | Entry point |
|---|---|
| Sign in / out | `/login`; dashboard profile menu |
| Create or select an employee | **Agents**; “Describe a job” creates a student agent |
| Teach method, context and format | **Agents → Teach** (graduation-cap button), then the Training tab |
| Correct teaching | Training tab → teaching-point edit |
| Upload data | **Data** (`/documents`), CSV/XLSX/PDF/DOCX/TXT/MD |
| Connect data | **Integrations** → Outlook / OneDrive / Microsoft 365 |
| Start work | **Assignments** in the sidebar; choose employee, authorized data source, deliverable and optional measure |
| Answer a clarification | Assignment detail → **Missing information** |
| Correct a mapping | Assignment detail → **Correct mapping** |
| Review result and evidence | Assignment detail → completed steps, results and mappings |
| Download an artifact | Assignment detail → **Artifacts → Download** |
| Approve an exact action | Assignment detail → **Approve this payload** |
| Inspect completion/uncertainty | Assignment detail status, failed/uncertain panels, Activity |
| Enable a send | Keep `ATOM_EMAIL_SEND_DISABLED=1`; a separately authorized live run must set the live-send flag and still approve the exact payload |

The ordinary form does not accept filesystem paths or database IDs. It lists
authorized catalog entries. “Other business concept…” lets you name the
measure your business uses when the physical column has an unfamiliar name;
the mapping clarification resolves the column and records the correction.

### Long-running and teaching-revision behavior

- An assignment stores the teaching snapshot accepted at start. Teaching
  changes made while it is running apply to new work; the active assignment
  keeps its revision until an explicit reassessment. The assignment detail
  states this and shows the revision actually used.
- A missing required qualification is a clarification, not a silent fallback.
  Equally applicable instructions that disagree are a conflict; the form names
  the conflicting keys. Expired teaching is excluded by its effective period.
- A durable wait names the correlation id and the party that must respond. A
  restart against the same data root reopens the same assignment and the same
  wait; the response is accepted once for that correlation.
- See `docs/acceptance/LONG_RUNNING_AND_TEACHING_COVERAGE_2026-10-30.md` for
  the transition-by-transition evidence table.

## Backup and recovery

1. Stop both processes.
2. Copy the whole `$ATOM_HOME` directory to a backup location. It contains the
   SQLite database, LanceDB memory, office artifacts, email attachments and
   BYOK files.
3. Keep `$ATOM_HOME/config/secrets.env` separately; it is the key material for
   the data root.
4. To restore, point the same environment variables at the restored directory
   and start normally. Do not re-seed or create a blank database over it.
5. `core/db_safety.py` snapshots the database during maintenance and logs a
   CRITICAL if the row-count fingerprint collapses. `backend/data/backups/`
   contains those snapshots for the default data root.

## Troubleshooting

- **Build refuses a loopback API URL** — set
  `NEXT_PUBLIC_ALLOW_LOOPBACK=1` for the build.
- **Login says “Unable to connect”** — set `ALLOWED_ORIGINS` to
  `http://127.0.0.1:3130,http://localhost:3130` and restart the backend.
- **Page loads but JavaScript/CSS is missing or 404** — copy `.next/static`
  and `public` into `.next/standalone` as shown above.
- **Backend not ready** — wait for `/api/health`; first startup initializes the
  database and tables.
- **Data disappears** — confirm every data path points at the same durable
  root. Relative paths are anchored to `backend/`.
- **Admin password changed unexpectedly** — `ADMIN_PASSWORD` was set on a
  restart. Unset it and restart; bootstrap only resets when the variable is
  present.
- **Port conflict** — stop the conflicting process or choose another port and
  rebuild the frontend with the matching `NEXT_PUBLIC_API_URL`.
- **Onboarding modal on a fresh workspace** — expected; it is not a failure.
- **Controlled acceptance** — set `ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT=1`
  and `ATOM_ASSIGNMENT_OUTBOX` in the backend environment, and build the
  frontend with `NEXT_PUBLIC_ASSIGNMENT_TRANSPORT=controlled`. This writes to a
  local JSONL outbox; it is not a production sender.

## Recorded clean-install acceptance

The exact commands above were executed in a new clone at
`/private/var/folders/.../fda_clean_final/atom-local`, with a new Python 3.11
virtual environment, a new `npm ci` install, a new `next build` and a new empty
data root.

- Python `3.11.16`; `pip install --prefer-binary -r requirements.txt`
  completed. Pinned: `lancedb 0.24.3`, `cryptography 42.0.8`,
  `schemathesis 3.39.16`.
- Node `v20.19.6`; npm `10.8.2`; `npm ci` and `next build` completed; build ID
  `jDccLkCOwPIvfD8dW-mSz`.
- Standalone frontend started with `.next/static` and `public` copied.
- Browser loaded the login page with **no failed JS/CSS/public asset responses
  and no page errors**. The only console messages were pre-auth shell requests
  (notification/preferences 401) and an unrelated `/api/canvas` 405; neither is
  an asset or a page error.
- Normal form login reached the dashboard.
- One supported operation completed through the UI: upload
  `clean_quote.csv`, select the employee and source, sum `Net Amount` to
  `2225.75 USD`, and download the DOCX artifact.
- Restart without `ADMIN_PASSWORD` preserved the login, assignment, result and
  artifact. The artifact SHA-256 before and after restart was identical:
  `25e5deb308506b68a757fe88c67a4360760730fe7282db3b6d5b26b26d530dff`.
- Controlled adapters were used where a live provider credential was not
  available; that is labelled separately from the live-connected evidence.
- Composite protocol/wait evidence: the approved controlled email carried
  `[Quote]` in the subject, `Dear colleague,` at the start and `Sales team` at
  the end. The successful wait used the genuinely missing `delivery_term`
  (`FOB destination`).
- Wait-value twins: a blank `Currency` column accepted `USD` and completed; an
  established `USD` value plus `USD` reply was a confirmation, not a conflict;
  a conflicting reply against established `USD` stayed waiting with no
  artifact. Exact comparison rejects `Not USD; use EUR`, `USDX` and `20` vs
  `120`; filtered rows and unreadable/incomplete evidence are handled
  separately. The blank-currency assignment survived a real restart with the
  same artifact hash and exactly one applied wait operation.

Clean-install evidence (executed on 5ce5f5715; the final source adds only wait-value/projection/test-id changes):
`docs/acceptance/evidence/durable_assignment_20261030/local-core-repro-5ce5f57/`

Long-running and complex teaching evidence:
`docs/acceptance/evidence/durable_assignment_20261030/composite-protocol-5ce5f57/`

Wait-value positive twins and negative control:
`docs/acceptance/evidence/durable_assignment_20261030/wait-value-e27ec63/`
and `docs/acceptance/LONG_RUNNING_AND_TEACHING_COVERAGE_2026-10-30.md`.
The earlier `composite-final-0efe3a9fb/` and `composite-long-running-0efe3a9fb/`
directories are preserved as prior attempts, not the final campaign.

Consolidated closure record:
`docs/acceptance/evidence/durable_assignment_20261030/final-local-closure-e27ec63.json`.

## Compatibility limits

This completion claim is bounded. It does **not** claim universal domain
competence, arbitrary Excel compatibility, arbitrary schema understanding,
embedded image/chart interpretation, every future canvas component, non-
Microsoft connectors, multi-worker campaigns or unrestricted autonomous
research. Sending remains qualified to provider acceptance and Sent Items
confirmation for the one recorded message; recipient delivery is not
independently confirmed.
