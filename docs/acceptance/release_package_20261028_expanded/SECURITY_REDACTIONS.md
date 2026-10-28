# Source-archive redactions

The distribution archive is built from the release tag but excludes tracked
files that contain non-placeholder secret material:

- `config/.env.production.template`
- `config/.env.development.template`
- `backend/scripts/start_simple_backend.py`
- `docs/acceptance/evidence/whole_app_20261027/review_boundary_20261027/probe_20261027/baseline.json`
- `archive/2026-07-consolidation/scripts/start-backend.sh` (contained a
  non-placeholder `ATOM_OAUTH_ENCRYPTION_KEY`)
- `frontend-nextjs/.preview-instance/` (build-machine absolute symlinks, not
  portable; excluded from the distribution archive)

Those paths remain in the repository history but are not part of the release
archive. The package's own `config.env.template` contains no secrets. The OAuth key in
the excluded archive script is not in this archive; the owner should still
rotate any key material that existed in tracked history. The
owner should rotate any credentials/signing keys that were present in the
excluded tracked files before distributing repository history.
