# Run Atom locally and finish your first job

Start with the deterministic sample: no provider key, connected account or
live send is required. For tested scope and known limits, see the
[acceptance record](../acceptance/VERIFIER_ACCEPTANCE_2026-11-01.md).

## 1. Check prerequisites

| Tool | Supported setup |
|---|---|
| Python | 3.11–3.13; 3.11 recommended. Python 3.14 is not supported by this dependency set. |
| Node.js | 20.9 or newer |
| npm, Git, Make | Available on your command line |

The measured fresh-worktree journey used macOS, Python 3.11, Node 20.19 and
warm package caches. It took approximately **5 min 15 s**. A 15-minute cold
installation is a target; download/build time on other machines is unmeasured.

## 2. Clone and set up

~~~bash
git clone https://github.com/rush86999/atom.git
cd atom
# Optional: pin the recommended tested snapshot instead of development main.
git checkout successor-first-use-2026-11-01
PYTHON=python3.11 make setup
~~~

Use `PYTHON=python3.12` or `PYTHON=python3.13` if that is your installed supported
interpreter. Setup creates `backend/venv`, installs backend/frontend dependencies
and generates local environment files when missing. Keep the generated secret
and encryption keys across restarts. Do not copy someone else's environment,
keys or database.

## 3. Start the app

From the repository root:

~~~bash
make dev
~~~

This starts the full FastAPI backend on port **8001** and Next.js frontend on
**3001**. Keep this terminal open. Wait for both servers to finish starting.
The API readiness endpoint is http://localhost:8001/health/ready.

Open **http://localhost:3001/login**. The local bootstrap account is
`admin@example.com`; its generated password is written to
`backend/logs/bootstrap_admin_password.txt` with owner-only permissions. Read
that file locally. Do not paste it into a public issue.

If `ADMIN_PASSWORD` was supplied before first startup, use that value instead.
The sample loader accepts an explicit password file through its CLI; run
`backend/venv/bin/python scripts/load_sample_workspace.py --help` for options.

## 4. Load the sample

In a second terminal, from the same repository root:

~~~bash
make sample
~~~

The loader signs into your running local app, creates/reuses **Sample Quote
Analyst**, records editable lessons, uploads the sample CSV and starts one
read/calculation/document assignment through product routes.

Expected result:

- The command prints `status: passed` and **232990.00**.
- **Assignments** shows *Sum Price for the sample quote sheet* completed.
- Download the generated DOCX from the assignment.
- Find the employee and editable lessons under **Agents → Sample Quote Analyst → Training**.

This sample creates local data and artifacts. It performs no email send or
connected-system write. It demonstrates deterministic calculation, not model
judgment. For your next workflow, use the [verified demo guide](../demo/VERIFIED_WORKFLOWS.md).

## Busy ports

Use matching ports for startup and the sample:

~~~bash
BACKEND_PORT=8101 FRONTEND_PORT=3101 make dev
# Second terminal:
make sample PORT=8101 FE_PORT=3101
~~~

Open http://localhost:3101. The development launcher sets the browser API URL,
allowed origins and hosts to match these ports. Do not stop an unrelated app
just to free the default ports.

## Restart and keep your work

Press **Ctrl+C** in the launch terminal, then run the same `make dev` command
again from the same checkout. Preserve the database, artifacts, memory and
generated keys. Completed assignments and durable questions should reopen;
the acceptance evidence records the tested restart/recovery paths.

The isolated acceptance launcher uses world-owned SQLite, artifact and memory
paths. Its storage configuration is separate from this ordinary development
setup; do not use test-world reset commands against your working data.

## Add models and connections after the sample

Open **Settings** to configure your own provider. General chat and model-backed
features need an available model; the sample does not. Local inference setup
is described in [Run with Ollama](run-with-ollama.md). A provider being available
does not establish its judgment quality.

Connectors need their own grants and source access. The accepted Microsoft
read-only and one-use Outlook send qualifications are bounded historical
records, not permission for new sends or proof that every connector works.

## If something fails

- **Python rejected:** check `python3.11 --version`, then use the explicit
  `PYTHON=python3.11 make setup` command.
- **Cannot sign in:** wait for readiness; confirm you are using the frontend
  port and generated password from this checkout.
- **Empty first visit:** use a checkout containing the successor's first-login
  fix. Confirm the sample ran against the same backend/port.
- **No provider:** the sample should not need one; other model-backed features
  require a configured, reachable provider.
- **Existing data trouble:** preserve the data and keys. Do not delete or
  reseed the database as a troubleshooting step.

See [troubleshooting](TROUBLESHOOTING.md), the
[measured first-use record](../demo/FIRST_USE_TEST_2026-11-01.md), or
[open a sanitized issue](https://github.com/rush86999/atom/issues).
