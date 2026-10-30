# Local installation and acceptance — fda4f2dc9

Status: **local core demonstrated; hosted deployment, public release and
publication remain deferred.** No production approval file or source-service
shutdown is required for this local procedure.

## Tested identity and environment

- Product: `fda4f2dc9376f20a6e10de6d7d1e55cf16eeffd4`
- Tree: `92924cd8f8f3cffa8e884a9a7fecc5f820f4f5ce8acbba60fdd257975df614fa`
- Frontend build: `7Y8qAVXDNHG0Q9YDMKwb4`
- Local test root: `/private/var/folders/.../fda_local_acceptance`
- API/frontend: `127.0.0.1:8071` / `127.0.0.1:3130`
- Audience: `single_user`; send disabled; no production approval.
- Existing source service PID `19046` on `8001` was not stopped or replaced.

## Exact local launch procedure

1. Get the frozen source at the tag and create a Python environment:

```bash
git clone --branch assignment-successor-2026-10-30-fda4f2dc9 \
  <repo-url> atom-local
cd atom-local/backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

2. Choose durable local paths outside the release checkout:

```bash
export ATOM_DATA_DIR="$HOME/atom-local-data"
export DATABASE_URL="sqlite:///$ATOM_DATA_DIR/atom.db"
export LANCEDB_URI="$ATOM_DATA_DIR/atom_memory"
export LANCEDB_URI_BASE="$ATOM_DATA_DIR/atom_memory"
export ATOM_OFFICE_DIR="$ATOM_DATA_DIR/office"
export ATOM_ASSIGNMENT_OUTPUT_DIR="$ATOM_DATA_DIR/office/assignments"
export ATOM_EMAIL_ATTACHMENT_DIR="$ATOM_DATA_DIR/email_attachments"
export ATOM_DEPLOYMENT_AUDIENCE=single_user
export ATOM_PILOT_USER_EMAIL=admin@example.com
export ATOM_EMAIL_SEND_DISABLED=1
export ATOM_ASSIGNMENT_ALLOW_LIVE_SEND=0
export ALLOWED_ORIGINS=http://127.0.0.1:3130,http://localhost:3130
```

3. First start creates the admin account. Supply a local password through the
environment; do not commit it or copy a production secret:

```bash
export ADMIN_PASSWORD='<local-only-password>'
.venv/bin/python -m uvicorn main_api_app:app --host 127.0.0.1 --port 8071
```

4. Build/start the frontend in another shell:

```bash
cd ../frontend-nextjs
npm ci
NEXT_PUBLIC_API_URL=http://127.0.0.1:8071 npm run build
PORT=3130 HOSTNAME=127.0.0.1 node .next/standalone/server.js
```

5. Open `http://127.0.0.1:3130/login` and sign in with the local admin
credentials. The dashboard, Assignments, Activity and Settings surfaces are
the normal core UI.

## Credentials

- Use your own `config/secrets.env` in mode `600` for any provider you connect.
- Never copy another machine's `secrets.env`, BYOK key or database.
- The local launch above works without provider credentials for controlled
  acceptance; live-connected retrieval requires your own OAuth grant.
- Keep `ATOM_EMAIL_SEND_DISABLED=1` and `ATOM_ASSIGNMENT_ALLOW_LIVE_SEND=0`
  unless a separate sending authorization is in force.

## Persistence and restart

Keep `ATOM_DATA_DIR`, `DATABASE_URL`, `LANCEDB_URI`, office and attachment
paths fixed across restarts. Stop the backend/frontend and start them again
with the same values. Teaching, assignment history, results and artifacts live
under that data root; they are not reconstructed from chat prose.

## Local acceptance results

- Normal browser form login/logout/relogin: **passed**; dashboard, Assignments
  and artifact surfaces opened.
- Integrated employee job: **completed** with:
  - connected Outlook-materialized HARSLE source retrieval;
  - taught document format (Summary/Findings/Sources, Arial 11);
  - calculation `216700.00`;
  - durable wait for missing currency, resolved as “Currency unstated by
    source.”;
  - formatted DOCX artifact;
  - payload-bound approval and controlled local outbox.
- Assignment detail in the UI shows all four steps applied and the result.
- Restart against the same local data root preserved status, teaching revision,
  history, artifact hash and outbox count.
- Sanitized fresh install (separate empty data root, no copied secrets or
  private paths, controlled adapters): **startup and browser login passed**;
  onboarding modal is expected on a fresh workspace.

Evidence:
`docs/acceptance/evidence/durable_assignment_20261030/local-acceptance-fda4f2dc9/`

## Troubleshooting

- **Login says “Unable to connect”** — set `ALLOWED_ORIGINS` to the frontend
  origin and restart the backend.
- **Backend not ready** — wait for `/api/health`; first startup initializes the
  database and tables.
- **Data disappears** — confirm all data paths point at the same durable root;
  relative paths are anchored to `backend/`.
- **Port conflict** — stop the conflicting local process or choose another
  port and rebuild the frontend with the matching `NEXT_PUBLIC_API_URL`.
- **Onboarding modal** — expected on a fresh workspace; it does not indicate a
  failure.
- **Controlled acceptance** — set `ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT=1` and
  `ATOM_ASSIGNMENT_OUTBOX`; this is a local test adapter, not a production
  sender.

## Deferred separately

Hosted deployment, public release, publication, production approval files and
source-service shutdown are not part of local readiness. The prepared
deployment package remains preserved and unexecuted.
