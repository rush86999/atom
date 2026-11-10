# GOAL-11 Office ordinary browser episode — preflight blocked

PR826 head was re-resolved from origin before source binding:
`96dd3afaf6a519848c04265db7249454020d7e85` (`refs/pull/826/head`), matching
the work order exactly. New isolated branch/worktree:
`codex/web-goal11-office-ordinary-browser-20261110` at
`/private/tmp/atom-goal11-office-browser-20261110`. No product source edits
were staged.

## Blocker (before any world/build/browser action)

`world_storage_guard check` fails hard:

```
worlds root does not exist and is not a symlink:
  /private/tmp/atom-goal11-office-browser-20261110/backend/data/acceptance_worlds
Refusing to run: the first mkdir would create a new tree
that is not the verified one.
```

`backend/data` exists, but the verified worlds root does not. The guard is
enabled with `layout: local`; no maintenance lock or runner is active. Per the
work order and AGENTS: **no mkdir, no symlink workaround, no
`ATOM_WORLD_STORAGE_BYPASS=1`, no live DB**.

## Other preflight facts

- disk free: 37 GiB (threshold 12 GiB)
- ports 3000/8000: free
- world launchers: none registered
- shared node_modules: `/private/tmp/atom-web-production-cookies-20261109/frontend-nextjs/node_modules`
- existing helpers are present after adding `scripts/acceptance/` to the
  worktree sparse checkout: `browser_document_export_ui.py`,
  `run_isolated.py`, `case5_browser_recovery.py`, `browser_verify.py`
- `ATOM_WORLD_STORAGE_BYPASS` is unset

## Not done

No acceptance world was created; no backend/frontend build, no browser launch,
no login/onboarding, no Canvas seed, no download capture, no product edit, no
provider/model/send/live DB. This is a storage preflight refusal, not a product
failure and not a routine permission checkpoint.

## Required next step

Root must provision or identify the verified `acceptance_worlds` root (or
explicitly authorize a specific existing verified root) and re-dispatch the
same bounded browser episode. No product code change is required.

Evidence:
- `preflight/world_storage_guard.proof` — exact guard output + exit
- `preflight/state.proof` — source/disk/memory/ports/cache/root state
- `manifest.json` — source/config hashes and actions not taken
