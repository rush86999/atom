# Python 3.13 NumPy resolver boundary

Frozen source: `965ec96db49b5b463c2679e5002cb26b9dad975e`. The original real Python 3.13 quickstart job failed: pip could not resolve the NumPy<2 requirement with storage/embedding dependencies. Original head, job identity, requirement hash and raw log are retained. No supported version was dropped and no failure was made optional.

The repair keeps the NumPy1 line on Python3.11/3.12 and selects NumPy>=2.1,<3 on3.13+, while retaining Arrow<26 and existing LanceDB pin. NumPy1.26 supports through Python3.12; NumPy2.1 adds Python3.13. NumPy2 breaks binary ABI compatibility, so each clean-runner matrix entry now imports the installed stack and writes/reads a synthetic temporary LanceDB vector record before backend boot. No application database or embedding model is used.

46 contract/marker/guard/preservation controls pass on each Python3.11/3.14 at this clean source, with actual commands/exits retained. The smoke script also passes in the existing diagnostic3.14 environment, whose LanceDB0.38 differs from the declared pin0.24.3. That is an implementation smoke, not a new supported-interpreter or pinned-install pass. Actual Python3.13 installation remains pending hosted execution. Application Python3.14 support, platform breadth, live models/providers and whole-app completion are not claimed.

The historical38111baf8 packet remains unchanged at its original source. This is its runtime/dependency successor, not a relabelled historical pass.

Sources: [NumPy1.26](https://numpy.org/doc/1.26/release/1.26.0-notes.html), [NumPy2.1](https://numpy.org/doc/2.1/release/2.1.0-notes.html), [NumPy2 migration/ABI](https://numpy.org/doc/stable/numpy_2_0_migration_guide.html).
