# Browser info-wait driver — identity hardening and merge evidence (2026-11-07)

Status: **PREPARATION ONLY.** No world, application server, browser, provider
shim process or live provider/model/account/credential was started. No
dependency was installed. Root owns the actual browser acceptance.

Source at this preflight: `8c7676fa34aab20104baf68ff369b14e5bd61165`.
Driver SHA-256: `83f2d8939691fe7730affc2ea5692090457445a700a721347a00876b7104b6bc`.

## Merge state

- `origin/main` (`cf351a5b0`) merged into the driver branch as `088365697`.
- Personal-answer branch `0903f9b56` merged as `9d282de3f`; its parent tip
  contains `f5562618c` (None/default personal-workspace answer repair) and the
  preserved evidence bundle `docs/acceptance/evidence/personal_information_answer_f5562618c/`.
- The public-answer repair now uses the shared `resolve_workspace_id()` for both
  the admitted wait and the current actor. Real workspace IDs remain exact.

## Fail-open identities fixed

1. **Frontend cwd** — the previous check passed when `lsof` returned `None`
   (unobserved). `_frontend_cwd_matches()` now requires an observed cwd and
   exact resolved equality with the world's `frontend_snapshot`. Both phases
   (`frontend_cwd_isolated` and `frontend_restarted_isolated`) assert both
   `cwd_observed` and `cwd_exact`.

2. **Initial backend source** — the previous evidence recorded
   `manifest.get("source_revision")`, which the real MANIFEST does not contain.
   Absence could not certify anything. The driver now requires:
   - frozen source present and equal to the source HEAD;
   - harness `R.preflight(world).source_revision` equal to the frozen source;
   - exported tree equal to `code_manifest.json`;
   - a non-empty `backend/` export hash;
   - the running server's health `cwd` and launch descriptor `export_path` both
     exactly `world/backend_root`;
   - a present MANIFEST code snapshot/archive hash.
   A missing MANIFEST `source_revision` is recorded
   (`manifest_source_revision_present: false`) but is never used as a pass;
   a present but conflicting value fails.

## Focused tests

```bash
python3 -m pytest scripts/tests/test_browser_agent_job_wait_identity.py -q
# 12 passed

TESTING=1 DATABASE_URL=sqlite:///<scratch>/atom.db \
ATOM_DATA_DIR=<scratch>/data ATOM_OFFICE_DIR=<scratch>/office \
LANCEDB_URI=<scratch>/lancedb \
python3 -m pytest backend/tests/test_lead_personal_information_answer.py -q
# 2 passed
```

Logs are preserved as `identity-tests.log` and `personal-answer-tests.log`.
The identity tests cover: unobserved/wrong/exact frontend cwd; valid source
binding with absent MANIFEST `source_revision`; matching present revision;
missing frozen source; missing export hash; export-tree drift; unobserved
health cwd; wrong descriptor export; conflicting MANIFEST revision; and
preflight-source mismatch.

## Preflight

```bash
python3 -m py_compile scripts/acceptance/browser_agent_job_wait.py
python3 scripts/acceptance/browser_agent_job_wait.py --help
python3 -m pyflakes scripts/acceptance/browser_agent_job_wait.py

TESTING=1 \
DATABASE_URL=sqlite:///<fresh>/atom.db \
ATOM_DATA_DIR=<fresh>/data \
ATOM_OFFICE_DIR=<fresh>/office \
python3 scripts/acceptance/browser_agent_job_wait.py --preflight \
  --out <fresh>/report
```

`preflight.json` reports `ok=true`: scratch environment, source HEAD, clean
backend tree, five authored `ReActStep` envelopes, the existing
`provider_shim.load_script` index, and labelled default transport. The only
warnings are the execute-only gaps in this preparation worktree:
`backend/venv314/bin/python` and `frontend-nextjs/node_modules` are absent and
were not installed.

## Root-owned execution

Run `--execute` from the prepared/frozen capture worktree, with a unique fresh
world, free ports, and an admin password source:

```bash
python scripts/acceptance/browser_agent_job_wait.py --execute \
  --world browser_wait_<unique> \
  --backend-port 8031 --frontend-port 3131 --shim-port 8097 \
  --out <scratch-evidence>/browser_wait_<sha10> \
  --expect-source-sha <frozen-sha> \
  --provision-admin-password
```

The driver still calls `world_storage_guard` before `build_world`, refuses an
existing world/live DB, measures disk through `storage_policy`, and never uses
the drive bypass. The authored ReAct steps remain simulated model decisions /
controlled transport; only the provider response is substituted.
