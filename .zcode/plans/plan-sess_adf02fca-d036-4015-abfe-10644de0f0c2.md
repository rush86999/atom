## Guide new users from login → first AI agent job

Today the journey is: land on `/dashboard` (finance zeros + 13 red integrations, no orientation) → self-discover Chat/Agents → hit dead ends ("No agents found.", no create-agent UI, no-key errors only handled in chat). Meanwhile a complete 4-step OnboardingWizard (Welcome → Profile → BYOK key/Ollama → Ready) already exists but is **double-broken**: middleware redirects `/` → `/dashboard` so its host page never renders, and the backend `User.onboarding_completed/onboarding_step` columns are commented out in the ORM (any status call 500s).

### Backend

1. **Re-enable onboarding columns** — `backend/core/models.py`: uncomment `onboarding_completed` + `onboarding_step` (leave the other commented columns alone).

2. **Idempotent column ensure** — `backend/api/onboarding_routes.py`: add `_ensure_onboarding_columns()` that runs `ALTER TABLE users ADD COLUMN ...` inside try/except (duplicate-column error = already present; works on SQLite and Postgres), called once at module import. Existing dev DBs won't have the columns even though the alembic migration defines them, and `create_all` never alters existing tables — without this every status call 500s on old DBs.

3. **New `GET /api/onboarding/progress`** in the same router — one cheap aggregate the UI polls:
   - `onboarding_completed`, `onboarding_step` (existing fields)
   - `provider_configured`: any BYOK provider key row or env-configured provider or `ATOM_LOCAL_ONLY`
   - `has_agent`: `AgentRegistry` row in the user's workspace/tenant (or `user_id`)
   - `first_job_done`: any `AgentExecution` for those scopes

### Frontend

4. **Mount the OnboardingWizard in `components/layout/Layout.tsx`** (global, like the existing `GraduationCelebration`) instead of unreachable `/`: fetch `/api/onboarding/status`; show the wizard when not completed. Silent no-op on 401/fetch failure (public pages). If dismissed without completing, remember in `localStorage` for the session so it doesn't nag on every navigation; re-offers on next login. Remove the dead mount from `pages/index.tsx` is NOT needed — leave index alone.

5. **New `components/Onboarding/GettingStartedCard.tsx`** on `/dashboard` top — a persistent 3-step checklist driven by `/api/onboarding/progress`:
   - ① **Connect an AI provider** → `/settings/ai` (✓ when `provider_configured`; also offers the free-Ollama hint)
   - ② **Set up your first agent** → `/agents` (with "browse templates" → `/marketplace`) (✓ when `has_agent`)
   - ③ **Run your first AI job** → `/chat` (example prompts live there) (✓ when `first_job_done`)
   Dismissible via localStorage (same pattern as `EmployeeOnboardingGuide`), auto-hides when all three are ✓.

6. **Shared provider pre-check** — new `hooks/useProviderStatus.ts` + a small amber banner component (same styling/CTA as the chat one: "Add an API key or enable local Ollama" → `Configure now → /settings/ai`), mounted in `AgentWorkflowGenerator` (Automations → AI Agents tab) and the agents-page Run Dialog, so users learn *before* burning a failed run, not after.

7. **Agents empty-state CTAs** — `pages/agents/index.tsx`: alongside "Browse templates", add "Describe a workflow → /automations" and "Chat with an agent → /chat".

### Verification
- In-process TestClient: column-ensure works on a fresh sqlite DB and on the existing dev DB copy; `/status` and `/progress` return 200 with the right shape; wizard `POST /update` round-trips.
- `npx tsc --noEmit --skipLibCheck` clean.
- Full E2E in a browser against my own instances (user's servers untouched): backend on :8011 (fresh DB, `ALLOWED_ORIGINS` incl. :3011) + `next dev` on :3011 with `NEXT_PUBLIC_API_URL=http://localhost:8011`; register a fresh user → wizard appears → skip/add key path → dashboard checklist shows step states → run first chat job → checklist step ③ turns ✓.
- Run backend tests touching onboarding/models import (`tests/` grep for onboarding) to catch import-order regressions.

Out of scope: visual workflow builder demo agents, exposing backend demo workflows, docs-link surface in UI, mobile onboarding.