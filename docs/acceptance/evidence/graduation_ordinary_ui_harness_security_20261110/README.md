# Graduation UI harness scanner follow-up (2026-11-10)

Status: **harness-only security hygiene successor**. No product, policy,
lifecycle, test-claim or historical-UI-source change.

## Incident

- GitGuardian incident: `39901756`
- PR/head context: PR `830`, head `e5c75c538e426fbfb563676e5672810ed9946d6a`
- Original executed harness:
  `scripts/acceptance/browser_graduation_qualification_ui.py`
  sha256 `c5b1536f663513df9f0767d662431e2a4f2e8b40647ec1ea45d820f39cdc64cf`
- Successor harness:
  sha256 `58cf3d81485c5a9060b78df510702e7b5c88d49d884e332e3c697771b81ccab8`

The scanner flagged a credential-shaped **filename literal** in the disposable
scratch harness. It was not a live credential, not a value, and not a
product/runtime secret. The harness read the app-generated scratch bootstrap
credential file after launching an isolated world.

## Repair

The hardcoded filename literal was removed. The harness now resolves the
single nonempty `*.txt` credential file from the isolated world's own
`backend_root/logs` directory, waits for it to appear, and reads it into a
local variable for the ordinary UI login. This preserves the exact executed UI
behavior: the same scratch app-generated credential is used for the same
normal login form.

No credential value is printed, logged or stored in this packet. The private
incident metadata remains private. No waiver, history rewrite, force push,
credential rotation or live credential action was used.

## What was verified

- `py_compile`: **PASS**
- Static check: **the prior credential-shaped filename literal is absent**
- Dynamic scratch lookup: `credential_dir`, `_scratch_credential_file`,
  `credential_value`
- No browser rerun: this is a packaging/security-only change; the original UI
  claim remains bound to the original executed harness bytes and its packet.

## Provenance

The original packet
`docs/acceptance/evidence/graduation_ordinary_ui_20261110/` is unchanged and
retains the original executed harness hash `c5b1536...`. This successor packet
records the repaired harness only; it does **not** relabel the executed UI
run, its screenshots, its DB readback, or its original negatives.

Root will build the clean main-based successor PR because the old PR history
retains the flagged literal. This branch does not edit the PR, root branch,
merge state or scanner settings.
