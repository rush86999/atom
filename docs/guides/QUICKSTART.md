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
