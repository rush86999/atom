# Local Ports & OAuth Redirect Contract

**Status: convention, enforced 2026-09-05** after a real incident: the
frontend auto-incremented from 3000 to 3001 when another project held 3000,
and a Zoho OAuth flow landed on the *wrong project's* frontend (its 404 page)
while the token exchange still succeeded server-side.

## Canonical port map (atom, open-source/local)

| Port | Service      | Binding rule |
|------|--------------|--------------|
| 3000 | ATOM frontend (next dev) | **Fixed.** Start via `scripts/start_frontend.sh` — never bare `npm run dev` (auto-increments when busy) |
| 8001 | ATOM backend (uvicorn)   | Fixed via `scripts/restart_backend.sh` |
| 11434| Ollama                   | Default; models live on the portable drive (see `scripts/drive_status.sh`) |

Sibling projects on this machine (e.g. **atom-saas** — the multitenant
cloud version that deploys to Fly) must NOT take atom's ports: use 3100+
for frontends and 8002+ for backends locally. atom-saas is an independent
deployment; its local dev port is its own choice, but 3000/8001 belong to
atom.

## The OAuth redirect contract

Browser-facing OAuth redirect URIs are registered in provider consoles
against **fixed ports**. That registration is a contract:

```
Provider console  --(redirect)-->  backend callback  --(token exchange)-->  FRONTEND_URL/oauth/success
   e.g. Zoho -> http://localhost:8001/api/v1/auth/oauth/zoho/callback
   e.g. Google -> http://localhost:3000/api/integrations/google/callback
```

- **Backend-callback registrations** (Zoho, Microsoft) are port-agnostic to
  the frontend — the backend owns `:8001`, and the post-exchange landing is
  `FRONTEND_URL` from `backend/.env`.
- **Frontend-callback registrations** (Google) embed the frontend port —
  moving the frontend off 3000 breaks them until the provider console is
  updated too.

Therefore: `FRONTEND_URL` in `backend/.env` must always equal the port the
frontend actually binds, and the frontend must always bind 3000.

## Fresh-installation checklist (correct/practical order)

1. **Backend first.** `scripts/restart_backend.sh` — it snapshots the DB,
   starts on 8001, and health-checks.
2. **Set `FRONTEND_URL`** in `backend/.env` to the frontend origin
   (`http://localhost:3000`).
3. **Register provider redirect URIs** (per provider console):
   - backend-callback apps: `http://localhost:8001/api/v1/auth/oauth/<provider>/callback`
   - frontend-callback apps: `http://localhost:3000/api/integrations/<provider>/callback`
4. **Frontend via the launcher:** `scripts/start_frontend.sh` — it fails
   loudly if 3000 is taken (naming the conflicting process) instead of
   drifting, and identity-verifies what answers.
5. **Verify the loop:** open the app, run one OAuth connect; the browser
   must land on `http://localhost:3000/oauth/success?provider=<p>`. If you
   see a 404 from an unfamiliar app, a port collision is serving someone
   else's frontend — run `lsof -ti :3000` and check its cwd.

## Incident recovery (what we actually did)

1. `lsof -ti :3000` + `lsof -p <pid>` revealed atom-saas's next-server on
   3000 (ATOM had silently drifted to 3001).
2. Stopped both frontends; restarted ATOM's via the launcher on 3000;
   atom-saas restarts later on its own port.
3. `FRONTEND_URL` restored to `http://localhost:3000`, backend restarted.
4. Token exchange was never broken — only the landing page. Check
   `integration_tokens.updated_at` in `backend/data/atom.db` to confirm a
   reconnection landed even when the browser landed somewhere odd.
