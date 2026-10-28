# Backup before pilot

- Stop new chat traffic.
- Copy the isolated pilot `atom.db` and its `-wal`/`-shm` sidecars to a
  timestamped backup directory.
- Copy the authoritative office artifact store (`ATOM_OFFICE_DIR`, default
  `backend/data/office/`) and the email attachment store
  (`ATOM_EMAIL_ATTACHMENT_DIR`, default `backend/data/email_attachments/`)
  with the database. Canvas rows point at these files by path; a DB-only
  restore leaves workbook/document/deck/attachment downloads missing.
- Copy the BYOK key store and encryption key read-only; never place them in
  the release package or logs.
- Record the app commit/tag, frontend build ID and config values with the
  backup.
- Verify the backup opens read-only and has the expected row counts.
- Do not clean or re-seed the database as part of backup.
