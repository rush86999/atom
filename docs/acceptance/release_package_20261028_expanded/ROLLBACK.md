# Rollback

1. Stop the pilot backend and frontend.
2. Restore the pre-pilot `atom.db` (and sidecars), the office artifact store
   (`ATOM_OFFICE_DIR`) and the email attachment store
   (`ATOM_EMAIL_ATTACHMENT_DIR`) from the verified backup. Restoring the DB
   alone is not sufficient: canvas rows reference these files.
3. Restore the previous release tag/package and its config template.
4. Start the previous package on the same scoped ports.
5. Run the post-start smoke for the restored package.
6. Record the rollback reason, timestamps and restored DB/package identity.

No deployment or live-data rollback is authorized by this package.
