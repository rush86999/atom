# Rollback

1. Stop the pilot backend and frontend.
2. Restore the pre-pilot `atom.db` (and sidecars) from the verified backup.
3. Restore the previous release tag/package and its config template.
4. Start the previous package on the same scoped ports.
5. Run the post-start smoke for the restored package.
6. Record the rollback reason, timestamps and restored DB/package identity.

No deployment or live-data rollback is authorized by this package.
