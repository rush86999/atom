# Source-archive redactions

The distribution archive is built from the release tag but excludes tracked
files that contain non-placeholder secret material:

- `config/.env.production.template`
- `config/.env.development.template`
- `backend/scripts/start_simple_backend.py`
- `docs/acceptance/evidence/whole_app_20261027/review_boundary_20261027/probe_20261027/baseline.json`

Those paths remain in the repository history but are not part of the release
archive. The package's own `config.env.template` contains no secrets. The
owner should rotate any credentials/signing keys that were present in the
excluded tracked files before distributing repository history.
