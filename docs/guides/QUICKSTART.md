# Atom quick start

The canonical guide is [Run Atom locally and finish your first job](../getting_started/quick-start.md).
It covers prerequisites, the recommended successor snapshot, setup, login,
the deterministic sample, matching port overrides and restart/data preservation.

```bash
git clone https://github.com/rush86999/atom.git
cd atom
git checkout successor-first-use-2026-11-01
PYTHON=python3.11 make setup
make dev
# Second terminal, from the same repository:
make sample
```

Expected result: **232990.00**, a completed assignment and downloadable DOCX.
No cloud key, connected account or live send is needed for this sample.

Open http://localhost:3001 and sign in as `admin@example.com` using the generated
password in `backend/logs/bootstrap_admin_password.txt`.

Measured first use was about **5 min 15 s with warm package caches** on one host.
The 15-minute cold-install target is not a guarantee. See the
[measured record](../demo/FIRST_USE_TEST_2026-11-01.md),
[verified demo](../demo/VERIFIED_WORKFLOWS.md) and
[tested limits](../acceptance/VERIFIER_ACCEPTANCE_2026-11-01.md).

## On-host transcription (operator only)

Atom can use an OpenAI-compatible transcription service that runs on the same
host as the backend. This is an **operator deployment step**, not a browser
setting and not an automatic model download. The operator starts the service,
places it in the backend's network namespace, and provisions the provider and
model in the database with the CLI below.

The ordinary **Add provider** form keeps its registration guard. The HTTP
registration endpoint rejects loopback, private and link-local addresses. This
CLI is the supported operator-only path for the on-host profile and preserves
that guard.

### Service profile

- OpenAI-compatible base URL: `http://127.0.0.1:<port>/v1`
- Transcription endpoint: `POST /v1/audio/transcriptions`
- Exactly one model id served by that endpoint, for example `whisper-1`
- The host must be a numeric loopback address (`127.0.0.1` or `::1`). The port
  must be explicit; the scheme must be `http`; userinfo, query strings,
  fragments, extra path segments and DNS aliases are rejected.
- Run the service in the backend's network namespace (for example a sidecar
  with `network_mode: "service:backend"`), so `127.0.0.1` means the backend
  container. A transcription endpoint on another host is outside this profile.

Example service profile (image and flags are operator-specific; Atom only
requires the endpoint contract):

```yaml
services:
  transcription:
    image: <openai-compatible-transcription-server>
    network_mode: "service:backend"
    command: ["--host", "127.0.0.1", "--port", "9000", "--model", "whisper-1"]
```

The [LocalAI Audio to Text documentation](https://localai.io/docs/models/capabilities/audio/audio-to-text/)
shows one example of this endpoint contract.

### Provision it

Set `DATABASE_URL` in the operator environment and apply the application's
database migrations before running the command:

```bash
cd backend
export DATABASE_URL="<application-database-url>"
# Apply the application's database migrations with this DATABASE_URL.
python -m scripts.register_local_transcription \
  --workspace-id "<existing-workspace-id>" \
  --name "On-host Whisper" \
  --base-url http://127.0.0.1:9000/v1 \
  --model whisper-1 \
  --audio-input-cost-per-second-usd 0
```

The workspace must already exist and have a tenant. `--name` is the stable
display name. `--audio-input-cost-per-second-usd` is required and must be a
finite, non-negative number; `0` is an explicit free rate. The command creates
one custom local provider and one capability row with `supports_chat=false`,
`supports_transcription=true` and the exact rate. It performs no outbound
requests, stores no API key and does not discover models.

Re-running an identical command is a no-op. For the same workspace and name,
changing the URL, model or rate is refused without updating or deleting
existing rows. A different workspace is provisioned independently, with its own
provider and capability row.

### Expected browser state

Open **Settings → Local Models** as a member of that workspace. The Local Models
settings view requires the `ATOM_PRODUCT_PROFILE=full` UI profile. The provider
appears once with the configured display name, type **Custom**, and the
`http://127.0.0.1:9000/v1` base URL. Its model list shows exactly the one model,
with **Transcription** enabled, **Chat** disabled, and the configured
USD-per-second rate. The recording/transcription model picker can then select
that model, and the backend sends audio to
`POST /v1/audio/transcriptions` through the provider.

For the broader operator-managed local-inference configuration pattern, see the
[Open WebUI environment configuration reference](https://docs.openwebui.com/reference/env-configuration/).
The strict loopback/no-DNS/no-userinfo rules follow the
[OWASP SSRF prevention guidance](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html).
