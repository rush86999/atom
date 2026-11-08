# Installed PostgreSQL schema baseline

Root discovered installed Homebrew PostgreSQL14.24 (x86_64 under this arm64 macOS environment) and exercised a fresh unprivileged scratch cluster using a private Unix socket only. No TCP listener, existing service/database, container, installation, download or provider was used. Each cluster root is0700. A fresh synthetic DB username with trust auth is limited to the private socket/directory; no operator credential is read.

Actual checkout27a1830a2 has the tested models.py byte-equal to main8ded (hash in result). TESTING=1 and an explicit separate scratch SQLite URL protect incidental app imports; the PostgreSQL engine is constructed separately with the exact new private socket and its data-directory identity independently queried. This is an ORM create_all check, NOT an Alembic migration, full app boot, multi-worker or concurrency qualification.

Initial cluster: initdb succeeds, schema transaction fails with PostgreSQL out-of-shared-memory and explicit HINT to increase max_locks_per_transaction. Original result/server log retained. This is a declared small-cluster resource setting, not mislabelled a production defect. Fresh adjusted cluster uses max_locks_per_transaction=512, shared_buffers16MB, max_connections10; all376 registered ORM tables are created and counted independently in information_schema. Both owned PostgreSQL processes stop normally with exit0.

initdb uses --no-sync for this bounded schema check. Crash durability/soak is explicitly NOT qualified. Both private cluster directories are retained outside Git. No current application data was inserted. COMPAT-03 remains unverified broadly; this evidence removes the false assumption that PostgreSQL runtime cannot be explored on the current host and provides the next prerequisite for exact CAS/transaction tests.

Runners are exact executed bytes, including absolute controlled-checkout path. There was no application code change and no historical rescore. Independent source-bound runtime/SQL behavior and actual migrations remain required.
