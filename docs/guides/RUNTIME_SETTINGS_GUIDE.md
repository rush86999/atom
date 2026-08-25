# Runtime Settings Guide — Environment Variables as UI Admin Settings

> **Last updated**: Aug 24, 2026. Admin → **Settings** (`/admin/settings`) manages every documented tunable without a restart.

## What this is

Every environment variable documented in CLAUDE.md (feature flags, thresholds, caps, cadences) is:

1. **Listed** in the admin settings UI with its live resolved value and where it came from,
2. **Editable** from the UI (writes a `runtime_settings` DB row), taking effect within the cache TTL (~60s) — no restart,
3. **Audited** — every change records who/when/old/new in `setting_change_audit`.

## Resolution precedence (important)

```
1. Explicit env var        ← ALWAYS WINS (kill switch)
2. runtime_settings row    ← what the UI edits
3. Catalog default         ← documented fallback
```

**An exported env var always beats a UI edit.** This is deliberate: an operator can always force behavior via the environment even after someone flips a toggle in the UI. The UI shows these rows with an amber **env override** badge and read-only value ("remove the export to edit here").

## How to use

| Task | Do this |
|---|---|
| Turn a feature on/off | Find it by category tab or search → flip the toggle → done |
| Tune a threshold | Edit the number → Save (Enter also saves) |
| Undo a UI edit | **Reset** button → falls back to env var or default |
| See what's in effect | **Source** column: `env override` / `UI setting` / `default` |
| Find who changed what | `GET /api/v1/admin/settings/audit` |

Changes propagate to all workers within ~60 seconds (`ATOM_SETTINGS_CACHE_TTL`). Restarts are never required but also never harmful.

## Secrets are locked

API keys (`OPENAI_API_KEY`, …), webhook shared secrets (`*_WEBHOOK_SECRET`), and credential paths show as **Managed by environment** — values never leave the server and cannot be written through the API. This is enforced server-side (403), not just hidden in the UI.

## Where edits apply today

Subsystems whose config resolvers read through `core/runtime_settings.py` observe UI edits immediately. As of this writing that includes: hallucination mitigation (self-consistency, MoA, cascade, tool cache…), execution sandbox, stage router (+ automation), fleet routing, agent radio, knowledge VFS, trust calibration knobs, org politics automation, LLM gateway, turn facts, doc freshness, memory consolidation, reviewer loop, contribution credit. Settings for not-yet-converted subsystems still resolve from env/default only — their rows are inert until the module adopts the resolver (one-line-per-flag change).

## API surface

```
GET    /api/v1/admin/settings              # catalog + resolved values + sources
GET    /api/v1/admin/settings/categories   # category list
GET    /api/v1/admin/settings/audit        # change history (?limit=50&setting_key=KEY)
PUT    /api/v1/admin/settings/{key}        # {"value": ...} — validated against type
DELETE /api/v1/admin/settings/{key}        # remove override
```

All endpoints require an admin role (`super_admin`/`owner`/`admin`/`workspace_admin`). Type mismatches return 400; secrets return 403; unknown keys 404.

## Adding a new setting

1. Add one line to `core/settings_catalog.py`: `B("MY_FLAG", True, "My Category", "What it does")` (or `I`/`F`/`S`/`J`).
2. In the subsystem's config module, replace `os.getenv(...)` with `get_bool_setting("MY_FLAG", True)` (or the typed getter).
3. Done — it appears in the UI automatically.
